# mcoc/prefix/account_prefix.py
import logging
from typing import Any, Optional, Callable, Dict

from redbot.core import commands

log = logging.getLogger("red.mcoc.prefix.account")

from ..common.champion_helpers import safe_send_ctx
from ..common.roster_helpers import ensure_user_manager
from ..common.roster_helpers import _ensure_hook_registered
from ..common.prefix_utils import get_runtime_prefix
from ..common.account_helpers import (
    ALLOWED_PROFILE_FIELDS,
    format_profile_embed,
    validate_profile_field,
    link_account as helper_link_account,
    unlink_account as helper_unlink_account,
    delete_user_profile as helper_delete_user_profile,
)

from ..common.pagination import PagesMenu

ACCOUNT_GROUP_HELP = "Account commands: info, view, set, link, unlink, delete, privacy, settings"


class AccountPrefix(commands.Cog):
    """
    Prefix commands for user account/profile management.
    """

    def __init__(self, bot_or_parent: Any):
        if hasattr(bot_or_parent, "bot") and hasattr(bot_or_parent, "cache"):
            self.parent = bot_or_parent
            self.bot = bot_or_parent.bot
        else:
            self.parent = None
            self.bot = bot_or_parent

        try:
            _ensure_hook_registered(self.parent)
        except Exception:
            pass

    async def _require_parent(self, ctx) -> bool:
        if not getattr(self, "parent", None):
            core = getattr(self.bot, "mcoc_core", None) or self.bot.get_cog("MCOC")
            if core:
                self.parent = core
                try:
                    _ensure_hook_registered(self.parent)
                except Exception:
                    pass
                return True
            await safe_send_ctx(ctx, "MCOC core not attached; account commands unavailable.")
            return False
        return True

    @commands.group(name="account", invoke_without_command=True)
    async def account(self, ctx):
        """Top-level account group help"""
        await safe_send_ctx(ctx, ACCOUNT_GROUP_HELP)

    @account.command(name="help")
    async def account_help(self, ctx):
        """Show account help and allowed fields"""
        prefix = get_runtime_prefix(ctx, default="///")
        lines = [
            ACCOUNT_GROUP_HELP,
            "",
            "**Fields you can set:**",
        ]
        for field, description in ALLOWED_PROFILE_FIELDS.items():
            # description may be a dict or string depending on your common helper
            if isinstance(description, dict):
                desc = description.get("desc", "")
            else:
                desc = str(description)
            lines.append(f"**{field}**: {desc}")
        lines.append("")
        lines.append(f"Use `{prefix}mcoc account set <field> <value>` to set a profile field.")
        lines.append(f"Use `{prefix}mcoc account link <mcoc_id>` to link your in-game id.")
        lines.append(f"Use `{prefix}mcoc account view [@member]` to view a profile.")
        lines.append(f"Use `{prefix}mcoc account settings` to list your saved settings.")
        await safe_send_ctx(ctx, "\n".join(lines))

    @account.command(name="info")
    async def account_info(self, ctx):
        """Show a short summary of your account and linked status."""
        if not await self._require_parent(ctx):
            return
        users = ensure_user_manager(self.parent)
        profile = users.get_profile(ctx.author.id) or {}
        linked = profile.get("linked", False)
        mcoc_id = profile.get("mcoc_id") or "Not linked"
        await safe_send_ctx(ctx, f"Account summary: linked={linked}, mcoc_id={mcoc_id}")

    @account.command(name="view")
    async def account_view(self, ctx, member: Optional[Any] = None):
        """View a user's profile. If no member is provided, view your own."""
        if not await self._require_parent(ctx):
            return

        users = ensure_user_manager(self.parent)
        _ensure_hook_registered(self.parent)

        # resolve target id
        try:
            target_id = ctx.author.id if member is None else getattr(member, "id", None) or int(member)
            target_id = int(target_id)
        except Exception:
            await safe_send_ctx(ctx, "Invalid user specified.")
            return

        guild_id = getattr(ctx.guild, "id", None)
        viewer_alliance = None
        try:
            # users.can_view_profile may raise or return False
            if not users.can_view_profile(ctx.author.id, target_id, guild_id=guild_id, viewer_alliance=viewer_alliance):
                await safe_send_ctx(ctx, "You do not have permission to view that profile.")
                return
        except Exception:
            if ctx.author.id != target_id:
                await safe_send_ctx(ctx, "You do not have permission to view that profile.")
                return

        profile = users.get_profile(target_id)
        if not profile:
            await safe_send_ctx(ctx, "No profile found for that user.")
            return

        # Prefer embed formatting if helper exists
        try:
            emb = format_profile_embed(ctx, profile, member)
            await ctx.send(embed=emb)
            return
        except Exception:
            # fallback to text
            lines = []
            if profile.get("linked"):
                lines.append("**linked**: True")
            if profile.get("mcoc_id"):
                lines.append(f"**mcoc_id**: {profile.get('mcoc_id')}")
            for k in ("mcoc_name", "website", "invite", "timezone", "alliance", "job", "created_at", "updated_at"):
                v = profile.get(k)
                if v:
                    lines.append(f"**{k}**: {v}")
            await safe_send_ctx(ctx, "\n".join(lines))

    @account.command(name="set")
    async def account_set(self, ctx, field: str, *, value: str):
        """Set a profile field. Example: ///mcoc account set mcoc_name Jason"""
        if not await self._require_parent(ctx):
            return

        if not validate_profile_field(field):
            allowed = ", ".join(sorted(ALLOWED_PROFILE_FIELDS.keys()))
            await safe_send_ctx(ctx, f"Invalid field. Allowed fields: {allowed}")
            return

        users = ensure_user_manager(self.parent)
        _ensure_hook_registered(self.parent)

        try:
            users.set_profile_field(ctx.author.id, field, value)
            await safe_send_ctx(ctx, f"Set **{field}** to `{value}`.")
        except Exception:
            log.exception("Failed to set profile field")
            await safe_send_ctx(ctx, "Failed to update profile.")

    @account.command(name="link")
    async def account_link(self, ctx, mcoc_id: Optional[str] = None):
        """Link your Discord account to an in-game account. Example: ///mcoc account link 123456789"""
        if not await self._require_parent(ctx):
            return

        if mcoc_id is None:
            prefix = get_runtime_prefix(ctx, default="///")
            await safe_send_ctx(ctx, f"Usage: `{prefix}mcoc account link <mcoc_id>`")
            return

        try:
            ok, msg = helper_link_account(self.parent, ctx.author.id, str(mcoc_id).strip())
            await safe_send_ctx(ctx, msg)
        except Exception:
            log.exception("Failed to link account")
            await safe_send_ctx(ctx, "Failed to link account. Try again later.")

    @account.command(name="unlink")
    async def account_unlink(self, ctx):
        """Unlink your in-game account from your Discord profile."""
        if not await self._require_parent(ctx):
            return

        try:
            ok, msg = helper_unlink_account(self.parent, ctx.author.id)
            await safe_send_ctx(ctx, msg)
        except Exception:
            log.exception("Failed to unlink account")
            await safe_send_ctx(ctx, "Failed to unlink account. Try again later.")

    @account.command(name="delete")
    async def account_delete(self, ctx):
        """Delete your user data file. This is irreversible."""
        if not await self._require_parent(ctx):
            return

        try:
            prompt = "Are you sure you want to delete your profile and roster? Reply with `yes` to confirm."
            confirmed, _ = await PagesMenu.confirm(self.bot, ctx, prompt, timeout=20.0)
            if not confirmed:
                await safe_send_ctx(ctx, "Deletion cancelled.")
                return

            ok, msg = helper_delete_user_profile(self.parent, ctx.author.id)
            await safe_send_ctx(ctx, msg)
        except Exception:
            log.exception("Failed to delete user data")
            await safe_send_ctx(ctx, "Failed to delete profile.")

    @account.command(name="settings")
    async def account_settings(self, ctx):
        """Show your current saved profile settings (editable fields)."""
        if not await self._require_parent(ctx):
            return
        users = ensure_user_manager(self.parent)
        try:
            profile = users.get_profile(ctx.author.id) or {}
            settings = {k: profile.get(k) for k in ALLOWED_PROFILE_FIELDS.keys()}
            await safe_send_ctx(ctx, f"Your settings: ```json\n{settings}\n```")
        except Exception:
            log.exception("Failed to fetch settings")
            await safe_send_ctx(ctx, "Failed to fetch settings.")

    @account.group(name="privacy", invoke_without_command=True)
    async def account_privacy(self, ctx):
        await safe_send_ctx(ctx, "Privacy commands: mode, allow_guild, revoke_guild")

    @account_privacy.command(name="mode")
    async def privacy_mode(self, ctx, mode: str):
        """Set privacy mode: private | guild | alliance | public"""
        if not await self._require_parent(ctx):
            return
        mode = mode.lower()
        try:
            users = ensure_user_manager(self.parent)
            users.set_privacy_mode(ctx.author.id, mode)
            await safe_send_ctx(ctx, f"Privacy mode set to **{mode}**.")
        except ValueError:
            await safe_send_ctx(ctx, "Invalid privacy mode. Choose one of: private, guild, alliance, public.")
        except Exception:
            log.exception("Failed to set privacy mode")
            await safe_send_ctx(ctx, "Failed to update privacy settings.")

    @account_privacy.command(name="allow_guild")
    async def privacy_allow_guild(self, ctx, guild_id: int):
        """Allow sharing with a specific guild (by id)."""
        if not await self._require_parent(ctx):
            return
        users = ensure_user_manager(self.parent)
        try:
            users.allow_guild(ctx.author.id, guild_id)
            await safe_send_ctx(ctx, f"Allowed sharing with guild `{guild_id}`.")
        except Exception:
            log.exception("Failed to allow guild")
            await safe_send_ctx(ctx, "Failed to update privacy settings.")

    @account_privacy.command(name="revoke_guild")
    async def privacy_revoke_guild(self, ctx, guild_id: int):
        """Revoke sharing with a specific guild (by id)."""
        if not await self._require_parent(ctx):
            return
        users = ensure_user_manager(self.parent)
        try:
            users.revoke_guild(ctx.author.id, guild_id)
            await safe_send_ctx(ctx, f"Revoked sharing with guild `{guild_id}`.")
        except Exception:
            log.exception("Failed to revoke guild")
            await safe_send_ctx(ctx, "Failed to update privacy settings.")


