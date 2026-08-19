import discord
from discord import app_commands

from .userdata import UserDataManager
from .hargs import parse_hargs
from .embeds import roster_entry_embed
from .pagination import PagesMenu


class RosterSlash(app_commands.Group):
    """
    Slash command group: /roster
    """

    def __init__(self, core):
        super().__init__(
            name="roster",
            description="Manage your personal champion roster"
        )
        self.core = core
        self.users = UserDataManager()
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
        champs = self.core.cache.get_all_champions()

        matches = [
            app_commands.Choice(name=c["name"], value=c["id"])
            for c in champs
            if current in c["name"].lower() or current in c["id"].lower()
        ]

        return matches[:25]

    # ---------------------------------------------------------
    # Autocomplete: hargs
    # ---------------------------------------------------------
    async def hargs_autocomplete(self, interaction: discord.Interaction, current: str):
        current = current.lower()

        presets = [
            "7*",
            "7*r1",
            "7*r2",
            "7*r3",
            "7*r4",
            "7*r5",
            "6*",
            "6*r1",
            "6*r2",
            "6*r3",
            "6*r4",
            "6*r5",
            "5*",
            "5*r1",
            "5*r2",
            "5*r3",
            "5*r4",
            "5*r5",
            "r1", "r2", "r3", "r4", "r5",
            "s0", "s20", "s40", "s80", "s120", "s200",
            "#bleed", "#poison", "#shock", "#incinerate",
        ]

        matches = [
            app_commands.Choice(name=p, value=p)
            for p in presets
            if current in p.lower()
        ]

        return matches[:25]



    # ---------------------------------------------------------
    # /roster add <champion> <hargs>
    # ---------------------------------------------------------
    @app_commands.command(name="add", description="Add a champion to your roster")
    @app_commands.autocomplete(champion=champion_autocomplete, hargs=hargs_autocomplete)
    async def add(self, interaction: discord.Interaction, champion: str, hargs: str):
        parsed = parse_hargs(hargs or "")

        champ = self.core.cache.get_champion(champion)
        if not champ:
            await interaction.response.send_message(
                f"Champion `{champion}` not found.",
                ephemeral=True
            )
            return

        rarity = parsed["rarities"][0] if parsed["rarities"] else None
        rank = parsed["ranks"][0] if parsed["ranks"] else None
        sig = parsed["sigs"][0] if parsed["sigs"] else 0
        tags = parsed["tags"]
        ascended = parsed["ascended"][0] if parsed["ascended"] else 0

        if rarity is None or rank is None:
            await interaction.response.send_message(
                "Adding a champion requires rarity and rank (e.g., `6*r3`).",
                ephemeral=True
            )
            return

        self.users.add_champion(
            interaction.user.id,
            champ_slug=champ["id"],
            rarity=rarity,
            rank=rank,
            sig=sig,
            tags=tags,
            ascended=ascended
        )

        embed = await roster_entry_embed(interaction, champ, {
            "rarity": rarity,
            "rank": rank,
            "sig": sig,
            "tags": tags,
            "ascended": ascended
        })

        await interaction.response.send_message(
            f"Added **{champ['name']}** to your roster.",
            embed=embed
        )

    # ---------------------------------------------------------
    # /roster remove <champion> <hargs?>
    # ---------------------------------------------------------
    @app_commands.command(name="remove", description="Remove a champion from your roster")
    @app_commands.autocomplete(champion=champion_autocomplete)
    async def remove(self, interaction: discord.Interaction, champion: str, hargs: str = None):
        parsed = parse_hargs(hargs or "")
        rarity = parsed["rarities"][0] if parsed["rarities"] else None

        removed = self.users.remove_champion(interaction.user.id, champion, rarity)

        if removed == 0:
            await interaction.response.send_message(
                "No matching champion found in your roster.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"Removed {removed} entries for `{champion}`."
            )

    # ---------------------------------------------------------
    # /roster update <champion> <hargs>
    # ---------------------------------------------------------
    @app_commands.command(name="update", description="Update a champion entry in your roster")
    @app_commands.autocomplete(champion=champion_autocomplete)
    async def update(self, interaction: discord.Interaction, champion: str, hargs: str):
        parsed = parse_hargs(hargs)

        rarity = parsed["rarities"][0] if parsed["rarities"] else None
        rank = parsed["ranks"][0] if parsed["ranks"] else None
        sig = parsed["sigs"][0] if parsed["sigs"] else None
        tags = parsed["tags"] if parsed["tags"] else None
        ascended = parsed["ascended"][0] if parsed["ascended"] else 0

        if rarity is None:
            await interaction.response.send_message(
                "Updating a champion requires rarity (e.g., `6*`).",
                ephemeral=True
            )
            return

        updated = self.users.update_champion(
            interaction.user.id,
            champ_slug=champion,
            rarity=rarity,
            rank=rank,
            sig=sig,
            tags=tags,
            ascended=ascended
        )

        if not updated:
            await interaction.response.send_message(
                "Champion not found in your roster.",
                ephemeral=True
            )
            return

        champ = self.core.cache.get_champion(champion)
        embed = await roster_entry_embed(interaction, champ, {
            "rarity": rarity,
            "rank": rank or 0,
            "sig": sig or 0,
            "tags": tags or [],
            "ascended": ascended or 0
        })

        await interaction.response.send_message(
            f"Updated **{champ['name']}**.",
            embed=embed
        )

    # ---------------------------------------------------------
    # /roster list <hargs?>
    # ---------------------------------------------------------
    @app_commands.command(name="list", description="List your roster with optional filters")
    async def list(self, interaction: discord.Interaction, hargs: str = None):
        parsed = parse_hargs(hargs or "")
        roster = self.users.list_roster(interaction.user.id)

        results = []
        for entry in roster:
            champ = self.core.cache.get_champion(entry["champion"])
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
            await interaction.response.send_message(
                "No roster entries match your filters.",
                ephemeral=True
            )
            return

        pages = []
        for champ, entry in results:
            embed = await roster_entry_embed(interaction, champ, entry)
            pages.append(embed)

        pages = PagesMenu.add_page_numbers(pages)

        await interaction.response.send_message(
            embed=pages[0],
            view=PagesMenu(pages, interaction.user)
        )

    # ---------------------------------------------------------
    # /roster export
    # ---------------------------------------------------------
    @app_commands.command(name="export", description="Export your roster as JSON")
    async def export(self, interaction: discord.Interaction):
        data = self.users.export(interaction.user.id)
        json_text = discord.utils.escape_markdown(str(data))

        await interaction.response.send_message(
            f"Your roster data:\n```json\n{json_text}\n```"
        )

    # ---------------------------------------------------------
    # /roster clear
    # ---------------------------------------------------------
    @app_commands.command(name="clear", description="Clear your entire roster")
    async def clear(self, interaction: discord.Interaction):
        self.users.delete_user(interaction.user.id)
        await interaction.response.send_message("Your roster has been cleared.")
