# Path: mcoc/slash/champions.py
# File-Version: 1.0
# File-Id: 6a3a5e88-2388-4157-8016-4f4394aceefc
# Purpose: Provide slash command handler for MCOC champion information commands.
# Public-API: _ChampionGroup
# Last-Modified: 2026-09-01
# Changelog:
#   1.0 2026-09-01  Initial stabilized API header
import logging
from typing import Optional, Any, List
from discord import app_commands
from redbot.core import commands

log = logging.getLogger("red.mcoc.slash.champions")

# Import shared helpers from common/champion_helpers.py
from ..common.helpers.champions import (
    resolve_champion,
    safe_respond_interaction,
    lookup_stat,
    add_page_footers,
    CDTEmbed,
    CDTConfirm,
    CDTPagesMenu,
)

# Keep the app_commands.Group lightweight and import-neutral
class _ChampionGroup(app_commands.Group):
    def __init__(self, core: Any):
        super().__init__(name="champ", description="Champion information commands")
        self.core = core
        self._init_failed = False

    # Helpers to access cache/index safely
    def _cache(self):
        return getattr(self.core, "cache", None)

    def _index(self):
        try:
            return getattr(self.core, "cache", None).index
        except Exception:
            return None

    # Autocomplete wrappers (prefer index methods, fallback to simple scan)
    async def champion_autocomplete(self, interaction, current: str):
        idx = self._index()
        cur = (current or "").lower()
        if idx and hasattr(idx, "champion_autocomplete"):
            try:
                return await idx.champion_autocomplete(interaction, cur)
            except Exception:
                log.exception("champion_autocomplete failed in CacheIndex")
        # fallback: build simple choices
        try:
            cache = self._cache()
            champs = cache.get_all_champions() if cache else []
            matches = []
            for c in champs:
                name = c.get("name") or ""
                cid = str(c.get("id") or c.get("slug") or "")
                if cur in name.lower() or cur in cid.lower():
                    matches.append(app_commands.Choice(name=name, value=cid))
                    if len(matches) >= 25:
                        break
            return matches
        except Exception:
            return []

    async def tag_autocomplete(self, interaction, current: str):
        idx = self._index()
        if idx and hasattr(idx, "tag_autocomplete"):
            try:
                return await idx.tag_autocomplete(interaction, current or "")
            except Exception:
                log.exception("tag_autocomplete failed in CacheIndex")
        return []

    async def ability_autocomplete(self, interaction, current: str):
        idx = self._index()
        if idx and hasattr(idx, "ability_autocomplete"):
            try:
                return await idx.ability_autocomplete(interaction, current or "")
            except Exception:
                log.exception("ability_autocomplete failed in CacheIndex")
        return []

    async def immunity_autocomplete(self, interaction, current: str):
        idx = self._index()
        if idx and hasattr(idx, "immunity_autocomplete"):
            try:
                return await idx.immunity_autocomplete(interaction, current or "")
            except Exception:
                log.exception("immunity_autocomplete failed in CacheIndex")
        return []

    # -------------------------
    # Commands
    # -------------------------
    @app_commands.command(name="info", description="Show champion information")
    @app_commands.autocomplete(champion=champion_autocomplete)
    async def info(self, interaction, champion: str):
        champ = resolve_champion(self._cache(), champion)
        if not champ:
            await safe_respond_interaction(interaction, content=f"Champion `{champion}` not found.", ephemeral=True)
            return
        try:
            embed = await CDTEmbed.champions_embed(interaction, champ)
            await safe_respond_interaction(interaction, embed=embed)
        except Exception:
            log.exception("Failed to build champion embed")
            await safe_respond_interaction(interaction, content=champ.get("name", "Unknown"), ephemeral=True)

    @app_commands.command(name="abilities", description="Show champion abilities")
    @app_commands.autocomplete(champion=champion_autocomplete)
    async def abilities(self, interaction, champion: str):
        champ = resolve_champion(self._cache(), champion)
        if not champ:
            await safe_respond_interaction(interaction, content=f"Champion `{champion}` not found.", ephemeral=True)
            return
        try:
            embed = await CDTEmbed.champions_embed(interaction, champ)
            await safe_respond_interaction(interaction, embed=embed)
        except Exception:
            log.exception("Failed to build abilities embed")
            await safe_respond_interaction(interaction, content="Abilities unavailable.", ephemeral=True)

    @app_commands.command(name="synergies", description="Show champion synergies")
    @app_commands.autocomplete(champion=champion_autocomplete)
    async def synergies(self, interaction, champion: str):
        champ = resolve_champion(self._cache(), champion)
        if not champ:
            await safe_respond_interaction(interaction, content=f"Champion `{champion}` not found.", ephemeral=True)
            return
        try:
            synergies = champ.get("synergies", []) or []
            embed = await CDTEmbed.synergy_embed(interaction, champ, synergies)
            await safe_respond_interaction(interaction, embed=embed)
        except Exception:
            log.exception("Failed to build synergies embed")
            await safe_respond_interaction(interaction, content="Synergies unavailable.", ephemeral=True)

    @app_commands.command(name="tags", description="List champions with a specific tag")
    @app_commands.autocomplete(tag=tag_autocomplete)
    async def tags(self, interaction, tag: str):
        cache = self._cache()
        champs = cache.get_all_champions() if cache else []
        matches = [c for c in champs if tag in (c.get("tags") or [])]
        if not matches:
            await safe_respond_interaction(interaction, content=f"No champions found with tag `{tag}`.", ephemeral=True)
            return
        try:
            embed = await CDTEmbed.tag_list_embed(interaction, tag, matches)
            await safe_respond_interaction(interaction, embed=embed)
        except Exception:
            await safe_respond_interaction(interaction, content=f"{len(matches)} champions found for tag `{tag}`.", ephemeral=True)

    @app_commands.command(name="stats", description="Show champion stats")
    @app_commands.autocomplete(champion=champion_autocomplete)
    async def stats(self, interaction, champion: str):
        champ = resolve_champion(self._cache(), champion)
        if not champ:
            await safe_respond_interaction(interaction, content=f"Champion `{champion}` not found.", ephemeral=True)
            return
        stats = champ.get("stats", {}) or {}
        if not stats:
            await safe_respond_interaction(interaction, content="No stats available for this champion.", ephemeral=True)
            return
        try:
            import discord
            embed = discord.Embed(title=f"{champ.get('name','Unknown')} — Stats", color=discord.Color.gold())
            for rarity, ranks in stats.items():
                for rank, values in ranks.items():
                    atk = values.get("attack", "N/A")
                    hp = values.get("health", "N/A")
                    embed.add_field(name=f"{rarity}★ Rank {rank}", value=f"Attack: {atk}\nHealth: {hp}", inline=False)
            await safe_respond_interaction(interaction, embed=embed)
        except Exception:
            log.exception("Failed to build stats embed")
            await safe_respond_interaction(interaction, content="Stats unavailable.", ephemeral=True)

    @app_commands.command(name="search", description="Search champions using filters")
    @app_commands.describe(
        champ_name="Name contains...",
        champ_class="Champion class (cosmic, tech, mutant, skill, mystic, science)",
        champ_rarity="Filter by rarity (1–7 stars)",
        champ_tag="Filter by tag",
        champ_ability="Filter by ability",
        champ_immunity="Filter by immunity",
        champ_synergy="Filter by synergy partner"
    )
    @app_commands.rename(
        champ_name="name",
        champ_class="class",
        champ_rarity="rarity",
        champ_tag="tag",
        champ_ability="ability",
        champ_immunity="immunity",
        champ_synergy="synergy"
    )
    @app_commands.autocomplete(
        champ_tag=tag_autocomplete,
        champ_ability=ability_autocomplete,
        champ_immunity=immunity_autocomplete,
        champ_synergy=champion_autocomplete
    )
    async def search(
        self,
        interaction,
        champ_name: Optional[str] = None,
        champ_class: Optional[str] = None,
        champ_rarity: Optional[int] = None,
        champ_tag: Optional[str] = None,
        champ_ability: Optional[str] = None,
        champ_immunity: Optional[str] = None,
        champ_synergy: Optional[str] = None
    ):
        idx = self._index()
        champs = idx.champions if idx and hasattr(idx, "champions") else (self._cache().get_all_champions() if self._cache() else [])
        results = []
        for champ in champs:
            try:
                if champ_name and champ_name.lower() not in (champ.get("name") or "").lower():
                    continue
                if champ_class and (champ.get("class") or "").lower() != champ_class.lower():
                    continue
                if champ_rarity and champ_rarity not in (champ.get("rarities") or []):
                    continue
                if champ_tag and champ_tag not in (champ.get("tags") or []):
                    continue
                if champ_ability:
                    abilities = champ.get("abilities") or []
                    found = False
                    for a in abilities:
                        if isinstance(a, dict):
                            if champ_ability == a.get("id") or champ_ability == a.get("name"):
                                found = True
                                break
                        else:
                            if str(a) == str(champ_ability):
                                found = True
                                break
                    if not found:
                        continue
                if champ_immunity and champ_immunity not in (champ.get("immunities") or []):
                    continue
                if champ_synergy:
                    synergies = champ.get("synergies", []) or []
                    partner_ids = [s.get("partner") for s in synergies if isinstance(s, dict)]
                    if champ_synergy not in partner_ids:
                        continue
                results.append(champ)
            except Exception:
                continue

        if not results:
            await safe_respond_interaction(interaction, content="No champions match your search filters.", ephemeral=True)
            return

        # Build pages and send with pagination view if available
        pages = []
        try:
            for champ in results:
                pages.append(await CDTEmbed.champions_embed(interaction, champ))
            pages = add_page_footers(pages)
            await safe_respond_interaction(interaction, embed=pages[0], followup=False)
            # attach view via direct tree response (discord will accept view on initial response)
            await interaction.response.edit_message(embed=pages[0], view=CDTPagesMenu(pages, interaction.user))
        except Exception:
            names = [c.get("name", "Unknown") for c in results][:50]
            await safe_respond_interaction(interaction, content=f"Matches ({len(results)}): {', '.join(names)}", ephemeral=True)


    @app_commands.command(name="calcstats", description="Calculate champion stats for a given rarity, rank, sig, and ascension")
    @app_commands.describe(
        champ_rarity="Star rarity (1–7)",
        champ_rank="Rank (1–5)",
        champ_sig="Signature level (0–200)",
        champ_ascended="Ascension level (0–5)",
        use_roster="Use your roster entry instead of manual inputs"
    )
    @app_commands.autocomplete(champion=champion_autocomplete)
    async def calcstats(
        self,
        interaction,
        champion: str,
        champ_rarity: Optional[int] = None,
        champ_rank: Optional[int] = None,
        champ_sig: Optional[int] = None,
        champ_ascended: int = 0,
        use_roster: bool = False
    ):
        champ = resolve_champion(self._cache(), champion)
        if not champ:
            await safe_respond_interaction(interaction, content=f"Champion `{champion}` not found.", ephemeral=True)
            return

        if use_roster:
            roster_sub = getattr(self.core, "roster_slash", None)
            try:
                roster = roster_sub.users.list_roster(interaction.user.id) if roster_sub else []
            except Exception:
                roster = []
            entry = next((e for e in roster if e.get("champion") == (champ.get("id") or champ.get("slug"))), None)
            if not entry:
                await safe_respond_interaction(interaction, content="You do not have this champion in your roster.", ephemeral=True)
                return
            champ_rarity = entry.get("rarity")
            champ_rank = entry.get("rank")
            champ_sig = entry.get("sig")
            champ_ascended = entry.get("ascended", 0)

        if champ_rarity is None or champ_rank is None:
            await safe_respond_interaction(interaction, content="You must specify rarity and rank (or enable `use_roster`).", ephemeral=True)
            return

        statline = lookup_stat(champ, champ_rarity, champ_rank, champ_ascended)
        if not statline:
            await safe_respond_interaction(interaction, content=f"No stat data available for {champ_rarity}★ {champ.get('name','Unknown')}.", ephemeral=True)
            return

        try:
            import discord
            embed = discord.Embed(
                title=f"{champ.get('name','Unknown')} — {champ_rarity}★ Rank {champ_rank}{' Ascended ' + str(champ_ascended) if champ_ascended else ''}",
                color=discord.Color.gold()
            )
            embed.add_field(name="Attack", value=statline.get("attack", "N/A"))
            embed.add_field(name="Health", value=statline.get("health", "N/A"))
            if champ_sig is not None:
                embed.add_field(name="Signature Level", value=str(champ_sig))
            thumb = (champ.get("images") or {}).get("portrait") or champ.get("portrait") or ""
            if thumb:
                try:
                    embed.set_thumbnail(url=thumb)
                except Exception:
                    pass
            await safe_respond_interaction(interaction, embed=embed)
        except Exception:
            log.exception("Failed to build calcstats embed")
            await safe_respond_interaction(interaction, content="Failed to calculate stats.", ephemeral=True)


class ChampionSlashCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._group: Optional[_ChampionGroup] = None

    async def cog_load(self):
        core = getattr(self.bot, "mcoc_core", None) or self.bot.get_cog("MCOC") or self.bot.get_cog("MCOCPrefix")
        try:
            self._group = _ChampionGroup(core or self.bot)
            try:
                self.bot.tree.add_command(self._group)
            except Exception:
                log.exception("Failed to add Champion group to tree")
        except Exception:
            log.exception("Failed to initialize Champion group")

    async def cog_unload(self):
        try:
            if self._group:
                self.bot.tree.remove_command(self._group.name)
        except Exception:
            log.exception("Failed to remove Champion group from tree")

    @property
    def group(self) -> Optional[_ChampionGroup]:
        return self._group


async def setup(bot):
    try:
        await bot.add_cog(ChampionSlashCog(bot))
    except Exception:
        log.exception("Failed to add ChampionSlashCog")
