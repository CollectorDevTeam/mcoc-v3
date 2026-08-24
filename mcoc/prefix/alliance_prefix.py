# mcoc/prefix/alliance.py
import logging
from typing import Optional
from redbot.core import commands

from ..common.alliance_helpers import (
    get_guild_config, set_guild_config, role_id_for_key,
    register_alliance, create_or_link_role, join_alliance, leave_alliance,
    is_leader_or_officer, is_leader, get_alliance_info, set_alliance_info_field,
    add_officer_by_id, remove_officer_by_id, unregister_alliance,
    _role_obj_for_key
)

from ..common.roster_helpers import ensure_user_manager, _ensure_hook_registered

log = logging.getLogger("red.mcoc.prefix.alliance")


class AlliancePrefix(commands.Cog):
    """MCOC alliance management commands (guild-scoped)."""

    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="alliance", invoke_without_command=True)
    async def alliance(self, ctx):
        """Alliance commands: create, setrole, settype, join, leave, unregister, export, settings"""
        await ctx.send("Alliance commands: `create <simple|complex> <name>`, `setrole`, `settype`, `join`, `leave`, `unregister`, `settings`")

    @alliance.command(name="create")
    @commands.admin_or_permissions(manage_guild=True)
    async def alliance_create(self, ctx, type_: str, *, name: str):
        """
        Create and register an alliance on this guild.
        Usage: ///mcoc alliance create <simple|complex> <Alliance Name>

        simple: minimal role set (alliance, officers, members) and basic settings.
        complex: creates additional battlegroup roles and enables advanced features.
        """
        guild = ctx.guild
        ok = await register_alliance(guild, name, type_=type_)
        if ok:
            await ctx.send(f"Alliance **{name}** registered on this guild.")
        else:
            await ctx.send("Failed to register alliance. Check logs.")

    @alliance.command(name="setrole")
    @commands.admin_or_permissions(manage_guild=True)
    async def alliance_setrole(self, ctx, key: str, role: Optional[commands.RoleConverter] = None):
        """Link an existing role to an alliance key.
        Keys: alliance, officers, members, bg1, bg2, bg3, aqbg1, aqbg2, aqbg3, awbg1, awbg2, awbg3
        Usage: ///mcoc alliance setrole <key> <@role>
        """
        guild = ctx.guild
        if role is None:
            await ctx.send("Usage: ///mcoc alliance setrole <key> <@role>")
            return
        mapped = await create_or_link_role(guild, role.name, key, role_obj=role)
        if mapped:
            await ctx.send(f"Linked role `{role.name}` to key `{key}`.")
        else:
            await ctx.send("Failed to link role. Check bot permissions and role hierarchy.")

    @alliance.command(name="join")
    async def alliance_join(self, ctx):
        """Join this guild's alliance (adds the configured members role)."""
        member = ctx.author
        guild = ctx.guild
        ok, msg = await join_alliance(member, guild, role_key="members")
        await ctx.send(msg)

    @alliance.command(name="leave")
    async def alliance_leave(self, ctx):
        """Leave this guild's alliance (removes alliance roles)."""
        member = ctx.author
        guild = ctx.guild
        ok, msg = await leave_alliance(member, guild)
        await ctx.send(msg)

    @alliance.command(name="unregister")
    @commands.admin_or_permissions(manage_guild=True)
    async def alliance_unregister(self, ctx, remove_roles: Optional[bool] = False):
        """Unregister alliance for this guild. Optionally remove roles (may hit rate limits)."""
        guild = ctx.guild
        ok = await unregister_alliance(guild, remove_roles=bool(remove_roles))
        if ok:
            await ctx.send("Alliance unregistered.")
        else:
            await ctx.send("Failed to unregister alliance. Check logs.")

    @alliance.command(name="settings")
    async def alliance_settings(self, ctx):
        """Show alliance settings and configured roles for this guild."""
        cfg = get_guild_config(ctx.guild.id)
        if not cfg:
            await ctx.send("No alliance configured for this guild.")
            return
        lines = []
        info = cfg.get("info", {})
        lines.append(f"Name: {info.get('name', 'Not set')}")
        lines.append(f"Tag: {info.get('tag', 'Not set')}")
        lines.append(f"Type: {cfg.get('type', 'Not set')}")
        roles = cfg.get("roles", {})
        for k, v in roles.items():
            lines.append(f"{k}: {v.get('name') if isinstance(v, dict) else v}")
        await ctx.send("\n".join(lines))

    # -----------------------------
    # Display alliance profile (public)
    # -----------------------------
    @alliance.command(name="info")
    async def alliance_info(self, ctx):
        """Show the alliance profile for this guild (public)."""
        cfg = get_guild_config(ctx.guild.id)
        if not cfg:
            await ctx.send("No alliance configured for this guild.")
            return
        info = cfg.get("info", {})
        lines = []
        lines.append(f"**Alliance**: {info.get('name', 'Unnamed')}")
        if info.get("tag"):
            lines.append(f"**Tag**: {info.get('tag')}")
        if info.get("invite"):
            lines.append(f"**Invite**: {info.get('invite')}")
        if info.get("about"):
            lines.append(f"**About**: {info.get('about')}")
        if info.get("started"):
            lines.append(f"**Started**: {info.get('started')}")
        await ctx.send("\n".join(lines))

    # -----------------------------
    # Set alliance profile fields (leader or officer)
    # -----------------------------
    @alliance.command(name="setinfo")
    async def alliance_setinfo(self, ctx, field: str, *, value: str = None):
        """
        Set an alliance info field. Allowed fields: name, tag, invite, about, started, poster, wartool.
        Use an empty value to clear the field.
        """
        allowed = {"name", "tag", "invite", "about", "started", "poster", "wartool"}
        if field not in allowed:
            await ctx.send("Invalid field. Allowed: " + ", ".join(sorted(allowed)))
            return

        # permission: leader or officer
        if not is_leader_or_officer(ctx.author, ctx.guild):
            await ctx.send("Only alliance leaders or officers can set alliance info.")
            return

        # normalize clearing
        val = value.strip() if value else None
        if val == "":
            val = None

        ok = set_alliance_info_field(ctx.guild.id, field, val)
        if ok:
            await ctx.send(f"Set `{field}` to `{val}`." if val is not None else f"Cleared `{field}`.")
        else:
            await ctx.send("Failed to update alliance info. Check logs.")


    @alliance.command(name="settype")
    @commands.admin_or_permissions(manage_guild=True)
    async def alliance_settype(self, ctx, type_: str):
        """Set alliance type: simple | complex. Leaders/admins only."""
        type_ = type_.lower()
        if type_ not in ("simple", "complex"):
            await ctx.send("Invalid type. Allowed: simple, complex. Example: ///mcoc alliance settype simple")
            return
        cfg = get_guild_config(ctx.guild.id) or {}
        cfg["type"] = type_
        set_guild_config(ctx.guild.id, cfg)
        await ctx.send(f"Alliance type set to `{type_}`.")

    # -----------------------------
    # Officer management (leader only)
    # -----------------------------
    @alliance.command(name="addofficer")
    async def alliance_addofficer(self, ctx, member: Optional[commands.MemberConverter] = None):
        """Add an officer (leader only). Assigns the officers role if configured and records officer id."""
        if not is_leader(ctx.author, ctx.guild):
            await ctx.send("Only the alliance leader can add officers.")
            return
        if member is None:
            await ctx.send("Usage: ///mcoc alliance addofficer @member")
            return

        cfg = get_guild_config(ctx.guild.id)
        officers_role = None
        if cfg:
            officers_role = _role_obj_for_key(cfg, ctx.guild, "officers")
        try:
            if officers_role:
                await member.add_roles(officers_role, reason="Promoted to alliance officer")
            add_officer_by_id(ctx.guild.id, member.id)
            await ctx.send(f"{member.display_name} is now an officer.")
        except Exception:
            log.exception("Failed to add officer role for %s", member.id)
            await ctx.send("Failed to add officer. Check bot permissions and role hierarchy.")

    @alliance.command(name="removeofficer")
    async def alliance_removeofficer(self, ctx, member: Optional[commands.MemberConverter] = None):
        """Remove an officer (leader only). Removes officers role if configured and clears officer id."""
        if not is_leader(ctx.author, ctx.guild):
            await ctx.send("Only the alliance leader can remove officers.")
            return
        if member is None:
            await ctx.send("Usage: ///mcoc alliance removeofficer @member")
            return

        cfg = get_guild_config(ctx.guild.id)
        officers_role = None
        if cfg:
            officers_role = _role_obj_for_key(cfg, ctx.guild, "officers")
        try:
            if officers_role and officers_role in member.roles:
                await member.remove_roles(officers_role, reason="Demoted from alliance officer")
            remove_officer_by_id(ctx.guild.id, member.id)
            await ctx.send(f"{member.display_name} is no longer an officer.")
        except Exception:
            log.exception("Failed to remove officer role for %s", member.id)
            await ctx.send("Failed to remove officer. Check bot permissions and role hierarchy.")

    # -----------------------------
    # Promote / demote (leader only)
    # -----------------------------
    @alliance.command(name="promote")
    async def alliance_promote(self, ctx, member: Optional[commands.MemberConverter] = None, role_key: str = "members"):
        """
        Promote a member into a battlegroup or officer. role_key examples: officers, bg1, bg2, bg3, aqbg1, awbg1
        Leader only.
        """
        if not is_leader(ctx.author, ctx.guild):
            await ctx.send("Only the alliance leader can promote members.")
            return
        if member is None:
            await ctx.send("Usage: ///mcoc alliance promote @member <role_key>")
            return

        cfg = get_guild_config(ctx.guild.id)
        if not cfg:
            await ctx.send("No alliance configured for this guild.")
            return
        role_map = cfg.get("roles", {})
        target = role_map.get(role_key)
        if not target:
            await ctx.send(f"No role configured for key `{role_key}`.")
            return
        role_obj = ctx.guild.get_role(target.get("id"))
        if not role_obj:
            await ctx.send("Configured role not found on server.")
            return
        try:
            await member.add_roles(role_obj, reason="Promoted via mcoc promote")
            # ensure member is in member_ids
            mids = cfg.setdefault("member_ids", [])
            if member.id not in mids:
                mids.append(member.id)
                set_guild_config(ctx.guild.id, cfg)
            await ctx.send(f"Promoted {member.display_name} to `{role_key}`.")
        except Exception:
            log.exception("Failed to promote %s to %s", member.id, role_key)
            await ctx.send("Failed to promote. Check bot permissions and role hierarchy.")

    @alliance.command(name="demote")
    async def alliance_demote(self, ctx, member: Optional[commands.MemberConverter] = None, role_key: str = "members"):
        """Demote a member by removing a configured role. Leader only."""
        if not is_leader(ctx.author, ctx.guild):
            await ctx.send("Only the alliance leader can demote members.")
            return
        if member is None:
            await ctx.send("Usage: ///mcoc alliance demote @member <role_key>")
            return
        cfg = get_guild_config(ctx.guild.id)
        role_map = cfg.get("roles", {})
        target = role_map.get(role_key)
        if not target:
            await ctx.send(f"No role configured for key `{role_key}`.")
            return
        role_obj = ctx.guild.get_role(target.get("id"))
        if not role_obj:
            await ctx.send("Configured role not found on server.")
            return
        try:
            if role_obj in member.roles:
                await member.remove_roles(role_obj, reason="Demoted via mcoc demote")
            # if removing members role, update member_ids
            if role_key == "members":
                mids = cfg.get("member_ids", [])
                if member.id in mids:
                    mids.remove(member.id)
                    cfg["member_ids"] = mids
                    set_guild_config(ctx.guild.id, cfg)
            await ctx.send(f"Demoted {member.display_name} from `{role_key}`.")
        except Exception:
            log.exception("Failed to demote %s from %s", member.id, role_key)
            await ctx.send("Failed to demote. Check bot permissions and role hierarchy.")

    # -----------------------------
    # List members (public / officer view)
    # -----------------------------
    @alliance.command(name="listmembers")
    async def alliance_listmembers(self, ctx):
        """List alliance members (brief). Officers and leaders see full list; public sees count."""
        cfg = get_guild_config(ctx.guild.id)
        if not cfg:
            await ctx.send("No alliance configured for this guild.")
            return
        mids = cfg.get("member_ids", [])
        if is_leader_or_officer(ctx.author, ctx.guild):
            # show mentions where possible
            mentions = []
            for uid in mids:
                member = ctx.guild.get_member(uid)
                if member:
                    mentions.append(member.mention)
                else:
                    mentions.append(str(uid))
            if not mentions:
                await ctx.send("No members recorded.")
            else:
                out = ", ".join(mentions)
                await ctx.send(f"Members ({len(mentions)}): {out}")
        else:
            await ctx.send(f"Alliance member count: {len(mids)}")


