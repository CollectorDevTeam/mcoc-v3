# mcoc/core.py
import logging

log = logging.getLogger("red.mcoc")

async def setup(bot):
    """
    Unified loader for MCOC package.
    - Initialize shared systems (mcoc.common.core.init_common_systems)
    - Load unified prefix root (mcoc.prefix.core.MCOCPrefix)
    - Load unified slash root (mcoc.slash.core.MCOCSlash)
    - Load diagnostics (optional)
    """
    try: 
        from .common.core import  init_common_systems
        core = init_common_systems(bot)
        await core.async_init()
    except Exception:
        log.exception("Failed to load Common Core")

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
        from .prefix.core import MCOCPrefix
        await bot.add_cog(MCOCPrefix(bot))
        log.debug("MCOCPrefix loaded")
    except Exception:
        log.exception("Failed to load MCOCPrefix")

    # # 3) Load the unified slash root: /mcoc
    # try:
    #     from .slash.core import MCOCSlash
    #     await bot.add_cog(MCOCSlash(bot))
    #     log.debug("MCOCSlash loaded")
    # except Exception:
    #     log.exception("Failed to load MCOCSlash (non-fatal)")

    # 4) Diagnostics (optional)
    try:
        from .diagnostics.diagnostics import Diagnostics
        await bot.add_cog(Diagnostics(bot))
        log.debug("Diagnostics loaded")
    except Exception:
        log.exception("Failed to load Diagnostics (non-fatal)")

    log.debug("mcoc package setup complete")
