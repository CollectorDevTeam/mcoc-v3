# mcoc/common/account_helpers.py
import logging
from typing import Dict, Any, Tuple, Optional

log = logging.getLogger("red.mcoc.account_helpers")

# Public metadata for profile fields (used by account_prefix help)
# common/account_helpers.py

ALLOWED_PROFILE_FIELDS = {
    "display_name": {"type": "str", "desc": "Preferred display name"},
    "mcoc_name": {"type": "str", "desc": "In-game username"},
    "mcoc_id": {"type": "str", "desc": "In-game id/slug"},
    "website": {"type": "str", "desc": "Personal website"},
    "invite": {"type": "str", "desc": "Recruiter/invite link"},
    "timezone": {"type": "str", "desc": "Timezone"},
    "alliance": {"type": "str", "desc": "Alliance name"},
    "job": {"type": "str", "desc": "Job/role"},
    "age": {"type": "str", "desc": "Age or birth year"},
    "gender": {"type": "str", "desc": "Gender"},
    "about": {"type": "str", "desc": "Short bio or notes"},
    "mastery": {"type": "str", "desc": "Mastery build or link"},
    "started": {"type": "str", "desc": "Playing since (ISO date)"},
    "roster_public": {"type": "bool", "desc": "Make roster visible to guild"},
    "privacy_mode": {"type": "str", "desc": "private|guild|alliance|public"},
    "linked": {"type": "bool", "desc": "Account linked flag"},
    "prestige_map": {"type": "dict", "desc": "Persisted prestige per champ"},
    "top5": {"type": "list", "desc": "Cached top 5 champion names"},
}

# user-visible -> stored key
FIELD_CANONICAL = {
    "display_name": "mcoc_name",
    "mcoc_name": "mcoc_name",
    "mcoc_id": "mcoc_id",
    "website": "website",
    "invite": "invite",
    "timezone": "timezone",
    "alliance": "alliance",
    "job": "job",
    "age": "age",
    "gender": "gender",
    "about": "about",
    "notes": "about",
    "mastery": "mastery",
    "started": "started",
    "roster_public": "roster_public",
    "privacy_mode": "privacy_mode",
    "linked": "linked",
    "prestige_map": "prestige_map",
    "top5": "top5",
}

def validate_profile_field(field: str) -> bool:
    key = field.strip()
    return key in FIELD_CANONICAL.keys() or key in set(FIELD_CANONICAL.values())

def get_profile_settings(profile: dict) -> dict:
    return {user_field: profile.get(stored_key) for user_field, stored_key in FIELD_CANONICAL.items()}

import discord
import datetime
from typing import Any, Dict, Optional, List
from .componentsV2 import CDTEmbed

def _format_date_iso(iso_str: Optional[str]) -> str:
    if not iso_str:
        return "Unknown"
    try:
        dt = datetime.datetime.fromisoformat(iso_str)
        return dt.date().isoformat()
    except Exception:
        return str(iso_str)

