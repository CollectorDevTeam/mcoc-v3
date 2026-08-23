# mcoc/slash/core.py
import logging
from typing import Any
from redbot.core import commands

log = logging.getLogger("red.mcoc.slash.core")


class MCOCSlash(commands.Cog):
    """
    Unified slash command root for MCOC.
    This cog loads the slash-layer cogs (champ, roster, admin).
    Each slash cog is expected to register its app command groups on cog_load.
    """

    def __init__(self, bot: Any):
        self.bot = bot
        # shared systems container created by mcoc/common/core.py
        self.parent = getattr(bot, "mcoc_core", None)
        # allow re-attach attempts if slash cogs load later
        try:
            self._attach_slash_cogs()
        except Exception:
            log.debug("Initial attach of slash cogs failed; will retry in cog_load", exc_info=True)

    async def cog_load(self):
        # refresh parent reference and try again
        self.parent = getattr(self.bot, "mcoc_core", None)
        try:
            self._attach_slash_cogs()
        except Exception:
            log.exception("Failed to attach slash cogs in cog_load")

    async def _attach_slash_cogs(self):
        from .champions_slash import ChampionSlashCog
        await self.bot.add_cog(ChampionSlashCog(self.bot))

        from .roster_slash import RosterSlashCog
        await self.bot.add_cog(RosterSlashCog(self.bot))

        from .admin_slash import AdminSlashCog
        await self.bot.add_cog(AdminSlashCog(self.bot))


    @commands.Cog.listener()
    async def on_ready(self):
        # refresh parent when bot is ready
        self.parent = getattr(self.bot, "mcoc_core", None)

    async def cog_unload(self):
        # attempt to clear any references
        try:
            if getattr(self.bot, "mcoc_slash", None) is self:
                delattr(self.bot, "mcoc_slash")
        except Exception:
            pass


async def setup(bot):
    try:
        cog = MCOCSlash(bot)
        await bot.add_cog(cog)
        # make discoverable if other code wants it
        try:
            bot.mcoc_slash = cog
        except Exception:
            pass
        log.debug("MCOCSlash loaded")
    except Exception:
        log.exception("Failed to add MCOCSlash")
