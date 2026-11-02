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
import inspect
import discord
from redbot.core import commands
from redbot.core import app_commands
from typing import Optional, Any

from ..common.components.componentsV2 import CDTEmbed, CDTPagesMenu
from ..common.helpers.admin_status import collect_admin_status_snapshot, build_admin_status_page_specs

log = logging.getLogger("red.mcoc.slash.admin")


def _interaction_done(interaction: discord.Interaction) -> bool:
    response = getattr(interaction, "response", None)
    if response is None or not hasattr(response, "is_done"):
        return False
    try:
        return bool(response.is_done())
    except Exception:
        return False


async def _edit_or_followup(
    interaction: discord.Interaction,
    *,
    content: Optional[str] = None,
    embed: Optional[discord.Embed] = None,
    view: Optional[discord.ui.View] = None,
    ephemeral: bool = True,
) -> None:
    if _interaction_done(interaction):
        try:
            await interaction.edit_original_response(content=content, embed=embed, view=view)
            return
        except Exception:
            pass
        try:
            await interaction.followup.send(content=content, embed=embed, view=view, ephemeral=ephemeral)
            return
        except Exception:
            pass

    response = getattr(interaction, "response", None)
    if response is not None and hasattr(response, "send_message"):
        try:
            await response.send_message(content=content, embed=embed, view=view, ephemeral=ephemeral)
            return
        except Exception:
            pass

    try:
        await interaction.followup.send(content=content, embed=embed, view=view, ephemeral=ephemeral)
    except Exception:
        log.exception("Failed to send interaction response")


class _AdminControlPanelView(discord.ui.View):
    def __init__(self, group: "_AdminGroup", requester_id: int):
        super().__init__(timeout=240)
        self.group = group
        self.requester_id = requester_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if getattr(interaction.user, "id", None) == self.requester_id:
            return True
        if await self.group._is_owner(interaction):
            return True
        await _edit_or_followup(interaction, content="Only the command invoker or a bot owner can use this panel.", ephemeral=True)
        return False

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, row=0)
    async def refresh_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        embed = await self.group._build_status_embed(interaction)
        await _edit_or_followup(interaction, embed=embed, view=self, ephemeral=True)

    @discord.ui.button(label="Diagnostics", style=discord.ButtonStyle.primary, row=0)
    async def diagnostics_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        embed = await self.group._build_status_embed(interaction)
        await _edit_or_followup(interaction, embed=embed, view=self, ephemeral=True)

        cache = self.group._cache_for(interaction)
        if cache is None:
            await interaction.followup.send("Diagnostics unavailable: cache subsystem is not attached.", ephemeral=True)
            return

        health = getattr(cache, "health_check", None)
        health_summary = health() if callable(health) else {"ok": True, "issues": [], "details": {}}
        snapshot = await collect_admin_status_snapshot(self.group._resolve_core(interaction), cache, health_summary)
        specs = build_admin_status_page_specs(snapshot)
        color = discord.Color.gold() if bool(health_summary.get("ok", True)) else discord.Color.orange()

        pages = []
        total_pages = len(specs)
        for index, spec in enumerate(specs, start=1):
            detail = CDTEmbed.embed(
                interaction,
                title=spec.get("title", "MCOC Diagnostics"),
                description=spec.get("description", ""),
                color=color,
            )
            try:
                CDTEmbed.set_footer(interaction, detail, text=f"Page {index} of {total_pages} | Collector | Admin Diagnostics")
            except Exception:
                pass
            pages.append(detail)

        if pages:
            await interaction.followup.send(embed=pages[0], view=CDTPagesMenu(pages, author=interaction.user), ephemeral=True)

    @discord.ui.button(label="Force Sync", style=discord.ButtonStyle.success, row=1)
    async def force_sync_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        ok, message = await self.group._execute_force_sync(interaction)
        embed = await self.group._build_status_embed(interaction)
        await _edit_or_followup(interaction, content=message, embed=embed, view=self, ephemeral=True)
        if not ok:
            log.warning("Admin panel force sync failed: %s", message)

    @discord.ui.button(label="Wipe Cache", style=discord.ButtonStyle.danger, row=1)
    async def wipe_cache_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await interaction.response.send_message(
            "Confirm full cache wipe? This deletes all cached JSON and requires a new sync.",
            view=_AdminWipeConfirmView(self.group, self),
            ephemeral=True,
        )


