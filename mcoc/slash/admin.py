# Path: mcoc/slash/admin.py
# File-Version: 1.0
# File-Id: 1c3c96fe-3dc6-4e19-9f5a-612f84770c1f
# Purpose: Provide slash command handler for MCOC admin commands.
# Public-API: _AdminGroup
# Last-Modified: 2026-09-01
# Used-By: None
# Changelog:
#   1.0 2026-09-01  Initial stabilized API header
import logging
import discord
from redbot.core import commands
from redbot.core import app_commands
from typing import Optional

from ..common.components.componentsV2 import CDTEmbed, CDTPagesMenu
from ..common.helpers.admin_status import collect_admin_status_snapshot, build_admin_status_page_specs

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
        cache = getattr(self.core, "cache", None)
        if not cache:
            await interaction.response.send_message("Cache not available on core.", ephemeral=True)
            return

        api_key = None
        interval = None
        try:
            if self.config:
                api_key = await self.config.api_key()
                interval = await self.config.sync_interval()
        except Exception:
            pass

        health = getattr(cache, "health_check", None)
        health_summary = health() if callable(health) else {"ok": True, "issues": [], "details": {}}
        snapshot = await collect_admin_status_snapshot(self.core, cache, health_summary)
        specs = build_admin_status_page_specs(snapshot)
        color = discord.Color.gold() if bool(health_summary.get("ok", True)) else discord.Color.orange()

        pages = []
        total_pages = len(specs)
        for index, spec in enumerate(specs, start=1):
            description = spec.get("description", "")
            if index == 1:
                description = f"API Key: {'Set' if api_key else 'Not Set'}\nSync Interval: {str(interval) + ' hours' if interval else 'Unknown'}\n\n{description}"
            embed = CDTEmbed.embed(interaction, title=spec.get("title", "MCOC Status"), description=description, color=color)
            try:
                CDTEmbed.set_footer(interaction, embed, text=f"Page {index} of {total_pages} | Collector | Admin Status")
            except Exception:
                pass
            pages.append(embed)

        await interaction.response.send_message(embed=pages[0], view=CDTPagesMenu(pages, author=interaction.user), ephemeral=True)

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

    @app_commands.command(name="slashstatus", description="Show app-command tree registration status")
    async def slashstatus(self, interaction: discord.Interaction):
        if not await self._is_owner(interaction):
            await interaction.response.send_message("You must be a bot owner to use this command.", ephemeral=True)
            return

        tree = getattr(interaction.client, "tree", None)
        if tree is None:
            await interaction.response.send_message("Discord app command tree is unavailable.", ephemeral=True)
            return

        app_id = None
        owner = None
        try:
            info = await interaction.client.application_info()
            app_id = getattr(info, "id", None)
            owner = getattr(info, "owner", None)
        except Exception:
            pass

        try:
            top = [cmd.name for cmd in tree.get_commands()]
        except Exception:
            top = []

        embed = CDTEmbed.embed(interaction, title="Slash Registration Status")
        embed.add_field(name="Application ID", value=str(app_id or "unknown"), inline=False)
        embed.add_field(name="Owner", value=str(owner or "unknown"), inline=False)
        embed.add_field(name="Guild Count", value=str(len(getattr(interaction.client, "guilds", []) or [])), inline=True)
        embed.add_field(name="Top-level Slash Commands", value=", ".join(top) if top else "none", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="slashsync", description="Force app-command sync (guild sync is immediate)")
    async def slashsync(self, interaction: discord.Interaction, guild_id: Optional[str] = None):
        if not await self._is_owner(interaction):
            await interaction.response.send_message("You must be a bot owner to use this command.", ephemeral=True)
            return

        tree = getattr(interaction.client, "tree", None)
        if tree is None:
            await interaction.response.send_message("Discord app command tree is unavailable.", ephemeral=True)
            return

        try:
            if guild_id:
                gid = int(guild_id)
                result = await tree.sync(guild=discord.Object(id=gid))
                names = [getattr(cmd, "name", "?") for cmd in (result or [])]
                await interaction.response.send_message(
                    f"Guild slash sync complete for `{gid}` ({len(names)} commands): {', '.join(names[:50])}",
                    ephemeral=True,
                )
                return

            result = await tree.sync()
            names = [getattr(cmd, "name", "?") for cmd in (result or [])]
            await interaction.response.send_message(
                f"Global slash sync complete ({len(names)} commands): {', '.join(names[:50])}",
                ephemeral=True,
            )
        except Exception as exc:
            log.exception("Slash sync failed")
            await interaction.response.send_message(f"Slash sync failed: {type(exc).__name__} {exc}", ephemeral=True)


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


async def setup(bot):
    try:
        await bot.add_cog(AdminSlashCog(bot))
    except Exception:
        log.exception("Failed to add AdminSlashCog")
