# mcoc/core.py
import logging

log = logging.getLogger("red.mcoc")

async def setup(bot):
    """
<<<<<<< HEAD
    Unified loader for MCOC package.
    - Initialize shared systems (mcoc.common.core.init_common_systems)
    - Load unified prefix root (mcoc.prefix.core.MCOCPrefix)
    - Load unified slash root (mcoc.slash.core.MCOCSlash)
    - Load diagnostics (optional)
    """

    # 1) Initialize shared systems (sets bot.mcoc_core)
    try:
        from .common.core import init_common_systems
        core = init_common_systems(bot)
        # run optional async init if implemented
        try:
            await core.async_init()
        except Exception:
            # async_init may be missing or fail; log and continue
            log.debug("common core async_init skipped or failed", exc_info=True)
        log.debug("Common systems initialized")
    except Exception:
        log.exception("Failed to initialize common systems")

    # 2) Load the unified prefix root: ///mcoc
    try:
=======
    Unified loader for all MCOC components.
    Loads:
        - Prefix root: MCOCPrefix  (///mcoc ...)
        - Slash root:  MCOCSlash   (/mcoc ...)
        - Diagnostics (optional)
        - Core cog (the one that owns cache/api)
    """

    # ---------------------------------------------------------
    # 1) Load the REAL prefix root: ///mcoc
    # ---------------------------------------------------------
    try:
>>>>>>> 2d2994f5d25d92f6ada7363380459e61dc28a29d
        from .prefix.core import MCOCPrefix
        await bot.add_cog(MCOCPrefix(bot))
        log.debug("MCOCPrefix loaded")
    except Exception:
        log.exception("Failed to load MCOCPrefix")

<<<<<<< HEAD
    # 3) Load the unified slash root: /mcoc
=======
    # ---------------------------------------------------------
    # 2) Load the REAL slash root: /mcoc
    # ---------------------------------------------------------
>>>>>>> 2d2994f5d25d92f6ada7363380459e61dc28a29d
    try:
        from .slash.core import MCOCSlash
        await bot.add_cog(MCOCSlash(bot))
        log.debug("MCOCSlash loaded")
    except Exception:
        log.exception("Failed to load MCOCSlash (non-fatal)")

<<<<<<< HEAD
    # 4) Diagnostics (optional)
=======
    # ---------------------------------------------------------
    # 3) Load diagnostics (optional)
    # ---------------------------------------------------------
>>>>>>> 2d2994f5d25d92f6ada7363380459e61dc28a29d
    try:
        from .diagnostics.diagnostics import Diagnostics
        await bot.add_cog(Diagnostics(bot))
        log.debug("Diagnostics loaded")
    except Exception:
        log.exception("Failed to load Diagnostics (non-fatal)")

<<<<<<< HEAD
=======
    # ---------------------------------------------------------
    # 4) Load the REAL core cog (the one that owns cache/api)
    # ---------------------------------------------------------
    try:
        from .core_cog import MCOC
        core = MCOC(bot)
        await bot.add_cog(core)
        bot.mcoc_core = core
        log.debug("Core MCOC attached as bot.mcoc_core")
    except Exception:
        log.exception("Failed to load core MCOC cog")

    # ---------------------------------------------------------
    # 5) Done
    # ---------------------------------------------------------
>>>>>>> 2d2994f5d25d92f6ada7363380459e61dc28a29d
    log.debug("mcoc package setup complete")
