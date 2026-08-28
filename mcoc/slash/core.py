# mcoc/slash/core.py
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

    # async def _attach_slash_cogs(self):
    #     try:
    #         from .champions import ChampionSlashCog
    #         await self.bot.add_cog(ChampionSlashCog(self.bot))
    #         log.debug("ChampionSlashCog loaded (slash)")
    #     except Exception:
    #         log.exception("Failed to load ChampionSlashCog")

    #     try:
    #         from .roster import RosterSlashCog
    #         await self.bot.add_cog(RosterSlashCog(self.bot))
    #         log.debug("RosterSlashCog loaded (slash)")
    #     except Exception:
    #         log.exception("Failed to load RosterSlashCog")

    #     try:
    #         from .admin import AdminSlashCog
    #         await self.bot.add_cog(AdminSlashCog(self.bot))
    #         log.debug("AdminSlashCog loaded (slash)")
    #     except Exception:
    #         log.debug("AdminSlashCog not present (optional)")

    @commands.Cog.listener()
    async def on_ready(self):
        self.parent = getattr(self.bot, "mcoc_core", None)

    async def cog_unload(self):
        try:
            if getattr(self.bot, "mcoc_slash", None) is self:
                delattr(self.bot, "mcoc_slash")
        except Exception:
            pass


async def setup(bot):
    try:
        cog = MCOCSlash(bot)
        await bot.add_cog(cog)
        bot.mcoc_slash = cog
        log.debug("MCOCSlash loaded")
    except Exception:
        log.exception("Failed to add MCOCSlash")
