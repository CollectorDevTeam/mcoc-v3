# mcoc/common/account.py
"""
Account helpers (consolidated).

This module centralizes all account/profile logic previously scattered between
prefix handlers and common helpers. It provides:

  - canonical metadata for profile fields (ALLOWED_PROFILE_FIELDS, FIELD_CANONICAL)
  - simple wrappers around the UserDataManager (get/set/delete profile fields)
  - linking/unlinking/deleting helpers that return (ok, message)
  - utilities to compute prestige/top5 from a user's roster and cache
  - a single high-level function to build a Collector-style profile display
    (returns a discord.Embed when possible, otherwise a text summary)

Design goals:
  - Keep I/O (sending messages) in prefix/slash layers; return values here.
  - Be defensive about missing core/cache/users implementations.
  - Make the profile-building logic testable and reusable by both prefix and slash code.
"""

from typing import Any, Dict, Optional, Tuple, List
import logging
import datetime

from mcoc.common.componentsV2 import CDTEmbed

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

    from datetime import datetime, timezone

def _format_playing_since(iso_date_str: Optional[str]) -> str:
    """
    Given an ISO date string (YYYY-MM-DD or full ISO), return:
    "Oct 15, 2015 - 3,970 days"
    If parsing fails, return the raw string or 'Not set'.
    """
    if not iso_date_str:
        return "Not set"

    s = str(iso_date_str).strip()
    # compute "today" once (use datetime module imported as `import datetime`)
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

    # fallback to fromisoformat (handles offsets and some variants)
    if dt is None:
        try:
            # datetime.fromisoformat may raise for date-only strings in some Python versions,
            # so try date.fromisoformat first for YYYY-MM-DD
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
        # parsing failed — return raw stored value
        log.warning("Failed to parse playing since date: %s", s)
        return s

    # normalize to date and compute delta
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


def get_profile(parent: Any, user_id: int) -> Dict[str, Any]:
    """
    Return the stored profile dict for user_id, or {} on failure.
    parent is the core object (or None).
    """
    try:
        users = _ensure_user_manager_from_parent(parent)
        if not users:
            return {}
        if hasattr(users, "get_profile"):
            return users.get_profile(user_id) or {}
        # fallback: try attribute access
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
        if hasattr(users, "set_profile_field"):
            users.set_profile_field(user_id, field, value)
            return True
        if hasattr(users, "set_profile_field_async") and callable(users.set_profile_field_async):
            # not awaited here; prefer synchronous API in this helper
            try:
                # attempt to call synchronously if possible
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
        # map to stored keys
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
def _parse_prestige_map(profile: Dict[str, Any]) -> Dict[str, int]:
    """
    Normalize a persisted prestige_map into a dict of { 'slug|stars': int }.
    """
    out: Dict[str, int] = {}
    try:
        pm = profile.get("prestige_map") or {}
        if isinstance(pm, dict):
            for k, v in pm.items():
                try:
                    out[k] = int(v) if v is not None else 0
                except Exception:
                    out[k] = 0
    except Exception:
        log.exception("_parse_prestige_map failed")
    return out


def compute_top5_from_profile(profile: Dict[str, Any]) -> Tuple[List[str], Optional[int], Optional[float]]:
    """
    Compute a Top 5 list and total prestige from a profile's persisted prestige_map.

    Returns:
      - top5_lines: list of formatted lines (already pretty-printed via format_top5_prestige_line)
      - total_prestige: sum of all prestige values (int) or None if no items
      - average_prestige: average prestige across items (float rounded to 2 decimals) or None
    """
    try:
        pm = _parse_prestige_map(profile)
        # normalize to list of (key, prestige) where prestige is int
        items = [(k, v) for k, v in pm.items() if isinstance(v, int)]
        if not items:
            return [], None, None

        # sort descending by prestige
        items.sort(key=lambda x: -x[1])

        # compute totals
        total = sum(v for _, v in items) if items else None
        average = (total / len(items)) if items else None
        average_rounded = round(average, 2) if average is not None else None

        # build top5 entries and format using format_top5_prestige_line when available
        top5 = items[:5]
        top5_lines: List[str] = []
        try:
            from mcoc.common.formatters import format_top5_prestige_line
            for i, (k, v) in enumerate(top5):
                # key format expected: "slug|stars"
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
                # champ_obj not available here (no cache), pass None
                line = format_top5_prestige_line(None, entry)
                # prepend numeric position for clarity
                top5_lines.append(f"{i+1}. {line}")
        except Exception:
            # fallback to simple textual lines if formatter not available or fails
            top5_lines = [f"{i+1}. {k.split('|')[0]} [{v}]" for i, (k, v) in enumerate(top5)]

        return top5_lines, total, average_rounded
    except Exception:
        log.exception("compute_top5_from_profile failed")
        return [], None, None



