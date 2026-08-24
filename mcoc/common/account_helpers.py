# mcoc/common/account_helpers.py
import logging
from typing import Dict, Any, Tuple, Optional

log = logging.getLogger("red.mcoc.account_helpers")

# Public metadata for profile fields (used by account_prefix help)
ALLOWED_PROFILE_FIELDS: Dict[str, str] = {
    "mcoc_name": "In-game player name",
    "mcoc_id": "In-game numeric id",
    "website": "Personal website or profile URL",
    "invite": "Alliance invite link or code",
    "timezone": "Timezone (e.g., America/Chicago)",
    "alliance": "Alliance name",
    "job": "Short job/role text",
}

def validate_profile_field(field: str) -> bool:
    """Return True if the field is allowed to be set by users."""
    return field in ALLOWED_PROFILE_FIELDS


def format_profile_embed(ctx, profile: Dict[str, Any], member_obj=None):
    """
    Build and return a discord.Embed for the profile.
    Signature matches usage in account_prefix: (ctx, profile, member_obj).
    Caller must handle exceptions if discord is not available.
    """
    import discord

    # Title selection
    title_name = None
    if member_obj and isinstance(member_obj, discord.Member):
        title_name = getattr(member_obj, "display_name", None)
    if not title_name:
        title_name = profile.get("mcoc_name") or profile.get("mcoc_id") or "User"

    lines = []
    if profile.get("linked"):
        lines.append("**linked**: True")
    if profile.get("mcoc_id"):
        lines.append(f"**mcoc_id**: {profile.get('mcoc_id')}")
    for k in ("mcoc_name", "website", "invite", "timezone", "alliance", "job", "created_at", "updated_at"):
        v = profile.get(k)
        if v:
            lines.append(f"**{k}**: {v}")

    emb = discord.Embed(title=f"Profile for {title_name}", description="\n".join(lines) or "Profile is empty.")
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
