# mcoc/core.py (good)
import logging

log = logging.getLogger("red.mcoc")

async def setup(bot):
    """
    Top-level async setup called by Red. Await bot.add_cog for each cog.
    """
    # 1) Prefix implementation (primary user-facing commands)
    try:
        from .prefix.mcocadmin_prefix import MCOCPrefix
        await bot.add_cog(MCOCPrefix(bot))
        log.debug("MCOCPrefix loaded")
    except Exception:
        log.exception("Failed to load MCOCPrefix")

    # 2) Diagnostics (owner-only)a
    try:
        from .diagnostics.diagnostics import Diagnostics
        await bot.add_cog(Diagnostics(bot))
        log.debug("Diagnostics loaded")
    except Exception:
        log.exception("Failed to load Diagnostics (non-fatal)")

    # 3) Slash app command wrapper cogs (register app command Groups on cog_load)
    try:
        from .slash.champions_slash import ChampionSlashCog
        await bot.add_cog(ChampionSlashCog(bot))
        log.debug("ChampionSlashCog loaded")
    except Exception:
        log.exception("Failed to load ChampionSlashCog (non-fatal)")

    try:
        from .slash.roster_slash import RosterSlashCog
        await bot.add_cog(RosterSlashCog(bot))
        log.debug("RosterSlashCog loaded")
    except Exception:
        log.exception("Failed to load RosterSlashCog (non-fatal)")

    try:
        from .slash.admin_slash import AdminSlashCog
        await bot.add_cog(AdminSlashCog(bot))
        log.debug("AdminSlashCog loaded")
    except Exception:
        log.exception("Failed to load AdminSlashCog (non-fatal)")


    # Prefix cogs for champion and roster text commands
    try:
        from .prefix.champions_prefix import ChampionsPrefix
        await bot.add_cog(ChampionsPrefix(bot))
        log.debug("ChampionsPrefix loaded")
    except Exception:
        log.exception("Failed to load ChampionsPrefix (non-fatal)")

    try:
        from .prefix.roster_prefix import RosterPrefix
        await bot.add_cog(RosterPrefix(bot))
        log.debug("RosterPrefix loaded")
    except Exception:
        log.exception("Failed to load RosterPrefix (non-fatal)")