def compute_top5_from_roster(parent: Any, roster: List[Dict[str, Any]], profile: Dict[str, Any]) -> Tuple[List[str], Optional[int]]:
    """
    Given a roster (list of entry dicts) and profile (for persisted prestige_map),
    compute a Top 5 by resolving prestige via cache/index where possible.

    Returns (top5_lines, total_prestige).
    """
    try:
        cache = getattr(parent, "cache", None)
        prestige_map = profile.get("prestige_map", {}) if isinstance(profile, dict) else {}
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
                # fallback to cache.get_prestige_value if available
                if p is None and cache and hasattr(cache, "get_prestige_value"):
                    try:
                        # cache.get_prestige_value(slug, stars, rank, asc, sig)
                        p = cache.get_prestige_value(slug, int(e.get("rarity") or e.get("stars") or stars), int(e.get("rank") or 1), int(e.get("ascended") or 0), int(e.get("sig") or 0))
                    except Exception:
                        p = None
                name = slug
                if cache:
                    try:
                        cobj = cache.get_champion(slug)
                        if cobj:
                            name = cobj.get("name") or cobj.get("slug") or slug
                    except Exception:
                        pass
                entries.append({"name": name, "prestige": int(p) if isinstance(p, (int, float)) else 0})
            except Exception:
                continue
        # sort and compute top5
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

    Parameters:
      - parent: core object (used to access cache/users)
      - ctx_or_author: Context or author-like object used for branding (author/avatar) when building embeds
      - target_id: user id to display
      - viewer_id: id of the viewer (for permission checks); if None, permission checks are not enforced here
      - prefer_embed: if True, attempt to return a Embed; otherwise return text

    Returns:
      - (embed_or_none, text_fallback_or_none)
        * If an embed was built, embed_or_none is a Embed (or discord.Embed) and text_fallback_or_none is None.
        * If embed could not be built, embed_or_none is None and text_fallback_or_none is a string summary.
    Notes:
      - This function does not send messages; callers should send the returned embed/text via safe_send_ctx or ctx.send.
      - Permission checks (privacy) are attempted if the users manager exposes can_view_profile.
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
            # if privacy check fails and viewer != target, deny by default
            if viewer_id is not None and viewer_id != target_id:
                return None, "You do not have permission to view that profile."

        top5_lines = []
        total_prestige = None

        # fetch profile
        profile = {}
        try:
            profile = users.get_profile(target_id) or {}
        except Exception:
            profile = {}

        if not profile:
            return None, "No profile found for that user."

        # Manual embed construction (defensive)
        try:
            # prefer to use Embed.embed if available
            try:
                emb = CDTEmbed.embed(ctx_or_author, title="CollectorVerse Profile")
            except Exception:
                # fallback to constructing a Embed instance directly
                emb = CDTEmbed.embed(ctx_or_author, title=f"{profile.get('mcoc_name') or profile.get('display_name') or str(target_id)} — Profile")
            # Linked / ID
            linked = profile.get("linked", False)
            mcoc_id = profile.get("mcoc_id") or profile.get("mcoc_name") or None
            CDTEmbed.add_field(ctx_or_author, emb, name="Linked", value=str(bool(linked)), inline=True)
            CDTEmbed.add_field(ctx_or_author, emb, name="MCOC Username", value=str(mcoc_id) if mcoc_id else "Not linked", inline=True)

            # Top5 / prestige: prefer cached top5 in profile, else compute from prestige_map
            top5_lines, total_prestige = compute_top5_from_profile(profile)
            if not top5_lines:
                # try to load roster and compute from roster if users exposes list_roster
                roster = []
                try:
                    lr = getattr(users, "list_roster", None)
                    if lr:
                        if hasattr(lr, "__call__"):
                            # try sync first, then async
                            try:
                                roster = lr(target_id) or []
                            except TypeError:
                                # maybe coroutine
                                import asyncio as _asyncio
                                if _asyncio.iscoroutinefunction(lr):
                                    roster = _asyncio.get_event_loop().run_until_complete(lr(target_id)) or []
                                else:
                                    roster = []
                except Exception:
                    roster = []
                if roster:
                    top5_lines, total_prestige = compute_top5_from_roster(parent, roster, profile)

            if total_prestige is not None:
                CDTEmbed.add_field(ctx_or_author, emb, name="Prestige (sum)", value=str(total_prestige), inline=False)
            # Format Top 5 using prestige formatter
            formatted_top5 = []
            if top5_lines:
                try:
                    from mcoc.common.formatters import format_champion_prestige_line
                    cache = getattr(parent, "cache", None)

                    for line in top5_lines:
                        # line looks like "1. slug [prestige]"
                        try:
                            slug = line.split(". ", 1)[1].split(" [", 1)[0]
                        except Exception:
                            slug = line

                        champ_obj = None
                        if cache:
                            try:
                                champ_obj = cache.get_champion(slug)
                            except Exception:
                                champ_obj = None

                        entry = {
                            "champion": slug,
                            "rarity": 6,        # best guess; prestige_map doesn't store rarity
                            "rank": 1,
                            "sig": 0,
                            "ascended": 0,
                            "prestige": int(line.split("[")[-1].rstrip("]")) if "[" in line else 0,
                        }

                        formatted_top5.append(format_champion_prestige_line(champ_obj, entry))
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
                CDTEmbed.add_field(ctx_or_author, emb,name="Playing Since", value=_format_playing_since(started), inline=True)

            CDTEmbed.set_footer(ctx_or_author, emb, text="Profile generated by MCOC")
            return emb, None
        except Exception:
            log.exception("build_profile_display: embed construction failed")
            # fall through to text fallback

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


# -----------------------------
# Backwards-compatible exports
# -----------------------------
# Keep the same function names used by prefix code so migration is straightforward.
# Prefix code can call these helpers and then send the returned embed/text via safe_send_ctx.
__all__ = (
    "ALLOWED_PROFILE_FIELDS",
    "FIELD_CANONICAL",
    "validate_profile_field",
    "get_profile_settings",
    "get_profile",
    "set_profile_field",
    "delete_user_profile",
    "link_account",
    "unlink_account",
    "compute_top5_from_profile",
    "compute_top5_from_roster",
    "build_profile_display",
)
