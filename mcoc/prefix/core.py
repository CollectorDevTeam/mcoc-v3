# mcoc/prefix/core.py
import logging
from typing import Any
from redbot.core import commands

log = logging.getLogger("red.mcoc.prefix.core")

from ..common.champion_helpers import safe_send_ctx
from ..common.alliance_helpers import (
    get_guild_config,
    set_guild_config,
    role_id_for_key,
    join_alliance,
    _role_obj_for_key,
    get_alliance_info,
)

from ..common.roster_helpers import ensure_user_manager, _ensure_hook_registered


class MCOCPrefix(commands.Cog):
    """
    Unified prefix command root for MCOC.
    Provides:
        ///mcoc champ   (champion lookup and info)
        ///mcoc roster  (manage your champion roster)
        ///mcoc admin   (administration and sync tools)
        ///mcoc account (user profile and privacy)
        ///mcoc alliance (alliance management)
    """

    def __init__(self, bot: Any):
        self.bot = bot

        # core may not be loaded yet; attach later
        self.parent = getattr(bot, "mcoc_core", None) or bot.get_cog("MCOC")

        # attempt registrar attach now
        try:
            self._attach_registrars()
        except Exception:
            log.exception("Initial registrar attach failed; will retry in cog_load")

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
        Attach champion, roster, alliance, and admin registrars to their mcoc subgroups.
        This method is safe to call multiple times; it will attempt to register optional
        prefix modules and will log full exceptions if they fail.
        """

        parent_getter = lambda: self._ensure_parent()

        # --------------------------
        # ACCOUNT (optional)
        # --------------------------
        try:
            from .account_prefix import register_with_group as reg_account
            account_group = getattr(self, "account")
            try:
                reg_account(account_group, parent_getter)
                log.debug("Attached account registrar to ///mcoc account")
            except Exception:
                log.exception("Failed to attach account registrar")
        except Exception:
            # log full exception so import/runtime errors are visible
            log.exception("Account registrar failed to attach (optional)")

        # --------------------------
        # ALLIANCE (optional)
        # --------------------------
        try:
            from .alliance_prefix import register_with_group as reg_alliance
            alliance_group = getattr(self, "alliance")
            try: 
                reg_alliance(alliance_group, parent_getter)
                log.debug("Attached alliance registrar to ///mcoc alliance")
            except Exception:
                log.exception("Failed to attach alliance registrar")
        except Exception:
            log.exception("Alliance registrar failed to attach (optional)")

        # --------------------------
        # CHAMPIONS
        # --------------------------
        try:
            from .champions_prefix import register_with_group as reg_champ
            champ_group = getattr(self, "champ")
            try: 
                reg_champ(champ_group, parent_getter)
                log.debug("Attached champions registrar to ///mcoc champ")
            except Exception:
                log.exception("Failed to attach champions registrar")
        except Exception:
            log.exception("Failed to attach champions registrar")

        # --------------------------
        # ROSTER
        # --------------------------
        try:
            from .roster_prefix import register_with_group as reg_roster
            roster_group = getattr(self, "roster")
            try:
                reg_roster(roster_group, parent_getter)
                log.debug("Attached roster registrar to ///mcoc roster")
            except Exception:
                log.exception("Failed to attach roster registrar")
        except Exception:
            log.exception("Roster registrar failed to attach (optional)")

        # --------------------------
        # ADMIN (optional)
        # --------------------------
        try:
            from .mcocadmin_prefix import register_with_group as reg_admin
            admin_group = getattr(self, "admin")
            try: 
                reg_admin(admin_group, parent_getter)
                log.debug("Attached admin registrar to ///mcoc admin")
            except Exception:
                log.exception("Failed to attach admin registrar")
        except Exception:
            log.exception("Admin registrar failed to attach (optional)")

    # ============================================================
    # TOP-LEVEL GROUP
    # ============================================================
    @commands.group(name="mcoc", invoke_without_command=True)
    async def mcoc(self, ctx):
        """
        MCOC root command.
        Use subcommands to access features:
          - ///mcoc champ   : champion lookup and stats
          - ///mcoc roster  : manage your roster (add/remove/list/export)
          - ///mcoc alliance : alliance registration and membership
          - ///mcoc account  : user profile and privacy settings
          - ///mcoc admin    : administrative utilities (if available)
        """
        await safe_send_ctx(
            ctx,
            "MCOC commands: `champ`, `roster`, `alliance`, `account`, `admin`, `status`.\n"
            "Type `///mcoc <subcommand> help` for more details on a subgroup."
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
        await safe_send_ctx(ctx, "Champion commands: `info`, `abilities`, `synergies`, `tags`, `stats`, `search`, `calcstats`.")

    @mcoc.group(name="roster", invoke_without_command=True)
    async def roster(self, ctx):
        await safe_send_ctx(ctx, "Roster commands: `add`, `remove`, `update`, `list`, `export`, `clear`.")

    @mcoc.group(name="admin", invoke_without_command=True)
    async def admin(self, ctx):
        await safe_send_ctx(ctx, "Admin commands (requires permissions): `status`, `sync`, `debug`.")

    @mcoc.group(name="account", invoke_without_command=True)
    async def account(self, ctx):
        await safe_send_ctx(ctx, "Account commands: `info`, `set`, `link`, `unlink`, `delete`, `privacy`.")

    @mcoc.group(name="alliance", invoke_without_command=True)
    async def alliance(self, ctx):
        await safe_send_ctx(ctx, "Alliance commands: `info`, `create`, `join`, `leave`, `settings`, `manage`.")


    # in your main cog or a dedicated event cog
    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        from ..common.alliance_helpers import _load_alliances, remove_guild_config, get_guild_config
        cfg = get_guild_config(role.guild.id)
        if not cfg:
            return
        # remove references to deleted role and persist
        changed = False
        for k, r in list(cfg.get("roles", {}).items()):
            if isinstance(r, dict) and r.get("id") == role.id:
                cfg["roles"].pop(k, None)
                changed = True
        if changed:
            set_guild_config(role.guild.id, cfg)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        # detect manual role grants to alliance member role and call join_alliance
        guild = after.guild
        cfg = get_guild_config(guild.id)
        if not cfg:
            return
        members_role_id = role_id_for_key(cfg, "members")
        if members_role_id and any(r.id == members_role_id for r in after.roles) and not any(r.id == members_role_id for r in before.roles):
            # user was given members role manually
            await join_alliance(after, guild, role_key="members")


async def setup(bot):
    try:
        await bot.add_cog(MCOCPrefix(bot))
        log.debug("MCOCPrefix loaded")
    except Exception:
        log.exception("Failed to add MCOCPrefix")
