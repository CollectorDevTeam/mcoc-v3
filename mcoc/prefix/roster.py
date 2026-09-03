# Path: mcoc/prefix/roster.py
# File-Version: 1.0
# File-Id: 694591c6-16db-4ce5-a833-d51d4e098b5c
# Purpose: Prefix roster commands and pager delegation.
# Public-API: RosterPrefix
# Internal: _require_parent, _resolve_target_member
# Last-Modified: 2026-09-01
"""Thin roster prefix layer.

This module resolves the user/context and delegates roster logic to the shared
helpers in mcoc.common.helpers.roster.
"""

from typing import Any, Optional, List, Tuple
import logging

from discord.member import Member
from discord.user import User
from redbot.core import commands

from mcoc.common import Core
from mcoc.common.helpers import account as Account
from mcoc.common.components.prefix_utils import safe_send_ctx
from mcoc.common.components.help_utils import send_or_brand_help
from mcoc.common.utilities.query_parser import parse_query

Embed = Core.Embed
PagesMenu = Core.PagesMenu
Roster = Core.Helpers.roster

log = logging.getLogger("red.mcoc.prefix.roster")


class RosterPrefix(commands.Cog):
    """Prefix commands for roster management."""

    def __init__(self, bot_or_parent: Any):
        if hasattr(bot_or_parent, "bot") and hasattr(bot_or_parent, "cache"):
            self.parent = bot_or_parent
            self.bot = bot_or_parent.bot
        else:
            self.parent = None
            self.bot = bot_or_parent
        self.prefix = getattr(bot_or_parent, "prefix", None)

    async def _require_parent(self, ctx) -> bool:
        if not getattr(self, "parent", None):
            core = getattr(self.bot, "mcoc_core", None) or self.bot.get_cog("MCOC")
            if core:
                self.parent = core
                return True
            await safe_send_ctx(ctx, "MCOC core not attached; roster commands unavailable.")
            return False
        return True

    async def _resolve_target_member(self, ctx, tokens: List[str]) -> Tuple[Optional[Any], List[str]]:
        if not tokens:
            return None, tokens
        first = tokens[0]
        try:
            if ctx.guild:
                member = await commands.MemberConverter().convert(ctx, first)
            else:
                member = await commands.UserConverter().convert(ctx, first)
            return member, tokens[1:]
        except Exception:
            return None, tokens

    async def _start_pages(self, ctx, pages: List[Any], empty_message: str) -> None:
        if not pages:
            await safe_send_ctx(ctx, empty_message)
            return
        try:
            pager = PagesMenu(pages, author=ctx.author)
            await pager.start(ctx)
            return
        except Exception:
            pass
        first = pages[0]
        await ctx.send(embed=first)

    async def _show_roster_operation_pages(self, ctx, operation: str, text: Optional[str] = None) -> None:
        raw = (text or "").strip()
        try:
            entries, filters = parse_query(raw, cache=getattr(self.parent, "cache", None)) if raw else ([], {})
        except Exception:
            entries, filters = [], {}

        parsed_filters = {}
        if entries:
            parsed_filters["explicit_entries"] = entries
        if isinstance(filters, dict):
            parsed_filters.update(filters)

        if not raw:
            try:
                if await Roster.start_roster_operation_flow(self.parent, ctx, operation, parsed_filters=parsed_filters):
                    return
            except Exception:
                log.exception("failed to start guided roster %s flow", operation)

        loader_map = {
            "add": Roster.get_roster_add_pages,
            "update": Roster.get_roster_update_pages,
            "rankup": Roster.get_roster_rankup_pages,
            "dupe": Roster.get_roster_dupe_pages,
            "ascend": Roster.get_roster_ascend_pages,
        }
        pages = await loader_map[operation](self.parent, ctx.author, parsed_filters=parsed_filters)
        await self._start_pages(ctx, pages, f"No roster entries are available for `{operation}`.")

    @commands.group(name="roster", invoke_without_command=True)
    async def roster(self, ctx, *args):
        """List or inspect roster entries for yourself or another member.
        Examples:
            {self.prefix}roster
            {self.prefix}roster @user
        """
        if args:
            member = None
            if isinstance(args[0], (Member, User)):
                member = args[0]
            else:
                try:
                    member = await commands.MemberConverter().convert(ctx, args[0]) if ctx.guild else await commands.UserConverter().convert(ctx, args[0])
                except Exception:
                    member = None
            if member is not None:
                await self.roster_list(ctx, str(member))
                return

        if not await self._require_parent(ctx):
            return

        user_id = getattr(ctx.author, "id", None)
        consented = bool(Account.user_has_consented(self.parent, user_id)) if user_id is not None else False
        if not consented:
            try:
                ok, msg = await Account.enroll_command_handler(self.parent, ctx, user_id)
                if ok:
                    await ctx.tick()
                else:
                    await safe_send_ctx(ctx, msg)
            except Exception:
                log.exception("roster: consent enrollment failed for %s", user_id)
                await safe_send_ctx(ctx, "Failed to start enrollment; try again later.")
            return

        try:
            await send_or_brand_help(ctx, "roster", title="Roster Help", fallback_text="Roster commands: list, add, remove, update, rankup, dupe, ascend, export, clear.")
        except Exception:
            await safe_send_ctx(ctx, "Roster commands: list, add, remove, update, rankup, dupe, ascend, export, clear.")

    @roster.command(name="search", aliases=["list", "find", "grep", "get"])
    async def roster_list(self, ctx, *items: str):
        """Search a user's roster, optionally filtered by query parameters.
        Examples:
            {self.prefix}roster search hero:Iron Man
            {self.prefix}roster list 5-star
            {self.prefix}roster find level:60
            {self.prefix}roster grep 4-star
            {self.prefix}roster get hero:Spider-Man
        """
        if not await self._require_parent(ctx):
            return

        tokens = list(items or [])
        target_member, tokens = await self._resolve_target_member(ctx, tokens)
        if target_member is None:
            target_member = ctx.author
        items_text = " ".join(tokens).strip()

        users = Roster.ensure_user_manager(self.parent)
        profile = {}
        if users and hasattr(users, "get_profile"):
            try:
                profile = users.get_profile(target_member.id) or {}
            except Exception:
                profile = {}

        if target_member.id != ctx.author.id and not getattr(users, "can_view_profile", lambda *a, **k: True)(ctx.author.id, target_member.id, guild_id=getattr(ctx.guild, "id", None)):
            if profile.get("public_roster") is False:
                await safe_send_ctx(ctx, "That user's roster is private.")
                return

        try:
            entries, filters = parse_query(items_text, cache=getattr(self.parent, "cache", None))
        except Exception:
            entries, filters = [], {}

        parsed_filters = {}
        if entries:
            parsed_filters["explicit_entries"] = entries
        if isinstance(filters, dict):
            parsed_filters.update(filters)

        try:
            pages = await Roster.get_roster_pages(self.parent, target_member, parsed_filters=parsed_filters)
            if not pages:
                await safe_send_ctx(ctx, "No roster entries match your filters.")
                return
            try:
                pager = PagesMenu(pages, author=ctx.author)
                await pager.start(ctx)
                return
            except Exception:
                first = pages[0]
                await ctx.send(embed=first)
                return
        except Exception:
            log.exception("roster_list failed")
            await safe_send_ctx(ctx, "An unexpected error occurred while building roster pages.")

    @roster.command(name="add")
    async def roster_add(self, ctx, *, text: Optional[str] = None):
        """Add champions to the user's roster based on the provided text input.
        Examples:
        {self.prefix}roster add 7*blackbolt --> 7-Star BlackBolt rank 1 sig 0
        {self.prefix}roster add 6*A1r3ironman --> 6-Star IronMan rank 3 sig 0 ascended 1

        """
        if not await self._require_parent(ctx):
            return
        user_id = getattr(ctx.author, "id", None)
        users = Roster.ensure_user_manager(self.parent)
        raw = (text or "").strip()
        if not raw:
            await self._show_roster_operation_pages(ctx, "add")
            return
        try:
            entries = Roster.parse_roster_entries_from_input(raw, getattr(self.parent, "cache", None))
        except Exception as exc:
            try:
                await self._show_roster_operation_pages(ctx, "add", raw)
                return
            except Exception:
                await safe_send_ctx(ctx, f"Failed to parse entries: {exc}")
            return

        added = 0
        for e in entries:
            try:
                users.add_champion(user_id, e["champion"], int(e["rarity"]), int(e["rank"]), int(e.get("sig", 0)), int(e.get("ascended", 0)), tags=e.get("tags", []))
                added += 1
            except Exception:
                log.exception("failed to add champion %s for %s", e, user_id)
        try:
            Roster.schedule_persist_user_prestige(self.parent, user_id)
        except Exception:
            pass
        await safe_send_ctx(ctx, f"Added {added} champion(s) to your roster.")

    @roster.command(name="remove", aliases=["rm", "del"])
    async def roster_remove(self, ctx, *, text: str):
        """Remove champions from the user's roster based on the provided text input."""
        if not await self._require_parent(ctx):
            return
        user_id = getattr(ctx.author, "id", None)
        users = Roster.ensure_user_manager(self.parent)
        try:
            entries = Roster.parse_roster_entries_from_input(text, getattr(self.parent, "cache", None))
        except Exception as exc:
            await safe_send_ctx(ctx, f"Failed to parse entries: {exc}")
            return

        removed = 0
        for e in entries:
            try:
                removed += int(users.remove_champion(user_id, e["champion"], int(e["rarity"])) or 0)
            except Exception:
                log.exception("failed to remove champion %s for %s", e, user_id)
        try:
            Roster.schedule_persist_user_prestige(self.parent, user_id)
        except Exception:
            pass
        await safe_send_ctx(ctx, f"Removed {removed} champion(s) from your roster.")

    @roster.command(name="update")
    async def roster_update(self, ctx, *, text: Optional[str] = None):
        """Update champions in the user's roster based on the provided text input."""
        if not await self._require_parent(ctx):
            return
        user_id = getattr(ctx.author, "id", None)
        users = Roster.ensure_user_manager(self.parent)
        raw = (text or "").strip()
        if not raw:
            await self._show_roster_operation_pages(ctx, "update")
            return
        try:
            entries = Roster.parse_roster_entries_from_input(raw, getattr(self.parent, "cache", None))
        except Exception as exc:
            try:
                await self._show_roster_operation_pages(ctx, "update", raw)
                return
            except Exception:
                await safe_send_ctx(ctx, f"Failed to parse update token: {exc}")
            return

        updated = 0
        for e in entries:
            try:
                if users.update_champion(user_id, e["champion"], int(e["rarity"]), rank=int(e.get("rank", 1)), sig=int(e.get("sig", 0)), ascended=int(e.get("ascended", 0)), tags=e.get("tags", [])):
                    updated += 1
            except Exception:
                log.exception("failed to update champion %s for %s", e, user_id)
        try:
            Roster.schedule_persist_user_prestige(self.parent, user_id)
        except Exception:
            pass
        await safe_send_ctx(ctx, f"Updated {updated} champion(s) in your roster.")

    @roster.command(name="rankup")
    async def roster_rankup(self, ctx, *, text: Optional[str] = None):
        """Review roster entries eligible for a rank up using the shared tier limits."""
        if not await self._require_parent(ctx):
            return
        await self._show_roster_operation_pages(ctx, "rankup", text)

    @roster.command(name="dupe", aliases=["sigup"])
    async def roster_dupe(self, ctx, *, text: Optional[str] = None):
        """Review roster entries eligible for a sig increase using the shared tier limits."""
        if not await self._require_parent(ctx):
            return
        await self._show_roster_operation_pages(ctx, "dupe", text)

    @roster.command(name="ascend")
    async def roster_ascend(self, ctx, *, text: Optional[str] = None):
        """Review roster entries eligible for ascension using the shared tier limits."""
        if not await self._require_parent(ctx):
            return
        await self._show_roster_operation_pages(ctx, "ascend", text)

    @roster.command(name="export")
    async def roster_export(self, ctx):
        """Export the user's roster and profile data."""
        if not await self._require_parent(ctx):
            return
        user_id = getattr(ctx.author, "id", None)
        users = Roster.ensure_user_manager(self.parent)
        try:
            data = users.export(user_id)
            await ctx.author.send(str(data))
            await safe_send_ctx(ctx, "I've DM'd your exported profile and roster.")
        except Exception:
            log.exception("roster_export failed for %s", user_id)
            await safe_send_ctx(ctx, "Failed to export your data.")

    @roster.command(name="clear")
    async def roster_clear(self, ctx, confirm: Optional[str] = None):
        """Clear the user's roster after confirmation."""
        if not await self._require_parent(ctx):
            return
        if not confirm or confirm.lower() not in {"confirm", "yes", "i confirm"}:
            await safe_send_ctx(ctx, "This will delete your roster. To proceed, run: ///roster clear confirm")
            return
        user_id = getattr(ctx.author, "id", None)
        users = Roster.ensure_user_manager(self.parent)
        try:
            data = users.export(user_id) if hasattr(users, "export") else {}
            if isinstance(data, dict):
                data["roster"] = []
                if hasattr(users, "import_data"):
                    users.import_data(user_id, data)
                elif hasattr(users, "_save"):
                    users._save(user_id, data)
            await safe_send_ctx(ctx, "Your roster has been cleared.")
        except Exception:
            log.exception("roster_clear failed for %s", user_id)
            await safe_send_ctx(ctx, "Failed to clear your roster.")

    @roster.command(name="link")
    async def roster_link(self, ctx, mcoc_id: str):
        """Link the user's account with the provided MCOC ID."""
        if not await self._require_parent(ctx):
            return
        ok, msg = Account.link_account(self.parent, getattr(ctx.author, "id", None), mcoc_id)
        await safe_send_ctx(ctx, msg if ok else f"Failed to link account: {msg}")

    @roster.command(name="unlink")
    async def roster_unlink(self, ctx):
        """Unlink the user's account from their MCOC ID."""
        if not await self._require_parent(ctx):
            return
        ok, msg = Account.unlink_account(self.parent, getattr(ctx.author, "id", None))
        await safe_send_ctx(ctx, msg if ok else f"Failed to unlink account: {msg}")


async def setup(bot):
    bot.add_cog(RosterPrefix(bot))

