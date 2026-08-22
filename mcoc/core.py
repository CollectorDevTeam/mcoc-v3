# mcoc/core.py
import logging

log = logging.getLogger("red.mcoc")

def setup(bot):
    """
    Top-level loader called by Red. Add cogs defensively so one failing
    submodule doesn't prevent others from loading.
    """
    # 1) Prefix implementation (primary user-facing commands)
    try:
        from .prefix.commands_prefix import MCOCPrefix
        bot.add_cog(MCOCPrefix(bot))
        log.debug("MCOCPrefix loaded")
    except Exception:
        log.exception("Failed to load MCOCPrefix")

    # 2) Diagnostics (owner-only prefix diagnostics) — optional but useful
    try:
        from .diagnostics.diagnostics import Diagnostics
        bot.add_cog(Diagnostics(bot))
        log.debug("Diagnostics loaded")
    except Exception:
        log.exception("Failed to load Diagnostics (non-fatal)")

    # 3) Do NOT auto-register slash groups here unless you want them global.
    # If you want slash groups registered automatically, do so in a safe try/except:
    # try:
    #     from .slash.champions_slash import ChampionSlash
    #     bot.add_cog(ChampionSlash(bot))
    # except Exception:
    #     log.exception("Failed to load ChampionSlash")
