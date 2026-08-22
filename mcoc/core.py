# mcoc/core.py
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

    # 2) Diagnostics (owner-only)
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

    # 4) Prefix cogs for champion and roster text commands
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

    # Ensure the core cog is discoverable by other cogs/registrars.
    # If your main core cog is named "MCOC" (class name or cog name), prefer to set it here.
    try:
        core = bot.get_cog("MCOC")
        if core:
            setattr(bot, "mcoc_core", core)
            log.debug("bot.mcoc_core set from existing cog 'MCOC'")
        else:
            # If the core cog is implemented under a different name or created elsewhere,
            # this is a safe no-op; registrars will still attempt bot.get_cog("MCOC") at runtime.
            log.debug("No 'MCOC' cog found to attach as bot.mcoc_core")
    except Exception:
        log.exception("Failed to set bot.mcoc_core")

    # Done
    log.debug("mcoc package setup complete")
