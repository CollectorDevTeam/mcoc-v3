# mcoc/prefix/alliance.py
"""
Prefix command handlers for alliance management.

This module is intentionally thin: it resolves context and delegates logic to
mcoc.common.alliance helpers. It focuses on user-friendly messages, confirmation
flows, and pagination where appropriate.
"""

from typing import Optional, Any, List
import logging
import asyncio

from redbot.core import commands

from mcoc.common import Core
Embed = Core.Embed
Confirm = Core.Confirm
PagesMenu = Core.PagesMenu
Alliance = Core.Helpers.alliance


from ..common.prefix_utils import safe_send_ctx
from ..common.help_utils import send_or_brand_help


log = logging.getLogger("red.mcoc.prefix.alliance")


class AlliancePrefix(commands.Cog):
    """MCOC alliance management prefix commands (guild-scoped)."""

    def __init__(self, bot):
        self.bot = bot
        self.parent = getattr(bot, "mcoc_core", None)

    @commands.group(name="alliance", send_or_brand_help=True)
    async def alliance(self, ctx):
        """Alliance commands: create, template, setrole, settype, join, leave, unregister, settings, manage, export, reconcile, promote, demote, profile"""
        prefix = getattr(ctx, "prefix", "///")
        help_text = (
            "Alliance commands:\n"
            f"`{prefix}mcoc alliance create <simple|complex> <name>` — register an alliance and create core roles\n"
            f"`{prefix}mcoc alliance template` — interactive template that creates a standard set of roles\n"
            f"`{prefix}mcoc alliance setrole <key> <@role>` — link an existing role to a key\n"
            f"`{prefix}mcoc alliance settype <simple|complex>` — convert alliance type\n"
            f"`{prefix}mcoc alliance manage` — management overview and quick actions\n"
            f"`{prefix}mcoc alliance profile [@member]` — show alliance or member profile\n"
        )
        await send_or_brand_help(ctx, "alliance", title="Alliance Help", fallback_text=help_text)

    # -----------------------------
    # Create / template
    # -----------------------------
    @alliance.command(name="create")
    @commands.admin_or_permissions(manage_guild=True)
    async def alliance_create(self, ctx, type_: str, *, name: str):
        """Create and register an alliance on this guild."""
        type_norm = (type_ or "").lower()
        if type_norm not in ("simple", "complex"):
            await safe_send_ctx(ctx, "Invalid type. Allowed: simple, complex.")
            return

        roles_to_create = [f"{name} Alliance", f"{name} Officers", f"{name} Members"]
        if type_norm == "complex":
            roles_to_create += [f"{name} Leader", f"{name} BG1", f"{name} BG2", f"{name} BG3", f"{name} AQBG1", f"{name} AWBG1"]

        prompt = "This will create/link the following roles:\n" + "\n".join(f"- {r}" for r in roles_to_create)
        confirmed = await Confirm(self.bot, ctx, prompt, timeout=30.0)
        if not confirmed:
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
        """Interactive template that creates a standard set of roles (asks for confirmation)."""
        guild = ctx.guild
        name = guild.name.split()[0] if guild and guild.name else "Alliance"
        roles_to_create = [f"{name} Alliance", f"{name} Officers", f"{name} Members", f"{name} Leader", f"{name} BG1", f"{name} BG2", f"{name} BG3"]
        prompt = "This will create the following roles:\n" + "\n".join(f"- {r}" for r in roles_to_create)
        confirmed = await Confirm(self.bot, ctx, prompt, timeout=30.0)
        if not confirmed:
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

    # -----------------------------
    # Role linking and type
    # -----------------------------
    @alliance.command(name="setrole")
    @commands.admin_or_permissions(manage_guild=True)
    async def alliance_setrole(self, ctx, key: str, role: Optional[commands.RoleConverter] = None):
        """Link an existing role to an alliance key."""
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
        """Set alliance type: simple | complex. Admins only."""
        type_norm = (type_ or "").lower()
        if type_norm not in ("simple", "complex"):
            await safe_send_ctx(ctx, "Invalid type. Allowed: simple, complex.")
            return
        ok = Alliance.set_alliance_type(ctx.guild.id, type_norm, guild_obj=ctx.guild)
        if ok:
            await safe_send_ctx(ctx, f"Alliance type set to `{type_norm}`.")
        else:
            await safe_send_ctx(ctx, "Failed to set alliance type. Check logs.")

    # -----------------------------
    # Join / leave
    # -----------------------------
    @alliance.command(name="join")
    async def alliance_join(self, ctx):
        """Join this guild's alliance (adds the configured members role)."""
        ok, msg = await Alliance.join_alliance(ctx.author, ctx.guild, role_key="members")
        await safe_send_ctx(ctx, msg)

    @alliance.command(name="leave")
    async def alliance_leave(self, ctx):
        """Leave this guild's alliance (removes alliance roles)."""
        ok, msg = await Alliance.leave_alliance(ctx.author, ctx.guild)
        await safe_send_ctx(ctx, msg)

    # -----------------------------
    # Unregister
    # -----------------------------
    @alliance.command(name="unregister")
    @commands.has_permissions(manage_guild=True)
    async def alliance_unregister(self, ctx, remove_roles: bool = False):
        cfg = Alliance.get_guild_config(ctx.guild.id)
        if not cfg:
            await safe_send_ctx(ctx, "No alliance configured.")
            return
        prompt = "Are you sure you want to unregister this alliance? Reply `yes` to confirm."
        confirmed = await Confirm(self.bot, ctx, prompt, timeout=20.0)
        if not confirmed:
            await safe_send_ctx(ctx, "Cancelled.")
            return
        ok = await Alliance.unregister_alliance(ctx.guild, remove_roles=remove_roles)
        if ok:
            await safe_send_ctx(ctx, "Alliance unregistered. A backup of the configuration was created.")
        else:
            await safe_send_ctx(ctx, "Failed to unregister; check logs.")

    # -----------------------------
    # Management / settings / export
    # -----------------------------
    @alliance.command(name="manage")
    async def alliance_manage(self, ctx):
        """Show management actions and configured role keys for this guild."""
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

    @alliance.command(name="settings")
    async def alliance_settings(self, ctx):
        """Show alliance settings and configured roles for this guild."""
        cfg = Alliance.get_guild_config(ctx.guild.id)
        if not cfg:
            await safe_send_ctx(ctx, "No alliance configured for this guild.")
            return
        info = cfg.get("info", {})
        emb = Embed.embed(ctx.author, title=info.get("name") or ctx.guild.name, description=info.get("about") or "")
        if info.get("tag"):
            emb.add_field(name="Tag", value=info.get("tag"), inline=False)
        if info.get("invite"):
            emb.add_field(name="Invite", value=info.get("invite"), inline=False)
        roles = cfg.get("roles", {})
        role_lines = []
        for key in ("alliance", "leader", "officers", "members", "bg1", "bg2", "bg3"):
            r = roles.get(key)
            role_lines.append(f"{key}: {r.get('name') if isinstance(r, dict) else (r or 'not set')}")
        if role_lines:
            emb.add_field(name="Configured roles", value="\n".join(role_lines), inline=False)
        try:
            await safe_send_ctx(ctx, None, embed=emb)
        except Exception:
            await safe_send_ctx(ctx, "\n".join(role_lines))

    # -----------------------------
    # Profile display
    # -----------------------------
    @alliance.command(name="profile")
    async def alliance_profile(self, ctx, member: Optional[commands.MemberConverter] = None):
        """
        Show a user's alliance profile or the guild's public alliance profile.
        """
        if member is None:
            cfg = Alliance.get_guild_config(ctx.guild.id)
            if not cfg:
                await safe_send_ctx(ctx, "No alliance configured for this guild.")
                return
            info = cfg.get("info", {})
            emb = Embed.embed(ctx.author, title=info.get("name") or ctx.guild.name, description=info.get("about") or "")
            if info.get("tag"):
                emb.add_field(name="Tag", value=info.get("tag"), inline=False)
            if info.get("invite"):
                emb.add_field(name="Invite", value=info.get("invite"), inline=False)
            if info.get("started"):
                emb.add_field(name="Started", value=info.get("started"), inline=False)
            role_lines = []
            for key in ("alliance", "leader", "officers", "members", "bg1", "bg2", "bg3"):
                r = cfg.get("roles", {}).get(key)
                role_lines.append(f"{key}: {r.get('name') if isinstance(r, dict) else (r or 'not set')}")
            if role_lines:
                emb.add_field(name="Configured roles", value="\n".join(role_lines), inline=False)
            try:
                if getattr(ctx.guild, "icon_url", None):
                    emb.set_thumbnail(url=ctx.guild.icon_url)
            except Exception:
                pass
            await safe_send_ctx(ctx, None, embed=emb)
            return

        # member provided: show private view if member is in this guild's alliance
        try:
            member_alliance_name = Alliance.get_user_alliance_in_guild(member.id, ctx.guild.id)
            if member_alliance_name:
                cfg = Alliance.get_guild_config(ctx.guild.id)
                emb = Embed.embed(ctx.author, title=f"{member.display_name} — {cfg.get('info', {}).get('name', ctx.guild.name)}")
                role_info = []
                for key, r in cfg.get("roles", {}).items():
                    if isinstance(r, dict):
                        role_obj = ctx.guild.get_role(r.get("id"))
                        if role_obj and role_obj in member.roles:
                            role_info.append(f"{key}: {role_obj.name}")
                if role_info:
                    emb.add_field(name="Roles", value="\n".join(role_info), inline=False)
                emb.add_field(name="Member ID", value=str(member.id), inline=True)
                try:
                    emb.set_thumbnail(url=member.avatar.url)
                except Exception:
                    pass
                await safe_send_ctx(ctx, None, embed=emb)
                return
            else:
                # public profile: search configured guilds for membership and show pages
                found = []
                for g in self.bot.guilds:
                    cfg = Alliance.get_guild_config(g.id)
                    if not cfg:
                        continue
                    mids = cfg.get("member_ids", [])
                    if member.id in mids:
                        found.append((g, cfg))
                if not found:
                    await safe_send_ctx(ctx, f"{member.display_name} is not recorded in any configured alliance.")
                    return
                pages = []
                for g, cfg in found:
                    emb = Embed.embed(ctx.author, title=cfg.get("info", {}).get("name", g.name))
                    if cfg.get("info", {}).get("tag"):
                        emb.add_field(name="Tag", value=cfg.get("info", {}).get("tag"), inline=False)
                    role_lines = []
                    for key, r in cfg.get("roles", {}).items():
                        if isinstance(r, dict):
                            role_obj = g.get_role(r.get("id"))
                            if role_obj and role_obj in member.roles:
                                role_lines.append(f"{key}: {role_obj.name}")
                    if role_lines:
                        emb.add_field(name=f"{member.display_name}'s roles", value="\n".join(role_lines), inline=False)
                    emb.set_footer(text=f"Server: {g.name} ({g.id})")
                    pages.append(emb)
                menu = PagesMenu(pages, ctx.author, timeout=120)
                await menu.start(ctx)
                return
        except Exception:
            log.exception("Failed to build profile for member %s", getattr(member, "id", None))
            await safe_send_ctx(ctx, "Failed to fetch profile. Check logs.")
            return

    # -----------------------------
    # Alliance info setters (leader/officer)
    # -----------------------------
    @alliance.command(name="setinfo")
    async def alliance_setinfo(self, ctx, field: str, *, value: Optional[str] = None):
        """
        Set an alliance info field. Allowed fields: name, tag, invite, about, started, poster, wartool.
        Use an empty value to clear the field.
        """
        allowed = {"name", "tag", "invite", "about", "started", "poster", "wartool"}
        if field not in allowed:
            await safe_send_ctx(ctx, "Invalid field. Allowed: " + ", ".join(sorted(allowed)))
            return
        if not Alliance.is_leader_or_officer(ctx.author, ctx.guild):
            await safe_send_ctx(ctx, "Only alliance leaders or officers can set alliance info.")
            return
        val = value.strip() if value else None
        if val == "":
            val = None
        ok = Alliance.set_alliance_info_field(ctx.guild.id, field, val)
        if ok:
            await safe_send_ctx(ctx, f"Set `{field}` to `{val}`." if val is not None else f"Cleared `{field}`.")
        else:
            await safe_send_ctx(ctx, "Failed to update alliance info. Check logs.")

    # -----------------------------
    # Officer management (leader only)
    # -----------------------------
    @alliance.command(name="addofficer")
    async def alliance_addofficer(self, ctx, member: Optional[commands.MemberConverter] = None):
        """Add an officer (leader only)."""
        if not Alliance.is_leader(ctx.author, ctx.guild):
            await safe_send_ctx(ctx, "Only the alliance leader can add officers.")
            return
        if member is None:
            await safe_send_ctx(ctx, "Usage: ///mcoc alliance addofficer @member")
            return
        cfg = Alliance.get_guild_config(ctx.guild.id)
        officers_role = None
        if cfg:
            officers_role = ctx.guild.get_role(cfg.get("roles", {}).get("officers", {}).get("id")) if cfg.get("roles", {}).get("officers") else None
        try:
            if officers_role:
                await member.add_roles(officers_role, reason="Promoted to alliance officer")
            Alliance.add_officer_by_id(ctx.guild.id, member.id)
            await safe_send_ctx(ctx, f"{member.display_name} is now an officer.")
        except Exception:
            log.exception("Failed to add officer role for %s", member.id)
            await safe_send_ctx(ctx, "Failed to add officer. Check bot permissions and role hierarchy.")

    @alliance.command(name="removeofficer")
    async def alliance_removeofficer(self, ctx, member: Optional[commands.MemberConverter] = None):
        """Remove an officer (leader only)."""
        if not Alliance.is_leader(ctx.author, ctx.guild):
            await safe_send_ctx(ctx, "Only the alliance leader can remove officers.")
            return
        if member is None:
            await safe_send_ctx(ctx, "Usage: ///mcoc alliance removeofficer @member")
            return
        cfg = Alliance.get_guild_config(ctx.guild.id)
        officers_role = None
        if cfg:
            officers_role = ctx.guild.get_role(cfg.get("roles", {}).get("officers", {}).get("id")) if cfg.get("roles", {}).get("officers") else None
        try:
            if officers_role and officers_role in member.roles:
                await member.remove_roles(officers_role, reason="Demoted from alliance officer")
            Alliance.remove_officer_by_id(ctx.guild.id, member.id)
            await safe_send_ctx(ctx, f"{member.display_name} is no longer an officer.")
        except Exception:
            log.exception("Failed to remove officer role for %s", member.id)
            await safe_send_ctx(ctx, "Failed to remove officer. Check bot permissions and role hierarchy.")

    # -----------------------------
    # Promote / demote (leader only)
    # -----------------------------
    @alliance.command(name="promote")
    async def alliance_promote(self, ctx, member: Optional[commands.MemberConverter] = None, role_key: str = "members"):
        """Promote a member into a battlegroup or officer. Leader only."""
        if not Alliance.is_leader(ctx.author, ctx.guild):
            await safe_send_ctx(ctx, "Only the alliance leader can promote members.")
            return
        if member is None:
            await safe_send_ctx(ctx, "Usage: ///mcoc alliance promote @member <role_key>")
            return
        cfg = Alliance.get_guild_config(ctx.guild.id)
        if not cfg:
            await safe_send_ctx(ctx, "No alliance configured for this guild.")
            return
        rid = cfg.get("roles", {}).get(role_key, {}).get("id")
        role_obj = ctx.guild.get_role(rid) if rid else None
        if not role_obj:
            await safe_send_ctx(ctx, f"No role configured or role not found for key `{role_key}`.")
            return
        try:
            await member.add_roles(role_obj, reason="Promoted via mcoc promote")
            mids = cfg.setdefault("member_ids", [])
            if member.id not in mids:
                mids.append(member.id)
                Alliance.set_guild_config(ctx.guild.id, cfg)
            await safe_send_ctx(ctx, f"Promoted {member.display_name} to `{role_key}`.")
        except Exception:
            log.exception("Failed to promote %s to %s", member.id, role_key)
            await safe_send_ctx(ctx, "Failed to promote. Check bot permissions and role hierarchy.")

    @alliance.command(name="demote")
    async def alliance_demote(self, ctx, member: Optional[commands.MemberConverter] = None, role_key: str = "members"):
        """Demote a member by removing a configured role. Leader only."""
        if not Alliance.is_leader(ctx.author, ctx.guild):
            await safe_send_ctx(ctx, "Only the alliance leader can demote members.")
            return
        if member is None:
            await safe_send_ctx(ctx, "Usage: ///mcoc alliance demote @member <role_key>")
            return
        cfg = Alliance.get_guild_config(ctx.guild.id)
        role_map = cfg.get("roles", {})
        target = role_map.get(role_key)
        if not target:
            await safe_send_ctx(ctx, f"No role configured for key `{role_key}`.")
            return
        role_obj = ctx.guild.get_role(target.get("id"))
        if not role_obj:
            await safe_send_ctx(ctx, "Configured role not found on server.")
            return
        try:
            if role_obj in member.roles:
                await member.remove_roles(role_obj, reason="Demoted via mcoc demote")
            if role_key == "members":
                mids = cfg.get("member_ids", [])
                if member.id in mids:
                    mids.remove(member.id)
                    cfg["member_ids"] = mids
                    Alliance.set_guild_config(ctx.guild.id, cfg)
            await safe_send_ctx(ctx, f"Demoted {member.display_name} from `{role_key}`.")
        except Exception:
            log.exception("Failed to demote %s from %s", member.id, role_key)
            await safe_send_ctx(ctx, "Failed to demote. Check bot permissions and role hierarchy.")

    # -----------------------------
    # List members
    # -----------------------------
    @alliance.command(name="listmembers")
    async def alliance_listmembers(self, ctx):
        """List alliance members (brief). Officers and leaders see full list; public sees count."""
        cfg = Alliance.get_guild_config(ctx.guild.id)
        if not cfg:
            await safe_send_ctx(ctx, "No alliance configured for this guild.")
            return
        mids = cfg.get("member_ids", [])
        if Alliance.is_leader_or_officer(ctx.author, ctx.guild):
            mentions = []
            for uid in mids:
                member = ctx.guild.get_member(uid)
                mentions.append(member.mention if member else str(uid))
            if not mentions:
                await safe_send_ctx(ctx, "No members recorded.")
            else:
                await safe_send_ctx(ctx, f"Members ({len(mentions)}): " + ", ".join(mentions))
        else:
            await safe_send_ctx(ctx, f"Alliance member count: {len(mids)}")


# Cog setup for Red (if used as a cog)
async def setup(bot):
    bot.add_cog(AlliancePrefix(bot))
