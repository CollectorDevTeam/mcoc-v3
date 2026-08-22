# mcoc/core.py
import logging

log = logging.getLogger("red.mcoc")

async def setup(bot):
    """
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
        from .prefix.core import MCOCPrefix
        await bot.add_cog(MCOCPrefix(bot))
        log.debug("MCOCPrefix loaded")
    except Exception:
        log.exception("Failed to load MCOCPrefix")

    # ---------------------------------------------------------
    # 2) Load the REAL slash root: /mcoc
    # ---------------------------------------------------------
    try:
        from .slash.core import MCOCSlash
        await bot.add_cog(MCOCSlash(bot))
        log.debug("MCOCSlash loaded")
    except Exception:
        log.exception("Failed to load MCOCSlash (non-fatal)")

    # ---------------------------------------------------------
    # 3) Load diagnostics (optional)
    # ---------------------------------------------------------
    try:
        from .diagnostics.diagnostics import Diagnostics
        await bot.add_cog(Diagnostics(bot))
        log.debug("Diagnostics loaded")
    except Exception:
        log.exception("Failed to load Diagnostics (non-fatal)")

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
    log.debug("mcoc package setup complete")
