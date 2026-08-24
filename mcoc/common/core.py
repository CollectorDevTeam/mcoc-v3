# mcoc/common/core.py
import logging
import time

log = logging.getLogger("red.mcoc.common.core")

from .cache import CacheManager
from .api import MCOCHubAPI
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
        self.ready = False
        self._async_initialized = False
        # ---------------------------------------------------------
        # Initialize shared systems
        # ---------------------------------------------------------
        try:
            self.cache = CacheManager(bot)
            self.api = MCOCHubAPI(
                api_key=None,
                key_getter=lambda: self.bot.get_shared_api_tokens("mcochub")
            )
            self.cacheindex = self.cache.index

            log.debug("Initialized common systems: cache, api, cacheindex")

        except Exception:
            log.exception("Failed to initialize common systems")
            self.cache = None
            self.api = None
            self.cacheindex = None
            # ensure flags are defined even on failure
            self.ready = False
            self._async_initialized = False

    async def async_init(self):
        """
        Optional async initialization:
            - load champion data
            - build cache index

        This method is idempotent and sets a ready flag on success.
        """
        # idempotent async init
        if getattr(self, "_async_initialized", False):
            log.debug("async_init already completed; skipping")
            return
        self._async_initialized = True

        start = time.perf_counter()
        try:
            if hasattr(self.cache, "load_all"):
                await self.cache.load_all()
                log.debug("Champion cache loaded")

            if hasattr(self.cacheindex, "build"):
                await self.cacheindex.build()
                log.debug("Cache index built")

            self.ready = True
            elapsed = time.perf_counter() - start
            log.debug("Completed async common initialization in %.3fs", elapsed)
        except Exception:
            self.ready = False
            log.exception("Failed during async common initialization")

    # mcoc/common/core.py (add method to MCOCCommonCore)
    async def close(self):
        try:
            if getattr(self, "api", None):
                await self.api.close()
                log.debug("MCOCHubAPI session closed from common core")
        except Exception:
            log.exception("Failed to close MCOCHubAPI session")

    def health(self) -> dict:
        """
        Return a small health summary of common subsystems.
        """
        return {
            "cache": bool(getattr(self, "cache", None)),
            "api": bool(getattr(self, "api", None)),
            "cacheindex": bool(getattr(self, "cacheindex", None)),
            "ready": bool(getattr(self, "ready", False)),
        }


def init_common_systems(bot):
    """
    Create the shared system container and attach it to bot.mcoc_core.
    Called once from mcoc/core.py.
    """
    core = MCOCCommonCore(bot)
    bot.mcoc_core = core
    return core
