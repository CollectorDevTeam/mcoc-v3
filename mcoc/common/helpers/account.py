# mcoc/common/account.py
"""
Account helpers (consolidated, sanitized).

Provides:
  - canonical metadata for profile fields (ALLOWED_PROFILE_FIELDS, FIELD_CANONICAL)
  - simple wrappers around the UserDataManager (get/set/delete profile fields)
  - linking/unlinking/deleting helpers that return (ok, message)
  - utilities to compute prestige/top5 from a user's roster and cache
  - enrollment / consent flow (CDTConfirm-based when available)
  - thin command wrappers used by prefix/slash layers

This file is intentionally defensive: it tolerates missing components and logs
useful diagnostics for action tracing.
"""

from typing import Any, Dict, Optional, Tuple, List, Union
import logging
import datetime
import re
import asyncio

from mcoc.common.componentsV2 import CDTEmbed

# types
from mcoc.common.types import Champion, champion_from_dict, User

log = logging.getLogger("red.mcoc.account_helpers")

# -----------------------------
# Public metadata for profile fields
# -----------------------------
ALLOWED_PROFILE_FIELDS: Dict[str, Dict[str, str]] = {
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
    # consent fields (used by enrollment flow)
    "consent": {"type": "bool", "desc": "User consented to privacy policy"},
    "consent_ts": {"type": "str", "desc": "Consent timestamp (ISO date)"},
    "consent_version": {"type": "str", "desc": "Policy version at consent"},
    "consent_source": {"type": "str", "desc": "Policy source URL"},
}

# user-visible -> stored key
FIELD_CANONICAL: Dict[str, str] = {
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
    "consent": "consent",
    "consent_ts": "consent_ts",
    "consent_version": "consent_version",
    "consent_source": "consent_source",
}

# -----------------------------
# Basic helpers
# -----------------------------
def validate_profile_field(field: str) -> bool:
    """
    Return True if the provided field name is allowed (either user-visible or stored key).
    """
    if not field:
        return False
    key = field.strip()
    return key in FIELD_CANONICAL.keys() or key in set(FIELD_CANONICAL.values())


