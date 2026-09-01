# mcoc/common/account.py
"""
Sanitized account helpers.

Provides:
  - profile field metadata
  - safe wrappers around the UserDataManager
  - top5/prestige computation (uses cache when available)
  - profile display builder (embed + text fallback)
  - enrollment/consent flow (CDTConfirm when available)
  - thin command helpers used by prefix handlers:
      user_has_consented(parent, user_id)
      enroll_command_handler(parent, ctx, user_id)
      handle_consent_response(parent, ctx, user_id, agree)
"""

from typing import Any, Dict, Optional, Tuple, List, Union
import logging
import datetime
import re
import asyncio

from mcoc.common.componentsV2 import CDTEmbed, CDTConfirm

# prefer the module-level userdata manager; fallback to parent-provided manager
from mcoc.common import userdata as userdata_module

# formatter helpers (used to render top5 lines)
from mcoc.common import formatters as formatters_module

# champion helpers (best-effort import)
try:
    from mcoc.common.types import Champion, champion_from_dict
except Exception:
    Champion = Any  # type: ignore
    def champion_from_dict(d: Any) -> Any:  # type: ignore
        return d

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
    "consent": {"type": "bool", "desc": "User consented to privacy policy"},
    "consent_ts": {"type": "str", "desc": "Consent timestamp (ISO date)"},
    "consent_version": {"type": "str", "desc": "Policy version at consent"},
    "consent_source": {"type": "str", "desc": "Policy source URL"},
}

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

# Policy metadata
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

# -----------------------------
# Basic helpers
# -----------------------------
def validate_profile_field(field: str) -> bool:
    if not field:
        return False
    key = field.strip()
    return key in FIELD_CANONICAL.keys() or key in set(FIELD_CANONICAL.values())


def get_profile_settings(profile: Dict[str, Any]) -> Dict[str, Any]:
    return {user_field: profile.get(stored_key) for user_field, stored_key in FIELD_CANONICAL.items()}


def _format_playing_since(iso_date_str: Optional[str]) -> str:
    if not iso_date_str:
        return "Not set"
    s = str(iso_date_str).strip()
    now = datetime.datetime.now().date()
    log.debug("Parsing playing since date: %s", s)
    dt = None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            dt = datetime.datetime.strptime(s, fmt)
            break
        except Exception:
            continue
    if dt is None:
        m = re.match(r"^\s*(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2,6})\s*$", s)
        if m:
            mm, dd, yy = m.group(1), m.group(2), m.group(3)
            try:
                if len(yy) == 2:
                    yint = int(yy)
                    yyyy = 2000 + yint if yint <= 29 else 1900 + yint
                else:
                    yyyy = int(yy)
                dt = datetime.datetime(yyyy, int(mm), int(dd))
            except Exception:
                dt = None
    if dt is None:
        try:
            if len(s) == 10 and s.count("-") == 2:
                d = datetime.date.fromisoformat(s)
                dt = datetime.datetime.combine(d, datetime.time.min)
            else:
                dt = datetime.datetime.fromisoformat(s)
        except Exception:
            dt = None
    if dt is None:
        log.warning("Failed to parse playing since date: %s", s)
        return s
    dt_date = dt.date()
    days = (now - dt_date).days
    pretty = dt_date.strftime("%b %d, %Y")
    return f"{pretty} - {days:,} days"


# -----------------------------
# UserDataManager wrappers
# -----------------------------
def _ensure_user_manager_from_parent(parent: Any):
    """
    Resolve a UserDataManager instance from parent/core or fallback to module-level manager.
    """
    try:
        if parent is not None:
            mgr = getattr(parent, "users", None) or getattr(parent, "user_manager", None)
            if mgr:
                return mgr
    except Exception:
        log.debug("_ensure_user_manager_from_parent: parent lookup failed", exc_info=True)
    try:
        return userdata_module.get_user_manager()
    except Exception:
        log.exception("_ensure_user_manager_from_parent: userdata.get_user_manager failed")
        return None


def get_profile(parent: Any, user_id: int) -> Dict[str, Any]:
    raw = {}
    try:
        users = _ensure_user_manager_from_parent(parent)
        if not users:
            return {}
        raw = users.get_profile(user_id) or {}
    except Exception:
        log.exception("get_profile failed for %s", user_id)
        return {}
    # If userdata manager returned full userdata, extract profile
    if isinstance(raw, dict) and "profile" in raw and isinstance(raw.get("profile"), dict):
        return raw.get("profile", {})
    return raw



