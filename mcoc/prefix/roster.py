# mcoc/prefix/roster.py
"""
Prefix command handler for roster operations.

This module is intentionally thin: it resolves the command context and target member,
delegates parsing, filtering, formatting and embed/page construction to
`mcoc.common.roster` helpers, and then starts a branded pager (PagesMenu).

Responsibilities kept here:
- Resolve optional leading mention/id into a Member/User (prefer guild Member).
- Perform context-specific privacy gating (viewer vs owner).
- Call common helpers to build pages or a ready pager.
- Start the pager and merge brand buttons into the pager view when possible.

All heavy lifting (parsing, matching explicit hargs, prestige, formatting,
embed construction, pagination) lives in `mcoc.common.roster`.
"""

from typing import Any, Optional, List, Tuple
import logging
from discord.member import Member
from discord.user import User
from redbot.core import commands
from mcoc.common import Core
Embed = Core.Embed
PagesMenu = Core.PagesMenu
Roster = Core.Helpers.roster

# from ..common.helpers.roster import ensure_user_manager, get_roster_pages, make_roster_pager
from mcoc.common.query_parser import parse_query
# from ..common.componentsV2 import Embed, PagesMenu
from mcoc.common.prefix_utils import safe_send_ctx
from mcoc.common.help_utils import send_or_brand_help 

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

        Behavior:
          - If first token resolves to a Member (in guild) or User, return it and drop token.
          - If resolution fails, return None and leave tokens unchanged.
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
            # Not a mention/id; caller will treat as filters for invoking user
            return None, tokens

    @commands.group(name="roster")
    async def roster(self, ctx, *args):
        """Top-level roster group help."""
        if args:
            if args[0] is Member or args[0] is User:
                member = args[0]
        else:
            member = None

        if member is not None:
            # redirect to list display for that member
            await self.roster_list(ctx, str(member))
            return
        else:
            # show help for this group
            # await send_or_brand_help(ctx, "roster", title="Roster Help", fallback_text="Roster commands: add, remove, update, list, export, clear.")
            return

    # -----------------------------
    # List (filters)
    # -----------------------------
    @roster.command(name="list")
    async def roster_list(self, ctx, *items: str):
        """
        List roster entries for a user (or yourself) with optional filters.

        Examples:
          ///mcoc roster list
          ///mcoc roster list @User
          ///mcoc roster list @User #bleed
          ///mcoc roster list @User colossus7*r1a1
          ///mcoc roster list #bleed 7-star 6-star
        """
        if not await self._require_parent(ctx):
            return

        # Convert tokens to mutable list for resolution
        tokens = list(items or [])

        # Try to resolve a leading mention/id into a target member
        target_member, tokens = await self._resolve_target_member(ctx, tokens)
        if target_member is None:
            # default to invoking user (Member if in guild)
            target_member = ctx.author

        # Reconstruct the remaining query text
        items_text = " ".join(tokens).strip()

        # Privacy check: quick guard using user manager if available
        users = Roster.ensure_user_manager(self.parent)
        try:
            profile = users.get_profile(target_member.id) if users and hasattr(users, "get_profile") else {}
        except Exception:
            profile = {}

        # If target is not the invoking user, enforce privacy policy if available
        if target_member.id != ctx.author.id:
            try:
                # prefer a can_view_profile/can_view_roster hook if present on users
                if users and hasattr(users, "can_view_profile"):
                    allowed = users.can_view_profile(ctx.author.id, target_member.id, guild_id=getattr(ctx.guild, "id", None))
                    if not allowed:
                        await safe_send_ctx(ctx, "You do not have permission to view that roster.")
                        return
                else:
                    # fallback to a simple public_roster flag in profile
                    if profile.get("public_roster") is False:
                        await safe_send_ctx(ctx, "That user's roster is private.")
                        return
            except Exception:
                # conservative fallback: deny if not the owner
                await safe_send_ctx(ctx, "You do not have permission to view that roster.")
                return

        # Delegate parsing to the shared query parser (keeps behavior consistent)
        cache = getattr(self.parent, "cache", None)
        try:
            entries, filters = parse_query(items_text, cache=cache)
        except Exception:
            # fallback: treat the raw text as filters only
            entries, filters = [], {}

        # Build parsed_filters shape expected by common/roster helpers.
        # If explicit entries exist, prefer passing them through as 'explicit_entries'.
        parsed_filters = {}
        if entries:
            parsed_filters["explicit_entries"] = entries
        # merge other filters if present
        if isinstance(filters, dict):
            parsed_filters.update(filters)

        # Prefer the convenience wrapper that returns a ready pager if available.
        # make_roster_pager should return a PagesMenu instance (or None on failure).
        try:
            pager = None
            if hasattr(self.parent, "mcoc_core"):  # defensive check; not required
                pass

            # Try to get a ready pager from common helper (preferred)
            try:
                pager = await Roster.make_roster_pager(self.parent, ctx, raw_input=items_text, target_token=None, parsed_filters=parsed_filters)
            except TypeError:
                # older helper signature may not accept these args; fall back to get_roster_pages
                pager = None
            except Exception:
                pager = None

            # If helper returned a ready pager, start it
            if pager is not None:
                try:
                    # Merge brand buttons if possible
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

            # Otherwise, request pages (embeds) and instantiate a pager here
            pages = await Roster.get_roster_pages(self.parent, target_member, parsed_filters=parsed_filters)

            if not pages:
                # No matches: send a single decorated embed
                try:
                    await ctx.send(embed=Embed.Embed.embed(target_member, title="Roster", description="No roster entries match your filters."))
                except Exception:
                    await safe_send_ctx(ctx, "No roster entries match your filters.")
                return

            # Ensure pages are embed objects; instantiate a pager defensively
            try:
                pager = PagesMenu(pages, author=ctx.author)
                                # Merge brand buttons into pager view if possible
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

                # Start the pager
                await pager.start(ctx)
                return

            except Exception:
                log.exception("Failed to instantiate/start PagesMenu; falling back to sending first embed")
                # Fallback: send the first embed (still decorated)
                try:
                    first = pages[0]
                    await ctx.send(embed=first)
                    return
                except Exception:
                    # Last resort: send a compact text summary
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

async def setup(bot):
    bot.add_cog(RosterPrefix(bot))