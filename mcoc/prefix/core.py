# mcoc/prefix/core.py
import logging
from typing import Any, Dict
import importlib
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
        self._registrars_attached = set()

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

    def can_view_profile(viewer_id: int, target_id: int, profile: Dict[str, Any]) -> Dict[str, Any]:
        mode = profile.get("privacy_mode", "private")
        if viewer_id == target_id:
            return profile
        if mode == "public":
            return profile
        if mode == "guild":
            # caller must pass guild context; simplified here
            return {k: v for k, v in profile.items() if k in ("display_name","roster_public")}
        return {k: v for k, v in profile.items() if k in ("display_name",)}


    # inside MCOCPrefix.__init__ (ensure this exists)
    # self._registrars_attached = set()

    def _attach_registrars(self):
        parent_getter = lambda: self._ensure_parent()

        def _try_attach(name: str, importer_path: str, group_attr: str):
            # already attached? skip
            if name in getattr(self, "_registrars_attached", set()):
                log.debug("Registrar %s already attached; skipping", name)
                return

            try:
                # Use importlib.import_module with package context so relative imports work
                module = importlib.import_module(importer_path, package=__package__)
                reg = getattr(module, "register_with_group", None)
                if not reg:
                    log.debug("Registrar %s has no register_with_group; skipping", name)
                    return
                group = getattr(self, group_attr, None)
                if group is None:
                    log.debug("Group %s not present on MCOCPrefix; skipping registrar %s", group_attr, name)
                    return
                try:
                    reg(group, parent_getter)
                    self._registrars_attached.add(name)
                    log.debug("Attached %s registrar to ///mcoc %s", name, group_attr)
                except Exception:
                    log.exception("Failed to attach %s registrar", name)
            except ModuleNotFoundError:
                # Optional registrars may not exist in some installs; log at debug to reduce noise
                log.debug("Registrar module %s not found (optional); skipping", importer_path)
            except Exception:
                log.exception("Failed to import registrar module for %s", name)

        # call for each registrar (use relative module paths because core.py is in mcoc.prefix)
        _try_attach("account", ".account_prefix", "account")
        _try_attach("alliance", ".alliance_prefix", "alliance")
        _try_attach("champions", ".champions_prefix", "champ")
        _try_attach("roster", ".roster_prefix", "roster")
        _try_attach("admin", ".mcocadmin_prefix", "admin")


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
    # place near the other subgroup methods in mcoc/prefix/core.py

    def _group_help_text(self, group: commands.Group, title: str, fallback: str = "") -> str:
        """
        Build a short help string for a commands.Group by enumerating its subcommands.
        Uses command.short_doc, command.help, or function docstring for descriptions.
        """
        try:
            cmds = []
            for name, cmd in sorted(group.commands.items(), key=lambda kv: kv[0]):
                # skip hidden or internal commands
                try:
                    if getattr(cmd, "hidden", False):
                        continue
                except Exception:
                    pass
                # prefer short_doc (Red/discord), then help, then func docstring
                desc = getattr(cmd, "short_doc", None) or getattr(cmd, "help", None) or (cmd.callback.__doc__ if getattr(cmd, "callback", None) else None)
                if desc:
                    # take first line only and trim
                    desc_line = str(desc).strip().splitlines()[0]
                else:
                    desc_line = ""
                cmds.append((name, desc_line))
            if not cmds:
                return fallback or f"{title} (no commands registered)"
            lines = [f"**{title}**"]
            # show up to 10 commands inline, then indicate more if present
            for name, desc in cmds[:20]:
                if desc:
                    lines.append(f"`{name}` — {desc}")
                else:
                    lines.append(f"`{name}`")
            return "\n".join(lines)
        except Exception:
            # fallback to the static fallback text on any error
            return fallback or f"{title} (help unavailable)"

    @mcoc.group(name="champ", invoke_without_command=True)
    async def champ(self, ctx):
        """Champion commands help (dynamic)."""
        try:
            text = self._group_help_text(self.champ, "Champion commands", "Champion commands: `info`, `abilities`, `synergies`, `tags`, `stats`, `search`, `calcstats`.")
            await safe_send_ctx(ctx, text)
        except Exception:
            await safe_send_ctx(ctx, "Champion commands: `info`, `abilities`, `synergies`, `tags`, `stats`, `search`, `calcstats`.")

    @mcoc.group(name="roster", invoke_without_command=True)
    async def roster(self, ctx):
        """Roster commands help (dynamic)."""
        try:
            text = self._group_help_text(self.roster, "Roster commands", "Roster commands: `add`, `remove`, `update`, `list`, `export`, `clear`.")
            await safe_send_ctx(ctx, text)
        except Exception:
            await safe_send_ctx(ctx, "Roster commands: `add`, `remove`, `update`, `list`, `export`, `clear`.")

    @mcoc.group(name="admin", invoke_without_command=True)
    async def admin(self, ctx):
        """Admin commands help (dynamic)."""
        try:
            text = self._group_help_text(self.admin, "Admin commands (requires permissions)", "Admin commands (requires permissions): `status`, `sync`, `debug`.")
            await safe_send_ctx(ctx, text)
        except Exception:
            await safe_send_ctx(ctx, "Admin commands (requires permissions): `status`, `sync`, `debug`.")

    @mcoc.group(name="account", invoke_without_command=True)
    async def account(self, ctx):
        """Account commands help (dynamic)."""
        try:
            text = self._group_help_text(self.account, "Account commands", "Account commands: `info`, `set`, `link`, `unlink`, `delete`, `privacy`.")
            await safe_send_ctx(ctx, text)
        except Exception:
            await safe_send_ctx(ctx, "Account commands: `info`, `set`, `link`, `unlink`, `delete`, `privacy`.")

    @mcoc.group(name="alliance", invoke_without_command=True)
    async def alliance(self, ctx):
        """Alliance commands help (dynamic)."""
        try:
            text = self._group_help_text(self.alliance, "Alliance commands", "Alliance commands: `info`, `create`, `join`, `leave`, `settings`, `manage`.")
            await safe_send_ctx(ctx, text)
        except Exception:
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
            await set_guild_config(role.guild.id, cfg)

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
