# mcoc/prefix/champions.py
"""
Prefix command handlers for champion-related commands.

This module is intentionally thin: it resolves the command context and target member (when applicable),
delegates parsing and page construction to mcoc.common.champions helpers, and starts the pager.

Responsibilities:
  - Resolve optional leading mention/id (when commands accept a target)
  - Delegate parsing to common.query_parser.parse_query
  - Call common.champions.make_champion_pager or get_champion_pages
  - Instantiate and start CDTPagesMenu when needed
  - Merge brand buttons into pager view when possible
  - Provide robust fallbacks and helpful user-facing messages
"""

from typing import Any, List, Optional, Tuple
import logging

from redbot.core import commands

from ..common.champions import make_champion_pager, get_champion_pages
from ..common.query_parser import parse_query
from ..common.componentsV2 import CDTEmbed, CDTPagesMenu
from ..common.prefix_utils import safe_send_ctx

log = logging.getLogger("red.mcoc.prefix.champions")


class ChampionsPrefix(commands.Cog):
    """Prefix commands for champion search and utilities (thin orchestration)."""

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
            await safe_send_ctx(ctx, "MCOC core not attached; champion commands unavailable.")
            return False
        return True

    # -----------------------------
    # Champion search
    # -----------------------------
    @commands.group(name="champ", invoke_without_command=True)
    async def champ(self, ctx):
        """Champion commands: search, abilities, info."""
        await safe_send_ctx(ctx, "Champion commands: search, abilities, info.")

    @champ.command(name="search")
    async def champ_search(self, ctx, *items: str):
        """
        Search champions (deck-first) with optional filters or explicit hargs tokens.

        Examples:
          ///mcoc champ search #bleed
          ///mcoc champ search "black bolt"
          ///mcoc champ search 7r1s40 blackbolt
        """
        if not await self._require_parent(ctx):
            return

        raw = " ".join(items or "").strip()
        cache = getattr(self.parent, "cache", None)

        # Parse query into explicit entries and filters (keeps behavior consistent)
        try:
            entries, filters = parse_query(raw, cache=cache)
        except Exception:
            entries, filters = [], {"raw_text": raw}

        parsed_filters = {}
        if entries:
            parsed_filters["explicit_entries"] = entries
        if isinstance(filters, dict):
            parsed_filters.update(filters)

        # Preferred: get a ready pager from common helper
        try:
            pager = await make_champion_pager(self.parent, ctx, raw_input=raw, parsed_filters=parsed_filters, author_for_controls=ctx.author)
        except Exception:
            pager = None

        if pager:
            # Merge brand buttons if possible
            try:
                brand_view = CDTEmbed.brand_view()
                if hasattr(pager, "add_item"):
                    for item in getattr(brand_view, "children", []):
                        try:
                            pager.add_item(item)
                        except Exception:
                            continue
            except Exception:
                pass

            try:
                await pager.start(ctx)
                return
            except Exception:
                log.exception("Failed to start pager returned by make_champion_pager; falling back to pages")

        # Fallback: request pages and instantiate pager here
        try:
            pages = await get_champion_pages(self.parent, ctx.author, filters=parsed_filters)
        except Exception:
            pages = []

        if not pages:
            try:
                await ctx.send(embed=CDTEmbed.embed(ctx.author, title="Champions", description="No champions match your search."))
            except Exception:
                await safe_send_ctx(ctx, "No champions match your search.")
            return

        # Instantiate pager defensively (support multiple constructor shapes)
        try:
            try:
                pager = CDTPagesMenu(pages, author=ctx.author)
            except TypeError:
                try:
                    pager = CDTPagesMenu(pages, ctx.author)
                except TypeError:
                    pager = CDTPagesMenu(pages)
                    if hasattr(pager, "author"):
                        try:
                            pager.author = ctx.author
                        except Exception:
                            pass

            # Merge brand buttons if possible
            try:
                brand_view = CDTEmbed.brand_view()
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
            log.exception("Failed to instantiate/start CDTPagesMenu for champion search")
            # Last resort: send first embed or compact summary
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
                    await safe_send_ctx(ctx, "Failed to display champion search results.")
                    return

    # -----------------------------
    # Abilities (simple wrapper)
    # -----------------------------
    @champ.command(name="abilities")
    async def champ_abilities(self, ctx, *, name: str):
        """
        Show champion abilities. Uses CDTEmbed.abilities_embed if available.
        """
        if not await self._require_parent(ctx):
            return

        cache = getattr(self.parent, "cache", None)
        champ_obj = None
        try:
            if cache:
                # try slug or name resolution
                try:
                    champ_obj = cache.get_champion(name)
                except Exception:
                    # fallback: search by name
                    for c in (cache.get_all_champions() or []):
                        if (c.get("name") or "").lower() == name.lower() or (c.get("slug") or "").lower() == name.lower():
                            champ_obj = c
                            break
        except Exception:
            champ_obj = None

        if not champ_obj:
            await safe_send_ctx(ctx, "Champion not found.")
            return

        # Try to use CDTEmbed.abilities_embed if present
        try:
            if hasattr(CDTEmbed, "abilities_embed"):
                emb = CDTEmbed.abilities_embed(ctx, champ_obj)
                if emb:
                    await ctx.send(embed=emb)
                    return
            # Fallback: simple abilities message if embed helper missing
            abilities = champ_obj.get("abilities") or champ_obj.get("ability_list") or []
            if not abilities:
                await safe_send_ctx(ctx, "Abilities unavailable.")
                return
            desc_lines = []
            for a in abilities:
                try:
                    title = a.get("name") or a.get("title") or "Ability"
                    text = a.get("description") or a.get("desc") or ""
                    desc_lines.append(f"**{title}** — {text}")
                except Exception:
                    continue
            desc = "\n\n".join(desc_lines) or "Abilities unavailable."
            try:
                await ctx.send(embed=CDTEmbed.embed(ctx.author, title=f"{champ_obj.get('name') or champ_obj.get('slug')}'s Abilities", description=desc))
            except Exception:
                await safe_send_ctx(ctx, desc)
            return
        except Exception:
            log.exception("Failed to render abilities for %s", name)
            await safe_send_ctx(ctx, "Abilities unavailable.")
            return

    # -----------------------------
    # Info (simple champion info)
    # -----------------------------
    @champ.command(name="info")
    async def champ_info(self, ctx, *, name: str):
        """
        Show basic champion info (class, tags, role).
        """
        if not await self._require_parent(ctx):
            return

        cache = getattr(self.parent, "cache", None)
        champ_obj = None
        try:
            if cache:
                try:
                    champ_obj = cache.get_champion(name)
                except Exception:
                    for c in (cache.get_all_champions() or []):
                        if (c.get("name") or "").lower() == name.lower() or (c.get("slug") or "").lower() == name.lower():
                            champ_obj = c
                            break
        except Exception:
            champ_obj = None

        if not champ_obj:
            await safe_send_ctx(ctx, "Champion not found.")
            return

        try:
            name_text = champ_obj.get("name") or champ_obj.get("slug") or "Unknown"
            cls = champ_obj.get("class") or "Unknown"
            tags = ", ".join(champ_obj.get("tags") or []) or "None"
            role = champ_obj.get("role") or champ_obj.get("archetype") or "Unknown"
            desc = f"**Class:** {cls}\n**Role:** {role}\n**Tags:** {tags}"
            await ctx.send(embed=CDTEmbed.embed(ctx.author, title=f"{name_text} — Info", description=desc))
        except Exception:
            log.exception("Failed to render champion info for %s", name)
            await safe_send_ctx(ctx, "Champion info unavailable.")
