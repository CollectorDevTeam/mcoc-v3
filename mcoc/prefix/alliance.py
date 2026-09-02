# Path: mcoc/prefix/alliance.py
# File-Version: 1.0
# File-Id: 5c3db849-bc05-4dec-9c10-932cb17d43b8
# Purpose: Prefix alliance commands and confirmations.
# Public-API: AlliancePrefix
# Internal: _confirm
# Last-Modified: 2026-09-01
"""Thin alliance prefix handlers.

The core logic lives in mcoc.common.helpers.alliance; these commands focus on
guild-scoped UX and confirmation flows.
"""

from typing import Optional, Any
import logging
import asyncio

from discord.member import Member
from discord.user import User
from redbot.core import commands

from mcoc.common import Core
from mcoc.common.components.componentsV2 import CDTConfirm
from mcoc.common.components.prefix_utils import safe_send_ctx
from mcoc.common.components.help_utils import send_or_brand_help

Alliance = Core.Helpers.alliance

log = logging.getLogger("red.mcoc.prefix.alliance")


async def _confirm(ctx, prompt: str, *, timeout: float = 25.0) -> bool:
    view = CDTConfirm(timeout=timeout, confirm_label="Yes", cancel_label="No")
    try:
        await ctx.send(prompt, view=view)
    except Exception:
        await safe_send_ctx(ctx, prompt)
        return False
    try:
        return bool(await view.wait_result())
    except Exception:
        return False


