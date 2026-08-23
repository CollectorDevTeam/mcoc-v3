# mcoc/prefix/champions_prefix.py
import logging
from typing import Optional, Any
from redbot.core import commands

log = logging.getLogger("red.mcoc.prefix.champions")

from ..common.champion_helpers import (
    resolve_champion,
    safe_send_ctx,
    lookup_stat,
    add_page_footers,
)

# Keep the original Cog so it can still be loaded independently for testing,
# but we will also provide a registrar function to attach these commands under
# another group (e.g., ///mcoc champ).
class ChampionsPrefix(commands.Cog):
    """
    Prefix (text) commands for champion lookups and utilities.
    Uses shared helpers from common/champion_helpers.py.
    """

    is_mcoc_prefix = True
    mcoc_version = "3.0.0"

    def __init__(self, bot_or_parent: Any):
        if hasattr(bot_or_parent, "bot") and hasattr(bot_or_parent, "cache"):
            self.parent = bot_or_parent
            self.bot = bot_or_parent.bot
        else:
            self.parent = None
            self.bot = bot_or_parent

    async def _require_parent(self, ctx) -> bool:
        # Try to attach core dynamically if possible
        if not getattr(self, "parent", None):
            try:
                core = getattr(self.bot, "mcoc_core", None) or self.bot.get_cog("MCOC")
                if core:
                    self.parent = core
                    return True
            except Exception:
                pass
            try:
                await ctx.send("MCOC core not attached; cache and API unavailable.")
            except Exception:
                pass
            return False
        return True

    @commands.group(name="champ", invoke_without_command=True)
    async def champ(self, ctx):
        await safe_send_ctx(ctx, "Use subcommands: `info`, `abilities`, `synergies`, `tags`, `stats`, `search`, `calcstats`.")

    @champ.command(name="info")
    async def champ_info(self, ctx, *, champion: str):
        if not await self._require_parent(ctx):
            return
        champ = resolve_champion(self.parent.cache, champion)
        if not champ:
            await safe_send_ctx(ctx, f"Champion `{champion}` not found.")
            return
        try:
            from ..common.embeds import champion_embed
            embed = await champion_embed(ctx, champ)
            await safe_send_ctx(ctx, embed=embed)
        except Exception:
            log.exception("champ info failed")
            await safe_send_ctx(ctx, f"{champ.get('name','Unknown')}")

    @champ.command(name="abilities")
    async def champ_abilities(self, ctx, *, champion: str):
        if not await self._require_parent(ctx):
            return
        champ = resolve_champion(self.parent.cache, champion)
        if not champ:
            await safe_send_ctx(ctx, f"Champion `{champion}` not found.")
            return
        try:
            from ..common.embeds import abilities_embed
            embed = await abilities_embed(ctx, champ)
            await safe_send_ctx(ctx, embed=embed)
        except Exception:
            log.exception("champ abilities failed")
            await safe_send_ctx(ctx, "Abilities unavailable.")

    @champ.command(name="synergies")
    async def champ_synergies(self, ctx, *, champion: str):
        if not await self._require_parent(ctx):
            return
        champ = resolve_champion(self.parent.cache, champion)
        if not champ:
            await safe_send_ctx(ctx, f"Champion `{champion}` not found.")
            return
        try:
            from ..common.embeds import synergy_embed
            synergies = champ.get("synergies", []) or []
            embed = await synergy_embed(ctx, champ, synergies)
            await safe_send_ctx(ctx, embed=embed)
        except Exception:
            log.exception("champ synergies failed")
            await safe_send_ctx(ctx, "Synergies unavailable.")

    @champ.command(name="tags")
    async def champ_tags(self, ctx, *, tag: str):
        if not await self._require_parent(ctx):
            return
        try:
            cache = getattr(self.parent, "cache", None)
            champs = cache.get_all_champions() if cache else []
            matches = [c for c in champs if tag in (c.get("tags") or [])]
            if not matches:
                await safe_send_ctx(ctx, f"No champions found with tag `{tag}`.")
                return
            from ..common.embeds import tag_list_embed
            embed = await tag_list_embed(ctx, tag, matches)
            await safe_send_ctx(ctx, embed=embed)
        except Exception:
            log.exception("champ tags failed")
            await safe_send_ctx(ctx, "Tag search failed.")

    @champ.command(name="stats")
    async def champ_stats(self, ctx, *, champion: str):
        if not await self._require_parent(ctx):
            return
        champ = resolve_champion(self.parent.cache, champion)
        if not champ:
            await safe_send_ctx(ctx, f"Champion `{champion}` not found.")
            return
        stats = champ.get("stats", {}) or {}
        if not stats:
            await safe_send_ctx(ctx, "No stats available for this champion.")
            return
        try:
            import discord
            embed = discord.Embed(title=f"{champ.get('name','Unknown')} — Stats", color=discord.Color.gold())
            for rarity, ranks in stats.items():
                for rank, values in ranks.items():
                    atk = values.get("attack", "N/A")
                    hp = values.get("health", "N/A")
                    embed.add_field(name=f"{rarity}★ Rank {rank}", value=f"Attack: {atk}\nHealth: {hp}", inline=False)
            await safe_send_ctx(ctx, embed=embed)
        except Exception:
            log.exception("champ stats failed")
            await safe_send_ctx(ctx, "Failed to build stats.")

    @champ.command(name="search")
    async def champ_search(self, ctx, *, query: str):
        if not await self._require_parent(ctx):
            return
        try:
            cache = getattr(self.parent, "cache", None)
            champs = cache.get_all_champions() if cache else []
            q = query.lower()
            results = []
            for c in champs:
                try:
                    name = (c.get("name") or "").lower()
                    slug = str(c.get("id") or c.get("slug") or "").lower()
                    tags = [t.lower() for t in (c.get("tags") or []) if isinstance(t, str)]
                    cls = (c.get("class") or "").lower()
                    if q in name or q in slug or q in cls or q in tags:
                        results.append(c)
                except Exception:
                    continue
            if not results:
                await safe_send_ctx(ctx, "No champions match your search.")
                return
            names = [r.get("name", "Unknown") for r in results][:20]
            await safe_send_ctx(ctx, f"Matches ({len(results)}): {', '.join(names)}")
        except Exception:
            log.exception("champ search failed")
            await safe_send_ctx(ctx, "Search failed.")

    @champ.command(name="calcstats")
    async def champ_calcstats(self, ctx, champion: str, rarity: Optional[int] = None, rank: Optional[int] = None, sig: Optional[int] = None, ascended: int = 0, use_roster: bool = False):
        if not await self._require_parent(ctx):
            return
        champ = resolve_champion(self.parent.cache, champion)
        if not champ:
            await safe_send_ctx(ctx, f"Champion `{champion}` not found.")
            return

        if use_roster:
            roster_sub = getattr(self.parent, "roster_prefix", None) or getattr(self.parent, "roster_slash", None)
            try:
                roster = roster_sub.users.list_roster(ctx.author.id) if roster_sub else []
            except Exception:
                roster = []
            entry = next((e for e in roster if e.get("champion") == (champ.get("id") or champ.get("slug"))), None)
            if not entry:
                await safe_send_ctx(ctx, "You do not have this champion in your roster.")
                return
            rarity = entry.get("rarity")
            rank = entry.get("rank")
            sig = entry.get("sig")
            ascended = entry.get("ascended", 0)

        if rarity is None or rank is None:
            await safe_send_ctx(ctx, "You must specify rarity and rank (or enable use_roster).")
            return

        statline = lookup_stat(champ, rarity, rank, ascended)
        if not statline:
            await safe_send_ctx(ctx, f"No stat data available for {rarity}★ {champ.get('name','Unknown')}.")
            return

        try:
            import discord
            embed = discord.Embed(
                title=f"{champ.get('name','Unknown')} — {rarity}★ Rank {rank}{' Ascended ' + str(ascended) if ascended else ''}",
                color=discord.Color.gold()
            )
            embed.add_field(name="Attack", value=statline.get("attack", "N/A"))
            embed.add_field(name="Health", value=statline.get("health", "N/A"))
            if sig is not None:
                embed.add_field(name="Signature Level", value=str(sig))
            thumb = (champ.get("images") or {}).get("portrait") or champ.get("portrait") or ""
            if thumb:
                try:
                    embed.set_thumbnail(url=thumb)
                except Exception:
                    pass
            await safe_send_ctx(ctx, embed=embed)
        except Exception:
            log.exception("calcstats embed failed")
            await safe_send_ctx(ctx, "Failed to calculate stats.")