# mcoc/prefix/alliance_prefix.py  (append near the bottom)

def register_with_group(group: commands.Group, parent_getter):
    """
    Attach alliance prefix commands to the provided `group`.
    parent_getter is a callable returning the core/parent object (or None).
    """
    def _safe_add(cmd_name, func):
        try:
            if group.get_command(cmd_name):
                return
        except Exception:
            pass
        group.command(name=cmd_name)(func)

    # wrappers reuse the alliance_helpers API
    async def _info(ctx):
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; alliance unavailable.")
            return
        from ..common.alliance_helpers import get_guild_config
        cfg = get_guild_config(ctx.guild.id)
        if not cfg:
            await ctx.send("No alliance configured for this guild.")
            return
        info = cfg.get("info", {})
        lines = [f"**Alliance**: {info.get('name','Unnamed')}"]
        if info.get("tag"):
            lines.append(f"**Tag**: {info.get('tag')}")
        if info.get("invite"):
            lines.append(f"**Invite**: {info.get('invite')}")
        if info.get("about"):
            lines.append(f"**About**: {info.get('about')}")
        await ctx.send("\n".join(lines))

    _safe_add("info", _info)

    async def _create(ctx, type_: str, *, name: str):
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; alliance unavailable.")
            return
        from ..common.alliance_helpers import register_alliance
        ok = await register_alliance(ctx.guild, name, type_=type_)
        await ctx.send(f"Alliance **{name}** registered." if ok else "Failed to register alliance.")

    _safe_add("create", _create)

    async def _join(ctx):
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; alliance unavailable.")
            return
        from ..common.alliance_helpers import join_alliance
        ok, msg = await join_alliance(ctx.author, ctx.guild, role_key="members")
        await ctx.send(msg)

    _safe_add("join", _join)

    async def _leave(ctx):
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; alliance unavailable.")
            return
        from ..common.alliance_helpers import leave_alliance
        ok, msg = await leave_alliance(ctx.author, ctx.guild)
        await ctx.send(msg)

    _safe_add("leave", _leave)

    async def _settings(ctx):
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; alliance unavailable.")
            return
        from ..common.alliance_helpers import get_guild_config
        cfg = get_guild_config(ctx.guild.id)
        if not cfg:
            await ctx.send("No alliance configured for this guild.")
            return
        info = cfg.get("info", {})
        roles = cfg.get("roles", {})
        lines = [f"Name: {info.get('name')}", f"Type: {cfg.get('type')}"]
        for k, v in roles.items():
            lines.append(f"{k}: {v.get('name') if isinstance(v, dict) else v}")
        await ctx.send("\n".join(lines))

    _safe_add("settings", _settings)
