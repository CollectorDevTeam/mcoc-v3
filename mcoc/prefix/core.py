# mcoc/prefix/core.py
"""
Prefix command root for MCOC.

This cog is a thin orchestration layer: it exposes the top-level ///mcoc group,
dynamically attaches registrar modules (account, alliance, champions, roster, admin),
and provides small helpers used by the prefix handlers (dynamic help, forwarding).
"""

from typing import Any, Dict, Optional
import importlib
import logging
import asyncio

from redbot.core import commands

from ..common.prefix_utils import safe_send_ctx
from ..common.alliance import (
    get_guild_config,
    set_guild_config,
    role_id_for_key,
    join_alliance,
    _role_obj_for_key,
    get_alliance_info,
)
from ..common.roster import ensure_user_manager, _ensure_hook_registered

log = logging.getLogger("red.mcoc.prefix.core")


class MCOCPrefix(commands.Cog):
    """
    Unified prefix command root for MCOC.

    Subgroups are attached via registrar modules. Registrar modules should expose
    a `register_with_group(group, parent_getter)` function that attaches commands
    to the provided group.
    """

    def __init__(self, bot: Any):
        self.bot = bot
        # parent is the shared core container (bot.mcoc_core) or the main MCOC cog
        self.parent = getattr(bot, "mcoc_core", None) or bot.get_cog("MCOC")
        self._registrars_attached = set()

        # attempt registrar attach now (may be retried in cog_load)
        try:
            self._attach_registrars()
        except Exception:
            log.exception("Initial registrar attach failed; will retry in cog_load")

    async def cog_load(self) -> None:
        # refresh core reference and try to attach registrars again
        self.parent = getattr(self.bot, "mcoc_core", None) or self.bot.get_cog("MCOC")
        try:
            self._attach_registrars()
        except Exception:
            log.exception("Registrar attach failed in cog_load")

    def _ensure_parent(self) -> Optional[Any]:
        """Return the core object if available."""
        return getattr(self, "parent", None) or self.bot.get_cog("MCOC")

    @staticmethod
    def can_view_profile(viewer_id: int, target_id: int, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simple privacy filter used by some prefix handlers.
        Returns a filtered profile dict appropriate for the viewer.
        """
        mode = profile.get("privacy_mode", "private")
        if viewer_id == target_id:
            return profile
        if mode == "public":
            return profile
        if mode == "guild":
            return {k: v for k, v in profile.items() if k in ("display_name", "roster_public")}
        return {k: v for k, v in profile.items() if k in ("display_name",)}

    def _attach_registrars(self) -> None:
        """
        Dynamically import and attach registrar modules.

        Registrar modules are optional; missing modules are skipped quietly.
        Registrar module names are relative to this package (mcoc.prefix).
        Each registrar module should expose `register_with_group(group, parent_getter)`.
        """
        parent_getter = lambda: self._ensure_parent()

        def _try_attach(name: str, importer_path: str, group_attr: str) -> None:
            if name in self._registrars_attached:
                log.debug("Registrar %s already attached; skipping", name)
                return

            try:
                module = importlib.import_module(importer_path, package=__package__)
                reg = getattr(module, "register_with_group", None)
                if not callable(reg):
                    log.debug("Registrar %s has no register_with_group; skipping", importer_path)
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
                # optional registrars may not exist in some installs
                log.debug("Registrar module %s not found (optional); skipping", importer_path)
            except Exception:
                log.exception("Failed to import registrar module for %s", name)

        # Attach known registrars (module paths are relative to mcoc.prefix)
        _try_attach("account", ".account", "account")
        _try_attach("alliance", ".alliance", "alliance")
        _try_attach("champions", ".champions", "champ")
        _try_attach("roster", ".roster", "roster")
        _try_attach("admin", ".mcocadmin", "admin")

    # ============================================================
    # Top-level group and status
    # ============================================================
    @commands.group(name="mcoc", invoke_without_command=True)
    async def mcoc(self, ctx):
        """
        MCOC root command. Shows available subgroups and a short help blurb.
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
    # Dynamic subgroup help and forwarding
    # ============================================================
    def _group_help_text(self, group: commands.Group, title: str, fallback: str = "") -> str:
        """
        Build a short help string for a commands.Group by enumerating its subcommands.
        """
        try:
            cmds = []
            for name, cmd in sorted(group.commands.items(), key=lambda kv: kv[0]):
                try:
                    if getattr(cmd, "hidden", False):
                        continue
                except Exception:
                    pass
                desc = getattr(cmd, "short_doc", None) or getattr(cmd, "help", None) or (cmd.callback.__doc__ if getattr(cmd, "callback", None) else None)
                desc_line = str(desc).strip().splitlines()[0] if desc else ""
                cmds.append((name, desc_line))
            if not cmds:
                return fallback or f"{title} (no commands registered)"
            lines = [f"**{title}**"]
            for name, desc in cmds[:20]:
                if desc:
                    lines.append(f"`{name}` — {desc}")
                else:
                    lines.append(f"`{name}`")
            return "\n".join(lines)
        except Exception:
            return fallback or f"{title} (help unavailable)"

    @mcoc.group(name="champ", invoke_without_command=True)
    async def champ(self, ctx):
        """Champion commands help (dynamic)."""
        try:
            text = self._group_help_text(self.champ, "Champion commands", "Champion commands: `info`, `abilities`, `search`, `stats`.")
            await safe_send_ctx(ctx, text)
        except Exception:
            await safe_send_ctx(ctx, "Champion commands: `info`, `abilities`, `search`, `stats`.")

    @mcoc.group(name="roster", invoke_without_command=True)
    async def roster(self, ctx, *items: str):
        """Roster commands help (dynamic). If args provided, forward to roster list subcommand."""
        if not items:
            try:
                text = self._group_help_text(self.roster, "Roster commands", "Roster commands: `add`, `remove`, `update`, `list`, `import`, `export`, `clear`.")
                await safe_send_ctx(ctx, text)
            except Exception:
                await safe_send_ctx(ctx, "Roster commands: `add`, `remove`, `update`, `list`, `import`, `export`, `clear`.")
            return

        # Args present -> forward to the registered group's list subcommand if available
        try:
            list_cmd = None
            try:
                list_cmd = self.roster.get_command("list")
            except Exception:
                list_cmd = None

            if list_cmd:
                # ctx.invoke accepts a Command object
                await ctx.invoke(list_cmd, *items)
                return

            # fallback: try to call a method named roster_list on this cog (legacy)
            if hasattr(self, "roster_list") and callable(getattr(self, "roster_list")):
                await self.roster_list(ctx, *items)
                return

            # final fallback: show help
            text = self._group_help_text(self.roster, "Roster commands", "Roster commands: `add`, `remove`, `update`, `list`, `export`, `clear`.")
            await safe_send_ctx(ctx, text)
        except Exception:
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
            text = self._group_help_text(self.account, "Account commands", "Account commands: `info`, `profile`, `set`, `link`, `unlink`, `delete`, `privacy`.")
            await safe_send_ctx(ctx, text)
        except Exception:
            await safe_send_ctx(ctx, "Account commands: `info`, `profile`, `set`, `link`, `unlink`, `delete`, `privacy`.")

    @mcoc.group(name="alliance", invoke_without_command=True)
    async def alliance(self, ctx):
        """Alliance commands help (dynamic)."""
        try:
            text = self._group_help_text(self.alliance, "Alliance commands", "Alliance commands: `info`, `create`, `join`, `leave`, `settings`, `manage`.")
            await safe_send_ctx(ctx, text)
        except Exception:
            await safe_send_ctx(ctx, "Alliance commands: `info`, `create`, `join`, `leave`, `settings`, `manage`.")

    # ============================================================
    # Event listeners (guild/role/member hooks)
    # ============================================================
    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        """
        Remove references to a deleted role from the alliance config for that guild.
        """
        try:
            cfg = get_guild_config(role.guild.id)
            if not cfg:
                return
            changed = False
            for k, r in list(cfg.get("roles", {}).items()):
                if isinstance(r, dict) and r.get("id") == role.id:
                    cfg["roles"].pop(k, None)
                    changed = True
            if changed:
                set_guild_config(role.guild.id, cfg)
        except Exception:
            log.exception("on_guild_role_delete failed for role %s", getattr(role, "id", None))

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        """
        Detect manual role grants to the configured members role and call join_alliance.
        """
        try:
            guild = after.guild
            cfg = get_guild_config(guild.id)
            if not cfg:
                return
            members_role_id = role_id_for_key(cfg, "members")
            if members_role_id and any(r.id == members_role_id for r in after.roles) and not any(r.id == members_role_id for r in before.roles):
                # user was given members role manually
                await join_alliance(after, guild, role_key="members")
        except Exception:
            log.exception("on_member_update failed for member %s", getattr(after, "id", None))


# Cog setup for Red (async setup)
async def setup(bot):
    try:
        await bot.add_cog(MCOCPrefix(bot))
        log.debug("MCOCPrefix loaded")
    except Exception:
        log.exception("Failed to add MCOCPrefix")
