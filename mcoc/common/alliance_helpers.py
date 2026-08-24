# mcoc/common/alliance_helpers.py
import json
import pathlib
import logging
import asyncio
from typing import Optional, Dict, Any, List, Tuple, Union

log = logging.getLogger("red.mcoc.alliance_helpers")
DATA_PATH = pathlib.Path("data") / "account" / "alliances.json"
DATA_PATH.parent.mkdir(parents=True, exist_ok=True)


def _load_alliances() -> Dict[str, Any]:
    try:
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_alliances(data: Dict[str, Any]) -> None:
    """
    Atomic save: write to a temp file then replace the target file.
    """
    try:
        tmp = DATA_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(DATA_PATH)
    except Exception:
        log.exception("Failed to save alliances.json")


def get_guild_config(guild_id: int) -> Dict[str, Any]:
    data = _load_alliances()
    return data.get(str(guild_id), {})


def set_guild_config(guild_id: int, cfg: Dict[str, Any]) -> None:
    data = _load_alliances()
    data[str(guild_id)] = cfg
    _save_alliances(data)


def remove_guild_config(guild_id: int) -> None:
    data = _load_alliances()
    data.pop(str(guild_id), None)
    _save_alliances(data)


# -----------------------------
# High-level operations (async)
# -----------------------------
async def create_or_link_role(guild, role_name: str, key: str, role_obj=None) -> Optional[Dict[str, Any]]:
    """
    Ensure a role exists and link it into the guild config under `roles[key]`.
    If role_obj provided, link that role; otherwise create a new role.
    Returns the role mapping dict {id, name} or None on failure.
    """
    try:
        cfg = get_guild_config(guild.id) or {}
        roles = cfg.setdefault("roles", {})
        if role_obj:
            role = role_obj
        else:
            # create role (may raise if bot lacks permissions)
            role = await guild.create_role(name=role_name, reason="mcoc alliance role creation")
        if not role:
            return None
        roles[key] = {"id": role.id, "name": role.name}
        set_guild_config(guild.id, cfg)
        return roles[key]
    except Exception:
        log.exception("create_or_link_role failed for guild %s key %s", getattr(guild, "id", None), key)
        return None


async def register_alliance(guild, alliance_name: str, alliance_tag: Optional[str] = None, type_: str = "simple") -> bool:
    """
    Register an alliance on this guild. Creates default roles (alliance, officers, members).
    """
    try:
        cfg = get_guild_config(guild.id) or {}
        cfg["type"] = type_
        cfg.setdefault("roles", {})
        # create/link core roles
        r1 = await create_or_link_role(guild, f"{alliance_name} Alliance", "alliance")
        r2 = await create_or_link_role(guild, f"{alliance_name} Officers", "officers")
        r3 = await create_or_link_role(guild, f"{alliance_name} Members", "members")
        # if any role creation/link failed, log but continue (admins can set roles manually)
        if not (r1 and r2 and r3):
            log.debug("One or more alliance roles failed to create/link for guild %s", guild.id)
        cfg.setdefault("info", {})["name"] = alliance_name
        if alliance_tag:
            cfg["info"]["tag"] = alliance_tag
        cfg.setdefault("settings", {})["max_members"] = 30
        cfg.setdefault("member_ids", [])
        cfg.setdefault("officer_ids", [])
        set_guild_config(guild.id, cfg)
        return True
    except Exception:
        log.exception("register_alliance failed for guild %s", getattr(guild, "id", None))
        return False


async def unregister_alliance(guild, remove_roles: bool = False) -> bool:
    """
    Unregister alliance for guild. Optionally remove roles (careful with rate limits).
    This will remove the guild's config entry. If remove_roles is True, it will
    attempt to delete configured roles with a short pause between deletions.
    """
    try:
        cfg = get_guild_config(guild.id)
        if not cfg:
            return False
        roles = cfg.get("roles", {})
        if remove_roles:
            for k, r in list(roles.items()):
                try:
                    role = guild.get_role(r.get("id"))
                    if role:
                        await role.delete(reason="mcoc alliance unregister")
                        # small pause to avoid hitting rate limits when deleting multiple roles
                        await asyncio.sleep(0.35)
                except Exception:
                    log.exception("Failed to delete role %s in guild %s", k, guild.id)
        remove_guild_config(guild.id)
        return True
    except Exception:
        log.exception("unregister_alliance failed for guild %s", getattr(guild, "id", None))
        return False