def get_profile_settings(profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return a mapping of user-visible field -> stored value for the given profile dict.
    """
    return {user_field: profile.get(stored_key) for user_field, stored_key in FIELD_CANONICAL.items()}


def _format_playing_since(iso_date_str: Optional[str]) -> str:
    """
    Given an ISO date string (YYYY-MM-DD or full ISO), return:
    "Oct 15, 2015 - 3,970 days"
    If parsing fails, return the raw string or 'Not set'.
    """
    if not iso_date_str:
        return "Not set"

    s = str(iso_date_str).strip()
    now = datetime.datetime.now().date()

    log.info("Parsing playing since date: %s", s)
    log.info("Today's date: %s", now)

    dt = None
    # try common ISO formats first
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            dt = datetime.datetime.strptime(s, fmt)
            break
        except Exception:
            continue

    # try common US formats (MM/DD/YYYY, M/D/YYYY, MM-DD-YYYY)
    if dt is None:
        m = re.match(r"^\s*(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2,6})\s*$", s)
        if m:
            mm, dd, yy = m.group(1), m.group(2), m.group(3)
            if len(yy) > 4 and yy.startswith("20"):
                yy = yy[:4]
            try:
                if len(yy) == 2:
                    yint = int(yy)
                    yyyy = 2000 + yint if yint <= 29 else 1900 + yint
                else:
                    yyyy = int(yy)
                dt = datetime.datetime(yyyy, int(mm), int(dd))
            except Exception:
                dt = None

    # fallback to fromisoformat (handles offsets and some variants)
    if dt is None:
        try:
            if len(s) == 10 and s.count("-") == 2:
                try:
                    d = datetime.date.fromisoformat(s)
                    dt = datetime.datetime.combine(d, datetime.time.min)
                except Exception:
                    dt = None
            if dt is None:
                dt = datetime.datetime.fromisoformat(s)
        except Exception:
            dt = None

    if dt is None:
        log.warning("Failed to parse playing since date: %s", s)
        return s

    dt_date = dt.date()
    days = (now - dt_date).days
    log.info("Days since playing since date: %s", days)
    pretty = dt_date.strftime("%b %d, %Y")
    return f"{pretty} - {days:,} days"


# -----------------------------
# UserDataManager wrappers
# -----------------------------
def _ensure_user_manager_from_parent(parent: Any):
    """
    Internal helper to resolve a UserDataManager instance from the core/parent object.
    This mirrors the behavior used elsewhere in the codebase (roster.ensure_user_manager).
    """
    try:
        from .roster import ensure_user_manager
        return ensure_user_manager(parent)
    except Exception:
        log.exception("_ensure_user_manager_from_parent: failed to import ensure_user_manager")
        return None


def get_user_from_parent(parent, user_id: int) -> Optional[User]:
    """
    Return a User dataclass constructed from stored profile data, or None.
    """
    users = _ensure_user_manager_from_parent(parent)
    if not users:
        return None
    try:
        raw = users.get_profile(user_id) or {}
    except Exception:
        raw = {}
    if not raw:
        return None
    try:
        return User.from_dict(raw)
    except Exception:
        log.exception("get_user_from_parent: failed to construct User from profile for %s", user_id)
        return None


def persist_user(parent, user: User) -> bool:
    """
    Persist a User dataclass to storage. This helper writes the full profile dict.
    It attempts to use a single profile write if supported, otherwise falls back to setting fields.
    """
    users = _ensure_user_manager_from_parent(parent)
    if not users:
        return False
    try:
        data = user.to_dict()
        # prefer a bulk set if available
        if hasattr(users, "set_profile"):
            try:
                users.set_profile(user.user_id, data)
                return True
            except Exception:
                pass
        # otherwise set fields individually
        for k, v in data.items():
            try:
                users.set_profile_field(user.user_id, k, v)
            except Exception:
                # ignore individual field failures but continue
                log.debug("persist_user: failed to set field %s for user %s", k, user.user_id)
        return True
    except Exception:
        log.exception("persist_user failed for %s", getattr(user, "user_id", "<unknown>"))
        return False


def get_profile(parent: Any, user_id: int) -> Dict[str, Any]:
    """
    Return the stored profile dict for user_id, or {} on failure.
    Kept for backwards compatibility with callers that expect a dict.
    """
    try:
        users = _ensure_user_manager_from_parent(parent)
        if not users:
            return {}
        if hasattr(users, "get_profile"):
            return users.get_profile(user_id) or {}
        return {}
    except Exception:
        log.exception("get_profile failed for %s", user_id)
        return {}


def set_profile_field(parent: Any, user_id: int, field: str, value: Any) -> bool:
    """
    Set a single profile field. Returns True on success, False otherwise.
    field should be the stored key (e.g., 'mcoc_id') — callers may map via FIELD_CANONICAL.
    """
    try:
        users = _ensure_user_manager_from_parent(parent)
        if not users:
            return False

        # Normalize 'started' to ISO date when possible using the User helper
        if field == "started" and value is not None:
            try:
                # use User._normalize_started for conservative normalization
                iso = User._normalize_started(value)
                if iso:
                    value = iso
                else:
                    log.warning("set_profile_field: could not normalize 'started' value=%r for user=%s", value, user_id)
            except Exception:
                log.exception("set_profile_field: error normalizing 'started' value=%r for user=%s", value, user_id)

        if hasattr(users, "set_profile_field"):
            users.set_profile_field(user_id, field, value)
            return True
        if hasattr(users, "set_profile_field_async") and callable(users.set_profile_field_async):
            try:
                users.set_profile_field_async(user_id, field, value)
                return True
            except Exception:
                return False
        return False
    except Exception:
        log.exception("set_profile_field failed for %s field=%s", user_id, field)
        return False


def delete_user_profile(parent: Any, user_id: int) -> Tuple[bool, str]:
    """
    Delete a user's profile/roster via the UserDataManager. Returns (ok, message).
    """
    try:
        users = _ensure_user_manager_from_parent(parent)
        if not users:
            return False, "User manager not available; cannot delete now."
        if hasattr(users, "delete_user"):
            deleted = users.delete_user(user_id)
            if deleted:
                return True, "Your profile and roster have been deleted."
            return False, "No profile file found to delete."
        return False, "User manager does not support deletion."
    except Exception:
        log.exception("delete_user_profile failed for %s", user_id)
        return False, "Failed to delete profile."


# -----------------------------
# Link / unlink helpers
# -----------------------------
def link_account(parent: Any, user_id: int, mcoc_id: str) -> Tuple[bool, str]:
    """
    Link a Discord user to an in-game id. Returns (ok, message).
    """
    try:
        users = _ensure_user_manager_from_parent(parent)
        if not users:
            return False, "User manager not available; cannot link now."
        users.set_profile_field(user_id, "mcoc_id", str(mcoc_id).strip())
        users.set_profile_field(user_id, "linked", True)
        return True, f"Linked your account to MCoc id `{mcoc_id}`."
    except Exception:
        log.exception("link_account failed for %s", user_id)
        return False, "Failed to link account."


def unlink_account(parent: Any, user_id: int) -> Tuple[bool, str]:
    """
    Unlink a Discord user from their in-game id. Returns (ok, message).
    """
    try:
        users = _ensure_user_manager_from_parent(parent)
        if not users:
            return False, "User manager not available; cannot unlink now."
        users.set_profile_field(user_id, "mcoc_id", None)
        users.set_profile_field(user_id, "linked", False)
        return True, "Your MCoc account has been unlinked."
    except Exception:
        log.exception("unlink_account failed for %s", user_id)
        return False, "Failed to unlink account."


# -----------------------------
# Prestige / Top5 computation
# -----------------------------
def _normalize_prestige_value(raw: Any) -> int:
    """
    Convert various prestige representations into an int.
    Accepts ints, floats, or strings like 'P12345', '12,345', ' 12345 '.
    Returns 0 on failure.
    """
    try:
        if raw is None:
            return 0
        if isinstance(raw, (int, float)):
            return int(raw)
        s = str(raw).strip()
        m = re.search(r"(\d[\d,]*)", s)
        if not m:
            return 0
        digits = m.group(1).replace(",", "")
        return int(digits)
    except Exception:
        return 0


def _parse_prestige_map(profile: Union[User, Dict[str, Any]]) -> Dict[str, int]:
    """
    Normalize a persisted prestige_map into a dict of { 'slug|stars': int }.
    Accepts either a User dataclass or a raw profile dict.
    """
    out: Dict[str, int] = {}
    try:
        if isinstance(profile, User):
            pm = profile.prestige_map or {}
        else:
            pm = profile.get("prestige_map") or {}
        if isinstance(pm, dict):
            for k, v in pm.items():
                try:
                    out[k] = _normalize_prestige_value(v)
                except Exception:
                    out[k] = 0
    except Exception:
        log.exception("_parse_prestige_map failed")
    return out


def compute_top5_from_profile(profile: Union[User, Dict[str, Any]]) -> Tuple[List[str], Optional[int], Optional[float]]:
    """
    Compute a Top 5 list and total prestige from a profile's persisted prestige_map.

    Accepts either a User dataclass or a raw profile dict.

    Returns:
      - top5_lines: list of formatted lines (already pretty-printed via format_top5_prestige_line)
      - total_prestige: sum of all prestige values (int) or None if no items
      - average_prestige: average prestige across items (float rounded to 2 decimals) or None
    """
    try:
        pm = _parse_prestige_map(profile)
        items = [(k, v) for k, v in pm.items() if isinstance(v, int)]
        if not items:
            return [], None, None

        items.sort(key=lambda x: -x[1])

        total = sum(v for _, v in items) if items else None
        average = (total / len(items)) if items else None
        average_rounded = round(average, 2) if average is not None else None

        top5 = items[:5]
        top5_lines: List[str] = []
        try:
            from mcoc.common.formatters import format_top5_prestige_line
            for i, (k, v) in enumerate(top5):
                try:
                    slug, stars = str(k).split("|", 1)
                    rarity = int(stars)
                except Exception:
                    slug = str(k)
                    rarity = 6
                entry = {
                    "champion": slug,
                    "rarity": rarity,
                    "rank": 1,
                    "sig": 0,
                    "ascended": 0,
                    "prestige": int(v) if isinstance(v, (int, float)) else 0,
                }
                # format without champion object here; caller may reformat with cache
                line = format_top5_prestige_line(None, entry)
                top5_lines.append(f"{i+1}. {line}")
        except Exception:
            top5_lines = [f"{i+1}. {k.split('|')[0]} [{v}]" for i, (k, v) in enumerate(top5)]

        return top5_lines, total, average_rounded
    except Exception:
        log.exception("compute_top5_from_profile failed")
        return [], None, None


def compute_top5_from_roster(parent: Any, roster: List[Dict[str, Any]], profile: Union[User, Dict[str, Any]]) -> Tuple[List[str], Optional[int]]:
    """
    Given a roster (list of entry dicts) and profile (for persisted prestige_map),
    compute a Top 5 by resolving prestige via cache/index where possible.

    Accepts profile as User or dict.

    Returns (top5_lines, total_prestige).
    """
    try:
        cache = getattr(parent, "cache", None)
        prestige_map = profile.prestige_map if isinstance(profile, User) else profile.get("prestige_map", {}) if isinstance(profile, dict) else {}
        entries: List[Dict[str, Any]] = []
        for e in roster:
            try:
                slug = str(e.get("champion") or "").strip()
                stars = int(e.get("rarity") or e.get("stars") or 0)
                key = f"{slug}|{stars}"
                p = None
                if key in prestige_map and prestige_map.get(key) is not None:
                    try:
                        p = int(prestige_map.get(key))
                    except Exception:
                        p = None
                if p is None and cache and hasattr(cache, "get_prestige_value"):
                    try:
                        p = cache.get_prestige_value(
                            slug,
                            int(e.get("rarity") or e.get("stars") or stars),
                            int(e.get("rank") or 1),
                            int(e.get("ascended") or 0),
                            int(e.get("sig") or 0),
                        )
                    except Exception:
                        p = None
                name = slug
                if cache:
                    try:
                        # prefer dataclass object when available
                        if hasattr(cache, "get_champion_obj"):
                            cobj = cache.get_champion_obj(slug)
                            if cobj:
                                name = cobj.name or cobj.slug or slug
                        else:
                            cobj = cache.get_champion(slug)
                            if cobj and isinstance(cobj, dict):
                                name = cobj.get("name") or cobj.get("slug") or slug
                    except Exception:
                        pass
                entries.append({"name": name, "prestige": int(p) if isinstance(p, (int, float)) else 0})
            except Exception:
                continue
        entries.sort(key=lambda x: (-int(x.get("prestige") or 0), x.get("name")))
        top5 = entries[:5]
        top5_lines = [f"{i+1}. {it['name']} [{it['prestige']}]" for i, it in enumerate(top5)]
        total = sum(int(it.get("prestige") or 0) for it in entries) if entries else None
        return top5_lines, total
    except Exception:
        log.exception("compute_top5_from_roster failed")
        return [], None


# -----------------------------
# Profile display builder
# -----------------------------
def _format_date_iso(iso_str: Optional[str]) -> str:
    if not iso_str:
        return "Unknown"
    try:
        dt = datetime.datetime.fromisoformat(iso_str)
        return dt.date().isoformat()
    except Exception:
        return str(iso_str)


def build_profile_display(parent: Any, ctx_or_author: Any, target_id: int, viewer_id: Optional[int] = None, *, prefer_embed: bool = True) -> Tuple[Optional[Any], Optional[str]]:
    """
    Build a profile display for target_id.

    Returns (embed_or_none, text_fallback_or_none).
    """
    try:
        users = _ensure_user_manager_from_parent(parent)
        if not users:
            return None, "User manager not available."

        # privacy check if available
        try:
            if viewer_id is not None and hasattr(users, "can_view_profile"):
                allowed = users.can_view_profile(viewer_id, target_id, guild_id=getattr(getattr(ctx_or_author, "guild", None), "id", None))
                if not allowed:
                    return None, "You do not have permission to view that profile."
        except Exception:
            if viewer_id is not None and viewer_id != target_id:
                return None, "You do not have permission to view that profile."

        top5_lines: List[str] = []
        total_prestige: Optional[int] = None

        # fetch profile as User when possible
        user_obj: Optional[User] = None
        try:
            user_obj = get_user_from_parent(parent, target_id)
        except Exception:
            user_obj = None

        profile: Dict[str, Any] = {}
        if user_obj:
            profile = user_obj.to_dict()
        else:
            try:
                profile = users.get_profile(target_id) or {}
            except Exception:
                profile = {}

        if not profile:
            return None, "No profile found for that user."

        # Manual embed construction (defensive)
        try:
            try:
                emb = CDTEmbed.embed(ctx_or_author, title="CollectorVerse Profile")
            except Exception:
                emb = CDTEmbed.embed(ctx_or_author, title=f"{profile.get('mcoc_name') or profile.get('display_name') or str(target_id)} — Profile")

            linked = profile.get("linked", False)
            mcoc_id = profile.get("mcoc_id") or profile.get("mcoc_name") or None
            CDTEmbed.add_field(ctx_or_author, emb, name="Linked", value=str(bool(linked)), inline=True)
            CDTEmbed.add_field(ctx_or_author, emb, name="MCOC Username", value=str(mcoc_id) if mcoc_id else "Not linked", inline=True)

            # Top5 / prestige: prefer cached top5 in profile, else compute from prestige_map
            top5_lines, total_prestige, _avg = compute_top5_from_profile(user_obj if user_obj else profile)
            if not top5_lines:
                roster = []
                try:
                    lr = getattr(users, "list_roster", None)
                    if lr:
                        if hasattr(lr, "__call__"):
                            try:
                                roster = lr(target_id) or []
                            except TypeError:
                                import asyncio as _asyncio
                                if _asyncio.iscoroutinefunction(lr):
                                    roster = _asyncio.get_event_loop().run_until_complete(lr(target_id)) or []
                                else:
                                    roster = []
                except Exception:
                    roster = []
                if roster:
                    top5_lines, total_prestige = compute_top5_from_roster(parent, roster, user_obj if user_obj else profile)

            if total_prestige is not None:
                CDTEmbed.add_field(ctx_or_author, emb, name="Prestige (sum)", value=str(total_prestige), inline=False)

            # Format Top 5 using prestige formatter and cache when available
            formatted_top5: List[str] = []
            if top5_lines:
                try:
                    from mcoc.common.formatters import format_top5_prestige_line
                    cache = getattr(parent, "cache", None)

                    for line in top5_lines:
                        try:
                            # already formatted if contains star emoji or custom emoji
                            if "]" in line and any(e in line for e in ("★", "<:", "🧬", "🛡️")):
                                formatted_top5.append(line.split(". ", 1)[1])
                                continue
                            # extract slug and prestige
                            slug = line.split(". ", 1)[1].split(" [", 1)[0]
                            prestige_val = 0
                            if "[" in line:
                                try:
                                    prestige_val = int(line.split("[")[-1].rstrip("]"))
                                except Exception:
                                    prestige_val = 0
                        except Exception:
                            slug = line
                            prestige_val = 0

                        champ_obj: Optional[Champion] = None
                        if cache:
                            try:
                                if hasattr(cache, "get_champion_obj"):
                                    champ_obj = cache.get_champion_obj(slug)
                                else:
                                    raw = cache.get_champion(slug)
                                    champ_obj = champion_from_dict(raw) if raw else None
                            except Exception:
                                champ_obj = None

                        entry = {
                            "champion": slug,
                            "rarity": 6,
                            "rank": 1,
                            "sig": 0,
                            "ascended": 0,
                            "prestige": int(prestige_val) if isinstance(prestige_val, (int, float)) else 0,
                        }

                        formatted_top5.append(format_top5_prestige_line(champ_obj, entry))
                except Exception:
                    formatted_top5 = top5_lines
            else:
                formatted_top5 = ["No roster or prestige data available."]

            CDTEmbed.add_field(ctx_or_author, emb, name="Top 5 Champions", value="\n".join(formatted_top5), inline=False)

            # Add other profile fields in a compact layout
            display_order = ["alliance", "job", "timezone", "website", "invite", "age", "gender", "mastery"]
            for key in display_order:
                val = profile.get(key)
                if val:
                    CDTEmbed.add_field(ctx_or_author, emb, name=key.replace("_", " ").title(), value=str(val), inline=True)

            about = profile.get("about") or profile.get("notes") or profile.get("description")
            if about:
                CDTEmbed.add_field(ctx_or_author, emb, name="About", value=str(about), inline=False)

            started = profile.get("started") or profile.get("created_at")
            if started:
                CDTEmbed.add_field(ctx_or_author, emb, name="Playing Since", value=_format_playing_since(started), inline=True)

            # Consent metadata (if present)
            try:
                consent = profile.get("consent")
                if consent is not None:
                    CDTEmbed.add_field(ctx_or_author, emb, name="Consent Given", value=str(bool(consent)), inline=True)
                consent_ts = profile.get("consent_ts")
                if consent_ts:
                    CDTEmbed.add_field(ctx_or_author, emb, name="Consent Date", value=_format_date_iso(consent_ts), inline=True)
            except Exception:
                pass

            CDTEmbed.set_footer(ctx_or_author, emb, text="Profile generated by MCOC")
            return emb, None
        except Exception:
            log.exception("build_profile_display: embed construction failed")

        # Text fallback
        try:
            lines: List[str] = []
            display_name = profile.get("mcoc_name") or profile.get("display_name") or str(target_id)
            lines.append(f"Profile — {display_name}")
            linked = profile.get("linked", False)
            mcoc_id = profile.get("mcoc_id") or profile.get("mcoc_name")
            lines.append(f"Linked: {linked}")
            lines.append(f"MCoc ID: {mcoc_id or 'Not linked'}")
            if total_prestige is not None:
                lines.append(f"Prestige (sum): {total_prestige}")
            if top5_lines:
                lines.append("Top 5 Champions:")
                lines.extend(top5_lines)
            else:
                lines.append("Top 5 Champions: none")
            settings = get_profile_settings(profile)
            lines.append("")
            lines.append("Profile fields:")
            lines.append(str(settings))
            return None, "\n".join(lines)
        except Exception:
            log.exception("build_profile_display: text fallback failed")
            return None, "Failed to build profile display."
    except Exception:
        log.exception("build_profile_display failed")
        return None, "Failed to build profile display."


# ----------------------------
# Enrollment / Consent flow (CDTConfirm-based opt-in)
# ----------------------------
POLICY_METADATA = {
    "privacy_policy": {
        "url": "https://raw.githubusercontent.com/CollectorDevTeam/mcoc-v3/main/mcoc/privacy_policy.md",
        "version": "v1.0",
    },
    "terms_of_service": {
        "url": "https://raw.githubusercontent.com/CollectorDevTeam/mcoc-v3/main/mcoc/terms_of_service.md",
        "version": "v1.0",
    },
}


def _record_consent(parent: Any, user_id: int, *, version: str, source: str) -> bool:
    """
    Synchronous persistence helper. Returns True on success.
    """
    try:
        user_obj = None
        try:
            user_obj = get_user_from_parent(parent, user_id)
        except Exception:
            user_obj = None

        ts = datetime.datetime.utcnow().isoformat()

        if user_obj:
            user_obj.consent = True
            user_obj.consent_ts = ts
            user_obj.consent_version = version
            user_obj.consent_source = source
            if not getattr(user_obj, "created_at", None):
                user_obj.created_at = ts
            user_obj.updated_at = ts
            ok = persist_user(parent, user_obj)
            log.info("consent:recorded user=%s method=typed ok=%s version=%s source=%s", user_id, ok, version, source)
            return ok

        # fallback: set fields individually
        ok1 = set_profile_field(parent, user_id, "consent", True)
        ok2 = set_profile_field(parent, user_id, "consent_ts", ts)
        ok3 = set_profile_field(parent, user_id, "consent_version", version)
        ok4 = set_profile_field(parent, user_id, "consent_source", source)
        ok = bool(ok1 and ok2 and ok3 and ok4)
        log.info("consent:recorded user=%s method=fields ok=%s version=%s source=%s", user_id, ok, version, source)
        return ok
    except Exception:
        log.exception("_record_consent failed for %s", user_id)
        return False


async def _maybe_async_record_consent(parent: Any, user_id: int, *, version: str, source: str) -> bool:
    """
    Async wrapper that runs the synchronous _record_consent off the event loop.
    """
    try:
        return await asyncio.to_thread(lambda: _record_consent(parent, user_id, version=version, source=source))
    except Exception:
        try:
            return _record_consent(parent, user_id, version=version, source=source)
        except Exception:
            log.exception("_maybe_async_record_consent fallback failed for %s", user_id)
            return False


async def accept_consent(parent: Any, user_id: int, *, policy_key: str = "privacy_policy") -> Tuple[bool, str]:
    """
    High-level helper to accept consent for a user.
    Returns (ok, message).
    """
    try:
        meta = POLICY_METADATA.get(policy_key, {})
        version = meta.get("version") or "v1.0"
        source = meta.get("url") or ""
        ok = await _maybe_async_record_consent(parent, user_id, version=version, source=source)
        if ok:
            log.info("consent:accepted user=%s version=%s", user_id, version)
            return True, "Consent recorded. Your CollectorVerse profile is now enrolled."
        log.warning("consent:accept_failed user=%s version=%s", user_id, version)
        return False, "Failed to record consent. Please try again later."
    except Exception:
        log.exception("accept_consent failed for %s", user_id)
        return False, "Failed to record consent due to an internal error."


async def decline_consent(parent: Any, user_id: int) -> Tuple[bool, str]:
    """
    Called when a user declines consent. We do not create a profile or persist personal data.
    Returns (ok, message).
    """
    try:
        # privacy-first: do not persist personal data on decline.
        try:
            set_profile_field(parent, user_id, "consent", False)
        except Exception:
            pass
        log.info("consent:declined user=%s", user_id)
        return True, "You have declined. No profile was created and no personal data was stored."
    except Exception:
        log.exception("decline_consent failed for %s", user_id)
        return False, "Failed to process your response. Please try again later."


async def revoke_consent(parent: Any, user_id: int) -> Tuple[bool, str]:
    """
    Revoke consent and delete the user's profile. Returns (ok, message).
    """
    try:
        ok, msg = delete_user_profile(parent, user_id)
        if ok:
            log.info("consent:revoked user=%s", user_id)
            return True, "Your consent has been revoked and your profile has been deleted."
        log.warning("consent:revoke_failed user=%s msg=%s", user_id, msg)
        return False, msg
    except Exception:
        log.exception("revoke_consent failed for %s", user_id)
        return False, "Failed to revoke consent; please try again later."


async def prompt_user_for_consent(parent: Any, ctx_or_author: Any, user_id: int, *, timeout: int = 120) -> Tuple[bool, str]:
    """
    Present a consent prompt to the user and record their response.

    Behavior:
      - Prefer mcoc.common.componentsV2.CDTConfirm view if available.
      - Fall back to a text instruction if interactive view is not available.
    """
    try:
        # short-circuit if user already consented
        try:
            u = get_user_from_parent(parent, user_id)
            if u and getattr(u, "consent", False):
                log.info("consent:prompt_skipped_already_consented user=%s", user_id)
                return True, "You have already enrolled and given consent."
        except Exception:
            pass

        policy = POLICY_METADATA.get("privacy_policy", {})
        terms = POLICY_METADATA.get("terms_of_service", {})
        privacy_url = policy.get("url")
        terms_url = terms.get("url")
        version = policy.get("version") or "v1.0"

        title = "CollectorVerse Account Consent"
        description = (
            "CollectorVerse stores a small set of MCOC-related profile and roster data to provide roster, prestige and profile features.\n\n"
            "Before we create or store your profile, please review our Privacy Policy and Terms of Service and explicitly agree.\n\n"
            f"Privacy Policy: {privacy_url}\n"
            f"Terms of Service: {terms_url}\n\n"
            "We will only store the data you explicitly provide and your consent metadata. You can revoke consent at any time."
        )

        # Build embed
        try:
            emb = CDTEmbed.embed(ctx_or_author, title=title, description=description)
            CDTEmbed.set_footer(ctx_or_author, emb, text=f"Policy version: {version}")
        except Exception:
            emb = None

        # Try branded Confirm view from componentsV2
        try:
            from mcoc.common.componentsV2 import CDTConfirm as _CDTConfirm  # type: ignore
            view = _CDTConfirm(timeout=timeout, confirm_label="Agree", cancel_label="Decline")
            sent = False
            try:
                if emb and hasattr(ctx_or_author, "send"):
                    await ctx_or_author.send(embed=emb, view=view)
                    sent = True
                elif emb and hasattr(ctx_or_author, "author") and hasattr(ctx_or_author.author, "send"):
                    await ctx_or_author.author.send(embed=emb, view=view)
                    sent = True
            except Exception:
                sent = False

            # fallback to channel if DM failed
            if not sent:
                try:
                    if emb and hasattr(ctx_or_author, "send"):
                        await ctx_or_author.send(embed=emb, view=view)
                        sent = True
                except Exception:
                    sent = False

            log.info("consent:prompt_shown user=%s via=%s", user_id, "DM" if sent else "channel")
            result = await view.wait_result()
            if result:
                ok, msg = await accept_consent(parent, user_id, policy_key="privacy_policy")
                return ok, msg
            else:
                ok, msg = await decline_consent(parent, user_id)
                return ok, msg

        except Exception:
            log.debug("CDTConfirm not available; falling back to text consent flow for user=%s", user_id)

        # Text fallback
        fallback_msg = (
            "To enroll, please review our policies:\n"
            f"Privacy Policy: {policy.get('url')}\n"
            f"Terms of Service: {terms.get('url')}\n\n"
            "If you agree, type: `///account agree`\n"
            "If you decline, type: `///account decline`\n"
            "This prompt will time out after a short period."
        )
        try:
            if hasattr(ctx_or_author, "send"):
                await ctx_or_author.send(fallback_msg)
            elif hasattr(ctx_or_author, "author") and hasattr(ctx_or_author.author, "send"):
                await ctx_or_author.author.send(fallback_msg)
        except Exception:
            pass
        log.info("consent:prompt_text_sent user=%s", user_id)
        return False, fallback_msg

    except Exception:
        log.exception("prompt_user_for_consent failed for %s", user_id)
        return False, "Failed to present consent prompt; please try again later."


# ---------------------------------------------------------------------
# Thin command wrappers for prefix/slash layers (exposed to prefix cog)
# ---------------------------------------------------------------------
async def enroll_command_handler(parent: Any, ctx_or_author: Any, user_id: int) -> Tuple[bool, str]:
    """
    Entry point for an enroll command or when ///account is invoked and no consent exists.
    Returns (ok, message) to be sent to the user.
    """
    try:
        try:
            user_obj = get_user_from_parent(parent, user_id)
        except Exception:
            user_obj = None

        if user_obj and getattr(user_obj, "consent", False):
            return True, "You have already enrolled and given consent."

        return await prompt_user_for_consent(parent, ctx_or_author, user_id)
    except Exception:
        log.exception("enroll_command_handler failed for %s", user_id)
        return False, "Enrollment failed; please try again later."


async def account_agree_command(parent: Any, ctx_or_author: Any, user_id: int) -> Tuple[bool, str]:
    """
    Handler for a text-based 'agree' command fallback (///account agree).
    """
    try:
        ok, msg = await accept_consent(parent, user_id, policy_key="privacy_policy")
        return ok, msg
    except Exception:
        log.exception("account_agree_command failed for %s", user_id)
        return False, "Failed to record consent; please try again later."


async def account_decline_command(parent: Any, ctx_or_author: Any, user_id: int) -> Tuple[bool, str]:
    """
    Handler for a text-based 'decline' command fallback (///account decline).
    """
    try:
        ok, msg = await decline_consent(parent, user_id)
        return ok, msg
    except Exception:
        log.exception("account_decline_command failed for %s", user_id)
        return False, "Failed to process decline; please try again later."


async def revoke_consent_command(parent: Any, ctx_or_author: Any, user_id: int) -> Tuple[bool, str]:
    """
    Public wrapper to revoke consent and delete a profile (used by prefix cog).
    """
    try:
        ok, msg = await revoke_consent(parent, user_id)
        return ok, msg
    except Exception:
        log.exception("revoke_consent_command failed for %s", user_id)
        return False, "Failed to revoke consent; please try again later."


# Backwards-compatible aliases expected by prefix code
# (prefix cog calls Account.enroll_command_handler, Account.account_agree_command, etc.)
enroll_command_handler = enroll_command_handler
account_agree_command = account_agree_command
account_decline_command = account_decline_command
revoke_consent = revoke_consent_command  # keep name used by some callers


# -----------------------------
# Public exports
# -----------------------------
__all__ = (
    "ALLOWED_PROFILE_FIELDS",
    "FIELD_CANONICAL",
    "validate_profile_field",
    "get_profile_settings",
    "get_profile",
    "get_user_from_parent",
    "persist_user",
    "set_profile_field",
    "delete_user_profile",
    "link_account",
    "unlink_account",
    "compute_top5_from_profile",
    "compute_top5_from_roster",
    "build_profile_display",
    "enroll_command_handler",
    "account_agree_command",
    "account_decline_command",
    "revoke_consent",
    "accept_consent",
    "decline_consent",
    "prompt_user_for_consent",
)