async def format_profile_embed(ctx, profile: Dict[str, Any], member: Optional[Any] = None) -> discord.Embed:
    """
    Build a Collector-style profile embed from stored profile dict.
    Returns a discord.Embed. Safe to call from prefix and slash handlers.
    """
    # Resolve display name
    display_name = profile.get("mcoc_name") or profile.get("display_name") or (member.display_name if getattr(member, "display_name", None) else None) or str(profile.get("mcoc_id") or "User")

    emb = CDTEmbed(ctx, title=f"{display_name} — Profile", colour=discord.Color.blue())
    # author / thumbnail
    try:
        if member and getattr(member, "avatar_url", None):
            emb.set_author(name=display_name, icon_url=member.avatar_url)
            emb.set_thumbnail(url=member.avatar_url)
        else:
            emb.set_author(name=display_name)
    except Exception:
        emb.set_author(name=display_name)

    # Linked / ID
    linked = profile.get("linked", False)
    mcoc_id = profile.get("mcoc_id") or profile.get("mcoc_name") or None
    emb.add_field(name="Linked", value=str(bool(linked)), inline=True)
    emb.add_field(name="MCoc ID", value=str(mcoc_id) if mcoc_id else "Not linked", inline=True)

    # Prestige and Top 5
    total_prestige = None
    top5_lines: List[str] = []
    # prefer cached top5
    if profile.get("top5"):
        for i, name in enumerate(profile.get("top5")[:5]):
            top5_lines.append(f"{i+1}. {name}")
    else:
        # try prestige_map to compute top5 if present
        pm = profile.get("prestige_map") or {}
        try:
            items = []
            for k, v in pm.items():
                try:
                    items.append((k, int(v)))
                except Exception:
                    continue
            items.sort(key=lambda x: -x[1])
            top5_lines = [f"{i+1}. {k.split('|')[0]} [{v}]" for i, (k, v) in enumerate(items[:5])]
            total_prestige = sum(v for _, v in items)
        except Exception:
            top5_lines = []

    if total_prestige is None:
        # try stored numeric total
        try:
            total_prestige = int(profile.get("prestige_total")) if profile.get("prestige_total") is not None else None
        except Exception:
            total_prestige = None

    if total_prestige is not None:
        emb.add_field(name="Prestige (sum)", value=str(total_prestige), inline=False)
    if top5_lines:
        emb.add_field(name="Top 5 Champions", value="\n".join(top5_lines), inline=False)
    else:
        emb.add_field(name="Top 5 Champions", value="No roster or prestige data available.", inline=False)

    # Add other profile fields in a compact layout
    display_order = ["alliance", "job", "timezone", "website", "invite", "age", "gender", "mastery"]
    for key in display_order:
        val = profile.get(key)
        if val:
            emb.add_field(name=key.replace("_", " ").title(), value=str(val), inline=True)

    # About / notes as description or field
    about = profile.get("about") or profile.get("notes") or profile.get("description")
    if about:
        emb.add_field(name="About", value=str(about), inline=False)

    # Started / membership
    started = profile.get("started") or profile.get("created_at")
    if started:
        emb.add_field(name="Playing Since", value=_format_date_iso(started), inline=True)

    emb.set_footer(text="Profile generated by MCOC")
    return emb

def link_account(parent, user_id: int, mcoc_id: str) -> Tuple[bool, str]:
    """
    Helper to link an account. Returns (ok, message).
    parent is expected to be the core object or None. This function will attempt
    to resolve a UserDataManager via roster_helpers.ensure_user_manager.
    """
    try:
        users = None
        if parent:
            try:
                from .roster_helpers import ensure_user_manager
                users = ensure_user_manager(parent)
            except Exception:
                users = None
        if not users:
            return False, "User manager not available; cannot link now."
        users.set_profile_field(user_id, "mcoc_id", str(mcoc_id).strip())
        users.set_profile_field(user_id, "linked", True)
        return True, f"Linked your account to MCoc id `{mcoc_id}`."
    except Exception:
        log.exception("link_account failed for %s", user_id)
        return False, "Failed to link account."


def unlink_account(parent, user_id: int) -> Tuple[bool, str]:
    """
    Helper to unlink an account. Returns (ok, message).
    """
    try:
        users = None
        if parent:
            try:
                from .roster_helpers import ensure_user_manager
                users = ensure_user_manager(parent)
            except Exception:
                users = None
        if not users:
            return False, "User manager not available; cannot unlink now."
        users.set_profile_field(user_id, "mcoc_id", None)
        users.set_profile_field(user_id, "linked", False)
        return True, "Your MCoc account has been unlinked."
    except Exception:
        log.exception("unlink_account failed for %s", user_id)
        return False, "Failed to unlink account."


def delete_user_profile(parent, user_id: int) -> Tuple[bool, str]:
    """
    Helper to delete a user's profile and roster. Returns (ok, message).
    """
    try:
        users = None
        if parent:
            try:
                from .roster_helpers import ensure_user_manager
                users = ensure_user_manager(parent)
            except Exception:
                users = None
        if not users:
            return False, "User manager not available; cannot delete now."
        deleted = users.delete_user(user_id)
        if deleted:
            return True, "Your profile and roster have been deleted."
        return False, "No profile file found to delete."
    except Exception:
        log.exception("delete_user_profile failed for %s", user_id)
        return False, "Failed to delete profile."
