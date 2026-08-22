# mcoc/slash/admin_slash.py
import logging
import discord
from discord import app_commands
from redbot.core import commands
from typing import Optional

log = logging.getLogger("red.mcoc.slash.admin")


class _AdminGroup(app_commands.Group):
    """
    Lightweight app_commands.Group that holds the slash handlers.
    Accepts a `core` object (your mcoc core cog) or a bot and resolves config/cache from it.
    """

    def __init__(self, core):
        super().__init__(name="mcocadmin", description="Admin commands for MCOC")
        self.core = core
        self.config = getattr(core, "config", None)
        self._init_failed = False

    async def _is_owner(self, interaction: discord.Interaction) -> bool:
        try:
            return await interaction.client.is_owner(interaction.user)
        except Exception:
            return False

    @app_commands.command(name="setapikey", description="Set the MCOCHUB API key")
    async def setapikey(self, interaction: discord.Interaction, key: str):
        if not await self._is_owner(interaction):
            await interaction.response.send_message("You must be a bot owner to use this command.", ephemeral=True)
            return
        if not self.config:
            await interaction.response.send_message("Configuration backend not available.", ephemeral=True)
            return
        await self.config.api_key.set(key)
        await interaction.response.send_message("API key saved.", ephemeral=True)

    @app_commands.command(name="clearapikey", description="Clear the stored API key")
    async def clearapikey(self, interaction: discord.Interaction):
        if not await self._is_owner(interaction):
            await interaction.response.send_message("You must be a bot owner to use this command.", ephemeral=True)
            return
        if not self.config:
            await interaction.response.send_message("Configuration backend not available.", ephemeral=True)
            return
        await self.config.api_key.set(None)
        await interaction.response.send_message("API key cleared.", ephemeral=True)

    @app_commands.command(name="status", description="Show sync and API status")
    async def status(self, interaction: discord.Interaction):
        metadata = getattr(self.core, "cache", None) and getattr(self.core.cache, "metadata", {})
        api_key = None
        interval = None
        try:
            if self.config:
                api_key = await self.config.api_key()
                interval = await self.config.sync_interval()
        except Exception:
            pass

        embed = discord.Embed(title="CollectorBot Status", color=discord.Color.gold())
        embed.add_field(name="API Key", value="Set" if api_key else "Not Set", inline=False)
        embed.add_field(name="Sync Interval", value=f"{interval} hours" if interval else "Unknown", inline=False)

        versions = (metadata or {}).get("versions", {})
        if versions:
            version_text = "\n".join(f"• {k}: `{v}`" for k, v in versions.items())
        else:
            version_text = "No cache metadata found."
        embed.add_field(name="Cached Versions", value=version_text, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="forcesync", description="Force a full sync from MCOCHUB")
    async def forcesync(self, interaction: discord.Interaction):
        if not await self._is_owner(interaction):
            await interaction.response.send_message("You must be a bot owner to use this command.", ephemeral=True)
            return
        if not getattr(self.core, "api", None):
            await interaction.response.send_message("Cannot sync: API key not set.", ephemeral=True)
            return
        await interaction.response.defer()
        ok = await getattr(self.core, "sync_data", lambda: False)()
        if ok:
            await interaction.followup.send("Sync complete.")
        else:
            await interaction.followup.send("Sync skipped (offline mode).")

    @app_commands.command(name="setsyncinterval", description="Set sync interval in hours")
    async def setsyncinterval(self, interaction: discord.Interaction, hours: int):
        if not await self._is_owner(interaction):
            await interaction.response.send_message("You must be a bot owner to use this command.", ephemeral=True)
            return
        if hours < 1:
            await interaction.response.send_message("Sync interval must be at least 1 hour.", ephemeral=True)
            return
        if not self.config:
            await interaction.response.send_message("Configuration backend not available.", ephemeral=True)
            return
        await self.config.sync_interval.set(hours)
        await interaction.response.send_message(f"Sync interval set to {hours} hours.", ephemeral=True)


class AdminSlashCog(commands.Cog):
    """Cog wrapper that registers the Admin app command group on cog_load/unload."""

    def __init__(self, bot):
        self.bot = bot
        self._group: Optional[_AdminGroup] = None

    async def cog_load(self):
        # Resolve core cog if present so the group can access config/cache/api
        core = getattr(self.bot, "mcoc_core", None) or self.bot.get_cog("MCOC") or self.bot.get_cog("MCOCPrefix")
        try:
            self._group = _AdminGroup(core or self.bot)
            # register the group on the tree; use try/except to avoid crashing load
            try:
                self.bot.tree.add_command(self._group)
            except Exception:
                log.exception("Failed to add Admin group to tree")
        except Exception:
            log.exception("Failed to initialize Admin group")

    async def cog_unload(self):
        # remove the group from the tree when the cog is unloaded
        try:
            if self._group:
                self.bot.tree.remove_command(self._group.name)
        except Exception:
            log.exception("Failed to remove Admin group from tree")

    # Optional: expose the group for diagnostics or other cogs
    @property
    def group(self) -> Optional[_AdminGroup]:
        return self._group


def setup(bot):
    try:
        bot.add_cog(AdminSlashCog(bot))
    except Exception:
        log.exception("Failed to add AdminSlashCog")
