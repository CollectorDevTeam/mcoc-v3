import discord
from discord import app_commands

from .embeds import champion_embed, abilities_embed, synergy_embed, tag_list_embed


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
        name="Name contains...",
        class_="Champion class (cosmic, tech, mutant, skill, mystic, science)",
        rarity="Filter by rarity (1–7 stars)",
        tag="Filter by tag",
        ability="Filter by ability",
        immunity="Filter by immunity",
        synergy="Filter by synergy partner"
    )
    @app_commands.autocomplete(
        tag=ChampionSlash.tag_autocomplete,
        ability=ChampionSlash.ability_autocomplete,
        immunity=ChampionSlash.immunity_autocomplete,
        synergy=ChampionSlash.champion_autocomplete
    )
    async def search(
        self,
        interaction: discord.Interaction,
        name: str = None,
        class_: str = None,
        rarity: int = None,
        tag: str = None,
        ability: str = None,
        immunity: str = None,
        synergy: str = None
    ):
        """
        Search champions using multiple filters.
        """

        champs = self.core.cache.index.champions  # fast list

        results = []

        for champ in champs:
            # Name filter
            if name and name.lower() not in champ["name"].lower():
                continue

            # Class filter
            if class_ and champ.get("class", "").lower() != class_.lower():
                continue

            # Rarity filter
            if rarity and rarity not in champ.get("rarities", []):
                continue

            # Tag filter
            if tag and tag not in champ.get("tags", []):
                continue

            # Ability filter
            if ability and ability not in champ.get("abilities", []):
                continue

            # Immunity filter
            if immunity and immunity not in champ.get("immunities", []):
                continue

            # Synergy partner filter
            if synergy:
                synergies = champ.get("synergies", [])
                partner_ids = [s["partner"] for s in synergies]
                if synergy not in partner_ids:
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
        rarity="Star rarity (1–7)",
        rank="Rank (1–5)",
        sig="Signature level (0–200)",
        ascended="Ascension level (0–5)",
        use_roster="Use your roster entry instead of manual inputs"
    )
    @app_commands.autocomplete(champion=ChampionSlash.champion_autocomplete)
    async def calcstats(
        self,
        interaction: discord.Interaction,
        champion: str,
        rarity: int = None,
        rank: int = None,
        sig: int = None,
        ascended: int = 0,
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

            rarity = entry["rarity"]
            rank = entry["rank"]
            sig = entry["sig"]
            ascended = entry.get("ascended", 0)

        # Validate inputs
        if rarity is None or rank is None:
            await interaction.response.send_message(
                "You must specify rarity and rank (or enable `use_roster`).",
                ephemeral=True
            )
            return

        stats_table = champ.get("stats", {})
        rarity_table = stats_table.get(str(rarity))

        if not rarity_table:
            await interaction.response.send_message(
                f"No stat data available for {rarity}★ {champ['name']}.",
                ephemeral=True
            )
            return

        # Handle ascension
        rank_key = str(rank)
        if ascended > 0:
            asc_key = f"{rank}A{ascended}"
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
            title=f"{champ['name']} — {rarity}★ Rank {rank}{' Ascended ' + str(ascended) if ascended else ''}",
            color=discord.Color.gold()
        )

        embed.add_field(name="Attack", value=statline.get("attack", "N/A"))
        embed.add_field(name="Health", value=statline.get("health", "N/A"))

        if sig is not None:
            embed.add_field(name="Signature Level", value=str(sig))

        embed.set_thumbnail(url=champ.get("portrait", ""))

        await interaction.response.send_message(embed=embed)
