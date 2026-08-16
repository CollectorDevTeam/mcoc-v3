from redbot.core import commands
import discord

from .userdata import UserDataManager
from .hargs import parse_hargs
from .embeds import roster_entry_embed
from .pagination import PagesMenu

class RosterCommands(commands.Cog):
    def __init__(self, core):
        self.core = core
        self.bot = core.bot
        self.cache = core.cache
        self.users = UserDataManager()

    # ----------------------------------------
    # /mcoc roster group
    # ----------------------------------------
    @commands.group()
    async def roster(self, ctx):
        """User roster commands."""
        pass

    # ----------------------------------------
    # /mcoc roster add <champion> <hargs>
    # ----------------------------------------
    @roster.command()
    async def add(self, ctx, champion: str, *, hargs: str = None):
        parsed = parse_hargs(hargs or "")

        champ = self.cache.get_champion(champion)
        if not champ:
            await ctx.send(f"Champion `{champion}` not found.")
            return

        rarity = parsed["rarities"][0] if parsed["rarities"] else None
        rank = parsed["ranks"][0] if parsed["ranks"] else None
        sig = parsed["sigs"][0] if parsed["sigs"] else 0
        tags = parsed["tags"]

        if rarity is None or rank is None:
            await ctx.send("Adding a champion requires rarity and rank (e.g., `6*r3`).")
            return

        self.users.add_champion(
            ctx.author.id,
            champ_slug=champ["slug"],
            rarity=rarity,
            rank=rank,
            sig=sig,
            tags=tags
        )

        embed = await roster_entry_embed(ctx, champ, {
            "rarity": rarity,
            "rank": rank,
            "sig": sig,
            "tags": tags
        })

        await ctx.send(f"Added **{champ['name']}** to your roster.", embed=embed)

    # ----------------------------------------
    # /mcoc roster remove <champion> <hargs?>
    # ----------------------------------------
    @roster.command()
    async def remove(self, ctx, champion: str, *, hargs: str = None):
        parsed = parse_hargs(hargs or "")
        rarity = parsed["rarities"][0] if parsed["rarities"] else None

        removed = self.users.remove_champion(ctx.author.id, champion, rarity)

        if removed == 0:
            await ctx.send("No matching champion found in your roster.")
        else:
            await ctx.send(f"Removed {removed} entries for `{champion}`.")

    # ----------------------------------------
    # /mcoc roster update <champion> <hargs>
    # ----------------------------------------
    @roster.command()
    async def update(self, ctx, champion: str, *, hargs: str):
        parsed = parse_hargs(hargs)

        rarity = parsed["rarities"][0] if parsed["rarities"] else None
        rank = parsed["ranks"][0] if parsed["ranks"] else None
        sig = parsed["sigs"][0] if parsed["sigs"] else None
        tags = parsed["tags"] if parsed["tags"] else None

        if rarity is None:
            await ctx.send("Updating a champion requires rarity (e.g., `6*`).")
            return

        updated = self.users.update_champion(
            ctx.author.id,
            champ_slug=champion,
            rarity=rarity,
            rank=rank,
            sig=sig,
            tags=tags
        )

        if not updated:
            await ctx.send("Champion not found in your roster.")
            return

        champ = self.cache.get_champion(champion)
        embed = await roster_entry_embed(ctx, champ, {
            "rarity": rarity,
            "rank": rank or 0,
            "sig": sig or 0,
            "tags": tags or []
        })

        await ctx.send(f"Updated **{champ['name']}**.", embed=embed)

    # ----------------------------------------
    # /mcoc roster list <hargs?>
    # ----------------------------------------
    @roster.command()
    async def list(self, ctx, *, hargs: str = None):
        parsed = parse_hargs(hargs or "")
        roster = self.users.list_roster(ctx.author.id)

        # Filter using hargs
        results = []
        for entry in roster:
            champ = self.cache.get_champion(entry["champion"])
            if not champ:
                continue

            # Apply hargs filters
            if parsed["rarities"] and entry["rarity"] not in parsed["rarities"]:
                continue
            if parsed["ranks"] and entry["rank"] not in parsed["ranks"]:
                continue
            if parsed["sigs"] and entry["sig"] not in parsed["sigs"]:
                continue
            for tag in parsed["tags"]:
                if tag not in entry["tags"]:
                    break
            else:
                results.append((champ, entry))

        if not results:
            await ctx.send("No roster entries match your filters.")
            return

        pages = []
        for champ, entry in results:
            embed = await roster_entry_embed(ctx, champ, entry)
            pages.append(embed)

        pages = PagesMenu.add_page_numbers(pages)
        champ, entry = results[0]
        embed = await roster_entry_embed(ctx, champ, entry)
        await ctx.send(embed=embed, view=PagesMenu(pages, ctx.author))

    # ----------------------------------------
    # /mcoc roster export
    # ----------------------------------------
    @roster.command()
    async def export(self, ctx):
        data = self.users.export(ctx.author.id)
        await ctx.send(f"Your roster data:\n```json\n{json.dumps(data, indent=2)}\n```")

    # ----------------------------------------
    # /mcoc roster clear
    # ----------------------------------------
    @roster.command()
    async def clear(self, ctx):
        self.users.delete_user(ctx.author.id)
        await ctx.send("Your roster has been cleared.")