def set_profile_field(parent: Any, user_id: int, field: str, value: Any) -> bool:
    try:
        users = _ensure_user_manager_from_parent(parent)
        if not users:
            log.debug("set_profile_field: no user manager available")
            return False
        # Normalize 'started' conservatively
        if field == "started" and value is not None:
            try:
                if isinstance(value, str) and len(value) == 10 and value.count("-") == 2:
                    # keep as-is if already ISO-like
                    pass
            except Exception:
                pass
        if hasattr(users, "set_profile_field"):
            users.set_profile_field(user_id, field, value)
            log.info("set_profile_field: user=%s field=%s value=%r", user_id, field, value)
            return True
        if hasattr(users, "set_profile_field_async") and callable(users.set_profile_field_async):
            try:
                users.set_profile_field_async(user_id, field, value)
                log.info("set_profile_field_async scheduled: user=%s field=%s", user_id, field)
                return True
            except Exception:
                log.exception("set_profile_field_async failed for %s field=%s", user_id, field)
                return False
        log.debug("set_profile_field: user manager lacks set_profile_field API")
        return False
    except Exception:
        log.exception("set_profile_field failed for %s field=%s", user_id, field)
        return False


def persist_profile(parent: Any, user_id: int, profile: Dict[str, Any]) -> bool:
    try:
        users = _ensure_user_manager_from_parent(parent)
        if not users:
            return False
        if hasattr(users, "set_profile"):
            try:
                users.set_profile(user_id, profile)
                log.info("persist_profile: bulk set_profile for user=%s", user_id)
                return True
            except Exception:
                log.debug("persist_profile: users.set_profile failed", exc_info=True)
        for k, v in (profile or {}).items():
            try:
                users.set_profile_field(user_id, k, v)
            except Exception:
                log.debug("persist_profile: failed to set field %s for user %s", k, user_id, exc_info=True)
        log.info("persist_profile: per-field write completed for user=%s", user_id)
        return True
    except Exception:
        log.exception("persist_profile failed for %s", user_id)
        return False


def delete_user_profile(parent: Any, user_id: int) -> Tuple[bool, str]:
    try:
        users = _ensure_user_manager_from_parent(parent)
        if not users:
            return False, "User manager not available; cannot delete now."
        if hasattr(users, "delete_user"):
            deleted = users.delete_user(user_id)
            if deleted:
                log.info("delete_user_profile: deleted user=%s", user_id)
                return True, "Your profile and roster have been deleted."
            log.info("delete_user_profile: no file to delete for user=%s", user_id)
            return False, "No profile file found to delete."
        return False, "User manager does not support deletion."
    except Exception:
        log.exception("delete_user_profile failed for %s", user_id)
        return False, "Failed to delete profile."


# -----------------------------
# Link / unlink helpers
# -----------------------------
def link_account(parent: Any, user_id: int, mcoc_id: str) -> Tuple[bool, str]:
    try:
        ok = set_profile_field(parent, user_id, "mcoc_id", str(mcoc_id).strip())
        if ok:
            set_profile_field(parent, user_id, "linked", True)
            log.info("link_account: user=%s mcoc_id=%s", user_id, mcoc_id)
            return True, f"Linked your account to MCOC id `{mcoc_id}`."
        return False, "Failed to link account."
    except Exception:
        log.exception("link_account failed for %s", user_id)
        return False, "Failed to link account."


def unlink_account(parent: Any, user_id: int) -> Tuple[bool, str]:
    try:
        set_profile_field(parent, user_id, "mcoc_id", None)
        set_profile_field(parent, user_id, "linked", False)
        log.info("unlink_account: user=%s", user_id)
        return True, "Your MCOC account has been unlinked."
    except Exception:
        log.exception("unlink_account failed for %s", user_id)
        return False, "Failed to unlink account."


# -----------------------------
# Prestige / Top5 computation
# -----------------------------
def _normalize_prestige_value(raw: Any) -> int:
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