class _AdminWipeConfirmView(discord.ui.View):
    def __init__(self, group: "_AdminGroup", panel: _AdminControlPanelView):
        super().__init__(timeout=90)
        self.group = group
        self.panel = panel

    @discord.ui.button(label="YES, WIPE CACHE", style=discord.ButtonStyle.danger)
    async def yes_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        cache = self.group._cache_for(interaction)
        if cache is None or not callable(getattr(cache, "wipe_cache", None)):
            await _edit_or_followup(interaction, content="Cache wipe unavailable: cache subsystem is not attached.", ephemeral=True)
            return
        try:
            result = cache.wipe_cache()
            removed = int(result.get("removed") or 0) if isinstance(result, dict) else 0
            message = f"Cache wipe complete. Removed {removed} file(s)."
        except Exception as exc:
            log.exception("Cache wipe failed")
            message = f"Cache wipe failed: {type(exc).__name__}: {exc}"

        embed = await self.group._build_status_embed(interaction)
        await _edit_or_followup(interaction, content=message, embed=embed, view=self.panel, ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await _edit_or_followup(interaction, content="Cache wipe cancelled.", ephemeral=True)


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

    def _resolve_core(self, interaction: Optional[discord.Interaction] = None) -> Optional[Any]:
        candidates: list[Any] = []
        if self.core is not None:
            candidates.append(self.core)

        client = getattr(interaction, "client", None) if interaction else None
        if client is not None:
            direct = getattr(client, "mcoc_core", None)
            if direct is not None:
                candidates.append(direct)
            get_cog = getattr(client, "get_cog", None)
            if callable(get_cog):
                for name in ("MCOC", "MCOCPrefix", "MCOCSlash"):
                    cog = get_cog(name)
                    if cog is None:
                        continue
                    candidates.append(cog)
                    parent = getattr(cog, "parent", None)
                    if parent is not None:
                        candidates.append(parent)
                    core_attr = getattr(cog, "core", None)
                    if core_attr is not None:
                        candidates.append(core_attr)

        for candidate in candidates:
            if candidate is None:
                continue
            if callable(getattr(candidate, "sync_data", None)):
                return candidate
            cache = getattr(candidate, "cache", None)
            api = getattr(candidate, "api", None)
            if cache is not None and api is not None and callable(getattr(cache, "sync", None)):
                return candidate
        return None

    def _cache_for(self, interaction: Optional[discord.Interaction] = None) -> Optional[Any]:
        core = self._resolve_core(interaction) or self.core
        cache = getattr(core, "cache", None)
        if cache is not None:
            return cache
        candidate = core if core is not None else self.core
        return getattr(candidate, "cache", None)

    async def _build_status_embed(self, interaction: discord.Interaction) -> discord.Embed:
        cache = self._cache_for(interaction)
        if cache is None:
            return CDTEmbed.embed(
                interaction,
                title="MCOC Admin Control Panel",
                description="Cache subsystem is unavailable. Reload the `mcoc` cog and try again.",
                color=discord.Color.orange(),
            )

        meta = getattr(cache, "metadata", {}) or {}
        versions = meta.get("versions", {}) or {}
        last_sync = meta.get("last_sync") or "Never"

        health_fn = getattr(cache, "health_check", None)
        health = health_fn() if callable(health_fn) else {"ok": True, "issues": [], "details": {}}
        issues = health.get("issues", []) if isinstance(health, dict) else []
        details = (health.get("details", {}) if isinstance(health, dict) else {}) or {}

        api_attached = bool(getattr(self._resolve_core(interaction), "api", None) or getattr(self.core, "api", None))
        healthy_files = sum(1 for item in details.values() if isinstance(item, dict) and item.get("valid"))
        checked_files = len(details)

        embed = CDTEmbed.embed(
            interaction,
            title="MCOC Admin Control Panel",
            description="Use the buttons below to run diagnostics, force a sync, or wipe cached data.",
            color=discord.Color.gold() if not issues else discord.Color.orange(),
        )
        embed.add_field(name="Last Sync", value=str(last_sync), inline=False)
        embed.add_field(name="API Attached", value="Yes" if api_attached else "No", inline=True)
        embed.add_field(name="Cache Health", value="Healthy" if not issues else "Issues Detected", inline=True)
        embed.add_field(name="Files Valid", value=f"{healthy_files}/{checked_files}", inline=True)
        embed.add_field(
            name="Key Versions",
            value=(
                f"champions={str(versions.get('champions') or 'n/a')[:12]}\n"
                f"cocpit={str(versions.get('cocpit_champions') or 'n/a')[:12]}\n"
                f"champstats={str(versions.get('champstats') or 'n/a')[:12]}"
            ),
            inline=False,
        )
        if issues:
            preview = "\n".join(f"- {issue}" for issue in issues[:4])
            embed.add_field(name="Top Issues", value=preview or "Unknown issues", inline=False)
        try:
            CDTEmbed.set_footer(interaction, embed, text="Collector | Admin Panel")
        except Exception:
            pass
        return embed

    async def _execute_force_sync(self, interaction: discord.Interaction) -> tuple[bool, str]:
        core = self._resolve_core(interaction)
        if core is None:
            return False, "Sync unavailable: core.sync_data is not configured."
        if not getattr(core, "api", None):
            return False, "Cannot sync: API key not set."
        ok = await self._run_force_sync(core)
        if ok:
            return True, "Sync complete."
        return False, "Sync skipped or failed. Check diagnostics for details."

    async def _run_force_sync(self, core: Any) -> bool:
        sync_data = getattr(core, "sync_data", None)
        if callable(sync_data):
            result = sync_data()
            return bool(await result) if inspect.isawaitable(result) else bool(result)

        cache = getattr(core, "cache", None)
        api = getattr(core, "api", None)
        if cache is not None and api is not None and callable(getattr(cache, "sync", None)):
            return bool(await cache.sync(api, include_champstats=True))

        return False

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
        if not await self._is_owner(interaction):
            await interaction.response.send_message("You must be a bot owner to use this command.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        panel = _AdminControlPanelView(self, requester_id=getattr(interaction.user, "id", 0))
        embed = await self._build_status_embed(interaction)
        await _edit_or_followup(interaction, embed=embed, view=panel, ephemeral=True)

    @app_commands.command(name="forcesync", description="Force a full sync from MCOCHUB")
    async def forcesync(self, interaction: discord.Interaction):
        if not await self._is_owner(interaction):
            await interaction.response.send_message("You must be a bot owner to use this command.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        ok, message = await self._execute_force_sync(interaction)
        await interaction.followup.send(message, ephemeral=True)
        if not ok:
            log.warning("Standalone forcesync failed: %s", message)

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
