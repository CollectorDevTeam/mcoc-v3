# Path: mcoc/slash/core.py
# File-Version: 1.0
# File-Id: 3b1f5d2a-8c4e-4f7a-9b2a-1d2f3e4c5b6d
# Purpose: Provide unified slash command root for MCOC, loading champion, roster, and admin slash cogs.
# Public-API: MCOCSlash
# Last-Modified: 2026-09-01
# Used-By: None
# Changelog:
#   1.0 2026-09-01  Initial stabilized API header
import logging
from typing import Any
from redbot.core import commands

log = logging.getLogger("red.mcoc.slash.core")


class MCOCSlash(commands.Cog):
    """
    Unified slash command root for MCOC.
    Loads slash-layer cogs (champ, roster, admin).
    """

    def __init__(self, bot: Any):
        self.bot = bot
        self.parent = getattr(bot, "mcoc_core", None)
        self._last_registration_report = {}
        # DO NOT call async functions here
        # slash cogs will attach in cog_load
        log.debug("MCOCSlash initialized (waiting for cog_load)")

    async def cog_load(self):
        # refresh parent reference
        self.parent = getattr(self.bot, "mcoc_core", None)

        try:
            await self._attach_slash_cogs()
            await self._ensure_groups_registered()
        except Exception:
            log.exception("Failed to attach slash cogs in cog_load")

    async def _attach_slash_cogs(self):
        slash_cogs = [
            ("mcoc.slash.champions", "ChampionSlashCog"),
            ("mcoc.slash.alliance", "AllianceSlashCog"),
            ("mcoc.slash.roster", "RosterSlashCog"),
            ("mcoc.slash.account", "AccountSlashCog"),
            ("mcoc.slash.admin", "AdminSlashCog"),
            ("mcoc.slash.contextmenu", "ContextMenuSlashCog"),
        ]

        for module_name, class_name in slash_cogs:
            try:
                mod = __import__(module_name, fromlist=[class_name])
                cog_cls = getattr(mod, class_name, None)
                if cog_cls is None:
                    log.debug("Slash module %s missing %s; skipping", module_name, class_name)
                    continue
                if self.bot.get_cog(class_name):
                    log.debug("Slash cog %s already loaded; skipping", class_name)
                    continue
                try:
                    await self.bot.add_cog(cog_cls(self.bot))
                    log.debug("%s loaded (slash)", class_name)
                except Exception:
                    try:
                        self.bot.add_cog(cog_cls(self.bot))
                        log.debug("%s loaded (slash, sync fallback)", class_name)
                    except Exception:
                        log.exception("Failed to load %s", class_name)
            except ModuleNotFoundError:
                log.debug("Slash module %s not present; skipping", module_name)
            except Exception:
                log.exception("Failed to import slash cog %s", class_name)

    def _tree_clear_disabled(self, name: str) -> None:
        """Best effort cleanup for trees that keep disabled command names across reloads."""
        if not name:
            return
        try:
            disabled = getattr(self.bot.tree, "_disabled_global_commands", None)
            if isinstance(disabled, dict):
                disabled.pop(name, None)
        except Exception:
            pass

    def _tree_register_group(self, group: Any) -> tuple[bool, str]:
        """Register an app_commands.Group with robust fallback and override support."""
        if group is None:
            return False, "group object is None"
        name = getattr(group, "name", None)
        if not name:
            return False, "group has no name"

        self._tree_clear_disabled(name)

        try:
            self.bot.tree.add_command(group, override=True)
            try:
                names = [getattr(c, "name", None) for c in self.bot.tree.get_commands()]
            except Exception:
                names = []
            if name in names:
                return True, "registered via add_command(override=True)"
            return False, "add_command(override=True) returned but group not visible in tree.get_commands()"
        except TypeError:
            # Older discord.py variants may not support override kwarg.
            pass
        except Exception:
            pass

        try:
            self.bot.tree.remove_command(name)
        except Exception:
            pass

        try:
            self._tree_clear_disabled(name)
            self.bot.tree.add_command(group)
            try:
                names = [getattr(c, "name", None) for c in self.bot.tree.get_commands()]
            except Exception:
                names = []
            if name in names:
                return True, "registered via remove+add fallback"
            return False, "remove+add fallback returned but group not visible in tree.get_commands()"
        except Exception as exc:
            log.exception("Failed to register slash group %s", name)
            return False, f"{type(exc).__name__}: {exc}"

    async def _ensure_groups_registered(self):
        """Ensure loaded slash cog groups are actually attached to the app command tree."""
        cogs = [
            "ChampionSlashCog",
            "AllianceSlashCog",
            "RosterSlashCog",
            "AccountSlashCog",
            "AdminSlashCog",
        ]

        registered = []
        missing = []
        report = {}
        for cog_name in cogs:
            cog = self.bot.get_cog(cog_name)
            if cog is None:
                missing.append(cog_name)
                report[cog_name] = {
                    "cog_loaded": False,
                    "group_present": False,
                    "group_name": None,
                    "registered": False,
                    "detail": "cog not loaded",
                }
                continue

            group = getattr(cog, "group", None)
            if group is None:
                group = getattr(cog, "_group", None)

            ok, detail = self._tree_register_group(group)
            group_name = getattr(group, "name", None) if group is not None else None
            report[cog_name] = {
                "cog_loaded": True,
                "group_present": group is not None,
                "group_name": group_name,
                "registered": ok,
                "detail": detail,
            }
            if ok:
                registered.append(group_name or cog_name)
            else:
                missing.append(cog_name)

        self._last_registration_report = report

        if registered:
            log.info("MCOC slash groups registered: %s", ", ".join(registered))
        if missing:
            log.warning("MCOC slash groups missing/unregistered: %s", ", ".join(missing))

    def get_registration_report(self):
        """Return the most recent slash group registration report."""
        return dict(self._last_registration_report or {})

    @commands.Cog.listener()
    async def on_ready(self):
        self.parent = getattr(self.bot, "mcoc_core", None)
        try:
            await self._ensure_groups_registered()
        except Exception:
            log.exception("Failed to ensure slash groups on_ready")

    async def cog_unload(self):
        try:
            if getattr(self.bot, "mcoc_slash", None) is self:
                delattr(self.bot, "mcoc_slash")
        except Exception:
            pass


# async def setup(bot):
#     try:
#         cog = MCOCSlash(bot)
#         await bot.add_cog(cog)
#         bot.mcoc_slash = cog
#         log.debug("MCOCSlash loaded")
#     except Exception:
#         log.exception("Failed to add MCOCSlash")
