# mcoc/prefix/account_prefix.py
import logging
from typing import Any, Optional

from redbot.core import commands

log = logging.getLogger("red.mcoc.prefix.account")

from ..common.roster_helpers import ensure_user_manager
from ..common.roster_helpers import _ensure_hook_registered  # safe no-op if already registered


class AccountPrefix(commands.Cog):
    """
    Prefix commands for user account/profile management.
    Commands:
      ///account view [@user]
      ///account set <field> <value>
      ///account delete
      ///account privacy mode <private|guild|alliance|public>
      ///account privacy allow_guild <guild_id>
      ///account privacy revoke_guild <guild_id>
    """

    def __init__(self, bot_or_parent: Any):
        # bot_or_parent may be the bot or the core object depending on how this cog is loaded
        if hasattr(bot_or_parent, "bot") and hasattr(bot_or_parent, "cache"):
            self.parent = bot_or_parent
            self.bot = bot_or_parent.bot
        else:
            self.parent = None
            self.bot = bot_or_parent

    async def _require_parent(self, ctx) -> bool:
        if not getattr(self, "parent", None):
            try:
                core = getattr(self.bot, "mcoc_core", None) or self.bot.get_cog("MCOC")
                if core:
                    self.parent = core
                    return True
            except Exception:
                pass
            try:
                await ctx.send("MCOC core not attached; account commands unavailable.")
            except Exception:
                pass
            return False
        return True

    @commands.group(name="account", invoke_without_command=True)
    async def account(self, ctx):
        await ctx.send("Account commands: view, set, delete, privacy")

    @account.command(name="view")
    async def account_view(self, ctx, member: Optional[Any] = None):
        """
        View a user's profile. If no member is provided, view your own.
        Respects privacy settings in UserDataManager.can_view_profile.
        """
        if not await self._require_parent(ctx):
            return

        users = ensure_user_manager(self.parent)
        _ensure_hook_registered(self.parent)

        target_id = ctx.author.id if member is None else getattr(member, "id", None) or member
        try:
            target_id = int(target_id)
        except Exception:
            await ctx.send("Invalid user specified.")
            return

        # privacy check
        guild_id = getattr(ctx.guild, "id", None)
        viewer_alliance = None
        try:
            # if your bot stores alliance membership per guild, you can resolve viewer_alliance here
            viewer_alliance = None
        except Exception:
            viewer_alliance = None

        try:
            if not users.can_view_profile(ctx.author.id, target_id, guild_id=guild_id, viewer_alliance=viewer_alliance):
                await ctx.send("You do not have permission to view that profile.")
                return
        except Exception:
            # fallback: allow viewing own profile only
            if ctx.author.id != target_id:
                await ctx.send("You do not have permission to view that profile.")
                return

        profile = users.get_profile(target_id)
        if not profile:
            await ctx.send("No profile found for that user.")
            return

        # Build a compact display
        lines = []
        for k in ("mcoc_name", "mcoc_id", "website", "invite", "timezone", "alliance", "job", "created_at", "updated_at"):
            v = profile.get(k)
            if v:
                lines.append(f"**{k}**: {v}")
        if not lines:
            await ctx.send("Profile is empty.")
            return

        try:
            import discord
            emb = discord.Embed(title=f"Profile for {member.display_name if member else ctx.author.display_name}", description="\n".join(lines))
            await ctx.send(embed=emb)
        except Exception:
            await ctx.send("\n".join(lines))

    @account.command(name="set")
    async def account_set(self, ctx, field: str, *, value: str):
        """
        Set a profile field. Allowed fields: mcoc_id, mcoc_name, website, invite, timezone, alliance, job
        Example: ///account set mcoc_name Jason
        """
        if not await self._require_parent(ctx):
            return

        allowed = {"mcoc_id", "mcoc_name", "website", "invite", "timezone", "alliance", "job"}
        if field not in allowed:
            await ctx.send(f"Invalid field. Allowed fields: {', '.join(sorted(allowed))}")
            return

        users = ensure_user_manager(self.parent)
        _ensure_hook_registered(self.parent)

        try:
            users.set_profile_field(ctx.author.id, field, value)
            await ctx.send(f"Set **{field}** to `{value}`.")
        except Exception:
            log.exception("Failed to set profile field")
            await ctx.send("Failed to update profile.")

    @account.command(name="delete")
    async def account_delete(self, ctx):
        """
        Delete your user data file. This is irreversible.
        """
        if not await self._require_parent(ctx):
            return

        users = ensure_user_manager(self.parent)
        _ensure_hook_registered(self.parent)

        # simple confirmation flow
        try:
            await ctx.send("Are you sure you want to delete your profile and roster? Reply with `yes` to confirm.")
            def _check(m):
                return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id
            try:
                msg = await self.bot.wait_for("message", check=_check, timeout=20.0)
                if msg.content.strip().lower() != "yes":
                    await ctx.send("Deletion cancelled.")
                    return
            except Exception:
                await ctx.send("No confirmation received; deletion cancelled.")
                return

            deleted = users.delete_user(ctx.author.id)
            if deleted:
                await ctx.send("Your profile and roster have been deleted.")
            else:
                await ctx.send("No profile file found to delete.")
        except Exception:
            log.exception("Failed to delete user data")
            await ctx.send("Failed to delete profile.")

    @account.group(name="privacy", invoke_without_command=True)
    async def account_privacy(self, ctx):
        await ctx.send("Privacy commands: mode, allow_guild, revoke_guild")

    @account_privacy.command(name="mode")
    async def privacy_mode(self, ctx, mode: str):
        """
        Set privacy mode: private | guild | alliance | public
        """
        if not await self._require_parent(ctx):
            return
        mode = mode.lower()
        try:
            users = ensure_user_manager(self.parent)
            users.set_privacy_mode(ctx.author.id, mode)
            await ctx.send(f"Privacy mode set to **{mode}**.")
        except ValueError:
            await ctx.send("Invalid privacy mode. Choose one of: private, guild, alliance, public.")
        except Exception:
            log.exception("Failed to set privacy mode")
            await ctx.send("Failed to update privacy settings.")

    @account_privacy.command(name="allow_guild")
    async def privacy_allow_guild(self, ctx, guild_id: int):
        """
        Allow sharing with a specific guild (by id).
        """
        if not await self._require_parent(ctx):
            return
        users = ensure_user_manager(self.parent)
        try:
            users.allow_guild(ctx.author.id, guild_id)
            await ctx.send(f"Allowed sharing with guild `{guild_id}`.")
        except Exception:
            log.exception("Failed to allow guild")
            await ctx.send("Failed to update privacy settings.")

    @account_privacy.command(name="revoke_guild")
    async def privacy_revoke_guild(self, ctx, guild_id: int):
        """
        Revoke sharing with a specific guild (by id).
        """
        if not await self._require_parent(ctx):
            return
        users = ensure_user_manager(self.parent)
        try:
            users.revoke_guild(ctx.author.id, guild_id)
            await ctx.send(f"Revoked sharing with guild `{guild_id}`.")
        except Exception:
            log.exception("Failed to revoke guild")
            await ctx.send("Failed to update privacy settings.")


