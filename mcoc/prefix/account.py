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

from typing import Any, Dict, List, Optional
import logging

from discord.member import Member
from discord.user import User
from redbot.core import commands

from mcoc.common import Core
from mcoc.common.helpers import account as Account
from mcoc.common.components.help_utils import send_or_brand_help
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

    def _stringify_setting_value(self, value: Any) -> str:
        if value is None:
            return "not set"
        if isinstance(value, str):
            s = value.strip()
            return s if s else "not set"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, list):
            if not value:
                return "not set"
            return ", ".join(str(v) for v in value)
        if isinstance(value, dict):
            if not value:
                return "not set"
            parts = []
            for k, v in value.items():
                parts.append(f"{k}: {v}")
            return "; ".join(parts)
        return str(value)

    def _build_settings_pages(self, ctx, target_user: Any) -> List[Any]:
        Embed = Core.Embed
        profile = Account.get_profile(self.parent, getattr(target_user, "id", None)) or {}
        field_meta: Dict[str, Dict[str, str]] = getattr(Account, "ALLOWED_PROFILE_FIELDS", {}) or {}
        key_map: Dict[str, str] = getattr(Account, "FIELD_CANONICAL", {}) or {}

        ordered_fields = list(field_meta.keys())
        if not ordered_fields:
            ordered_fields = sorted(set(key_map.keys()) | set(key_map.values()))

        page_entries: List[tuple] = []
        for field in ordered_fields:
            stored_key = key_map.get(field, field)
            raw = profile.get(stored_key)
            shown = self._stringify_setting_value(raw)
            page_entries.append((field, shown))

        per_page = 12
        pages: List[Any] = []
        for i in range(0, len(page_entries), per_page):
            chunk = page_entries[i:i + per_page]
            emb = Embed.embed(
                ctx,
                title=f"{getattr(target_user, 'display_name', 'User')} Account Settings",
                description="Profile fields and current values.",
            )
            for field_name, field_value in chunk:
                val = field_value
                if len(val) > 900:
                    val = val[:897] + "..."
                Embed.add_field(ctx, emb, name=field_name, value=val, inline=False)
            pages.append(emb)

        if not pages:
            emb = Embed.embed(
                ctx,
                title=f"{getattr(target_user, 'display_name', 'User')} Account Settings",
                description="No account settings found.",
            )
            pages.append(emb)
        return pages

    async def _send_settings_pages(self, ctx, target_user: Any) -> None:
        pages = self._build_settings_pages(ctx, target_user)
        menu_cls = Core.PagesMenu
        if menu_cls is None or len(pages) == 1:
            await safe_send_ctx(ctx, None, embed=pages[0])
            return
        try:
            menu = menu_cls(pages, author=ctx.author, timeout=120)
            await menu.start(ctx)
            return
        except Exception:
            await safe_send_ctx(ctx, None, embed=pages[0])

    async def _handle_set(self, ctx, args: tuple) -> None:
        if len(args) < 2:
            fields = sorted(getattr(Account, "ALLOWED_PROFILE_FIELDS", {}).keys())
            await safe_send_ctx(
                ctx,
                "Usage: ///account set <field> <value>\n"
                f"Fields: {', '.join(fields) if fields else 'none'}",
            )
            return

        field = str(args[1]).strip().lower()
        key_map: Dict[str, str] = getattr(Account, "FIELD_CANONICAL", {}) or {}
        stored_field = key_map.get(field, field)
        if not Account.validate_profile_field(field):
            await safe_send_ctx(ctx, f"Unknown profile field: {field}")
            return

        if len(args) < 3:
            await safe_send_ctx(ctx, "Provide a value, or use `clear` to remove it.")
            return
        value_text = " ".join(str(a) for a in args[2:]).strip()
        lowered = value_text.lower()
        if lowered in {"clear", "none", "null", "unset"}:
            value: Any = None
        elif stored_field in {"roster_public", "linked", "consent"}:
            value = lowered in {"1", "true", "yes", "on"}
        else:
            value = value_text

        ok = Account.set_profile_field(self.parent, getattr(ctx.author, "id", None), stored_field, value)
        if ok:
            pretty = "not set" if value is None else self._stringify_setting_value(value)
            await safe_send_ctx(ctx, f"Updated {stored_field}: {pretty}")
        else:
            await safe_send_ctx(ctx, "Failed to update that profile field.")

    @commands.group(name="account", invoke_without_command=True)
    async def account(self, ctx, *args: str):
        """View account/profile assistance and consent actions."""
        if not await self._require_parent(ctx):
            return

        if args and args[0].lower() in {"agree", "accept"}:
            _, msg = await Account.handle_consent_response(self.parent, ctx, getattr(ctx.author, "id", None), True)
            await safe_send_ctx(ctx, msg)
            return
        if args and args[0].lower() in {"decline", "deny"}:
            _, msg = await Account.handle_consent_response(self.parent, ctx, getattr(ctx.author, "id", None), False)
            await safe_send_ctx(ctx, msg)
            return

        if args and args[0].lower() == "set":
            await self._handle_set(ctx, args)
            return

        if not args:
            status = "consented" if Account.user_has_consented(self.parent, getattr(ctx.author, "id", None)) else "not consented"
            await send_or_brand_help(
                ctx,
                "account",
                title="Account Help",
                fallback_text=(
                    "Account commands: profile, settings, set, privacy, link, unlink, agree, decline.\n"
                    f"Consent status: {status}."
                ),
            )
            return

        if args and args[0].lower() in {"profile", "settings"}:
            target = ctx.author
            if len(args) > 1:
                resolved = await self._resolve_target_user(ctx, args[1])
                if resolved is None:
                    await safe_send_ctx(ctx, "Could not resolve that user.")
                    return
                target = resolved
            if args[0].lower() == "settings":
                await self._send_settings_pages(ctx, target)
            else:
                await self._send_profile_display(ctx, target)
            return

        if args:
            resolved = await self._resolve_target_user(ctx, args[0])
            if resolved is not None:
                await self._send_profile_display(ctx, resolved)
                return

        await safe_send_ctx(ctx, "Unknown account subcommand. Try `///account` for help.")

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
        await self._send_settings_pages(ctx, target)

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
