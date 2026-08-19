import discord
from discord import app_commands

from .embeds import champion_embed, abilities_embed, synergy_embed, tag_list_embed
from .pagination import PagesMenu


class ChampionSlash(app_commands.Group):
    """
    Slash command group: /champ
    """

    def __init__(self, core):
        super().__init__(
            name="champ",
            description="Champion information commands"
        )
        self.core = core
        self._init_failed = False

        try:
            # Put only lightweight setup here (no network calls).
            # Example: set attributes, prepare local helpers, register state.
            # Do NOT raise exceptions for tracing; log instead.
            # (If you previously registered subcommands here, keep only definitions,
            #  but avoid anything that can throw at import time.)
            pass

        except Exception:
            import logging
            log = logging.getLogger("red.mcoc.core")
            log.exception("ChampionSlash constructor failed; continuing without slash group")
            # mark failure so core can skip adding this group
            self._init_failed = True

    # ---------------------------------------------------------
    # Autocomplete: champion names
    # ---------------------------------------------------------
    async def champion_autocomplete(self, interaction: discord.Interaction, current: str):
        current = current.lower()
        return await self.core.cache.index.champion_autocomplete(interaction, current)
        # champs = self.core.cache.get_all_champions()

        # matches = [
        #     app_commands.Choice(name=c["name"], value=c["id"])
        #     for c in champs
        #     if current in c["name"].lower() or current in c["id"].lower()
        # ]

        # return matches[:25]

    # ---------------------------------------------------------
    # Autocomplete: tags
    # ---------------------------------------------------------
    async def tag_autocomplete(self, interaction: discord.Interaction, current: str):
        current = current.lower()
        return await self.core.cache.index.tag_autocomplete(interaction, current)
        # tags = self.core.cache.get_all_tags()  # returns list of tag strings

        # matches = [
        #     app_commands.Choice(name=t, value=t)
        #     for t in tags
        #     if current in t.lower()
        # ]

        # return matches[:25]

    # ---------------------------------------------------------
    # Autocomplete: abilities
    # ---------------------------------------------------------
    async def ability_autocomplete(self, interaction: discord.Interaction, current: str):
        current = current.lower()
        return await self.core.cache.index.ability_autocomplete(interaction, current)
        # abilities = self.core.cache.get_all_abilities()  # list of ability dicts

        # matches = [
        #     app_commands.Choice(name=a["name"], value=a["id"])
        #     for a in abilities
        #     if current in a["name"].lower()
        # ]

        # return matches[:25]

    # ---------------------------------------------------------
    # Autocomplete: immunities
    # ---------------------------------------------------------
    async def immunity_autocomplete(self, interaction: discord.Interaction, current: str):
        current = current.lower()
        return await self.core.cache.index.immunity_autocomplete(interaction, current)
        # immunities = self.core.cache.get_all_immunities()  # list of immunity dicts

        # matches = [
        #     app_commands.Choice(name=i["name"], value=i["id"])
        #     for i in immunities
        #     if current in i["name"].lower()
        # ]

        # return matches[:25]
    
    # ---------------------------------------------------------
    # /champ info <champion>
    # ---------------------------------------------------------
    @app_commands.command(name="info", description="Show champion information")
    @app_commands.autocomplete(champion=champion_autocomplete)
    async def info(self, interaction: discord.Interaction, champion: str):
        champ = self.core.cache.get_champion(champion)
        if not champ:
            await interaction.response.send_message(
                f"Champion `{champion}` not found.",
                ephemeral=True
            )
            return

        embed = await champion_embed(interaction, champ)
        await interaction.response.send_message(embed=embed)

    # ---------------------------------------------------------
    # /champ abilities <champion>
    # ---------------------------------------------------------
    @app_commands.command(name="abilities", description="Show champion abilities")
    @app_commands.autocomplete(champion=champion_autocomplete)
    async def abilities(self, interaction: discord.Interaction, champion: str):
        champ = self.core.cache.get_champion(champion)
        if not champ:
            await interaction.response.send_message(
                f"Champion `{champion}` not found.",
                ephemeral=True
            )
            return

        embed = await abilities_embed(interaction, champ)
        await interaction.response.send_message(embed=embed)

    # ---------------------------------------------------------
    # /champ synergies <champion>
    # ---------------------------------------------------------
    @app_commands.command(name="synergies", description="Show champion synergies")
    @app_commands.autocomplete(champion=champion_autocomplete)
    async def synergies(self, interaction: discord.Interaction, champion: str):
        champ = self.core.cache.get_champion(champion)
        if not champ:
            await interaction.response.send_message(
                f"Champion `{champion}` not found.",
                ephemeral=True
            )
            return

        synergies = champ.get("synergies", [])
        embed = await synergy_embed(interaction, champ, synergies)
        await interaction.response.send_message(embed=embed)

    # ---------------------------------------------------------
    # /champ tags <tag>
    # ---------------------------------------------------------
    @app_commands.command(name="tags", description="List champions with a specific tag")
    @app_commands.autocomplete(tag=tag_autocomplete)
    async def tags(self, interaction: discord.Interaction, tag: str):
        champs = self.core.cache.get_all_champions()
        matches = [c for c in champs if tag in c.get("tags", [])]

        if not matches:
            await interaction.response.send_message(
                f"No champions found with tag `{tag}`.",
                ephemeral=True
            )
            return

        embed = await tag_list_embed(interaction, tag, matches)
        await interaction.response.send_message(embed=embed)

    # ---------------------------------------------------------
    # /champ stats <champion>
    # ---------------------------------------------------------
    @app_commands.command(name="stats", description="Show champion stats")
    @app_commands.autocomplete(champion=champion_autocomplete)
    async def stats(self, interaction: discord.Interaction, champion: str):
        champ = self.core.cache.get_champion(champion)
        if not champ:
            await interaction.response.send_message(
                f"Champion `{champion}` not found.",
                ephemeral=True
            )
            return

        stats = champ.get("stats", {})
        if not stats:
            await interaction.response.send_message(
                "No stats available for this champion.",
                ephemeral=True
            )
            return

        # Simple stats embed
        embed = discord.Embed(
            title=f"{champ['name']} — Stats",
            color=discord.Color.gold()
        )

        for rarity, ranks in stats.items():
            for rank, values in ranks.items():
                embed.add_field(
                    name=f"{rarity}★ Rank {rank}",
                    value=f"Attack: {values['attack']}\nHealth: {values['health']}",
                    inline=False
                )

        await interaction.response.send_message(embed=embed)

    
    # ---------------------------------------------------------
    # /champ search
    # ---------------------------------------------------------
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
        interaction: discord.Interaction,
        champ_name: str = None,
        champ_class: str = None,
        champ_rarity: int = None,
        champ_tag: str = None,
        champ_ability: str = None,
        champ_immunity: str = None,
        champ_synergy: str = None
    ):
        """
        Search champions using multiple filters.
        """

        champs = self.core.cache.index.champions  # fast list

        results = []

        for champ in champs:
            # Name filter
            if champ_name and champ_name.lower() not in champ["name"].lower():
                continue

            # Class filter
            if champ_class and champ.get("class", "").lower() != champ_class.lower():
                continue

            # Rarity filter
            if champ_rarity and champ_rarity not in champ.get("rarities", []):
                continue

            # Tag filter
            if champ_tag and champ_tag not in champ.get("tags", []):
                continue

            # Ability filter
            if champ_ability and champ_ability not in champ.get("abilities", []):
                continue

            # Immunity filter
            if champ_immunity and champ_immunity not in champ.get("immunities", []):
                continue

            # Synergy partner filter
            if champ_synergy:
                synergies = champ.get("synergies", [])
                partner_ids = [s["partner"] for s in synergies]
                if champ_synergy not in partner_ids:
                    continue

            results.append(champ)

        if not results:
            await interaction.response.send_message(
                "No champions match your search filters.",
                ephemeral=True
            )
            return

        # Build embeds
        pages = []
        for champ in results:
            embed = await champion_embed(interaction, champ)
            pages.append(embed)

        pages = PagesMenu.add_page_numbers(pages)

        await interaction.response.send_message(
            embed=pages[0],
            view=PagesMenu(pages, interaction.user)
        )

    # ---------------------------------------------------------
    # /champ calcstats
    # ---------------------------------------------------------
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
        interaction: discord.Interaction,
        champion: str,
        champ_rarity: int = None,
        champ_rank: int = None,
        champ_sig: int = None,
        champ_ascended: int = 0,
        use_roster: bool = False
    ):
        """
        Calculate stats for a champion using MCOCHub stat tables.
        Supports roster champions (rarity, rank, sig, ascension).
        """

        champ = self.core.cache.get_champion(champion)
        if not champ:
            await interaction.response.send_message(
                f"Champion `{champion}` not found.",
                ephemeral=True
            )
            return

        # If using roster, pull user’s stored entry
        if use_roster:
            roster = self.core.roster_slash.users.list_roster(interaction.user.id)
            entry = next((e for e in roster if e["champion"] == champ["id"]), None)

            if not entry:
                await interaction.response.send_message(
                    "You do not have this champion in your roster.",
                    ephemeral=True
                )
                return

            champ_rarity = entry["rarity"]
            champ_rank = entry["rank"]
            champ_sig = entry["sig"]
            champ_ascended = entry.get("ascended", 0)

        # Validate inputs
        if champ_rarity is None or champ_rank is None:
            await interaction.response.send_message(
                "You must specify rarity and rank (or enable `use_roster`).",
                ephemeral=True
            )
            return

        stats_table = champ.get("stats", {})
        rarity_table = stats_table.get(str(champ_rarity))

        if not rarity_table:
            await interaction.response.send_message(
                f"No stat data available for {champ_rarity}★ {champ['name']}.",
                ephemeral=True
            )
            return

        # Handle ascension
        rank_key = str(champ_rank)
        if champ_ascended > 0:
            asc_key = f"{champ_rank}A{champ_ascended}"
            if asc_key in rarity_table:
                rank_key = asc_key

        if rank_key not in rarity_table:
            await interaction.response.send_message(
                f"No stat data for rank `{rank_key}`.",
                ephemeral=True
            )
            return

        statline = rarity_table[rank_key]

        # Build embed
        embed = discord.Embed(
            title=f"{champ['name']} — {champ_rarity}★ Rank {champ_rank}{' Ascended ' + str(champ_ascended) if champ_ascended else ''}",
            color=discord.Color.gold()
        )

        embed.add_field(name="Attack", value=statline.get("attack", "N/A"))
        embed.add_field(name="Health", value=statline.get("health", "N/A"))

        if champ_sig is not None:
            embed.add_field(name="Signature Level", value=str(champ_sig))

        embed.set_thumbnail(url=champ.get("portrait", ""))

        await interaction.response.send_message(embed=embed)