async def join_alliance(member, guild, role_key: str = "members") -> Tuple[bool, str]:
    """
    Add member to alliance members role (role_key). Enforce single-alliance rule within this guild.
    Returns (success, message).
    """
    try:
        cfg = get_guild_config(guild.id)
        if not cfg:
            return False, "Alliance not configured on this guild."
        roles = cfg.get("roles", {})
        target = roles.get(role_key) or roles.get("members")
        if not target:
            return False, "Members role not configured."

        # enforce max members
        max_m = cfg.get("settings", {}).get("max_members", 30)
        mids = cfg.setdefault("member_ids", [])
        if member.id not in mids and len(mids) >= max_m:
            return False, f"Alliance is full (max {max_m} members)."

        # remove member from other alliance-related roles in this guild
        for k, r in roles.items():
            rid = r.get("id") if isinstance(r, dict) else None
            if rid and any(role.id == rid for role in member.roles):
                if k == role_key:
                    continue
                try:
                    role_obj = guild.get_role(rid)
                    if role_obj:
                        await member.remove_roles(role_obj, reason="Switching alliance membership")
                except Exception:
                    log.exception("Failed to remove old alliance role %s from member %s", rid, member.id)

        # add target role
        role_obj = guild.get_role(target["id"])
        if not role_obj:
            return False, "Configured role not found on server."
        await member.add_roles(role_obj, reason="Joining alliance via mcoc")

        # update member_ids
        if member.id not in mids:
            mids.append(member.id)
            cfg["member_ids"] = mids
            set_guild_config(guild.id, cfg)

        return True, "Joined alliance."
    except Exception:
        log.exception("join_alliance failed for member %s", getattr(member, "id", None))
        return False, "Internal error"


async def leave_alliance(member, guild) -> Tuple[bool, str]:
    """
    Remove member from alliance roles and update config.
    """
    try:
        cfg = get_guild_config(guild.id)
        if not cfg:
            return False, "Alliance not configured."
        roles = cfg.get("roles", {})
        # remove all alliance-related roles
        for k, r in roles.items():
            rid = r.get("id") if isinstance(r, dict) else None
            if rid:
                role_obj = guild.get_role(rid)
                if role_obj and role_obj in member.roles:
                    try:
                        await member.remove_roles(role_obj, reason="Leaving alliance via mcoc")
                    except Exception:
                        log.exception("Failed to remove role %s from member %s", rid, member.id)
        # update member_ids
        mids = cfg.get("member_ids", [])
        if member.id in mids:
            mids.remove(member.id)
            cfg["member_ids"] = mids
            set_guild_config(guild.id, cfg)
        return True, "Left alliance."
    except Exception:
        log.exception("leave_alliance failed for member %s", getattr(member, "id", None))
        return False, "Internal error"


# -----------------------------
# Utility helpers
# -----------------------------
def role_id_for_key(cfg: Dict[str, Any], key: str) -> Optional[int]:
    r = cfg.get("roles", {}).get(key)
    return r.get("id") if isinstance(r, dict) else None


def get_user_alliance_in_guild(user_id: int, guild_id: int) -> Optional[str]:
    """
    Return the alliance name for the user in this guild, or None.
    """
    cfg = get_guild_config(guild_id)
    mids = cfg.get("member_ids", [])
    if user_id in mids:
        return cfg.get("info", {}).get("name")
    return None


def get_alliance_role_for_user(user_id: int, guild_id: int) -> Optional[int]:
    cfg = get_guild_config(guild_id)
    mids = cfg.get("member_ids", [])
    if user_id not in mids:
        return None
    roles = cfg.get("roles", {})
    member_role = roles.get("members")
    if isinstance(member_role, dict):
        return member_role.get("id")
    for k, r in roles.items():
        rid = r.get("id") if isinstance(r, dict) else None
        if rid:
            return rid
    return None


