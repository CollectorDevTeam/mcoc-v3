# mcoc/prefix/account_prefix.py
import logging
from typing import Any, Optional

from redbot.core import commands

log = logging.getLogger("red.mcoc.prefix.account")

from ..common.roster_helpers import ensure_user_manager
from ..common.roster_helpers import _ensure_hook_registered  # safe no-op if already registered
from ..common.prefix_utils import get_runtime_prefix
from ..common.prefix_meta import ALLOWED_PROFILE_FIELDS, ACCOUNT_GROUP_HELP


class AccountPrefix(commands.Cog):
    """
    Prefix commands for user account/profile management.
    Commands:
      ///mcoc account info [@user]
      ///mcoc account set <field> <value>
      ///mcoc account link <mcoc_id>
      ///mcoc account unlink
      ///mcoc account delete
      ///mcoc account privacy ...
    """

    def __init__(self, bot_or_parent: Any):
        # bot_or_parent may be the bot or the core object depending on how this cog is loaded
        if hasattr(bot_or_parent, "bot") and hasattr(bot_or_parent, "cache"):
            self.parent = bot_or_parent
            self.bot = bot_or_parent.bot
        else:
            self.parent = None
            self.bot = bot_or_parent

        # ensure hook registration early (no-op if parent is None)
        try:
            _ensure_hook_registered(self.parent)
        except Exception:
            pass

        # keep a cached user manager reference for convenience
        try:
            self.user_manager = ensure_user_manager(self.parent)
        except Exception:
            self.user_manager = None

    async def _require_parent(self, ctx) -> bool:
        if not getattr(self, "parent", None):
            try:
                core = getattr(self.bot, "mcoc_core", None) or self.bot.get_cog("MCOC")
                if core:
                    self.parent = core
                    # re-resolve user manager and register hook
                    try:
                        _ensure_hook_registered(self.parent)
                        self.user_manager = ensure_user_manager(self.parent)
                    except Exception:
                        pass
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
        """Top-level account group help"""
        await ctx.send(ACCOUNT_GROUP_HELP.get("account", "Account commands: info, set, link, unlink, delete, privacy"))

    @account.command(name="help")
    async def account_help(self, ctx):
        """Show account help and allowed fields"""
        # prefer the runtime prefix from ctx if available; fall back to self.prefix
        prefix = get_runtime_prefix(ctx, default=self.prefix or "///")
        lines = [ACCOUNT_GROUP_HELP.get("account", "Account commands: info, set, link, unlink, delete, privacy"), "", "**Fields you can set:**"]
        for field, description in ALLOWED_PROFILE_FIELDS.items():
            lines.append(f"**{field}**: {description}")
        lines.append("")
        lines.append(f"Use `{prefix}mcoc account set <field> <value>` to set a profile field.")
        lines.append(f"Use `{prefix}mcoc account link <mcoc_id>` to link your in-game id.")
        await ctx.send("\n".join(lines))

    @account.command(name="info")
    async def account_info(self, ctx, member: Optional[Any] = None):
        """Alias for account view"""
        await self.account_view(ctx, member)

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
        # include linked status and mcoc_id first if present
        if profile.get("linked"):
            lines.append("**linked**: True")
        if profile.get("mcoc_id"):
            lines.append(f"**mcoc_id**: {profile.get('mcoc_id')}")

        for k in ("mcoc_name", "website", "invite", "timezone", "alliance", "job", "created_at", "updated_at"):
            v = profile.get(k)
            if v:
                lines.append(f"**{k}**: {v}")
        if not lines:
            await ctx.send("Profile is empty.")
            return

        try:
            import discord
            # prefer the provided member object for a friendly display name when available
            member_obj = None
            if isinstance(member, discord.Member):
                member_obj = member
            else:
                try:
                    member_obj = ctx.guild.get_member(target_id) if ctx.guild else None
                except Exception:
                    member_obj = None

            if member_obj:
                title_name = getattr(member_obj, "display_name", str(target_id))
            else:
                if target_id == ctx.author.id:
                    title_name = getattr(ctx.author, "display_name", str(target_id))
                else:
                    title_name = str(target_id)

            emb = discord.Embed(title=f"Profile for {title_name}", description="\n".join(lines))
            await ctx.send(embed=emb)
        except Exception:
            await ctx.send("\n".join(lines))

    @account.command(name="set")
    async def account_set(self, ctx, field: str, *, value: str):
        """
        Set a profile field.
        Allowed fields are provided by the bot's account metadata.
        Example: ///mcoc account set mcoc_name Jason
        """
        if not await self._require_parent(ctx):
            return

        # validate against central metadata
        if field not in ALLOWED_PROFILE_FIELDS:
            allowed = ", ".join(sorted(ALLOWED_PROFILE_FIELDS.keys()))
            await ctx.send(f"Invalid field. Allowed fields: {allowed}")
            return

        users = ensure_user_manager(self.parent)
        _ensure_hook_registered(self.parent)

        try:
            users.set_profile_field(ctx.author.id, field, value)
            await ctx.send(f"Set **{field}** to `{value}`.")
        except Exception:
            log.exception("Failed to set profile field")
            await ctx.send("Failed to update profile.")

    @account.command(name="link")
    async def account_link(self, ctx, mcoc_id: Optional[str] = None):
        """
        Link your Discord account to an in-game account.
        Simple flow: provide your in-game id (mcoc_id) and it will be stored.
        Example: ///mcoc account link 123456789
        """
        if not await self._require_parent(ctx):
            return

        users = ensure_user_manager(self.parent)
        _ensure_hook_registered(self.parent)

        if mcoc_id is None:
            # use runtime prefix if available
            prefix = getattr(ctx, "prefix", None) or self.prefix or "///"
            await ctx.send(f"Usage: `{prefix}mcoc account link <mcoc_id>`")
            return

        try:
            users.set_profile_field(ctx.author.id, "mcoc_id", str(mcoc_id).strip())
            users.set_profile_field(ctx.author.id, "linked", True)
            await ctx.send(f"Linked your account to MCoc id `{mcoc_id}`.")
        except Exception:
            log.exception("Failed to link account")
            await ctx.send("Failed to link account. Try again later.")

    @account.command(name="unlink")
    async def account_unlink(self, ctx):
        """
        Unlink your in-game account from your Discord profile.
        """
        if not await self._require_parent(ctx):
            return

        users = ensure_user_manager(self.parent)
        _ensure_hook_registered(self.parent)

        try:
            profile = users.get_profile(ctx.author.id) or {}
            if not profile.get("mcoc_id") and not profile.get("linked"):
                await ctx.send("No linked MCoc account found.")
                return

            # clear fields
            users.set_profile_field(ctx.author.id, "mcoc_id", None)
            users.set_profile_field(ctx.author.id, "linked", False)
            await ctx.send("Your MCoc account has been unlinked.")
        except Exception:
            log.exception("Failed to unlink account")
            await ctx.send("Failed to unlink account. Try again later.")

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
        users = ensure_user_manager(parent)
        try:
            target = ctx.author.id if member is None else getattr(member, "id", member)
            profile = users.get_profile(target)
            await ctx.send(f"Profile: ```json\n{profile}\n```")
        except Exception:
            await ctx.send("Failed to fetch profile.")

    _safe_add("info", _view)
    _safe_add("view", _view)

    async def _set(ctx, field: str, *, value: str):
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; account unavailable.")
            return
        if field not in ALLOWED_PROFILE_FIELDS:
            await ctx.send("Invalid field. Allowed: " + ", ".join(sorted(ALLOWED_PROFILE_FIELDS.keys())))
            return
        users = ensure_user_manager(parent)
        try:
            users.set_profile_field(ctx.author.id, field, value)
            await ctx.send(f"Set {field}.")
        except Exception:
            await ctx.send("Failed to set profile field.")

    _safe_add("set", _set)

    async def _link(ctx, mcoc_id: Optional[str] = None):
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; account unavailable.")
            return
        users = ensure_user_manager(parent)
        if mcoc_id is None:
            await ctx.send("Usage: ///mcoc account link <mcoc_id>")
            return
        try:
            users.set_profile_field(ctx.author.id, "mcoc_id", str(mcoc_id).strip())
            users.set_profile_field(ctx.author.id, "linked", True)
            await ctx.send(f"Linked your account to MCoc id `{mcoc_id}`.")
        except Exception:
            await ctx.send("Failed to link account.")

    _safe_add("link", _link)

    async def _unlink(ctx):
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; account unavailable.")
            return
        users = ensure_user_manager(parent)
        try:
            users.set_profile_field(ctx.author.id, "mcoc_id", None)
            users.set_profile_field(ctx.author.id, "linked", False)
            await ctx.send("Unlinked your account.")
        except Exception:
            await ctx.send("Failed to unlink account.")

    _safe_add("unlink", _unlink)

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

    async def _privacy(ctx, subcommand: str, *args):
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; account unavailable.")
            return
        users = ensure_user_manager(parent)
        try:
            if subcommand == "mode" and args:
                users.set_profile_field(ctx.author.id, "privacy_mode", args[0])
                await ctx.send(f"Set privacy mode to `{args[0]}`.")
            elif subcommand == "allow_guild" and args:
                guild_id = args[0]
                allowed_guilds = users.get_profile(ctx.author.id).get("allowed_guilds", [])
                if guild_id not in allowed_guilds:
                    allowed_guilds.append(guild_id)
                    users.set_profile_field(ctx.author.id, "allowed_guilds", allowed_guilds)
                await ctx.send(f"Allowed sharing with guild `{guild_id}`.")
            elif subcommand == "revoke_guild" and args:
                guild_id = args[0]
                allowed_guilds = users.get_profile(ctx.author.id).get("allowed_guilds", [])
                if guild_id in allowed_guilds:
                    allowed_guilds.remove(guild_id)
                    users.set_profile_field(ctx.author.id, "allowed_guilds", allowed_guilds)
                await ctx.send(f"Revoked sharing with guild `{guild_id}`.")
            else:
                await ctx.send("Invalid privacy subcommand or missing arguments.")
        except Exception:
            await ctx.send("Failed to update privacy settings.")

    _safe_add("privacy", _privacy)