class AlliancePrefix(commands.Cog):
    """MCOC alliance management prefix commands (guild-scoped)."""

    def __init__(self, bot):
        self.bot = bot
        self.parent = getattr(bot, "mcoc_core", None)

    @commands.group(name="alliance")
    async def alliance(self, ctx, *args):
        """Alliance help and guild-scoped alliance management."""
        if args and isinstance(args[0], (Member, User)):
            return
        await send_or_brand_help(ctx, "alliance", title="Alliance Help", fallback_text="Alliance commands: create, template, setrole, settype, join, leave, manage, profile.")

    @alliance.command(name="create")
    @commands.admin_or_permissions(manage_guild=True)
    async def alliance_create(self, ctx, type_: str, *, name: str):
        type_norm = (type_ or "").lower()
        if type_norm not in ("simple", "complex"):
            await safe_send_ctx(ctx, "Invalid type. Allowed: simple, complex.")
            return
        roles_to_create = [f"{name} Alliance", f"{name} Officers", f"{name} Members"]
        if type_norm == "complex":
            roles_to_create += [f"{name} Leader", f"{name} BG1", f"{name} BG2", f"{name} BG3", f"{name} AQBG1", f"{name} AWBG1"]
        prompt = "This will create/link the following roles:\n" + "\n".join(f"- {r}" for r in roles_to_create)
        if not await _confirm(ctx, prompt):
            await safe_send_ctx(ctx, "Cancelled. No changes were made.")
            return

        ok = await Alliance.register_alliance(ctx.guild, name, alliance_tag=None, type_=type_norm)
        if ok:
            await safe_send_ctx(ctx, f"Alliance **{name}** registered on this guild.")
        else:
            await safe_send_ctx(ctx, "Failed to register alliance. Check logs.")

    @alliance.command(name="template")
    @commands.admin_or_permissions(manage_guild=True)
    async def alliance_template(self, ctx):
        guild = ctx.guild
        name = guild.name.split()[0] if guild and guild.name else "Alliance"
        roles_to_create = [f"{name} Alliance", f"{name} Officers", f"{name} Members", f"{name} Leader", f"{name} BG1", f"{name} BG2", f"{name} BG3"]
        prompt = "This will create the following roles:\n" + "\n".join(f"- {r}" for r in roles_to_create)
        if not await _confirm(ctx, prompt):
            await safe_send_ctx(ctx, "Cancelled. No roles were created.")
            return
        created = []
        for rname in roles_to_create:
            try:
                role = await guild.create_role(name=rname, reason="Alliance template creation")
                created.append(role.name)
                await asyncio.sleep(0.25)
            except Exception:
                log.exception("Failed to create role %s in guild %s", rname, guild.id)
        await safe_send_ctx(ctx, f"Created roles: {', '.join(created) if created else 'none (check logs)'}")

    @alliance.command(name="setrole")
    @commands.admin_or_permissions(manage_guild=True)
    async def alliance_setrole(self, ctx, key: str, role: Optional[Any] = None):
        if role is None:
            await safe_send_ctx(ctx, "Usage: ///mcoc alliance setrole <key> <@role>")
            return
        mapped = await Alliance.create_or_link_role(ctx.guild, role.name, key, role_obj=role)
        if mapped:
            await safe_send_ctx(ctx, f"Linked role `{role.name}` to key `{key}`.")
        else:
            await safe_send_ctx(ctx, "Failed to link role. Check bot permissions and role hierarchy.")

    @alliance.command(name="settype")
    @commands.admin_or_permissions(manage_guild=True)
    async def alliance_settype(self, ctx, type_: str):
        type_norm = (type_ or "").lower()
        if type_norm not in ("simple", "complex"):
            await safe_send_ctx(ctx, "Invalid type. Allowed: simple, complex.")
            return
        ok = Alliance.set_alliance_type(ctx.guild.id, type_norm, guild_obj=ctx.guild)
        await safe_send_ctx(ctx, f"Alliance type set to `{type_norm}`." if ok else "Failed to set alliance type. Check logs.")

    @alliance.command(name="join")
    async def alliance_join(self, ctx):
        ok, msg = await Alliance.join_alliance(ctx.author, ctx.guild, role_key="members")
        await safe_send_ctx(ctx, msg)

    @alliance.command(name="leave")
    async def alliance_leave(self, ctx):
        ok, msg = await Alliance.leave_alliance(ctx.author, ctx.guild)
        await safe_send_ctx(ctx, msg)

    @alliance.command(name="unregister")
    @commands.has_permissions(manage_guild=True)
    async def alliance_unregister(self, ctx, remove_roles: bool = False):
        cfg = Alliance.get_guild_config(ctx.guild.id)
        if not cfg:
            await safe_send_ctx(ctx, "No alliance configured.")
            return
        if not await _confirm(ctx, "Are you sure you want to unregister this alliance?", timeout=20.0):
            await safe_send_ctx(ctx, "Cancelled.")
            return
        ok = await Alliance.unregister_alliance(ctx.guild, remove_roles=remove_roles)
        await safe_send_ctx(ctx, "Alliance unregistered. A backup of the configuration was created." if ok else "Failed to unregister; check logs.")

    @alliance.command(name="manage")
    async def alliance_manage(self, ctx):
        if not Alliance.is_alliance_manager(ctx.author, ctx.guild):
            await safe_send_ctx(ctx, "You do not have permission to manage this alliance.")
            return
        cfg = Alliance.get_guild_config(ctx.guild.id)
        if not cfg:
            await safe_send_ctx(ctx, "No alliance configured for this guild.")
            return
        roles = cfg.get("roles", {})
        keys = ["alliance", "leader", "officers", "members", "bg1", "bg2", "bg3", "aqbg1", "awbg1", "managers"]
        lines = [f"Name: {cfg.get('info', {}).get('name', 'Not set')}", f"Type: {cfg.get('type', 'Not set')}", "", "**Configured role keys:**"]
        for k in keys:
            v = roles.get(k)
            lines.append(f"{k}: {v.get('name') if isinstance(v, dict) else (v or 'not set')}")
        await safe_send_ctx(ctx, "\n".join(lines))

    @alliance.command(name="profile")
    async def alliance_profile(self, ctx, member: Optional[Any] = None):
        cfg = Alliance.get_guild_config(ctx.guild.id)
        if not cfg:
            await safe_send_ctx(ctx, "No alliance configured for this guild.")
            return
        info = cfg.get("info", {})
        lines = [f"Name: {info.get('name') or ctx.guild.name}", f"Type: {cfg.get('type', 'unknown')}"]
        if info.get("tag"):
            lines.append(f"Tag: {info.get('tag')}")
        if info.get("invite"):
            lines.append(f"Invite: {info.get('invite')}")
        await safe_send_ctx(ctx, "\n".join(lines))


async def setup(bot):
    bot.add_cog(AlliancePrefix(bot))
