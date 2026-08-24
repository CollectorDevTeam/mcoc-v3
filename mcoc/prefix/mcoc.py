# mcoc/prefix/mcoc.py
import logging
from typing import Any
from redbot.core import commands

log = logging.getLogger("red.mcoc.prefix.mcoc")

from ..common.champion_helpers import safe_send_ctx

class MCOCPrefix(commands.Cog):
    """
    Top-level ///mcoc prefix group. This cog attaches the existing champion
    and roster command implementations from mcoc/prefix/champions_prefix.py
    and mcoc/prefix/roster_prefix.py as the mcoc -> champ and mcoc -> roster
    subgroups (so users run ///mcoc champ ... and ///mcoc roster ...).
    """

    def __init__(self, bot: Any):
        self.bot = bot
        # parent/core may be attached later; keep a reference if already present
        self.parent = getattr(bot, "mcoc_core", None) or bot.get_cog("MCOC") or bot.get_cog("MCOCPrefix")

        # Try to attach registrars now; if modules or core aren't ready, cog_load will retry
        try:
            self._attach_registrars()
        except Exception:
            log.debug("Initial attach_registrars attempt failed; will try in cog_load", exc_info=True)

    async def cog_load(self):
        # refresh parent reference and attempt attach again
        self.parent = getattr(self.bot, "mcoc_core", None) or self.bot.get_cog("MCOC") or self.bot.get_cog("MCOCPrefix")
        try:
            self._attach_registrars()
        except Exception:
            log.exception("Failed to attach prefix registrars in cog_load")

    def _ensure_parent(self):
        """
        Return the current core/parent object or None.
        Used by registrars via a parent_getter closure.
        """
        return getattr(self, "parent", None) or self.bot.get_cog("MCOC")

    def _attach_registrars(self):
        """
        Import registrars from champions_prefix and roster_prefix and attach their
        commands to this cog's `champ` and `roster` subgroups.
        This is idempotent: calling multiple times will not duplicate commands.
        """
        parent_getter = lambda: self._ensure_parent()

        try: 
            from .account_prefix import register_with_group as register_account
        except Exception:
            log.debug("account_prefix not importable; skipping attach", exc_info=True)
        else:
            try:
                account_group = getattr(self, "account", None)
                if account_group is not None:
                    register_account(account_group, parent_getter)
                    log.debug("Attached account prefix commands to ///mcoc account")
            except Exception:
                log.exception("register_account failed")

        # inside _attach_registrars in mcoc/prefix/mcoc.py
        try:
            from .alliance_prefix import register_with_group as register_alliance
        except Exception:
            log.debug("alliance_prefix not importable; skipping attach", exc_info=True)
        else:
            try:
                alliance_group = getattr(self, "alliance", None)
                if alliance_group is not None:
                    register_alliance(alliance_group, parent_getter)
                    log.debug("Attached alliance prefix commands to ///mcoc alliance")
            except Exception:
                log.exception("register_alliance failed")

        # Attach champions registrar
        try:
            from .champions_prefix import register_with_group as register_champions
        except Exception:
            log.debug("champions_prefix not importable; skipping attach", exc_info=True)
        else:
            try:
                # getattr(self, "champ") returns the Command object created by the decorator below
                champ_group = getattr(self, "champ", None)
                if champ_group is None:
                    log.debug("champ group missing on MCOCPrefix; unexpected")
                else:
                    register_champions(champ_group, parent_getter)
                    log.debug("Attached champions prefix commands to ///mcoc champ")
            except Exception:
                log.exception("register_champions failed")

        # Attach roster registrar
        try:
            from .roster_prefix import register_with_group as register_roster
        except Exception:
            log.debug("roster_prefix not importable; skipping attach", exc_info=True)
        else:
            try:
                roster_group = getattr(self, "roster", None)
                if roster_group is None:
                    log.debug("roster group missing on MCOCPrefix; unexpected")
                else:
                    register_roster(roster_group, parent_getter)
                    log.debug("Attached roster prefix commands to ///mcoc roster")
            except Exception:
                log.exception("register_roster failed")

    # -------------------------
    # Top-level mcoc group and subgroups
    # -------------------------
    @commands.group(name="mcoc", invoke_without_command=True)
    async def mcoc(self, ctx):
        await safe_send_ctx(ctx, "Use subcommands: `champ`, `roster`, `status`, `sync`.")

    @mcoc.command(name="status")
    async def mcoc_status(self, ctx):
        ok = bool(getattr(self, "parent", None) or self.bot.get_cog("MCOC"))
        cache = getattr(self.parent, "cache", None) if getattr(self, "parent", None) else None
        await safe_send_ctx(ctx, f"MCOC core attached: {ok}\nCache available: {bool(cache)}")

    # Define the subgroup command objects so registrars can attach to them
    @mcoc.group(name="champ", invoke_without_command=True)
    async def champ(self, ctx):
        await safe_send_ctx(ctx, "Use subcommands: `info`, `abilities`, `synergies`, `tags`, `stats`, `search`, `calcstats`.")

    @mcoc.group(name="roster", invoke_without_command=True)
    async def roster(self, ctx):
        await safe_send_ctx(ctx, "Use subcommands: `add`, `remove`, `update`, `list`, `export`, `clear`.")

    @mcoc.group(name="alliance", invoke_without_command=True)
    async def alliance(self, ctx):
        await safe_send_ctx(ctx, "Use subcommands: `info`, `create`, `join`, `leave`, `manage`.")

# Red setup
async def setup(bot):
    try:
        await bot.add_cog(MCOCPrefix(bot))
    except Exception:
        log.exception("Failed to add MCOCPrefix")
