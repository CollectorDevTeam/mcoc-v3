# mcoc/prefix/roster.py
"""
Prefix command handler for roster operations.

Provides:
  - roster (group)
  - roster list
  - roster add
  - roster remove
  - roster update
  - roster export
  - roster clear
  - roster link
  - roster unlink

This file is defensive: it tolerates missing helpers, logs decisions, and uses
mcoc.common.roster and mcoc.common.account where available.
"""

from typing import Any, Optional, List, Tuple, Dict
import logging
from discord.member import Member
from discord.user import User
from redbot.core import commands
from mcoc.common import Core
Embed = Core.Embed
PagesMenu = Core.PagesMenu
Roster = Core.Helpers.roster

from mcoc.common.query_parser import parse_query
from mcoc.common.prefix_utils import safe_send_ctx
from mcoc.common.help_utils import send_or_brand_help
from mcoc.common import account as Account  # consent helper

log = logging.getLogger("red.mcoc.prefix.roster")


class RosterPrefix(commands.Cog):
    """Prefix commands for roster management (thin orchestration layer)."""

    def __init__(self, bot_or_parent: Any):
        # bot_or_parent may be the core or the bot depending on how this cog is loaded
        if hasattr(bot_or_parent, "bot") and hasattr(bot_or_parent, "cache"):
            self.parent = bot_or_parent
            self.bot = bot_or_parent.bot
        else:
            self.parent = None
            self.bot = bot_or_parent

    async def _require_parent(self, ctx) -> bool:
        """Ensure the core/parent is attached; send a helpful message if not."""
        if not getattr(self, "parent", None):
            core = getattr(self.bot, "mcoc_core", None) or self.bot.get_cog("MCOC")
            if core:
                self.parent = core
                return True
            await safe_send_ctx(ctx, "MCOC core not attached; roster commands unavailable.")
            return False
        return True

    async def _resolve_target_member(self, ctx, tokens: List[str]) -> Tuple[Optional[Any], List[str]]:
        """
        Resolve an optional leading mention/id token into a Member/User.
        Returns (resolved_member_or_none, remaining_tokens_list).
        """
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

    # -----------------------------
    # Top-level roster group
    # -----------------------------
    @commands.group(name="roster", invoke_without_command=True)
    async def roster(self, ctx, *args):
        """
        Top-level roster group.

        Behavior:
          - If a member/user token is provided, redirect to roster list for that member.
          - If no token and invoking user has not consented -> start enrollment prompt.
          - If no token and invoking user has consented -> show roster help.
        """
        # Try to resolve a leading member token if present
        member = None
        if args:
            if isinstance(args[0], (Member, User)):
                member = args[0]
            else:
                try:
                    if ctx.guild:
                        member = await commands.MemberConverter().convert(ctx, args[0])
                    else:
                        member = await commands.UserConverter().convert(ctx, args[0])
                except Exception:
                    member = None

        if member is not None:
            # redirect to list display for that member
            await self.roster_list(ctx, str(member))
            return

        if not await self._require_parent(ctx):
            return

        user_id = getattr(ctx.author, "id", None)

        # Defensive consent check
        try:
            if hasattr(Account, "user_has_consented"):
                consented = Account.user_has_consented(self.parent, user_id)
            else:
                users = Roster.ensure_user_manager(self.parent)
                profile = users.get_profile(user_id) if users and hasattr(users, "get_profile") else {}
                if isinstance(profile, dict) and "profile" in profile and isinstance(profile.get("profile"), dict):
                    p = profile.get("profile", {})
                else:
                    p = profile if isinstance(profile, dict) else {}
                consented = bool(p.get("consent", False))
        except Exception:
            log.exception("roster: consent check failed for %s", user_id)
            consented = False

        log.debug("roster command invoked by %s consent=%s", user_id, consented)

        if not consented:
            # Start enrollment flow; prefer Account.enroll_command_handler if available
            try:
                if hasattr(Account, "enroll_command_handler"):
                    ok, msg = await Account.enroll_command_handler(self.parent, ctx, user_id)
                    if not ok:
                        log.warning("roster: enroll_command_handler reported failure for %s: %s", user_id, msg)
                else:
                    # fallback minimal prompt
                    policy_url = getattr(Account, "POLICY_METADATA", {}).get("privacy_policy", {}).get("url", "https://raw.githubusercontent.com/CollectorDevTeam/mcoc-v3/main/mcoc/privacy_policy.md")
                    dm_text = (
                        "To use roster features you must consent to the CollectorDevTeam privacy policy.\n\n"
                        f"Please review the policy here: {policy_url}\n\n"
                        "If you agree, run: ///account agree\nIf you decline, run: ///account decline"
                    )
                    try:
                        await ctx.author.send(dm_text)
                        log.info("roster: sent fallback enrollment DM to %s", user_id)
                    except Exception:
                        await safe_send_ctx(ctx, f"I couldn't DM you. Please review the privacy policy: {policy_url}")
                        log.info("roster: fallback enrollment message sent in-channel for %s", user_id)
            except Exception:
                log.exception("roster: enroll_command_handler failed for %s", user_id)
                await safe_send_ctx(ctx, "Failed to start enrollment; try again later.")
                return

            try:
                await ctx.tick()
            except Exception:
                try:
                    await safe_send_ctx(ctx, "I've sent you enrollment instructions (DM or channel).")
                except Exception:
                    log.exception("roster: failed to acknowledge enrollment prompt for %s", user_id)
            return

        # consented -> show roster help
        try:
            await send_or_brand_help(ctx, "roster", title="Roster Help", fallback_text="Roster commands: list, add, remove, update, export, clear, link, unlink.")
        except Exception:
            log.exception("roster: failed to show roster help for %s", user_id)
            try:
                await safe_send_ctx(ctx, "Roster commands: list, add, remove, update, export, clear, link, unlink.")
            except Exception:
                pass
            return

    # -----------------------------
    # List (filters)
    # -----------------------------
    @roster.command(name="list")
    async def roster_list(self, ctx, *items: str):
        """
        List roster entries for a user (or yourself) with optional filters.
        """
        if not await self._require_parent(ctx):
            return

        tokens = list(items or [])
        target_member, tokens = await self._resolve_target_member(ctx, tokens)
        if target_member is None:
            target_member = ctx.author

        items_text = " ".join(tokens).strip()

        users = Roster.ensure_user_manager(self.parent)
        try:
            profile = users.get_profile(target_member.id) if users and hasattr(users, "get_profile") else {}
        except Exception:
            profile = {}

        # privacy enforcement
        if target_member.id != ctx.author.id:
            try:
                if users and hasattr(users, "can_view_profile"):
                    allowed = users.can_view_profile(ctx.author.id, target_member.id, guild_id=getattr(ctx.guild, "id", None))
                    if not allowed:
                        await safe_send_ctx(ctx, "You do not have permission to view that roster.")
                        return
                else:
                    if profile.get("public_roster") is False:
                        await safe_send_ctx(ctx, "That user's roster is private.")
                        return
            except Exception:
                await safe_send_ctx(ctx, "You do not have permission to view that roster.")
                return

        cache = getattr(self.parent, "cache", None)
        try:
            entries, filters = parse_query(items_text, cache=cache)
        except Exception:
            entries, filters = [], {}

        parsed_filters = {}
        if entries:
            parsed_filters["explicit_entries"] = entries
        if isinstance(filters, dict):
            parsed_filters.update(filters)

        # Try to get a ready pager first
        try:
            pager = None
            try:
                pager = await Roster.make_roster_pager(self.parent, ctx, raw_input=items_text, target_token=None, parsed_filters=parsed_filters)
            except TypeError:
                pager = None
            except Exception:
                pager = None

            if pager is not None:
                try:
                    try:
                        brand_view = Embed.brand_view()
                        if hasattr(pager, "add_item"):
                            for item in getattr(brand_view, "children", []):
                                try:
                                    pager.add_item(item)
                                except Exception:
                                    continue
                    except Exception:
                        pass
                    await pager.start(ctx)
                    return
                except Exception:
                    log.exception("Failed to start pager returned by make_roster_pager; falling back to pages")

            pages = await Roster.get_roster_pages(self.parent, target_member, parsed_filters=parsed_filters)

            if not pages:
                try:
                    await ctx.send(embed=Embed.Embed.embed(target_member, title="Roster", description="No roster entries match your filters."))
                except Exception:
                    await safe_send_ctx(ctx, "No roster entries match your filters.")
                return

            try:
                pager = PagesMenu(pages, author=ctx.author)
                try:
                    brand_view = Embed.brand_view()
                    if hasattr(pager, "add_item"):
                        for item in getattr(brand_view, "children", []):
                            try:
                                pager.add_item(item)
                            except Exception:
                                continue
                except Exception:
                    pass
                await pager.start(ctx)
                return
            except Exception:
                log.exception("Failed to instantiate/start PagesMenu; falling back to sending first embed")
                try:
                    first = pages[0]
                    await ctx.send(embed=first)
                    return
                except Exception:
                    try:
                        titles = []
                        for p in pages[:50]:
                            t = getattr(p, "title", None) if not isinstance(p, dict) else p.get("title")
                            titles.append(t or "Entry")
                        await ctx.send(f"Matches ({len(pages)}): {', '.join(titles)}")
                        return
                    except Exception:
                        await safe_send_ctx(ctx, "Failed to display roster pages.")
                        return

        except Exception:
            log.exception("Unexpected error in roster_list")
            await safe_send_ctx(ctx, "An unexpected error occurred while building roster pages.")
            return

    # -----------------------------
    # Add
    # -----------------------------
    @roster.command(name="add")
    async def roster_add(self, ctx, *, text: str):
        """
        Add one or more champions to your roster.
        Example: ///roster add 7* ironman r1 s0, 6* colossus r1 s0
        """
        if not await self._require_parent(ctx):
            return
        user_id = getattr(ctx.author, "id", None)
        users = Roster.ensure_user_manager(self.parent)
        cache = getattr(self.parent, "cache", None)

        try:
            entries = Roster.parse_roster_entries_from_input(text, cache)
        except Exception as exc:
            log.debug("roster_add: parse failed: %s", exc)
            await safe_send_ctx(ctx, f"Failed to parse entries: {exc}")
            return

        added = 0
        for e in entries:
            try:
                users.add_champion(user_id, e["champion"], int(e["rarity"]), int(e["rank"]), int(e.get("sig", 0)), int(e.get("ascended", 0)), tags=e.get("tags", []))
                added += 1
            except Exception:
                log.exception("roster_add: failed to add %s for %s", e, user_id)
                continue

        # schedule prestige persistence if helper available
        try:
            Roster.schedule_persist_user_prestige(self.parent, user_id)
        except Exception:
            log.debug("roster_add: schedule_persist_user_prestige not available or failed", exc_info=True)

        await safe_send_ctx(ctx, f"Added {added} champion(s) to your roster.")

    # -----------------------------
    # Remove
    # -----------------------------
    @roster.command(name="remove")
    async def roster_remove(self, ctx, *, text: str):
        """
        Remove champions from your roster. Accepts same parsing as add.
        Example: ///roster remove ironman7, colossus6
        """
        if not await self._require_parent(ctx):
            return
        user_id = getattr(ctx.author, "id", None)
        users = Roster.ensure_user_manager(self.parent)
        cache = getattr(self.parent, "cache", None)

        try:
            entries = Roster.parse_roster_entries_from_input(text, cache)
        except Exception as exc:
            log.debug("roster_remove: parse failed: %s", exc)
            await safe_send_ctx(ctx, f"Failed to parse entries: {exc}")
            return

        removed = 0
        for e in entries:
            try:
                count = users.remove_champion(user_id, e["champion"], int(e["rarity"]))
                removed += int(count or 0)
            except Exception:
                log.exception("roster_remove: failed to remove %s for %s", e, user_id)
                continue

        try:
            Roster.schedule_persist_user_prestige(self.parent, user_id)
        except Exception:
            pass

        await safe_send_ctx(ctx, f"Removed {removed} champion(s) from your roster.")

    # -----------------------------
    # Update
    # -----------------------------
    @roster.command(name="update")
    async def roster_update(self, ctx, *, text: str):
        """
        Update a champion entry. Use harg token with rank/sig/ascended.
        Example: ///roster update ironman7 r2 s1
        """
        if not await self._require_parent(ctx):
            return
        user_id = getattr(ctx.author, "id", None)
        users = Roster.ensure_user_manager(self.parent)
        cache = getattr(self.parent, "cache", None)

        try:
            entries = Roster.parse_roster_entries_from_input(text, cache)
        except Exception as exc:
            log.debug("roster_update: parse failed: %s", exc)
            await safe_send_ctx(ctx, f"Failed to parse update token: {exc}")
            return

        updated = 0
        for e in entries:
            try:
                ok = users.update_champion(user_id, e["champion"], int(e["rarity"]), rank=int(e.get("rank", 1)), sig=int(e.get("sig", 0)), ascended=int(e.get("ascended", 0)), tags=e.get("tags", []))
                if ok:
                    updated += 1
            except Exception:
                log.exception("roster_update: failed to update %s for %s", e, user_id)
                continue

        try:
            Roster.schedule_persist_user_prestige(self.parent, user_id)
        except Exception:
            pass

        await safe_send_ctx(ctx, f"Updated {updated} champion(s) in your roster.")

    # -----------------------------
    # Export
    # -----------------------------
    @roster.command(name="export")
    async def roster_export(self, ctx):
        """
        Export your full user data (profile + roster) as JSON text in DM.
        """
        if not await self._require_parent(ctx):
            return
        user_id = getattr(ctx.author, "id", None)
        users = Roster.ensure_user_manager(self.parent)
        try:
            data = users.export(user_id)
            # send as DM (avoid large attachments); present compact summary in-channel
            try:
                await ctx.author.send("Your exported profile and roster (JSON):")
                await ctx.author.send(str(data))
                await safe_send_ctx(ctx, "I've DM'd your exported profile and roster.")
            except Exception:
                await safe_send_ctx(ctx, "Failed to DM you the export. If you have DMs disabled, enable them and try again.")
        except Exception:
            log.exception("roster_export failed for %s", user_id)
            await safe_send_ctx(ctx, "Failed to export your data.")

    # -----------------------------
    # Clear
    # -----------------------------
    @roster.command(name="clear")
    async def roster_clear(self, ctx, confirm: Optional[str] = None):
        """
        Clear your roster entirely. Requires explicit 'confirm' token to proceed.
        Example: ///roster clear CONFIRM
        """
        if not await self._require_parent(ctx):
            return
        user_id = getattr(ctx.author, "id", None)
        if not confirm or confirm.lower() not in ("confirm", "yes", "i confirm", "confirm-clear"):
            await safe_send_ctx(ctx, "This will delete your roster. To proceed, run: ///roster clear confirm")
            return
        users = Roster.ensure_user_manager(self.parent)
        try:
            # replace with empty roster and persist
            data = users._load(user_id) if hasattr(users, "_load") else users.export(user_id)
            if isinstance(data, dict):
                data["roster"] = []
                users._save(user_id, data) if hasattr(users, "_save") else users.import_data(user_id, data)
            await safe_send_ctx(ctx, "Your roster has been cleared.")
            try:
                Roster.schedule_persist_user_prestige(self.parent, user_id)
            except Exception:
                pass
        except Exception:
            log.exception("roster_clear failed for %s", user_id)
            await safe_send_ctx(ctx, "Failed to clear your roster.")

    # -----------------------------
    # Link / Unlink
    # -----------------------------
    @roster.command(name="link")
    async def roster_link(self, ctx, mcoc_id: str):
        """
        Link your Discord account to an in-game id.
        Example: ///roster link my_mcoc_id
        """
        if not await self._require_parent(ctx):
            return
        user_id = getattr(ctx.author, "id", None)
        try:
            ok, msg = Account.link_account(self.parent, user_id, mcoc_id)
            if ok:
                await safe_send_ctx(ctx, msg)
            else:
                await safe_send_ctx(ctx, f"Failed to link account: {msg}")
        except Exception:
            log.exception("roster_link failed for %s", user_id)
            await safe_send_ctx(ctx, "Failed to link your account.")

    @roster.command(name="unlink")
    async def roster_unlink(self, ctx):
        """
        Unlink your Discord account from any in-game id.
        """
        if not await self._require_parent(ctx):
            return
        user_id = getattr(ctx.author, "id", None)
        try:
            ok, msg = Account.unlink_account(self.parent, user_id)
            if ok:
                await safe_send_ctx(ctx, msg)
            else:
                await safe_send_ctx(ctx, f"Failed to unlink account: {msg}")
        except Exception:
            log.exception("roster_unlink failed for %s", user_id)
            await safe_send_ctx(ctx, "Failed to unlink your account.")


async def setup(bot):
    bot.add_cog(RosterPrefix(bot))
