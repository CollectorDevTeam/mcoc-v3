# mcoc/common/core.py
import logging

log = logging.getLogger("red.mcoc.common.core")

from .cache import CacheManager
from .api import MCOCHUBAPI as APIClient
from .cacheindex import CacheIndex


class MCOCCommonCore:
    """
    Lightweight container for shared MCOC systems:
        - cache
        - api
        - cacheindex

    This is NOT a Cog.
    It is imported by mcoc/core.py and attached to bot.mcoc_core.
    Prefix and slash layers read shared systems from bot.mcoc_core.
    """

    def __init__(self, bot):
        self.bot = bot

        # ---------------------------------------------------------
        # Initialize shared systems
        # ---------------------------------------------------------
        try:
            self.cache = CacheManager(bot)
            self.api = APIClient(bot)
            self.cacheindex = CacheIndex(bot)

            log.debug("Initialized common systems: cache, api, cacheindex")

        except Exception:
            log.exception("Failed to initialize common systems")
            self.cache = None
            self.api = None
            self.cacheindex = None

    async def async_init(self):
        """
        Optional async initialization:
            - load champion data
            - build cache index
        """
        try:
            if hasattr(self.cache, "load_all"):
                await self.cache.load_all()
                log.debug("Champion cache loaded")

            if hasattr(self.cacheindex, "build"):
                await self.cacheindex.build()
                log.debug("Cache index built")

        except Exception:
            log.exception("Failed during async common initialization")


def init_common_systems(bot):
    """
    Create the shared system container and attach it to bot.mcoc_core.
    Called once from mcoc/core.py.
    """
    core = MCOCCommonCore(bot)
    bot.mcoc_core = core
    return core
