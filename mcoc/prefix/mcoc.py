# mcoc/prefix/mcoc.py
import logging
from typing import Any, Optional
from redbot.core import commands

log = logging.getLogger("red.mcoc.prefix.mcoc")

from ..common.champion_helpers import safe_send_ctx

class MCOCPrefix(commands.Cog):
    """
    Top-level ///mcoc prefix group. This cog attaches the existing champion
    command implementations from mcoc/prefix/champions_prefix.py as the
    mcoc -> champ subgroup (so users run ///mcoc champ ...).
    """

    def __init__(self, bot: Any):
        self.bot = bot
        # try to attach core if already present; parent may be None until core loads
        self.parent = getattr(bot, "mcoc_core", None) or bot.get_cog("MCOC") or bot.get_cog("MCOCPrefix")

        # attempt to attach champion commands now; if core or champions module
        # isn't available yet, cog_load will try again.
        try:
            self._attach_champions()
        except Exception:
            # defer to cog_load for a second attempt and log the failure
            log.debug("Initial attach_champions attempt failed; will try in cog_load", exc_info=True)

    async def cog_load(self):
        # ensure parent reference is up to date
        self.parent = getattr(self.bot, "mcoc_core", None) or self.bot.get_cog("MCOC") or self.bot.get_cog("MCOCPrefix")
        try:
            self._attach_champions()
        except Exception:
            log.exception("Failed to attach champions commands to ///mcoc champ in cog_load")

    def _ensure_parent(self):
        """
        Return the current core/parent object or None.
        Used by registrars via a parent_getter closure.
        """
        return getattr(self, "parent", None) or self.bot.get_cog("MCOC")

    def _attach_champions(self):
        """
        Import the registrar from champions_prefix and attach its commands
        to the `champ` subgroup of this cog.
        """
        # Import lazily so module import stays light
        try:
            from .champions_prefix import register_with_group as register_champions
        except Exception:
            # champions_prefix not importable (not present or has errors)
            log.debug("champions_prefix not importable; skipping attach", exc_info=True)
            return

        # Ensure the mcoc -> champ group exists on this cog
        # The decorator below creates the command object; getattr returns it.
        champ_group = getattr(self, "champ", None)
        if champ_group is None:
            # If the group isn't defined (unexpected), create a lightweight group command object
            # by defining a no-op command on the class. This is defensive; normally the
            # @commands.group decorator in this class will create `champ`.
            @commands.group(name="champ", invoke_without_command=True)
            async def champ(self, ctx):
                await safe_send_ctx(ctx, "Use subcommands: `info`, `abilities`, `synergies`, `tags`, `stats`, `search`, `calcstats`.")
            # attach the created command to the class instance
            setattr(self, "champ", champ)
            champ_group = getattr(self, "champ")

        # parent_getter closure used by the registrar to find the core at runtime
        parent_getter = lambda: self._ensure_parent()

        # Call the registrar to attach commands to the champ subgroup
        try:
            register_champions(champ_group, parent_getter)
            log.debug("Attached champions prefix commands to ///mcoc champ")
        except Exception:
            log.exception("register_champions failed")

    # Top-level mcoc group and a minimal status command
    @commands.group(name="mcoc", invoke_without_command=True)
    async def mcoc(self, ctx):
        await safe_send_ctx(ctx, "Use subcommands: `champ`, `roster`, `status`, `sync`.")

    @mcoc.command(name="status")
    async def mcoc_status(self, ctx):
        ok = bool(getattr(self, "parent", None) or self.bot.get_cog("MCOC"))
        cache = getattr(self.parent, "cache", None) if getattr(self, "parent", None) else None
        await safe_send_ctx(ctx, f"MCOC core attached: {ok}\nCache available: {bool(cache)}")

# Red setup
async def setup(bot):
    try:
        await bot.add_cog(MCOCPrefix(bot))
    except Exception:
        log.exception("Failed to add MCOCPrefix")
