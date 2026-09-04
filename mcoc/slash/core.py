# Path: mcoc/slash/core.py
# File-Version: 1.0
# File-Id: 3b1f5d2a-8c4e-4f7a-9b2a-1d2f3e4c5b6d
# Purpose: Provide unified slash command root for MCOC, loading champion, roster, and admin slash cogs.
# Public-API: MCOCSlash
# Last-Modified: 2026-09-01
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
        # DO NOT call async functions here
        # slash cogs will attach in cog_load
        log.debug("MCOCSlash initialized (waiting for cog_load)")

    async def cog_load(self):
        # refresh parent reference
        self.parent = getattr(self.bot, "mcoc_core", None)

        try:
            await self._attach_slash_cogs()
        except Exception:
            log.exception("Failed to attach slash cogs in cog_load")

    async def _attach_slash_cogs(self):
        slash_cogs = [
            ("mcoc.slash.champions", "ChampionSlashCog"),
            ("mcoc.slash.roster", "RosterSlashCog"),
            ("mcoc.slash.admin", "AdminSlashCog"),
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

    @commands.Cog.listener()
    async def on_ready(self):
        self.parent = getattr(self.bot, "mcoc_core", None)

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
