# mcoc/prefix/core.py
import logging
from typing import Any
from redbot.core import commands

log = logging.getLogger("red.mcoc.prefix.core")

from ..common.champion_helpers import safe_send_ctx


class MCOCPrefix(commands.Cog):
    """
    Unified prefix command root for MCOC.
    Provides:
        ///mcoc champ   (champion prefix commands)
        ///mcoc roster  (roster prefix commands)
        ///mcoc admin   (admin prefix commands)
    """

    def __init__(self, bot: Any):
        self.bot = bot

        # core may not be loaded yet; attach later
        self.parent = getattr(bot, "mcoc_core", None) or bot.get_cog("MCOC")

        # attempt registrar attach now
        try:
            self._attach_registrars()
        except Exception:
            log.debug("Initial registrar attach failed; will retry in cog_load", exc_info=True)

    async def cog_load(self):
        # refresh core reference
        self.parent = getattr(self.bot, "mcoc_core", None) or self.bot.get_cog("MCOC")

        try:
            self._attach_registrars()
        except Exception:
            log.exception("Registrar attach failed in cog_load")

    def _ensure_parent(self):
        """
        Return the core cog if available.
        """
        return getattr(self, "parent", None) or self.bot.get_cog("MCOC")

    def _attach_registrars(self):
        """
        Attach champion, roster, and admin registrars to their mcoc subgroups.
        """

        parent_getter = lambda: self._ensure_parent()

        # --------------------------
        # ACCOUNT (optional)
        # --------------------------
        try:
            from .account_prefix import register_with_group as reg_account
            account_group = getattr(self, "account")
            reg_account(account_group, parent_getter)
            log.debug("Attached account registrar to ///mcoc account")
        except Exception:
            log.debug("Account registrar not present (optional)")

        # --------------------------
        # CHAMPIONS
        # --------------------------
        try:
            from .champions_prefix import register_with_group as reg_champ
            champ_group = getattr(self, "champ")
            reg_champ(champ_group, parent_getter)
            log.debug("Attached champions registrar to ///mcoc champ")
        except Exception:
            log.exception("Failed to attach champions registrar")

        # --------------------------
        # ROSTER
        # --------------------------
        try:
            from .roster_prefix import register_with_group as reg_roster
            roster_group = getattr(self, "roster")
            reg_roster(roster_group, parent_getter)
            log.debug("Attached roster registrar to ///mcoc roster")
        except Exception:
            log.exception("Failed to attach roster registrar")

        # --------------------------
        # ADMIN (optional)
        # --------------------------
        try:
            from .mcocadmin_prefix import register_with_group as reg_admin
            admin_group = getattr(self, "admin")
            reg_admin(admin_group, parent_getter)
            log.debug("Attached admin registrar to ///mcoc admin")
        except Exception:
            log.debug("Admin registrar not present (optional)")

    # ============================================================
    # TOP-LEVEL GROUP
    # ============================================================
    @commands.group(name="mcoc", invoke_without_command=True)
    async def mcoc(self, ctx):
        await safe_send_ctx(
            ctx,
            "Subcommands: `champ`, `roster`, `admin`, `account`, `status`"
        )

    @mcoc.command(name="status")
    async def mcoc_status(self, ctx):
        core = self._ensure_parent()
        cache = getattr(core, "cache", None) if core else None
        await safe_send_ctx(
            ctx,
            f"MCOC core attached: {bool(core)}\nCache available: {bool(cache)}"
        )

    # ============================================================
    # SUBGROUPS
    # ============================================================
    @mcoc.group(name="champ", invoke_without_command=True)
    async def champ(self, ctx):
        await safe_send_ctx(ctx, "Champion commands: info, abilities, synergies, tags, stats, search, calcstats")

    @mcoc.group(name="roster", invoke_without_command=True)
    async def roster(self, ctx):
        await safe_send_ctx(ctx, "Roster commands: add, remove, update, list, export, clear")

    @mcoc.group(name="admin", invoke_without_command=True)
    async def admin(self, ctx):
        await safe_send_ctx(ctx, "Admin commands: status, sync, debug (if implemented)")

    @mcoc.group(name="account", invoke_without_command=True)
    async def account(self, ctx):
        await safe_send_ctx(ctx, "Account commands: info, link, unlink")


async def setup(bot):
    try:
        await bot.add_cog(MCOCPrefix(bot))
        log.debug("MCOCPrefix loaded")
    except Exception:
        log.exception("Failed to add MCOCPrefix")
