# mcoc/slash/roster_slash.py
import logging
from typing import Optional, Any, List
from discord import app_commands
from redbot.core import commands

log = logging.getLogger("red.mcoc.slash.roster")

from ..common.hargs import parse_hargs
from ..common.roster_helpers import (
    ensure_user_manager,
    extract_entry_from_parsed,
    build_roster_pages,
    validate_entry_for_add,
)
from ..common.embeds import roster_entry_embed  # used as fallback in some handlers


class _RosterGroup(app_commands.Group):
    def __init__(self, core: Any):
        super().__init__(name="roster", description="Manage your personal champion roster")
        self.core = core
        self._init_failed = False
        # do not create heavy objects here

    # Autocomplete: champion names (prefer index)
    async def champion_autocomplete(self, interaction, current: str):
        idx = getattr(self.core, "cache", None) and getattr(self.core.cache, "index", None)
        cur = (current or "").lower()
        if idx and hasattr(idx, "champion_autocomplete"):
            try:
                return await idx.champion_autocomplete(interaction, cur)
            except Exception:
                log.exception("champion_autocomplete failed in CacheIndex")
        # fallback simple scan
        try:
            champs = getattr(self.core, "cache", None) and self.core.cache.get_all_champions() or []
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

    # Autocomplete: hargs presets
    async def hargs_autocomplete(self, interaction, current: str):
        cur = (current or "").lower()
        presets = [
            "7*", "7*r1", "7*r2", "7*r3", "7*r4", "7*r5",
            "6*", "6*r1", "6*r2", "6*r3", "6*r4", "6*r5",
            "5*", "5*r1", "5*r2", "5*r3", "5*r4", "5*r5",
            "r1", "r2", "r3", "r4", "r5",
            "s0", "s20", "s40", "s80", "s120", "s200",
            "#bleed", "#poison", "#shock", "#incinerate",
        ]
        return [app_commands.Choice(name=p, value=p) for p in presets if cur in p.lower()][:25]

    # -------------------------
    # /roster add
    # -------------------------
    @app_commands.command(name="add", description="Add a champion to your roster")
    @app_commands.autocomplete(champion=champion_autocomplete, hargs=hargs_autocomplete)
    async def add(self, interaction, champion: str, hargs: str):
        parsed = parse_hargs(hargs or "")
        entry = extract_entry_from_parsed(parsed)

        # validate champion exists
        cache = getattr(self.core, "cache", None)
        champ = None
        if cache:
            try:
                champ = cache.get_champion(champion)
            except Exception:
                champ = None

        if not champ:
            await interaction.response.send_message(f"Champion `{champion}` not found.", ephemeral=True)
            return

        if not validate_entry_for_add(entry):
            await interaction.response.send_message("Adding a champion requires rarity and rank (e.g., `6*r3`).", ephemeral=True)
            return

        users = ensure_user_manager(self.core)
        try:
            users.add_champion(
                interaction.user.id,
                champ_slug=champ.get("id") or champ.get("slug"),
                rarity=entry["rarity"],
                rank=entry["rank"],
                sig=entry.get("sig", 0),
                tags=entry.get("tags", []),
            )
        except Exception:
            log.exception("Failed to add champion to roster")
            await interaction.response.send_message("Failed to add champion to roster.", ephemeral=True)
            return

        try:
            embed = await roster_entry_embed(interaction, champ, {
                "rarity": entry["rarity"],
                "rank": entry["rank"],
                "sig": entry.get("sig", 0),
                "tags": entry.get("tags", []),
                "ascended": entry.get("ascended", 0),
            })
        except Exception:
            embed = None

        await interaction.response.send_message(f"Added **{champ.get('name','Unknown')}** to your roster.", embed=embed)

    # -------------------------
    # /roster remove
    # -------------------------
    @app_commands.command(name="remove", description="Remove a champion from your roster")
    @app_commands.autocomplete(champion=champion_autocomplete)
    async def remove(self, interaction, champion: str, hargs: Optional[str] = None):
        parsed = parse_hargs(hargs or "")
        rarity = parsed["rarities"][0] if parsed["rarities"] else None

        users = ensure_user_manager(self.core)
        try:
            removed = users.remove_champion(interaction.user.id, champion, rarity)
        except Exception:
            log.exception("Failed to remove champion from roster")
            removed = 0

        if removed == 0:
            await interaction.response.send_message("No matching champion found in your roster.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Removed {removed} entries for `{champion}`.")

    # -------------------------
    # /roster update
    # -------------------------
    @app_commands.command(name="update", description="Update a champion entry in your roster")
    @app_commands.autocomplete(champion=champion_autocomplete)
    async def update(self, interaction, champion: str, hargs: str):
        parsed = parse_hargs(hargs or "")
        entry = extract_entry_from_parsed(parsed)

        if entry.get("rarity") is None:
            await interaction.response.send_message("Updating a champion requires rarity (e.g., `6*`).", ephemeral=True)
            return

        users = ensure_user_manager(self.core)
        try:
            updated = users.update_champion(
                interaction.user.id,
                champ_slug=champion,
                rarity=entry["rarity"],
                rank=entry.get("rank"),
                sig=entry.get("sig"),
                tags=entry.get("tags"),
            )
        except Exception:
            log.exception("Failed to update champion")
            updated = False

        if not updated:
            await interaction.response.send_message("Champion not found in your roster.", ephemeral=True)
            return

        cache = getattr(self.core, "cache", None)
        champ = cache.get_champion(champion) if cache else None
        try:
            embed = await roster_entry_embed(interaction, champ, {
                "rarity": entry["rarity"],
                "rank": entry.get("rank") or 0,
                "sig": entry.get("sig") or 0,
                "tags": entry.get("tags") or [],
                "ascended": entry.get("ascended") or 0
            })
        except Exception:
            embed = None

        await interaction.response.send_message(f"Updated **{champ.get('name','Unknown') if champ else champion}**.", embed=embed)

    # -------------------------
    # /roster list
    # -------------------------
    @app_commands.command(name="list", description="List your roster with optional filters")
    async def list(self, interaction, hargs: Optional[str] = None):
        parsed = parse_hargs(hargs or "")
        pages = await build_roster_pages(self.core, interaction.user.id, parsed)

        if not pages:
            await interaction.response.send_message("No roster entries match your filters.", ephemeral=True)
            return

        # add page numbers and send with PagesMenu if available
        try:
            from ..common.pagination import PagesMenu
            # add footers if helper exists
            try:
                from ..common.roster_helpers import add_page_footers  # optional; may not exist
                pages = add_page_footers(pages)
            except Exception:
                pass
            await interaction.response.send_message(embed=pages[0], view=PagesMenu(pages, interaction.user))
        except Exception:
            # fallback: send simple list
            names = [p.get("title") or "Entry" for p in pages][:50]
            await interaction.response.send_message(f"Matches ({len(pages)}): {', '.join(names)}", ephemeral=True)

    # -------------------------
    # /roster export
    # -------------------------
    @app_commands.command(name="export", description="Export your roster as JSON")
    async def export(self, interaction):
        users = ensure_user_manager(self.core)
        data = users.export(interaction.user.id) if users else {}
        import discord
        json_text = discord.utils.escape_markdown(str(data))
        await interaction.response.send_message(f"Your roster data:\n```json\n{json_text}\n```")

    # -------------------------
    # /roster clear
    # -------------------------
    @app_commands.command(name="clear", description="Clear your entire roster")
    async def clear(self, interaction):
        users = ensure_user_manager(self.core)
        if users:
            users.delete_user(interaction.user.id)
        await interaction.response.send_message("Your roster has been cleared.")

# Cog wrapper for slash roster group
class RosterSlashCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._group: Optional[_RosterGroup] = None

    async def cog_load(self):
        # Resolve core if present so the group can access cache/config
        core = getattr(self.bot, "mcoc_core", None) or self.bot.get_cog("MCOC") or self.bot.get_cog("MCOCPrefix")
        try:
            self._group = _RosterGroup(core or self.bot)
            try:
                self.bot.tree.add_command(self._group)
            except Exception:
                log.exception("Failed to add Roster group to tree")
        except Exception:
            log.exception("Failed to initialize Roster group")

    async def cog_unload(self):
        try:
            if self._group:
                self.bot.tree.remove_command(self._group.name)
        except Exception:
            log.exception("Failed to remove Roster group from tree")

    @property
    def group(self) -> Optional[_RosterGroup]:
        return self._group


def setup(bot):
    try:
        bot.add_cog(RosterSlashCog(bot))
    except Exception:
        log.exception("Failed to add RosterSlashCog")
