# Path: mcoc/slash/champions.py
# File-Version: 1.0
# File-Id: 6a3a5e88-2388-4157-8016-4f4394aceefc
# Purpose: Provide slash command handler for MCOC champion information commands.
# Public-API: _ChampionGroup
# Last-Modified: 2026-09-01
# Used-By: mcoc/common/components/componentsV2.py, mcoc/common/helpers/champions.py
# Changelog:
#   1.0 2026-09-01  Initial stabilized API header
import logging
from typing import Optional, Any, List
from redbot.core import commands
from redbot.core import app_commands

log = logging.getLogger("red.mcoc.slash.champions")

# Import shared helpers from common/champion_helpers.py
from ..common.helpers.champions import (
    resolve_champion,
    safe_respond_interaction,
    lookup_stat,
    add_page_footers,
    get_cocpit_champion_data,
    get_cocpit_cached_abilities,
    get_cocpit_cached_stats,
    build_cocpit_ability_lines,
    build_cocpit_core_ability_fields,
    build_cocpit_synergy_lines,
    build_cocpit_synergy_intersection_lines,
    build_cocpit_synergy_activation_sets,
    build_champion_ability_lines,
    build_champion_synergy_lines,
    chunk_text_blocks,
    chunk_embed_fields,
    _champion_matches_filters,
)
from ..common.components.componentsV2 import CDTEmbed, CDTPagesMenu

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

    def _normalize_token(self, value: Any) -> str:
        return "".join(ch for ch in str(value or "").lower() if ch.isalnum())

    def _apply_source_footer(self, embeds: List[Any], source_label: str) -> List[Any]:
        if not embeds:
            return embeds
        for emb in embeds:
            try:
                CDTEmbed.set_footer(None, emb, text=f"Source: {source_label}")
            except Exception:
                continue
        return embeds

    def _iter_cache_choices(self, field: str) -> List[str]:
        values: List[str] = []
        cache = self._cache()
        champs = cache.get_all_champions() if cache and hasattr(cache, "get_all_champions") else []
        seen = set()
        for champ in champs or []:
            if not isinstance(champ, dict):
                continue
            for item in champ.get(field) or []:
                if isinstance(item, dict):
                    candidate = item.get("name") or item.get("id")
                else:
                    candidate = item
                text = str(candidate or "").strip()
                if not text:
                    continue
                key = text.lower()
                if key in seen:
                    continue
                seen.add(key)
                values.append(text)
        return sorted(values)

    async def tag_autocomplete(self, interaction, current: str):
        idx = self._index()
        cur = (current or "").lower()
        if idx and hasattr(idx, "tag_autocomplete"):
            try:
                return await idx.tag_autocomplete(interaction, current or "")
            except Exception:
                log.exception("tag_autocomplete failed in CacheIndex")
        try:
            tags = self._iter_cache_choices("tags")
            return [app_commands.Choice(name=t, value=t) for t in tags if not cur or cur in t.lower()][:25]
        except Exception:
            return []

    async def ability_autocomplete(self, interaction, current: str):
        idx = self._index()
        cur = (current or "").lower()
        if idx and hasattr(idx, "ability_autocomplete"):
            try:
                return await idx.ability_autocomplete(interaction, current or "")
            except Exception:
                log.exception("ability_autocomplete failed in CacheIndex")
        try:
            abilities = self._iter_cache_choices("abilities")
            return [app_commands.Choice(name=a, value=a) for a in abilities if not cur or cur in a.lower()][:25]
        except Exception:
            return []

    async def immunity_autocomplete(self, interaction, current: str):
        idx = self._index()
        cur = (current or "").lower()
        if idx and hasattr(idx, "immunity_autocomplete"):
            try:
                return await idx.immunity_autocomplete(interaction, current or "")
            except Exception:
                log.exception("immunity_autocomplete failed in CacheIndex")
        try:
            immunities = self._iter_cache_choices("immunities")
            return [app_commands.Choice(name=i, value=i) for i in immunities if not cur or cur in i.lower()][:25]
        except Exception:
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
            embed = CDTEmbed.champion_embed(interaction, champ)
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
            cocpit_cached = get_cocpit_cached_abilities(self.core, champ)
            field_source = None
            source_label = "MCOCHub cache"
            if cocpit_cached:
                source_label = "Cocpit cache"
                field_source = {
                    "coreAbilities": {
                        item.get("title") or "Core Ability": [{"id": item.get("id"), "text": item.get("text")}]
                        for item in (cocpit_cached.get("core_abilities") or [])
                        if isinstance(item, dict)
                    }
                }
            else:
                field_source = await get_cocpit_champion_data(self.core, champ)
                if field_source:
                    source_label = "Cocpit live"

            fields = build_cocpit_core_ability_fields(field_source or {})
            if fields:
                pages = []
                for page_fields in chunk_embed_fields(fields):
                    embed = CDTEmbed.embed(interaction, title=f"{champ.get('name','Unknown')} Core Abilities", description="")
                    for field_name, field_value in page_fields:
                        embed.add_field(name=field_name, value=field_value, inline=False)
                    pages.append(embed)
                pages = self._apply_source_footer(pages, source_label)
                await safe_respond_interaction(interaction, embed=pages[0], view=CDTPagesMenu(pages, author=interaction.user))
                return

            lines = build_cocpit_ability_lines(field_source) if field_source else []
            if not lines:
                lines = build_champion_ability_lines(champ, cache=self._cache())
                source_label = "MCOCHub cache"
            if not lines:
                await safe_respond_interaction(interaction, content="Abilities unavailable.", ephemeral=True)
                return
            pages = [CDTEmbed.embed(interaction, title=f"{champ.get('name','Unknown')} Abilities", description=page) for page in chunk_text_blocks(lines)]
            pages = self._apply_source_footer(pages, source_label)
            await safe_respond_interaction(interaction, embed=pages[0], view=CDTPagesMenu(pages, author=interaction.user))
        except Exception:
            log.exception("Failed to build abilities embed")
            await safe_respond_interaction(interaction, content="Abilities unavailable.", ephemeral=True)

    @app_commands.command(name="synergies", description="Show champion synergies")
    @app_commands.autocomplete(champion=champion_autocomplete)
    async def synergies(self, interaction, champion: str, teammates: Optional[str] = None):
        champ = resolve_champion(self._cache(), champion)
        if not champ:
            await safe_respond_interaction(interaction, content=f"Champion `{champion}` not found.", ephemeral=True)
            return
        try:
            cocpit = await get_cocpit_champion_data(self.core, champ)
            cache = self._cache()
            team = [champ]
            seen = {self._normalize_token(champ.get("id") or champ.get("slug") or champ.get("name"))}
            if teammates:
                for token in [part.strip() for part in teammates.split(",") if part.strip()]:
                    resolved = resolve_champion(cache, token)
                    if not resolved:
                        continue
                    key = self._normalize_token(resolved.get("id") or resolved.get("slug") or resolved.get("name"))
                    if key in seen:
                        continue
                    seen.add(key)
                    team.append(resolved)
                    if len(team) >= 5:
                        break

            if cocpit and len(team) > 1:
                active_lines, inactive_lines = build_cocpit_synergy_activation_sets(champ, team, cocpit, cache=cache)
                pages = []
                if active_lines:
                    pages.extend([CDTEmbed.embed(interaction, title=f"Activated Synergies: {champ.get('name','Unknown')}", description=page) for page in chunk_text_blocks(active_lines)])
                if inactive_lines:
                    pages.extend([CDTEmbed.embed(interaction, title=f"Unactivated Synergies: {champ.get('name','Unknown')}", description=page) for page in chunk_text_blocks(inactive_lines)])
                if not pages:
                    await safe_respond_interaction(interaction, content="No synergy cards available for this team.", ephemeral=True)
                    return
                pages = self._apply_source_footer(pages, "Cocpit")
                await safe_respond_interaction(interaction, embed=pages[0], view=CDTPagesMenu(pages, author=interaction.user))
                return

            if cocpit:
                lines = build_cocpit_synergy_lines(cocpit, cache=cache)
                source_label = "Cocpit"
                title = f"{champ.get('name','Unknown')} Synergies"
            else:
                lines = build_champion_synergy_lines(champ, cache=cache)
                source_label = "MCOCHub cache"
                title = f"{champ.get('name','Unknown')} Synergies"
            if not lines:
                await safe_respond_interaction(interaction, content="Synergies unavailable.", ephemeral=True)
                return
            pages = [CDTEmbed.embed(interaction, title=title, description=page) for page in chunk_text_blocks(lines)]
            pages = self._apply_source_footer(pages, source_label)
            await safe_respond_interaction(interaction, embed=pages[0], view=CDTPagesMenu(pages, author=interaction.user))
        except Exception:
            log.exception("Failed to build synergies embed")
            await safe_respond_interaction(interaction, content="Synergies unavailable.", ephemeral=True)

    async def _lookup_tag(self, interaction, tag: str):
        cache = self._cache()
        champs = cache.get_all_champions() if cache else []
        wanted = self._normalize_token(tag)
        matches = []
        for champ in champs:
            tags = champ.get("tags") or []
            if any(self._normalize_token(value) == wanted for value in tags):
                matches.append(champ)
        if not matches:
            await safe_respond_interaction(interaction, content=f"No champions found with tag `{tag}`.", ephemeral=True)
            return
        try:
            embed = CDTEmbed.tag_list_embed(interaction, tag, matches)
            await safe_respond_interaction(interaction, embed=embed)
        except Exception:
            await safe_respond_interaction(interaction, content=f"{len(matches)} champions found for tag `{tag}`.", ephemeral=True)

    @app_commands.command(name="tag", description="List champions with a specific tag")
    @app_commands.autocomplete(tag=tag_autocomplete)
    async def tag(self, interaction, tag: str):
        await self._lookup_tag(interaction, tag)

    @app_commands.command(name="tags", description="List champions with a specific tag")
    @app_commands.autocomplete(tag=tag_autocomplete)
    async def tags(self, interaction, tag: str):
        await self._lookup_tag(interaction, tag)

    @app_commands.command(name="stats", description="Show champion stats")
    @app_commands.describe(
        rarity="Star rarity (1-7)",
        rank="Rank",
        sig="Signature level",
        ascended="Ascension level"
    )
    @app_commands.autocomplete(champion=champion_autocomplete)
    async def stats(self, interaction, champion: str, rarity: int, rank: int, sig: int = 0, ascended: int = 0):
        champ = resolve_champion(self._cache(), champion)
        if not champ:
            await safe_respond_interaction(interaction, content=f"Champion `{champion}` not found.", ephemeral=True)
            return

        cocpit_stats = get_cocpit_cached_stats(self.core, champ, rarity, rank, sig, ascended)
        try:
            import discord
            title = f"{champ.get('name','Unknown')} — {rarity}★ R{rank} Sig {sig} Asc {ascended}"
            embed = discord.Embed(title=title, color=discord.Color.gold())
            if cocpit_stats:
                embed.add_field(name="Attack", value=str(cocpit_stats.get("attack", "N/A")), inline=True)
                embed.add_field(name="Health", value=str(cocpit_stats.get("health", "N/A")), inline=True)
                embed.add_field(name="Prestige", value=str(cocpit_stats.get("prestige", "N/A")), inline=True)
                row_sig = cocpit_stats.get("sig_level")
                if row_sig is not None and int(row_sig) != int(sig):
                    embed.add_field(name="Sig Note", value=f"Closest cached sig: {row_sig}", inline=False)
            else:
                statline = lookup_stat(champ, rarity, rank, ascended)
                if not statline:
                    await safe_respond_interaction(interaction, content="No Cocpit stats available for that combination.", ephemeral=True)
                    return
                embed.add_field(name="Attack", value=str(statline.get("attack", "N/A")), inline=True)
                embed.add_field(name="Health", value=str(statline.get("health", "N/A")), inline=True)
                embed.add_field(name="Prestige", value="N/A", inline=True)
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
        champ_name=champion_autocomplete,
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
        cache = self._cache()
        champs = idx.champions if idx and hasattr(idx, "champions") else (cache.get_all_champions() if cache else [])

        filters = {
            "name": champ_name or None,
            "classes": [champ_class] if champ_class else [],
            "tags": [champ_tag] if champ_tag else [],
            "abilities": [champ_ability] if champ_ability else [],
            "immunities": [champ_immunity] if champ_immunity else [],
            "tiers": [str(champ_rarity)] if champ_rarity is not None else [],
            "rarities": [str(champ_rarity)] if champ_rarity is not None else [],
        }

        synergy_target = resolve_champion(cache, champ_synergy) if champ_synergy else None
        synergy_token = self._normalize_token((synergy_target or {}).get("id") or (synergy_target or {}).get("slug") or champ_synergy)

        results = []
        for champ in champs:
            try:
                if not _champion_matches_filters(champ, filters):
                    continue
                if synergy_token:
                    matched = False
                    for synergy in champ.get("synergies") or []:
                        if not isinstance(synergy, dict):
                            continue
                        partners = synergy.get("synergy_with") or synergy.get("partners") or []
                        if isinstance(partners, list):
                            for partner in partners:
                                if isinstance(partner, dict):
                                    token = self._normalize_token(partner.get("champName") or partner.get("champPortraitName") or partner.get("name") or partner.get("id"))
                                else:
                                    token = self._normalize_token(partner)
                                if token and token == synergy_token:
                                    matched = True
                                    break
                        if matched:
                            break
                    if not matched:
                        continue
                results.append(champ)
            except Exception:
                continue

        if not results:
            await safe_respond_interaction(interaction, content="No champions match your search filters.", ephemeral=True)
            return

        try:
            pages = [CDTEmbed.champion_embed(interaction, champ) for champ in results]
            pages = add_page_footers(pages)
            await safe_respond_interaction(interaction, embed=pages[0], view=CDTPagesMenu(pages, author=interaction.user))
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