# -------------------------
# Registrar wrappers
# -------------------------
def register_with_group(group: commands.Group, parent_getter: Callable[[], Any]):
    """
    Attach account prefix commands to the provided `group`.
    parent_getter is a callable returning the core/parent object (or None).
    """

    def _safe_add(cmd_name: str):
        def _decorator(func):
            try:
                if group.get_command(cmd_name):
                    log.debug("Command %s already exists; skipping", cmd_name)
                    return func
            except Exception:
                pass
            group.command(name=cmd_name)(func)
            return func
        return _decorator

    # info alias for view
    @_safe_add("info")
    async def _info(ctx, member: Optional[Any] = None):
        parent = parent_getter()
        if not parent:
            await safe_send_ctx(ctx, "MCOC core not attached; account unavailable.")
            return
        users = ensure_user_manager(parent)
        try:
            target = ctx.author.id if member is None else getattr(member, "id", member)
            profile = users.get_profile(int(target)) or {}
            await safe_send_ctx(ctx, f"Profile: ```json\n{profile}\n```")
        except Exception:
            await safe_send_ctx(ctx, "Failed to fetch profile.")

    # view (alias)
    @_safe_add("view")
    async def _view(ctx, member: Optional[Any] = None):
        parent = parent_getter()
        if not parent:
            await safe_send_ctx(ctx, "MCOC core not attached; account unavailable.")
            return
        users = ensure_user_manager(parent)
        try:
            target_id = ctx.author.id if member is None else getattr(member, "id", member)
            profile = users.get_profile(int(target_id))
            if not profile:
                await safe_send_ctx(ctx, "No profile found.")
                return
            # redact based on privacy
            viewer_id = ctx.author.id
            if int(target_id) != viewer_id:
                mode = profile.get("privacy_mode", "private")
                if mode == "private":
                    public = {k: v for k, v in profile.items() if k in ("display_name", "roster_public")}
                    await safe_send_ctx(ctx, f"Profile (limited): ```json\n{public}\n```")
                    return
            await safe_send_ctx(ctx, f"Profile: ```json\n{profile}\n```")
        except Exception:
            await safe_send_ctx(ctx, "Failed to fetch profile.")

    @_safe_add("set")
    async def _set(ctx, field: str, *, value: str):
        """Set a profile field. Allowed: mcoc_id, display_name, roster_public, privacy_mode, notes."""
        parent = parent_getter()
        if not parent:
            await safe_send_ctx(ctx, "MCOC core not attached; account unavailable.")
            return
        field = field.strip()
        if field not in ALLOWED_PROFILE_FIELDS:
            await safe_send_ctx(ctx, "Invalid field. Allowed: " + ", ".join(sorted(ALLOWED_PROFILE_FIELDS.keys())))
            return
        # normalize booleans and enums
        if isinstance(ALLOWED_PROFILE_FIELDS[field], dict) and ALLOWED_PROFILE_FIELDS[field].get("type") == "bool":
            val = str(value).strip().lower() in ("1", "true", "yes", "on")
        elif field == "privacy_mode":
            val = str(value).strip().lower()
            if val not in ("private", "guild", "alliance", "public"):
                await safe_send_ctx(ctx, "Invalid privacy_mode. Allowed: private, guild, alliance, public.")
                return
        else:
            val = value.strip()
        users = ensure_user_manager(parent)
        try:
            users.set_profile_field(ctx.author.id, field, val)
            await safe_send_ctx(ctx, f"Set **{field}** to `{val}`.")
        except Exception:
            await safe_send_ctx(ctx, "Failed to set profile field.")

    @_safe_add("settings")
    async def _settings(ctx):
        """Show your current saved profile settings (editable fields)."""
        parent = parent_getter()
        if not parent:
            await safe_send_ctx(ctx, "MCOC core not attached; account unavailable.")
            return
        users = ensure_user_manager(parent)
        try:
            profile = users.get_profile(ctx.author.id) or {}
            settings = {k: profile.get(k) for k in ALLOWED_PROFILE_FIELDS.keys()}
            await safe_send_ctx(ctx, f"Your settings: ```json\n{settings}\n```")
        except Exception:
            await safe_send_ctx(ctx, "Failed to fetch settings.")

    @_safe_add("link")
    async def _link(ctx, mcoc_id: Optional[str] = None):
        parent = parent_getter()
        if not parent:
            await safe_send_ctx(ctx, "MCOC core not attached; account unavailable.")
            return
        if mcoc_id is None:
            prefix = getattr(ctx, "prefix", None) or "///"
            await safe_send_ctx(ctx, f"Usage: {prefix}mcoc account link <mcoc_id>")
            return
        users = ensure_user_manager(parent)
        try:
            users.set_profile_field(ctx.author.id, "mcoc_id", str(mcoc_id).strip())
            users.set_profile_field(ctx.author.id, "linked", True)
            await safe_send_ctx(ctx, f"Linked your account to MCoc id `{mcoc_id}`.")
        except Exception:
            await safe_send_ctx(ctx, "Failed to link account.")

    @_safe_add("unlink")
    async def _unlink(ctx):
        parent = parent_getter()
        if not parent:
            await safe_send_ctx(ctx, "MCOC core not attached; account unavailable.")
            return
        users = ensure_user_manager(parent)
        try:
            users.set_profile_field(ctx.author.id, "mcoc_id", None)
            users.set_profile_field(ctx.author.id, "linked", False)
            await safe_send_ctx(ctx, "Unlinked your account.")
        except Exception:
            await safe_send_ctx(ctx, "Failed to unlink account.")

    @_safe_add("delete")
    async def _delete(ctx):
        parent = parent_getter()
        if not parent:
            await safe_send_ctx(ctx, "MCOC core not attached; account unavailable.")
            return
        users = ensure_user_manager(parent)
        try:
            prompt = "Are you sure you want to delete your profile and roster? Reply with `yes` to confirm."
            confirmed, _ = await PagesMenu.confirm(ctx.bot, ctx, prompt, timeout=20.0)
            if not confirmed:
                await safe_send_ctx(ctx, "Deletion cancelled.")
                return
            users.delete_user(ctx.author.id)
            await safe_send_ctx(ctx, "Deleted your profile.")
        except Exception:
            await safe_send_ctx(ctx, "Failed to delete profile.")

    @_safe_add("privacy")
    async def _privacy_group(ctx):
        await safe_send_ctx(ctx, "Privacy commands: mode, allow_guild, revoke_guild")

    @_safe_add("privacy mode")
    async def _privacy_mode(ctx, mode: str):
        parent = parent_getter()
        if not parent:
            await safe_send_ctx(ctx, "MCOC core not attached; account unavailable.")
            return
        users = ensure_user_manager(parent)
        try:
            users.set_privacy_mode(ctx.author.id, mode)
            await safe_send_ctx(ctx, f"Set privacy mode to `{mode}`.")
        except Exception:
            await safe_send_ctx(ctx, "Failed to update privacy settings.")

    @_safe_add("privacy allow_guild")
    async def _privacy_allow(ctx, guild_id: int):
        parent = parent_getter()
        if not parent:
            await safe_send_ctx(ctx, "MCOC core not attached; account unavailable.")
            return
        users = ensure_user_manager(parent)
        try:
            users.allow_guild(ctx.author.id, guild_id)
            await safe_send_ctx(ctx, f"Allowed sharing with guild `{guild_id}`.")
        except Exception:
            await safe_send_ctx(ctx, "Failed to update privacy settings.")

    @_safe_add("privacy revoke_guild")
    async def _privacy_revoke(ctx, guild_id: int):
        parent = parent_getter()
        if not parent:
            await safe_send_ctx(ctx, "MCOC core not attached; account unavailable.")
            return
        users = ensure_user_manager(parent)
        try:
            users.revoke_guild(ctx.author.id, guild_id)
            await safe_send_ctx(ctx, f"Revoked sharing with guild `{guild_id}`.")
        except Exception:
            await safe_send_ctx(ctx, "Failed to update privacy settings.")

    log.debug("Account registrar attached to group")
