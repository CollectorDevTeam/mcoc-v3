# Path: mcoc/common/core.py
# File-Version: 1.0
# File-Id: 8ba5afa0-27a4-4971-b118-23fdb47c47aa
# Purpose: Provide a centralized container for shared MCOC systems and manage their lifecycle.
# Public-API: MCOCCommonCore
# Last-Modified: 2026-09-01
# Changelog:
#   1.0 2026-09-01  Initial stabilized API header

"""
Lightweight shared systems container for MCOC.

Attach an instance to bot.mcoc_core via init_common_systems(bot).
Provides:
  - cache: CacheManager instance or None
  - api: MCOCHubAPI instance or None
  - cacheindex: cache.index or None
  - async_init coroutine to perform optional async initialization
  - close coroutine to gracefully shut down resources
  - health method for quick status checks
"""

from typing import Any, Optional, Dict
import logging
import time
import inspect
import asyncio

from mcoc.common.api.cache import CacheManager
from mcoc.common.api.api import MCOCHubAPI

log = logging.getLogger("red.mcoc.common.core")


class MCOCCommonCore:
    """
    Container for shared MCOC systems.

    Attributes:
      bot: the bot instance
      cache: CacheManager or None
      api: MCOCHubAPI or None
      cacheindex: cache.index or None
      ready: bool indicating async init success
    """

    def __init__(self, bot: Any):
        self.bot = bot
        self.ready: bool = False
        self._async_initialized: bool = False
        self.cache: Optional[CacheManager] = None
        self.api: Optional[MCOCHubAPI] = None
        self.cacheindex: Optional[Any] = None

        try:
            # Initialize cache manager
            self.cache = CacheManager(bot)
            # Provide a key getter that awaits the async Red token lookup method.
            async def _key_getter() -> Optional[str]:
                try:
                    getter = getattr(self.bot, "get_shared_api_tokens", None)
                    if not callable(getter):
                        return None
                    tokens = await getter("mcochub")
                    if isinstance(tokens, dict):
                        return tokens.get("api_key") or tokens.get("key") or tokens.get("apikey") or None
                    if isinstance(tokens, str):
                        return tokens
                    return None
                except Exception:
                    log.exception("Failed to resolve MCOCHub API key from bot")
                    return None

            # Initialize API wrapper
            self.api = MCOCHubAPI(api_key=None, key_getter=_key_getter)
            # Expose cacheindex if available
            self.cacheindex = getattr(self.cache, "index", None)

            log.debug("Initialized common systems: cache=%s api=%s cacheindex=%s", bool(self.cache), bool(self.api), bool(self.cacheindex))
        except Exception:
            log.exception("Failed to initialize common systems")
            self.cache = None
            self.api = None
            self.cacheindex = None
            self.ready = False
            self._async_initialized = False

    async def async_init(self) -> None:
        """
        Optional async initialization that is safe to call multiple times.

        Behavior:
          - If cache.load_all exists and is coroutine function, await it.
          - If cache.load_all exists and is sync, call it.
          - Same for cacheindex.build.
          - Sets self.ready True on success.
        """
        if getattr(self, "_async_initialized", False):
            log.debug("async_init already completed; skipping")
            return
        self._async_initialized = True

        start = time.perf_counter()
        try:
            # load cache data if available
            if self.cache is not None:
                load_all = getattr(self.cache, "load_all", None)
                if callable(load_all):
                    try:
                        if inspect.iscoroutinefunction(load_all):
                            await load_all()
                        else:
                            result = load_all()
                            if asyncio.iscoroutine(result):
                                await result
                        log.debug("Champion cache loaded")
                    except Exception:
                        log.exception("cache.load_all failed")

            # build cache index if available
            if self.cacheindex is not None:
                build_fn = getattr(self.cacheindex, "build", None)
                if callable(build_fn):
                    try:
                        if inspect.iscoroutinefunction(build_fn):
                            await build_fn()
                        else:
                            result = build_fn()
                            if asyncio.iscoroutine(result):
                                await result
                        log.debug("Cache index built")
                    except Exception:
                        log.exception("cacheindex.build failed")

            self.ready = True
            elapsed = time.perf_counter() - start
            log.debug("Completed async common initialization in %.3fs", elapsed)
        except Exception:
            self.ready = False
            log.exception("Failed during async common initialization")

    async def close(self) -> None:
        """
        Gracefully close resources. Safe to call from shutdown hooks.
        """
        try:
            if self.api is not None:
                close_fn = getattr(self.api, "close", None)
                if callable(close_fn):
                    try:
                        if inspect.iscoroutinefunction(close_fn):
                            await close_fn()
                        else:
                            result = close_fn()
                            if asyncio.iscoroutine(result):
                                await result
                        log.debug("MCOCHubAPI session closed from common core")
                    except Exception:
                        log.exception("Failed to close MCOCHubAPI session")
        except Exception:
            log.exception("Unexpected error during common core close")

    def health(self) -> Dict[str, bool]:
        """
        Return a small health summary of common subsystems.
        """
        return {
            "cache": bool(self.cache),
            "api": bool(self.api),
            "cacheindex": bool(self.cacheindex),
            "ready": bool(self.ready),
        }

    def __repr__(self) -> str:
        return f"<MCOCCommonCore cache={bool(self.cache)} api={bool(self.api)} ready={self.ready}>"


def init_common_systems(bot: Any) -> MCOCCommonCore:
    """
    Create and attach the shared system container to bot.mcoc_core.
    Returns the created core instance.
    """
    core = MCOCCommonCore(bot)
    setattr(bot, "mcoc_core", core)
    return core