def _parse_prestige_map(profile: Union[Dict[str, Any], Any]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    try:
        pm = {}
        if isinstance(profile, dict):
            pm = profile.get("prestige_map") or {}
        else:
            pm = getattr(profile, "prestige_map", {}) or {}
        if isinstance(pm, dict):
            for k, v in pm.items():
                try:
                    out[k] = _normalize_prestige_value(v)
                except Exception:
                    out[k] = 0
    except Exception:
        log.exception("_parse_prestige_map failed")
    return out


def compute_top5_from_profile(profile: Union[Dict[str, Any], Any]) -> Tuple[List[str], Optional[int], Optional[float]]:
    try:
        pm = _parse_prestige_map(profile)
        items = [(k, v) for k, v in pm.items() if isinstance(v, int)]
        if not items:
            log.debug("compute_top5_from_profile: no prestige items")
            return [], None, None
        items.sort(key=lambda x: -x[1])
        total = sum(v for _, v in items) if items else None
        average = (total / len(items)) if items else None
        avg_rounded = round(average, 2) if average is not None else None
        top5 = items[:5]
        lines: List[str] = []
        for i, (k, v) in enumerate(top5):
            try:
                slug, stars = str(k).split("|", 1)
            except Exception:
                slug = str(k)
            prestige_val = int(v) if isinstance(v, (int, float)) else 0
            lines.append(f"{i+1}. {slug} [{prestige_val}]")
        log.debug("compute_top5_from_profile: top5=%s total=%s avg=%s", lines, total, avg_rounded)
        return lines, total, avg_rounded
    except Exception:
        log.exception("compute_top5_from_profile failed")
        return [], None, None


def compute_top5_from_roster(parent: Any, roster: List[Dict[str, Any]], profile: Union[Dict[str, Any], Any]) -> Tuple[List[str], Optional[int]]:
    try:
        cache = getattr(parent, "cache", None)
        prestige_map = {}
        if isinstance(profile, dict):
            prestige_map = profile.get("prestige_map", {}) or {}
        else:
            prestige_map = getattr(profile, "prestige_map", {}) or {}
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
                        if hasattr(cache, "get_champion_obj"):
                            cobj = cache.get_champion_obj(slug)
                            if cobj:
                                name = getattr(cobj, "name", None) or getattr(cobj, "slug", slug)
                        else:
                            raw = cache.get_champion(slug)
                            if raw and isinstance(raw, dict):
                                name = raw.get("name") or raw.get("slug") or slug
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

        profile = {}
        try:
            profile = users.get_profile(target_id) or {}
        except Exception:
            profile = {}

        if not profile:
            return None, "No profile found for that user."

        # Build embed
        try:
            emb = CDTEmbed.embed(ctx_or_author, title="CollectorVerse Profile")
            linked = profile.get("linked", False)
            mcoc_id = profile.get("mcoc_id") or profile.get("mcoc_name") or None
            CDTEmbed.add_field(ctx_or_author, emb, name="Linked", value=str(bool(linked)), inline=True)
            CDTEmbed.add_field(ctx_or_author, emb, name="MCOC Username", value=str(mcoc_id) if mcoc_id else "Not linked", inline=True)

            # Top5: prefer cached top5 in profile, else compute
            top5_lines, total_prestige, _avg = compute_top5_from_profile(profile)
            if not top5_lines:
                roster = []
                try:
                    lr = getattr(users, "list_roster", None)
                    if lr:
                        roster = lr(target_id) if not asyncio.iscoroutinefunction(lr) else asyncio.get_event_loop().run_until_complete(lr(target_id))
                except Exception:
                    roster = []
                if roster:
                    top5_lines, total_prestige = compute_top5_from_roster(parent, roster, profile)

            if total_prestige is not None:
                CDTEmbed.add_field(ctx_or_author, emb, name="Prestige (sum)", value=str(total_prestige), inline=False)

            # Format Top 5 using formatter and cache
            formatted_top5: List[str] = []
            if top5_lines:
                try:
                    fmt = formatters_module.format_top5_prestige_line
                    cache = getattr(parent, "cache", None)
                    for line in top5_lines:
                        # detect already formatted lines
                        if "]" in line and any(e in line for e in ("★", "<:", "🧬", "🛡️")):
                            formatted_top5.append(line.split(". ", 1)[1])
                            continue
                        try:
                            slug = line.split(". ", 1)[1].split(" [", 1)[0]
                            prestige_val = 0
                            if "[" in line:
                                prestige_val = int(line.split("[")[-1].rstrip("]"))
                        except Exception:
                            slug = line
                            prestige_val = 0

                        champ_obj = None
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
                        formatted_top5.append(fmt(champ_obj, entry))
                except Exception:
                    log.exception("build_profile_display: formatting top5 failed; falling back to raw lines")
                    formatted_top5 = [l.split(". ", 1)[1] if ". " in l else l for l in top5_lines]
            else:
                formatted_top5 = ["No roster or prestige data available."]

            CDTEmbed.add_field(ctx_or_author, emb, name="Top 5 Champions", value="\n".join(formatted_top5), inline=False)

            # other fields
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

            # Consent metadata
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
            lines.append(f"MCOC ID: {mcoc_id or 'Not linked'}")
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
# Enrollment / Consent flow
# ----------------------------
def user_has_consented(parent: Any, user_id: int) -> bool:
    try:
        profile = get_profile(parent, user_id) or {}
        consent = profile.get("consent")
        return bool(consent)
    except Exception:
        log.exception("user_has_consented check failed for %s", user_id)
        return False


def _record_consent(parent: Any, user_id: int, *, version: str, source: str) -> bool:
    try:
        ts = datetime.datetime.utcnow().isoformat()
        ok1 = set_profile_field(parent, user_id, "consent", True)
        ok2 = set_profile_field(parent, user_id, "consent_ts", ts)
        ok3 = set_profile_field(parent, user_id, "consent_version", version)
        ok4 = set_profile_field(parent, user_id, "consent_source", source)
        ok = bool(ok1 and ok2 and ok3 and ok4)
        log.info("consent:recorded user=%s ok=%s version=%s source=%s", user_id, ok, version, source)
        return ok
    except Exception:
        log.exception("_record_consent failed for %s", user_id)
        return False
# --- add near the bottom of mcoc/common/account.py ---

def user_has_consented(parent: Any, user_id: int) -> bool:
    """
    Return True if the stored profile indicates consent.
    Defensive: handles both module-level userdata shape and plain profile dict.
    """
    try:
        profile = get_profile(parent, user_id) or {}
        # If get_profile returned a full userdata dict, extract 'profile'
        if isinstance(profile, dict) and "profile" in profile and isinstance(profile.get("profile"), dict):
            profile = profile.get("profile", {})
        consent = profile.get("consent")
        log.info("user_has_consented: user=%s consent=%s", user_id, bool(consent))
        return bool(consent)
    except Exception:
        log.exception("user_has_consented check failed for %s", user_id)
        return False


async def enroll_command_handler(parent: Any, ctx: Any, user_id: int) -> Tuple[bool, str]:
    """
    Start an enrollment/consent prompt. Returns (ok, message).
    Uses CDTConfirm when available; falls back to DM text prompt.
    """
    try:
        version = POLICY_METADATA["privacy_policy"]["version"]
        source = POLICY_METADATA["privacy_policy"]["url"]
        prompt_text = (
            "To enroll, please review our policies:\n"
            f"Privacy Policy: {source}\n"
            f"Terms of Service: {POLICY_METADATA['terms_of_service']['url']}\n\n"
            "If you agree, type: ///account agree\n"
            "If you decline, type: ///account decline\n"
        )

        # Try CDTConfirm if available
        try:
            view = CDTConfirm(timeout=60.0, confirm_label="Agree", cancel_label="Decline")
            dm = None
            try:
                dm = await ctx.author.create_dm()
            except Exception:
                dm = None
            send_target = dm or ctx
            await send_target.send(prompt_text, view=view)
            log.info("consent:prompt_shown user=%s via=%s (CDTConfirm)", user_id, "DM" if dm else "channel")

            async def _wait_and_record():
                try:
                    res = await view.wait_result()
                    if res is True:
                        ok = _record_consent(parent, user_id, version=version, source=source)
                        log.info("consent:accepted user=%s ok=%s", user_id, ok)
                    elif res is False:
                        set_profile_field(parent, user_id, "consent", False)
                        set_profile_field(parent, user_id, "consent_ts", datetime.datetime.utcnow().isoformat())
                        log.info("consent:declined user=%s", user_id)
                except Exception:
                    log.exception("enroll_command_handler: error waiting for CDTConfirm result for user=%s", user_id)

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(_wait_and_record())
            except RuntimeError:
                asyncio.ensure_future(_wait_and_record())

            return True, "Enrollment prompt sent."
        except Exception:
            log.debug("CDTConfirm not available; falling back to text prompt", exc_info=True)

        # Fallback: plain text DM or channel
        try:
            dm = None
            try:
                dm = await ctx.author.create_dm()
            except Exception:
                dm = None
            send_target = dm or ctx
            await send_target.send(prompt_text)
            log.info("consent:prompt_shown user=%s via=%s (text)", user_id, "DM" if dm else "channel")
            return True, "Enrollment prompt sent."
        except Exception:
            log.exception("enroll_command_handler: failed to send prompt to user=%s", user_id)
            return False, "Failed to send enrollment prompt."
    except Exception:
        log.exception("enroll_command_handler unexpected error for user=%s", user_id)
        return False, "Failed to start enrollment."


async def handle_consent_response(parent: Any, ctx: Any, user_id: int, agree: bool) -> Tuple[bool, str]:
    """
    Record a typed consent response (///account agree or ///account decline).
    """
    try:
        version = POLICY_METADATA["privacy_policy"]["version"]
        source = POLICY_METADATA["privacy_policy"]["url"]
        if agree:
            ok = _record_consent(parent, user_id, version=version, source=source)
            if ok:
                return True, "Consent recorded. Thank you."
            return False, "Failed to record consent."
        else:
            # record explicit decline
            set_profile_field(parent, user_id, "consent", False)
            set_profile_field(parent, user_id, "consent_ts", datetime.datetime.utcnow().isoformat())
            log.info("consent:declined user=%s", user_id)
            return True, "Decline recorded."
    except Exception:
        log.exception("handle_consent_response failed for %s", user_id)
        return False, "Failed to record consent response."


async def enroll_command_handler(parent: Any, ctx: Any, user_id: int) -> Tuple[bool, str]:
    """
    Start an enrollment/consent prompt.

    Returns (ok, message) where ok indicates whether the prompt was delivered.
    """
    try:
        version = POLICY_METADATA["privacy_policy"]["version"]
        source = POLICY_METADATA["privacy_policy"]["url"]
        prompt_text = (
            "To enroll, please review our policies:\n"
            f"Privacy Policy: {source}\n"
            f"Terms of Service: {POLICY_METADATA['terms_of_service']['url']}\n\n"
            "If you agree, type: ///account agree\n"
            "If you decline, type: ///account decline\n"
            "This prompt will time out after a short period."
        )

        # Try to use CDTConfirm if available
        try:
            view = CDTConfirm(timeout=60.0, confirm_label="Agree", cancel_label="Decline")
            # prefer DM
            dm = None
            try:
                dm = await ctx.author.create_dm()
            except Exception:
                dm = None
            send_target = dm or ctx
            try:
                await send_target.send(prompt_text, view=view)
                log.info("consent:prompt_shown user=%s via=%s (CDTConfirm)", user_id, "DM" if dm else "channel")
                async def _wait_and_record():
                    try:
                        res = await view.wait_result()
                        if res is True:
                            ok = _record_consent(parent, user_id, version=version, source=source)
                            log.info("consent:accepted user=%s version=%s ok=%s", user_id, version, ok)
                        elif res is False:
                            set_profile_field(parent, user_id, "consent", False)
                            set_profile_field(parent, user_id, "consent_ts", datetime.datetime.utcnow().isoformat())
                            log.info("consent:declined user=%s", user_id)
                    except Exception:
                        log.exception("enroll_command_handler: error waiting for CDTConfirm result for user=%s", user_id)
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(_wait_and_record())
                except RuntimeError:
                    asyncio.ensure_future(_wait_and_record())
                return True, "Enrollment prompt sent."
            except Exception:
                log.debug("CDTConfirm send failed; falling back to text DM", exc_info=True)
        except Exception:
            log.debug("CDTConfirm not available; falling back to text prompt", exc_info=True)

        # Fallback: plain text DM or channel
        try:
            dm = None
            try:
                dm = await ctx.author.create_dm()
            except Exception:
                dm = None
            send_target = dm or ctx
            await send_target.send(prompt_text)
            log.info("consent:prompt_shown user=%s via=%s (text)", user_id, "DM" if dm else "channel")
            return True, "Enrollment prompt sent."
        except Exception:
            log.exception("enroll_command_handler: failed to send prompt to user=%s", user_id)
            return False, "Failed to send enrollment prompt."
    except Exception:
        log.exception("enroll_command_handler unexpected error for user=%s", user_id)
        return False, "Failed to start enrollment."


async def handle_consent_response(parent: Any, ctx: Any, user_id: int, agree: bool) -> Tuple[bool, str]:
    """
    Record a typed consent response (///account agree or decline).
    """
    try:
        version = POLICY_METADATA["privacy_policy"]["version"]
        source = POLICY_METADATA["privacy_policy"]["url"]
        if agree:
            ok = _record_consent(parent, user_id, version=version, source=source)
            if ok:
                log.info("consent:recorded user=%s method=typed ok=True version=%s source=%s", user_id, version, source)
                return True, "Thank you — your consent has been recorded."
            else:
                log.warning("consent:recorded failed for user=%s", user_id)
                return False, "Failed to record consent. Try again later."
        else:
            set_profile_field(parent, user_id, "consent", False)
            set_profile_field(parent, user_id, "consent_ts", datetime.datetime.utcnow().isoformat())
            log.info("consent:declined user=%s", user_id)
            return True, "You have declined enrollment. Your profile remains private."
    except Exception:
        log.exception("handle_consent_response failed for %s", user_id)
        return False, "Failed to record your response."
