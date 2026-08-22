# mcoc/core.py (good)
import logging

log = logging.getLogger("red.mcoc")

async def setup(bot):
    """
    Top-level async setup called by Red. Await bot.add_cog for each cog.
    """
    # 1) Prefix implementation (primary user-facing commands)
    try:
        from .prefix.commands_prefix import MCOCPrefix
        await bot.add_cog(MCOCPrefix(bot))
        log.debug("MCOCPrefix loaded")
    except Exception:
        log.exception("Failed to load MCOCPrefix")

    # 2) Diagnostics (owner-only)
    try:
        from .diagnostics.diagnostics import Diagnostics
        await bot.add_cog(Diagnostics(bot))
        log.debug("Diagnostics loaded")
    except Exception:
        log.exception("Failed to load Diagnostics (non-fatal)")