# -----------------------------
# Role / permission helpers
# -----------------------------
def _role_obj_for_key(cfg: Dict[str, Any], guild, key: str):
    """
    Return a discord.Role for a configured role key (roles[key]) or None.
    Safe to call when cfg or role entry is missing.
    """
    try:
        r = cfg.get("roles", {}).get(key)
        if not isinstance(r, dict):
            return None
        return guild.get_role(r.get("id"))
    except Exception:
        log.exception("_role_obj_for_key failed for guild %s key %s", getattr(guild, "id", None), key)
        return None


def is_leader_or_officer(member, guild) -> bool:
    """
    Return True if member is alliance leader or officer in this guild.
    Leader is the 'alliance' role; officers are 'officers' role.
    """
    try:
        cfg = get_guild_config(guild.id)
        if not cfg:
            return False
        alliance_role = _role_obj_for_key(cfg, guild, "alliance")
        officers_role = _role_obj_for_key(cfg, guild, "officers")
        if alliance_role and alliance_role in member.roles:
            return True
        if officers_role and officers_role in member.roles:
            return True
        # fallback to officer_ids in config
        officers_ids = cfg.get("officer_ids", [])
        if member.id in officers_ids:
            return True
        return False
    except Exception:
        log.exception("is_leader_or_officer check failed for member %s", getattr(member, "id", None))
        return False


def is_leader(member, guild) -> bool:
    """Return True if member has the alliance leader role."""
    try:
        cfg = get_guild_config(guild.id)
        if not cfg:
            return False
        alliance_role = _role_obj_for_key(cfg, guild, "alliance")
        return alliance_role in member.roles if alliance_role else False
    except Exception:
        log.exception("is_leader check failed for member %s", getattr(member, "id", None))
        return False


# -----------------------------
# Info getters/setters
# -----------------------------
def get_alliance_info(guild_id: int) -> Dict[str, Any]:
    """Return the info dict for the guild (may be empty)."""
    cfg = get_guild_config(guild_id)
    return cfg.get("info", {}) if cfg else {}


def set_alliance_info_field(guild_id: int, field: str, value: Union[str, None]) -> bool:
    """
    Set a single info field (name, tag, invite, about, started, poster, wartool).
    Use None to clear.
    """
    try:
        cfg = get_guild_config(guild_id) or {}
        info = cfg.setdefault("info", {})
        if value is None:
            info.pop(field, None)
        else:
            info[field] = value
        set_guild_config(guild_id, cfg)
        return True
    except Exception:
        log.exception("Failed to set alliance info field %s for guild %s", field, guild_id)
        return False

def set_alliance_type(guild_id: int, type_: str) -> bool:
    try:
        cfg = get_guild_config(guild_id) or {}
        cfg["type"] = type_
        set_guild_config(guild_id, cfg)
        return True
    except Exception:
        log.exception("Failed to set alliance type for guild %s", guild_id)
        return False

# -----------------------------
# Officer management
# -----------------------------
def add_officer_by_id(guild_id: int, user_id: int) -> bool:
    """Record a user id in officer_ids list (does not assign role)."""
    try:
        cfg = get_guild_config(guild_id) or {}
        officers = cfg.setdefault("officer_ids", [])
        if user_id not in officers:
            officers.append(user_id)
            cfg["officer_ids"] = officers
            set_guild_config(guild_id, cfg)
        return True
    except Exception:
        log.exception("Failed to add officer %s to guild %s", user_id, guild_id)
        return False


def remove_officer_by_id(guild_id: int, user_id: int) -> bool:
    try:
        cfg = get_guild_config(guild_id) or {}
        officers = cfg.get("officer_ids", [])
        if user_id in officers:
            officers.remove(user_id)
            cfg["officer_ids"] = officers
            set_guild_config(guild_id, cfg)
        return True
    except Exception:
        log.exception("Failed to remove officer %s from guild %s", user_id, guild_id)
        return False


def get_officer_ids(guild_id: int) -> List[int]:
    """Return the list of officer user IDs for the guild."""
    try:
        cfg = get_guild_config(guild_id) or {}
        return cfg.get("officer_ids", [])
    except Exception:
        log.exception("Failed to get officer IDs for guild %s", guild_id)
        return []


# Backwards-compatible alias (some code referenced this name previously)
alliance_info = get_alliance_info
