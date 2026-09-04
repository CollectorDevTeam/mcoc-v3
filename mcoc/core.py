# Path: mcoc/core.py
# File-Version: 1.0
# File-Id: f8e367b2-24bd-436b-834c-b26b77bc6af9
# Purpose: Provide the main setup function for the MCOC package, initializing shared systems and registering feature cogs.
# Public-API: setup
# Last-Modified: 2026-09-01
# Changelog:
#   1.0 2026-09-01  Initial stabilized API header
"""
Unified package loader for MCOC.

Responsibilities:
 - initialize shared systems (mcoc.common.core.init_common_systems)
 - attach the shared core container to bot.mcoc_core
 - perform optional async initialization of common systems
 - register the compatibility prefix root (MCOCPrefix)
 - register top-level feature cogs when available (AccountPrefix, RosterPrefix, AlliancePrefix, ChampionsPrefix, MCOCAdminPrefix)
 - load optional slash root and diagnostics if present

This file intentionally prefers explicit Cog registration for the feature modules
so top-level commands (///account, ///roster, ///alliance, ///champ) are available
immediately and can be reloaded independently during development.
"""

from typing import Any
import logging

log = logging.getLogger("red.mcoc")


async def setup(bot: Any) -> None:
    """
    Async setup entrypoint called by Red when the mcoc package is loaded.
    """
    # 1) Initialize shared systems and attach to bot.mcoc_core
    core = None
    try:
        from .common.core import init_common_systems
        core = init_common_systems(bot)
        # attach to bot explicitly (init_common_systems does this, but be explicit)
        setattr(bot, "mcoc_core", core)
    except Exception:
        log.exception("Failed to create common core container")
        core = None

    # 2) Optional async initialization of common systems (idempotent)
    if core is not None:
        try:
            # async_init may raise or be missing; guard defensively
            async_init = getattr(core, "async_init", None)
            if callable(async_init):
                try:
                    await async_init()
                except Exception:
                    log.exception("common core async_init failed (continuing)")
            else:
                log.debug("common core has no async_init; skipping")
        except Exception:
            log.exception("Unexpected error during common core async init")

    # 3) Register the compatibility prefix root (///mcoc)
    try:
        from .prefix.core import MCOCPrefix
        try:
            await bot.add_cog(MCOCPrefix(bot))
            log.debug("MCOCPrefix loaded")
        except Exception:
            # Some Red installs expect synchronous add_cog; try fallback
            try:
                bot.add_cog(MCOCPrefix(bot))
                log.debug("MCOCPrefix loaded (sync fallback)")
            except Exception:
                log.exception("Failed to add MCOCPrefix cog")
    except Exception:
        log.exception("Failed to import MCOCPrefix (compatibility root)")

    # 4) Register top-level prefix feature cogs if present.
    #    These are optional; failures are non-fatal but logged.
    #    Registering them here ensures ///account, ///roster, ///alliance, ///champ, ///mcocadmin exist.
    feature_cogs = [
        ("mcoc.prefix.account", "AccountPrefix"),
        ("mcoc.prefix.roster", "RosterPrefix"),
        ("mcoc.prefix.alliance", "AlliancePrefix"),
        ("mcoc.prefix.champions", "ChampionsPrefix"),
        ("mcoc.prefix.admin", "MCOCAdminPrefix"),
    ]

    for module_path, class_name in feature_cogs:
        try:
            mod = __import__(module_path, fromlist=[class_name])
            cog_cls = getattr(mod, class_name, None)
            if cog_cls is None:
                log.debug("Module %s loaded but %s not found; skipping", module_path, class_name)
                continue
            try:
                await bot.add_cog(cog_cls(bot))
                log.debug("Loaded feature cog %s from %s", class_name, module_path)
            except Exception:
                # fallback to sync add_cog if async add_cog fails
                try:
                    bot.add_cog(cog_cls(bot))
                    log.debug("Loaded feature cog %s (sync fallback) from %s", class_name, module_path)
                except Exception:
                    log.exception("Failed to add feature cog %s from %s", class_name, module_path)
        except ModuleNotFoundError:
            # Not installed in this environment; skip quietly at debug level
            log.debug("Feature module %s not present; skipping", module_path)
        except Exception:
            log.exception("Failed to import feature module %s", module_path)

    # 5) Optional: load slash root if available (non-fatal)
    try:
        from .slash.core import MCOCSlash  # type: ignore
        try:
            await bot.add_cog(MCOCSlash(bot))
            log.debug("MCOCSlash loaded")
        except Exception:
            try:
                bot.add_cog(MCOCSlash(bot))
                log.debug("MCOCSlash loaded (sync fallback)")
            except Exception:
                log.exception("Failed to add MCOCSlash cog")
    except ModuleNotFoundError:
        log.debug("Slash core not present; skipping")
    except Exception:
        log.exception("Failed to import MCOCSlash (non-fatal)")

    # 6) Optional diagnostics cog (non-fatal)
    try:
        from .diagnostics.diagnostics import Diagnostics  # type: ignore
        try:
            await bot.add_cog(Diagnostics(bot))
            log.debug("Diagnostics loaded")
        except Exception:
            try:
                bot.add_cog(Diagnostics(bot))
                log.debug("Diagnostics loaded (sync fallback)")
            except Exception:
                log.exception("Failed to add Diagnostics cog")
    except ModuleNotFoundError:
        log.debug("Diagnostics module not present; skipping")
    except Exception:
        log.exception("Failed to import Diagnostics (non-fatal)")

    log.debug("mcoc package setup complete")