# Registrar: attach these commands under another group (e.g., ///mcoc champ)
def register_with_group(group: commands.Group, parent_getter):
    """
    Attach champion prefix commands to the provided `group` (a commands.Group).
    parent_getter is a callable returning the core/parent object (or None).
    """

    # local imports for embed builders (keeps module import light)
    from ..common.embeds import champion_embed, abilities_embed, synergy_embed, tag_list_embed

    # info
    async def _info(ctx, *, champion: str):
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; cache and API unavailable.")
            return
        cache = getattr(parent, "cache", None)
        champ = resolve_champion(cache, champion)
        if not champ:
            await ctx.send(f"Champion `{champion}` not found.")
            return
        try:
            embed = await champion_embed(ctx, champ)
            await ctx.send(embed=embed)
        except Exception:
            log.exception("register info failed")
            await ctx.send(champ.get("name", "Unknown"))

    _safe_add(cmd_name="info", func=_info)

    # abilities
    async def _abilities(ctx, *, champion: str):
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; cache and API unavailable.")
            return
        cache = getattr(parent, "cache", None)
        champ = resolve_champion(cache, champion)
        if not champ:
            await ctx.send(f"Champion `{champion}` not found.")
            return
        try:
            embed = await abilities_embed(ctx, champ)
            await ctx.send(embed=embed)
        except Exception:
            log.exception("register abilities failed")
            await ctx.send("Abilities unavailable.")

    _safe_add(cmd_name="abilities", func=_abilities)

    # synergies
    async def _synergies(ctx, *, champion: str):
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; cache and API unavailable.")
            return
        cache = getattr(parent, "cache", None)
        champ = resolve_champion(cache, champion)
        if not champ:
            await ctx.send(f"Champion `{champion}` not found.")
            return
        try:
            synergies = champ.get("synergies", []) or []
            embed = await synergy_embed(ctx, champ, synergies)
            await ctx.send(embed=embed)
        except Exception:
            log.exception("register synergies failed")
            await ctx.send("Synergies unavailable.")

    _safe_add(cmd_name="synergies", func=_synergies)

    # tags
    async def _tags(ctx, *, tag: str):
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; cache and API unavailable.")
            return
        cache = getattr(parent, "cache", None)
        champs = cache.get_all_champions() if cache else []
        matches = [c for c in champs if tag in (c.get("tags") or [])]
        if not matches:
            await ctx.send(f"No champions found with tag `{tag}`.")
            return
        try:
            embed = await tag_list_embed(ctx, tag, matches)
            await ctx.send(embed=embed)
        except Exception:
            log.exception("register tags failed")
            await ctx.send(f"{len(matches)} champions found for tag `{tag}`.")

    _safe_add(cmd_name="tags", func=_tags)

    # search (simple)
    async def _search(ctx, *, query: str):
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; cache and API unavailable.")
            return
        cache = getattr(parent, "cache", None)
        champs = cache.get_all_champions() if cache else []
        q = (query or "").lower()
        results = []
        for c in champs:
            try:
                if q in (c.get("name") or "").lower() or q in str(c.get("id") or c.get("slug") or "").lower():
                    results.append(c)
            except Exception:
                continue
        if not results:
            await ctx.send("No champions match your search.")
            return
        names = [r.get("name", "Unknown") for r in results][:20]
        await ctx.send(f"Matches ({len(results)}): {', '.join(names)}")

    _safe_add(cmd_name="search", func=_search)

    # calcstats (simple wrapper)
    async def _calcstats(ctx, champion: str, rarity: Optional[int] = None, rank: Optional[int] = None, sig: Optional[int] = None, ascended: int = 0, use_roster: bool = False):
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; cache and API unavailable.")
            return
        cache = getattr(parent, "cache", None)
        champ = resolve_champion(cache, champion)
        if not champ:
            await ctx.send(f"Champion `{champion}` not found.")
            return

        if use_roster:
            roster_sub = getattr(parent, "roster_prefix", None) or getattr(parent, "roster_slash", None)
            try:
                roster = roster_sub.users.list_roster(ctx.author.id) if roster_sub else []
            except Exception:
                roster = []
            entry = next((e for e in roster if e.get("champion") == (champ.get("id") or champ.get("slug"))), None)
            if not entry:
                await ctx.send("You do not have this champion in your roster.")
                return
            rarity = entry.get("rarity")
            rank = entry.get("rank")
            sig = entry.get("sig")
            ascended = entry.get("ascended", 0)

        if rarity is None or rank is None:
            await ctx.send("You must specify rarity and rank (or enable use_roster).")
            return

        statline = lookup_stat(champ, rarity, rank, ascended)
        if not statline:
            await ctx.send(f"No stat data available for {rarity}★ {champ.get('name','Unknown')}.")
            return

        try:
            import discord
            embed = discord.Embed(
                title=f"{champ.get('name','Unknown')} — {rarity}★ Rank {rank}{' Ascended ' + str(ascended) if ascended else ''}",
                color=discord.Color.gold()
            )
            embed.add_field(name="Attack", value=statline.get("attack", "N/A"))
            embed.add_field(name="Health", value=statline.get("health", "N/A"))
            if sig is not None:
                embed.add_field(name="Signature Level", value=str(sig))
            thumb = (champ.get("images") or {}).get("portrait") or champ.get("portrait") or ""
            if thumb:
                try:
                    embed.set_thumbnail(url=thumb)
                except Exception:
                    pass
            await ctx.send(embed=embed)
        except Exception:
            log.exception("register calcstats failed")
            await ctx.send("Failed to calculate stats.")

    def _safe_add(cmd_name, func):
        try:
            if group.get_command(cmd_name):
                log.debug("Command %s already exists; skipping", cmd_name)
                return
        except Exception:
            pass
        group.command(name=cmd_name)(func)

# Note: remove or comment out the module-level setup if you do not want this file
# to register a standalone ChampionsPrefix cog (which would create a top-level ///champ).
# If you still want the standalone cog for testing, keep the setup below; otherwise
# remove it to avoid duplicate top-level commands.

# async def setup(bot):
#     try:
#         await bot.add_cog(ChampionsPrefix(bot))
#     except Exception:
#         log.exception("Failed to add ChampionsPrefix")