# Optional: register these commands under another group (e.g., ///mcoc account)
def register_with_group(group: commands.Group, parent_getter):
    """
    Attach account prefix commands to the provided `group`.
    parent_getter is a callable returning the core/parent object (or None).
    """

    def _safe_add(cmd_name, func):
        try:
            if group.get_command(cmd_name):
                log.debug("Command %s already exists; skipping", cmd_name)
                return
        except Exception:
            pass
        group.command(name=cmd_name)(func)

    async def _view(ctx, member: Optional[Any] = None):
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; account unavailable.")
            return
        # reuse the cog logic by instantiating a temporary helper
        from ..common.roster_helpers import ensure_user_manager as _ensure
        users = _ensure(parent)
        try:
            profile = users.get_profile(ctx.author.id if member is None else getattr(member, "id", member))
            await ctx.send(f"Profile: ```json\n{profile}\n```")
        except Exception:
            await ctx.send("Failed to fetch profile.")

    _safe_add("view", _view)

    async def _set(ctx, field: str, *, value: str):
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; account unavailable.")
            return
        users = ensure_user_manager(parent)
        try:
            users.set_profile_field(ctx.author.id, field, value)
            await ctx.send(f"Set {field}.")
        except Exception:
            await ctx.send("Failed to set profile field.")

    _safe_add("set", _set)

    async def _delete(ctx):
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; account unavailable.")
            return
        users = ensure_user_manager(parent)
        try:
            users.delete_user(ctx.author.id)
            await ctx.send("Deleted your profile.")
        except Exception:
            await ctx.send("Failed to delete profile.")

    _safe_add("delete", _delete)
