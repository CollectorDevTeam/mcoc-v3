# Path: mcoc/prefix/account.py
# File-Version: 1.0
# File-Id: dfa776d3-4249-4539-8d75-4db5460c1f70
# Purpose: Prefix account commands and consent/profile helpers.
# Public-API: AccountPrefix
# Internal: _require_parent
# Last-Modified: 2026-09-01
"""Account prefix commands.

This module owns the user-facing consent, profile, and account-link surfaces.
The heavier logic remains in mcoc.common.helpers.account.
"""

from typing import Any, Optional
import logging

from discord.member import Member
from discord.user import User
from redbot.core import commands

from mcoc.common import Core
from mcoc.common.helpers import account as Account
from mcoc.common.components.prefix_utils import safe_send_ctx

log = logging.getLogger("red.mcoc.prefix.account")


class AccountPrefix(commands.Cog):
    """Account/profile/consent prefix commands."""

    def __init__(self, bot_or_parent: Any):
        if hasattr(bot_or_parent, "bot") and hasattr(bot_or_parent, "cache"):
            self.parent = bot_or_parent
            self.bot = bot_or_parent.bot
        else:
            self.parent = None
            self.bot = bot_or_parent

    async def _require_parent(self, ctx) -> bool:
        if not getattr(self, "parent", None):
            core = getattr(self.bot, "mcoc_core", None) or self.bot.get_cog("MCOC")
            if core:
                self.parent = core
                return True
            await safe_send_ctx(ctx, "MCOC core not attached; account commands unavailable.")
            return False
        return True

    async def _resolve_target_user(self, ctx, token: str) -> Optional[Any]:
        try:
            if ctx.guild:
                return await commands.MemberConverter().convert(ctx, token)
            return await commands.UserConverter().convert(ctx, token)
        except Exception:
            return None

    async def _send_profile_display(self, ctx, target_user: Any) -> None:
        emb, text = Account.build_profile_display(
            self.parent,
            ctx,
            getattr(target_user, "id", None),
            viewer_id=getattr(ctx.author, "id", None),
            prefer_embed=True,
        )
        if emb is not None:
            await safe_send_ctx(ctx, None, embed=emb)
            return
        await safe_send_ctx(ctx, text or "No profile found for that user.")

    @commands.group(name="account", invoke_without_command=True)
    async def account(self, ctx, *args: str):
        """View account/profile assistance and consent actions."""
        if not await self._require_parent(ctx):
            return
        user_id = getattr(ctx.author, "id", None)
        if args and args[0].lower() in {"agree", "accept"}:
            _, msg = await Account.handle_consent_response(self.parent, ctx, user_id, True)
            await safe_send_ctx(ctx, msg)
            return
        if args and args[0].lower() in {"decline", "deny"}:
            _, msg = await Account.handle_consent_response(self.parent, ctx, user_id, False)
            await safe_send_ctx(ctx, msg)
            return

        if args and args[0].lower() in {"profile", "settings"}:
            target = ctx.author
            if len(args) > 1:
                resolved = await self._resolve_target_user(ctx, args[1])
                if resolved is None:
                    await safe_send_ctx(ctx, "Could not resolve that user.")
                    return
                target = resolved
            await self._send_profile_display(ctx, target)
            return

        if args:
            resolved = await self._resolve_target_user(ctx, args[0])
            if resolved is not None:
                await self._send_profile_display(ctx, resolved)
                return

        status = "consented" if Account.user_has_consented(self.parent, user_id) else "not consented"
        await safe_send_ctx(ctx, f"Account status: {status}. Use `///account agree` or `///account decline` to manage consent.")

    @account.command(name="agree")
    async def account_agree(self, ctx):
        if not await self._require_parent(ctx):
            return
        _, msg = await Account.handle_consent_response(self.parent, ctx, getattr(ctx.author, "id", None), True)
        await safe_send_ctx(ctx, msg)

    @account.command(name="decline")
    async def account_decline(self, ctx):
        if not await self._require_parent(ctx):
            return
        _, msg = await Account.handle_consent_response(self.parent, ctx, getattr(ctx.author, "id", None), False)
        await safe_send_ctx(ctx, msg)

    @account.command(name="profile")
    async def account_profile(self, ctx, member: Optional[Any] = None):
        if not await self._require_parent(ctx):
            return
        target = member if isinstance(member, (Member, User)) else ctx.author
        await self._send_profile_display(ctx, target)

    @account.command(name="settings")
    async def account_settings(self, ctx, member: Optional[Any] = None):
        if not await self._require_parent(ctx):
            return
        target = member if isinstance(member, (Member, User)) else ctx.author
        await self._send_profile_display(ctx, target)

    @account.command(name="privacy")
    async def account_privacy(self, ctx, mode: Optional[str] = None):
        if not await self._require_parent(ctx):
            return
        user_id = getattr(ctx.author, "id", None)
        modes = {"private", "guild", "alliance", "public"}
        if mode is None:
            profile = Account.get_profile(self.parent, user_id) or {}
            current = profile.get("privacy_mode") or "private"
            await safe_send_ctx(ctx, f"Current privacy mode: {current}")
            return
        if mode.lower() not in modes:
            await safe_send_ctx(ctx, "Allowed privacy modes: private, guild, alliance, public.")
            return
        ok = Account.set_profile_field(self.parent, user_id, "privacy_mode", mode.lower())
        await safe_send_ctx(ctx, "Privacy mode updated." if ok else "Failed to update privacy mode.")

    @account.command(name="link")
    async def account_link(self, ctx, mcoc_id: str):
        if not await self._require_parent(ctx):
            return
        ok, msg = Account.link_account(self.parent, getattr(ctx.author, "id", None), mcoc_id)
        await safe_send_ctx(ctx, msg if ok else f"Failed to link account: {msg}")

    @account.command(name="unlink")
    async def account_unlink(self, ctx):
        if not await self._require_parent(ctx):
            return
        ok, msg = Account.unlink_account(self.parent, getattr(ctx.author, "id", None))
        await safe_send_ctx(ctx, msg if ok else f"Failed to unlink account: {msg}")


async def setup(bot):
    bot.add_cog(AccountPrefix(bot))
