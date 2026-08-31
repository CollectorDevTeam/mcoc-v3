# mcoc/prefix/core.py
"""
Prefix command root for MCOC (hybrid mode).

Behavior:
 - Each feature module (account, roster, alliance, champ, admin) should register
   itself as a top-level Cog (///account, ///roster, ///alliance, ///champ, ///mcocadmin).
 - This MCOCPrefix Cog remains as a thin compatibility entrypoint:
     - `///mcoc` shows a short help and can forward `///mcoc <sub> ...` to the
       corresponding top-level command if it exists (e.g., ///mcoc account -> ///account).
 - Keep registrar pattern removed; prefer explicit Cog registration for each module.
"""

from typing import Any, Dict, Optional, Sequence
from mcoc.common import Core
Embed = Core.Embed
Entitlements = Core.Entitlements
Helpers = Core.Helpers
Alliance = Helpers.alliance
Roster = Helpers.roster

import importlib
import logging

from redbot.core import commands

from mcoc.common.prefix_utils import safe_send_ctx

log = logging.getLogger("red.mcoc.prefix.core")


class MCOCPrefix(commands.Cog):
    """
    Thin compatibility Cog exposing ///mcoc root and a forwarding helper.

    Top-level feature Cogs should register themselves directly (async setup).
    This Cog helps users who still type ///mcoc <sub> by forwarding to the
    top-level command if present, otherwise showing a short help.
    """

    def __init__(self, bot: Any):
        self.bot = bot
        # parent may be the shared core container or the main MCOC cog
        self.parent = getattr(bot, "mcoc_core", None) or bot.get_cog("MCOC")
        # ensure roster hooks if parent present
        try:
            Roster._ensure_hook_registered(self.parent)
        except Exception:
            pass

    # -------------------------
    # Helper: find top-level command
    # -------------------------
    def _find_top_command(self, name: str) -> Optional[commands.Command]:
        """
        Return a top-level Command object for `name` if registered, else None.
        Example names: "account", "roster", "alliance", "champ", "mcocadmin"
        """
        try:
            # bot.get_command returns a Command or None
            return self.bot.get_command(name)
        except Exception:
            return None

    # -------------------------
    # mcoc root (forwards when possible)
    # -------------------------
    @commands.group(name="mcoc", invoke_without_command=True)
    async def mcoc(self, ctx, subcommand: Optional[str] = None, *args: str):
        """
        Compatibility root. If a subcommand name is provided and a top-level
        command with that name exists, forward the invocation to it.
        Otherwise show a short help pointing to top-level commands.
        """
        # If user provided a subcommand name, attempt to forward (existing logic)...
        if subcommand:
            cmd = self._find_top_command(subcommand)
            if cmd:
                try:
                    # Attempt to invoke the top-level command with the provided args.
                    # If this succeeds, return immediately and do not emit fallback help.
                    await ctx.invoke(cmd, *args)
                    return
                except commands.CommandError:
                    # Command invocation failed at the command layer; log and fall through to help.
                    log.exception("Forwarding ///mcoc %s to top-level command failed", subcommand)
                except Exception:
                    # Unexpected error while forwarding; log and fall through to help.
                    log.exception("Unexpected error forwarding ///mcoc %s", subcommand)

        # No forwarding possible or forwarding failed: show attractive embed help (use Embed)
        try:
            emb = Embed(ctx, title="Challenger Help Menu", color=Embed.get_color_value(ctx))
            Embed.add_field(name="Syntax", value="`///mcoc [subcommand] [args...]`", inline=False)
            Embed.add_field(name="Description", value="Compatibility root. Use top-level commands directly for faster access.", inline=False)
            Embed.add_field(name="Top-level commands", value="`///account`, `///roster`, `///alliance`, `///champ`, `///mcocadmin`, `///mcoc status`", inline=False)
            Embed.set_footer(text="Type `///help <command>` for more details.")
            await safe_send_ctx(ctx, None, embed=emb)
        except Exception:
            # fallback to text only if embed fails
            await safe_send_ctx(ctx, "MCOC compatibility root. Use `///account`, `///roster`, `///alliance`, `///champ`, `///mcocadmin`.")


    @mcoc.command(name="status")
    async def mcoc_status(self, ctx):
        """
        Show a brief status of the core container and cache.
        """
        core = getattr(self.bot, "mcoc_core", None) or self.bot.get_cog("MCOC")
        cache = getattr(core, "cache", None) if core else None
        await safe_send_ctx(
            ctx,
            f"MCOC core attached: {bool(core)}\nCache available: {bool(cache)}"
        )

    # -------------------------
    # Dynamic help builder (used by other groups if needed)
    # -------------------------
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

    # -------------------------
    # Convenience forwarding endpoints (optional)
    # -------------------------
    # These are small helpers so users can type ///mcoc account and still get
    # the top-level behavior. They are intentionally minimal and simply call
    # the top-level command if present.

    @mcoc.group(name="account", invoke_without_command=True)
    async def mcoc_account(self, ctx, *args: str):
        """
        Forwarder for account: tries to invoke top-level ///account if present.
        """
        cmd = self._find_top_command("account")
        if not cmd:
            # No top-level account command registered; show a short fallback help.
            await safe_send_ctx(ctx, "Account commands: info, profile, set, link, unlink, delete, privacy. Use ///account for top-level access.")
            return

        # If args are empty, prefer to invoke the top-level command with no args
        # (this mirrors user typing ///account directly). If invocation fails, show fallback.
        try:
            await ctx.invoke(cmd, *args)
            return
        except commands.CommandError:
            log.exception("Failed to forward ///mcoc account to ///account")
            await safe_send_ctx(ctx, "Account commands: info, profile, set, link, unlink, delete, privacy. Use ///account for top-level access.")
        except Exception:
            log.exception("Unexpected error forwarding ///mcoc account to ///account")
            await safe_send_ctx(ctx, "Account commands: info, profile, set, link, unlink, delete, privacy. Use ///account for top-level access.")


    @mcoc.group(name="roster", invoke_without_command=True)
    async def mcoc_roster(self, ctx, *args: str):
        cmd = self._find_top_command("roster")
        if cmd:
            try:
                await ctx.invoke(cmd, *args)
                return
            except Exception:
                log.exception("Failed to forward ///mcoc roster to ///roster")
        await safe_send_ctx(ctx, "Roster commands: add, remove, update, list, import, export, clear. Use ///roster for top-level access.")

    @mcoc.group(name="alliance", invoke_without_command=True)
    async def mcoc_alliance(self, ctx, *args: str):
        cmd = self._find_top_command("alliance")
        if cmd:
            try:
                await ctx.invoke(cmd, *args)
                return
            except Exception:
                log.exception("Failed to forward ///mcoc alliance to ///alliance")
        await safe_send_ctx(ctx, "Alliance commands: info, create, join, leave, settings, manage. Use ///alliance for top-level access.")

    @mcoc.group(name="champ", invoke_without_command=True)
    async def mcoc_champ(self, ctx, *args: str):
        cmd = self._find_top_command("champ")
        if cmd:
            try:
                await ctx.invoke(cmd, *args)
                return
            except Exception:
                log.exception("Failed to forward ///mcoc champ to ///champ")
        await safe_send_ctx(ctx, "Champion commands: info, abilities, search, stats. Use ///champ for top-level access.")

    @mcoc.group(name="admin", invoke_without_command=True)
    async def mcoc_admin(self, ctx, *args: str):
        cmd = self._find_top_command("mcocadmin")
        if cmd:
            try:
                await ctx.invoke(cmd, *args)
                return
            except Exception:
                log.exception("Failed to forward ///mcoc admin to ///mcocadmin")
        await safe_send_ctx(ctx, "Admin commands: status, sync, debug. Use ///mcocadmin for top-level access.")

    def apply_role_entitlements_to_user(guild_cfg, role_id, user_id):
        role_key = f"role:{role_id}"
        role_ent = guild_cfg.entitlements.get(role_key)
        if not role_ent:
            return
        user_key = f"user:{user_id}"
        user_ent = guild_cfg.entitlements.get(user_key) or Entitlements.UserEntitlement()
        user_ent.subscriber = user_ent.subscriber or getattr(role_ent, "subscriber", False)
        user_ent.guild_owner_plus = user_ent.guild_owner_plus or getattr(role_ent, "guild_owner_plus", False)
        if getattr(role_ent, "expires_at", None):
            user_ent.expires_at = role_ent.expires_at
        guild_cfg.entitlements[user_key] = user_ent
        Entitlements.set_guild_config(guild_cfg.guild_id, guild_cfg)
        Entitlements.log_action(guild_cfg, 0, "apply_role_entitlement", f"role:{role_id} -> user:{user_id}")

    def render_group_help_embed(self, ctx, group: commands.Group, title: str, fallback: str = ""):
        text = ""
        try:
            text = self._group_help_text(group, title, fallback)
        except Exception:
            text = fallback or title
        emb = Embed(ctx, title=title, description=text)
        try:
            Embed.set_footer(ctx, emb, footer_text="Type ///help <command> for details")
        except Exception:
            pass
        return emb

    # -------------------------
    # Event listeners (guild/role/member hooks)
    # -------------------------
    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        """
        Remove references to a deleted role from the alliance config for that guild.
        """
        try:
            cfg = Alliance.get_guild_config(role.guild.id)
            if not cfg:
                return
            changed = False
            for k, r in list(cfg.get("roles", {}).items()):
                if isinstance(r, dict) and r.get("id") == role.id:
                    cfg["roles"].pop(k, None)
                    changed = True
            if changed:
                Alliance.set_guild_config(role.guild.id, cfg)
        except Exception:
            log.exception("on_guild_role_delete failed for role %s", getattr(role, "id", None))

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        try:
            guild = after.guild
            cfg = Alliance.get_guild_config(guild.id)
            if not cfg:
                return
            before_ids = {r.id for r in before.roles}
            after_ids = {r.id for r in after.roles}
            added = after_ids - before_ids
            removed = before_ids - after_ids

            for rid in added:
                if f"role:{rid}" in cfg.get("entitlements", {}):
                    Entitlements.apply_role_entitlements_to_user(cfg, rid, after.id)

            for rid in removed:
                if f"role:{rid}" in cfg.get("entitlements", {}):
                    Entitlements.remove_role_entitlements_from_user(cfg, rid, after.id)

            # existing members role behavior
            members_role_id = Alliance.role_id_for_key(cfg, "members")
            if members_role_id and members_role_id in added:
                await Alliance.join_alliance(after, guild, role_key="members")
            
        except Exception:
            log.exception("on_member_update failed for member %s", getattr(after, "id", None))


# Cog setup for Red (async setup)
async def setup(bot):
    try:
        await bot.add_cog(MCOCPrefix(bot))
        log.debug("MCOCPrefix loaded (compatibility root)")
    except Exception:
        log.exception("Failed to add MCOCPrefix")
