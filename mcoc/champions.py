from redbot.core import commands, app_commands
import discord

from .embeds import champion_embed, abilities_embed, synergy_embed, tag_list_embed
from .hargs import parse_hargs
from .pagination import PagesMenu

class ChampionsCommands(commands.Cog):
    def __init__(self, core):
        self.core = core
        self.bot = core.bot
        self.cache = core.cache

    # ----------------------------------------
    # Autocomplete helper
    # ----------------------------------------
    async def champion_autocomplete(self, interaction: discord.Interaction, current: str):
        current = current.lower()
        champs = self.cache.get_all_champions()

        matches = [
            app_commands.Choice(name=c["name"], value=c["slug"])
            for c in champs
            if current in c["name"].lower() or current in c["slug"]
        ]

        return matches[:25]


    # ----------------------------------------
    # /mcoc champ group
    # ----------------------------------------
    @commands.group()
    async def champ(self, ctx):
        """Champion info commands."""
        pass

    # ----------------------------------------
    # /mcoc champ info <champion>
    # ----------------------------------------
    @champ.command()
    async def info(self, ctx, *, champion: str):
        champ = self.cache.get_champion(champion)
        if not champ:
            await ctx.send(f"Champion `{champion}` not found.")
            return

        embed = await champion_embed(ctx, champ)
        await ctx.send(embed=embed)

    # ----------------------------------------
    # /mcoc champ abilities <champion>
    # ----------------------------------------
    @champ.command()
    async def abilities(self, ctx, *, champion: str):
        champ = self.cache.get_champion(champion)
        if not champ:
            await ctx.send(f"Champion `{champion}` not found.")
            return

        embed = await abilities_embed(ctx, champ)
        await ctx.send(embed=embed)

    # ----------------------------------------
    # /mcoc champ synergies <champion...>
    # ----------------------------------------
    @champ.command()
    async def synergies(self, ctx, *champions: str):
        if not champions:
            await ctx.send("Please specify at least one champion.")
            return

        # Load each champion
        champ_objs = []
        for slug in champions:
            c = self.cache.get_champion(slug)
            if not c:
                await ctx.send(f"Champion `{slug}` not found.")
                return
            champ_objs.append(c)

        # Union of synergies
        synergy_union = []
        for c in champ_objs:
            synergy_union.extend(c.get("synergies", []))

        # Remove duplicates by name
        seen = set()
        final = []
        for syn in synergy_union:
            if syn["name"] not in seen:
                seen.add(syn["name"])
                final.append(syn)

        embed = await synergy_embed(ctx, champ_objs[0], final)
        await ctx.send(embed=embed)

    # ----------------------------------------
    # /mcoc champ tags <tag>
    # ----------------------------------------
    @champ.command()
    async def tags(self, ctx, *, tag: str):
        champs = self.cache.get_all_champions()
        matches = [c for c in champs if tag.lower() in [t.lower() for t in c["tags"]]]

        pages = []
        for c in matches:
            embed = await champion_embed(ctx, c)
            pages.append(embed)

        pages = PagesMenu.add_page_numbers(pages)
        embed = await tag_list_embed(ctx, tag, matches)
        await ctx.send(embed=embed, view=PagesMenu(pages, ctx.author))

    # ----------------------------------------
    # /mcoc champ stats <hargs>
    # ----------------------------------------
    @champ.command()
    async def stats(self, ctx, *, hargs: str):
        parsed = parse_hargs(hargs)

        if not parsed["champion"]:
            await ctx.send("Stats require a champion name.")
            return

        champ = self.cache.get_champion(parsed["champion"])
        if not champ:
            await ctx.send(f"Champion `{parsed['champion']}` not found.")
            return

        rarity = parsed["rarities"][0] if parsed["rarities"] else None
        rank = parsed["ranks"][0] if parsed["ranks"] else None
        sig = parsed["sigs"][0] if parsed["sigs"] else None

        if rarity is None or rank is None:
            await ctx.send("Stats require rarity and rank (e.g., `6*r3`).")
            return

        stats = champ["stats"].get(str(rarity), {}).get(str(rank), {})
        if not stats:
            await ctx.send("Stats not found for that rarity/rank.")
            return

        desc = "\n".join([f"{k}: {v}" for k, v in stats.items()])
        embed = await champion_embed(ctx, champ)
        embed.add_field(name="Stats", value=desc, inline=False)

        await ctx.send(embed=embed)
