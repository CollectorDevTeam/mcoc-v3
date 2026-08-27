# mcoc/prefix/alliance.py
import logging
import asyncio
from typing import Optional, Any, List
from datetime import datetime

from dateutil.parser import parse as date_parse
from redbot.core import commands
from ..common.componentsV2 import CDTEmbed, ConfirmView, PaginatorView
from ..common.alliance_helpers import (
    get_guild_config, set_guild_config, role_id_for_key,
    register_alliance, create_or_link_role, join_alliance, leave_alliance,
    is_leader_or_officer, is_leader, is_alliance_manager, get_alliance_info, set_alliance_info_field,
    add_officer_by_id, remove_officer_by_id, unregister_alliance,
    _role_obj_for_key, get_user_alliance_in_guild
)

from ..common.roster_helpers import ensure_user_manager, _ensure_hook_registered

log = logging.getLogger("red.mcoc.prefix.alliance")


class AlliancePrefix(commands.Cog):
    """MCOC alliance management commands (guild-scoped)."""

    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="alliance", invoke_without_command=True)
    async def alliance(self, ctx):
        """Alliance commands: create, template, setrole, settype, join, leave, unregister, settings, manage, export, reconcile, promote, demote, profile"""
        help_text = (
            "Alliance commands:\n"
            "`create <simple|complex> <name>` — register an alliance and create core roles\n"
            "`template` — interactive template that creates a standard set of roles (asks for confirmation)\n"
            "`setrole <key> <@role>` — link an existing role to a key (keys: alliance, officers, members, leader, bg1, bg2, bg3, aqbg1, awbg1)\n"
            "`settype <simple|complex>` — convert alliance type; complex creates battlegroup/leader roles\n"
            "`manage` — management overview and quick actions (managers/leaders)\n"
            "`settings` / `info` — show alliance settings and public profile\n"
            "`profile [@member]` — show a user's alliance profile (public). If run in the user's alliance guild, private details are shown.\n"
            "`export` — export roster CSV (admins)\n"
            "`reconcile [apply=True]` — dry-run or apply fixes for missing configured roles (admins)\n"
            "`promote` / `demote` — leader-only role assignment\n"
            "`unregister [remove_roles]` — unregister alliance (admins; confirmation required)\n"
        )
        await ctx.send(help_text)

    # ---------------------------------
    # Alliance creation and template commands
    # ---------------------------------
    @alliance.command(name="create")
    @commands.admin_or_permissions(manage_guild=True)
    async def alliance_create(self, ctx, type_: str, *, name: str):
        """
        Create and register an alliance on this guild.
        Usage: ///mcoc alliance create <simple|complex> <Alliance Name>
        """
        guild = ctx.guild
        type_norm = (type_ or "").lower()
        if type_norm not in ("simple", "complex"):
            await ctx.send("Invalid type. Allowed: simple, complex. Example: ///mcoc alliance create simple CDT1")
            return

        # Describe what will be created and ask for confirmation via PagesMenu.confirm
        roles_to_create = [f"{name} Alliance", f"{name} Officers", f"{name} Members"]
        if type_norm == "complex":
            roles_to_create += [
                f"{name} Leader", f"{name} BG1", f"{name} BG2", f"{name} BG3",
                f"{name} AQBG1", f"{name} AWBG1"
            ]

        prompt = (
            "This will register the alliance and create/link the following roles:\n"
            + "\n".join(f"- {r}" for r in roles_to_create)
            + "\n\nReply with `yes` to proceed or anything else to cancel."
        )

        confirmed, _ = await ConfirmView.confirm(self.bot, ctx, prompt, timeout=30.0)
        if not confirmed:
            await ctx.send("Cancelled. No changes were made.")
            return

        ok = await register_alliance(guild, name, alliance_tag=None, type_=type_norm)
        if ok:
            await ctx.send(f"Alliance **{name}** registered on this guild.")
        else:
            await ctx.send("Failed to register alliance. Check logs.")

    @alliance.command(name="template")
    @commands.admin_or_permissions(manage_guild=True)
    async def alliance_template(self, ctx):
        """Interactive template that creates a standard set of roles (asks for confirmation)."""
        guild = ctx.guild
        name = f"{guild.name.split()[0]}"
        roles_to_create = [
            f"{name} Alliance", f"{name} Officers", f"{name} Members",
            f"{name} Leader", f"{name} BG1", f"{name} BG2", f"{name} BG3"
        ]
        prompt = "This will create the following roles:\n" + "\n".join(f"- {r}" for r in roles_to_create)
        prompt += "\n\nReply with `yes` to proceed or anything else to cancel."

        confirmed, _ = await ConfirmView.confirm(self.bot, ctx, prompt, timeout=30.0)
        if not confirmed:
            await ctx.send("Cancelled. No roles were created.")
            return

        created = []
        for rname in roles_to_create:
            try:
                role = await guild.create_role(name=rname, reason="Alliance template creation")
                created.append(role.name)
                await asyncio.sleep(0.25)
            except Exception:
                log.exception("Failed to create role %s in guild %s", rname, guild.id)
        await ctx.send(f"Created roles: {', '.join(created) if created else 'none (check logs)'}")

    # ---------------------------------
    # Alliance role management commands
    # ---------------------------------
    @alliance.command(name="setrole")
    @commands.admin_or_permissions(manage_guild=True)
    async def alliance_setrole(self, ctx, key: str, role: Optional[commands.RoleConverter] = None):
        """Link an existing role to an alliance key."""
        guild = ctx.guild
        if role is None:
            await ctx.send("Usage: ///mcoc alliance setrole <key> <@role>\nKeys: alliance, officers, members, leader, bg1, bg2, bg3, aqbg1, awbg1")
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
    @commands.has_permissions(manage_guild=True)
    async def alliance_unregister(self, ctx, remove_roles: bool = False):
        cfg = get_guild_config(ctx.guild.id)
        if not cfg:
            await ctx.send("No alliance configured.")
            return

        prompt = (
            "Are you sure you want to unregister this alliance? This will remove the alliance configuration "
            "and optionally delete configured roles. Reply `yes` to confirm."
        )
        confirmed, _ = await ConfirmView.confirm(self.bot, ctx, prompt, timeout=20.0)
        if not confirmed:
            await ctx.send("Cancelled.")
            return

        ok = await unregister_alliance(ctx.guild, remove_roles=remove_roles)
        if ok:
            await ctx.send("Alliance unregistered. A backup of the configuration was created.")
        else:
            await ctx.send("Failed to unregister; check logs.")

    # ---------------------------------
    # Alliance management commands
    # ---------------------------------
    @alliance.command(name="export")
    @commands.has_permissions(manage_guild=True)
    async def alliance_export(self, ctx):
        """Export roster CSV for alliance members (admin only)."""
        # Placeholder: implement CSV export using ensure_user_manager and ChampionRoster
        await ctx.send("Export not implemented in this build. Use the export utility when available.")

    @alliance.command(name="manage")
    async def alliance_manage(self, ctx):
        """Show management actions and configured role keys for this guild."""
        if not is_alliance_manager(ctx.author, ctx.guild):
            await ctx.send("You do not have permission to manage this alliance.")
            return

        cfg = get_guild_config(ctx.guild.id)
        if not cfg:
            await ctx.send("No alliance configured for this guild.")
            return

        roles = cfg.get("roles", {})
        keys = ["alliance", "leader", "officers", "members", "bg1", "bg2", "bg3", "aqbg1", "awbg1", "managers"]
        lines = [
            "**Alliance management**",
            f"Name: {cfg.get('info', {}).get('name', 'Not set')}",
            f"Type: {cfg.get('type', 'Not set')}",
            "",
            "**Configured role keys:**"
        ]
        for k in keys:
            v = roles.get(k)
            lines.append(f"{k}: {v.get('name') if isinstance(v, dict) else (v or 'not set')}")
        lines.append("")
        lines.append("**Quick actions**:")
        lines.append("`///mcoc alliance setrole <key> <@role>` — link an existing role to a key")
        lines.append("`///mcoc alliance settype <simple|complex>` — create battlegroup/leader roles (admins only)")
        lines.append("`///mcoc alliance setinfo <field> <value>` — set profile fields (leader/officer)")
        lines.append("`///mcoc alliance unregister <remove_roles>` — unregister alliance (admins only)")
        await ctx.send("\n".join(lines))

    @alliance.command(name="reconcile")
    @commands.has_permissions(manage_guild=True)
    async def alliance_reconcile(self, ctx, apply: bool = False):
        """Dry-run reconciliation between alliances.json and guild roles. Use apply=True to fix."""
        cfg = get_guild_config(ctx.guild.id)
        if not cfg:
            await ctx.send("No alliance configured.")
            return
        missing = []
        for key, entry in cfg.get("roles", {}).items():
            rid = entry.get("id") if isinstance(entry, dict) else None
            if rid is None or ctx.guild.get_role(rid) is None:
                missing.append(key)
        if not missing:
            await ctx.send("All configured roles exist on this server.")
            return
        if not apply:
            await ctx.send("Missing role keys: " + ", ".join(missing) + ". Run with `apply=True` to attempt fixes.")
            return
        created = []
        for k in missing:
            mapped = await create_or_link_role(ctx.guild, f"{cfg.get('info', {}).get('name','Alliance')} {k.capitalize()}", k)
            if mapped:
                created.append(k)
        await ctx.send(f"Created/linked roles: {', '.join(created) if created else 'none (check logs)'}")

    @alliance.command(name="settype")
    @commands.admin_or_permissions(manage_guild=True)
    async def alliance_settype(self, ctx, type_: str):
        """Set alliance type: simple | complex. Admins only. Use complex to create leader and BG roles."""
        type_norm = (type_ or "").lower()
        if type_norm not in ("simple", "complex"):
            await ctx.send("Invalid type. Allowed: simple, complex. Example: ///mcoc alliance settype complex")
            return

        cfg = get_guild_config(ctx.guild.id) or {}
        cfg["type"] = type_norm
        set_guild_config(ctx.guild.id, cfg)

        if type_norm == "complex":
            name = cfg.get("info", {}).get("name", "Alliance")
            created = []
            for key, label in [("leader", "Leader"), ("bg1", "BG1"), ("bg2", "BG2"), ("bg3", "BG3"), ("aqbg1", "AQBG1"), ("awbg1", "AWBG1")]:
                if not cfg.get("roles", {}).get(key):
                    mapped = await create_or_link_role(ctx.guild, f"{name} {label}", key)
                    if mapped:
                        created.append(key)
            await ctx.send(f"Alliance type set to `{type_norm}`. Created roles: {', '.join(created) if created else 'none (or already present)'}")
        else:
            await ctx.send(f"Alliance type set to `{type_norm}`.")

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
    # Display alliance profile (public / per-user)
    # -----------------------------
    @alliance.command(name="profile")
    async def alliance_profile(self, ctx, member: Optional[commands.MemberConverter] = None):
        """
        Show a user's alliance profile.
        - If no member provided, show the guild's public alliance profile.
        - If member provided, show public profile for that user.
        - If the command is run inside the user's alliance guild, show private details.
        """
        # If no member provided, show guild profile (alias for info/settings)
        if member is None:
            # show guild public profile
            cfg = get_guild_config(ctx.guild.id)
            if not cfg:
                await ctx.send("No alliance configured for this guild.")
                return
            info = cfg.get("info", {})
            emb = CDTEmbed.embed(ctx, title=info.get("name") or ctx.guild.name, color=CDTEmbed.get_color_value(ctx))
            if info.get("tag"):
                emb.add_field(name="Tag", value=info.get("tag"), inline=False)
            if info.get("about"):
                emb.description = info.get("about")
            if info.get("invite"):
                emb.add_field(name="Invite", value=info.get("invite"), inline=False)
            if info.get("started"):
                emb.add_field(name="Started", value=info.get("started"), inline=False)
            # configured roles
            role_lines = []
            for key in ("alliance", "leader", "officers", "members", "bg1", "bg2", "bg3"):
                r = cfg.get("roles", {}).get(key)
                if isinstance(r, dict):
                    role_lines.append(f"**{key}**: {r.get('name')} (`{r.get('id')}`)")
                elif r:
                    role_lines.append(f"**{key}**: {r}")
            if role_lines:
                emb.add_field(name="Configured roles", value="\n".join(role_lines), inline=False)
            if ctx.guild.icon_url:
                emb.set_thumbnail(url=ctx.guild.icon_url)
            await ctx.send(embed=emb)
            return

        # member provided: determine alliances for that user
        # check if this guild is one of the user's alliances and whether we are in that guild
        # Use get_user_alliance_in_guild to check membership in this guild
        try:
            # If the command is invoked in the member's alliance guild, show private details
            member_alliance_name = get_user_alliance_in_guild(member.id, ctx.guild.id)
            if member_alliance_name:
                # private view: show member's roles and membership info
                cfg = get_guild_config(ctx.guild.id)
                emb = CDTEmbed.embed(ctx, title=f"{member.display_name} — {cfg.get('info', {}).get('name', ctx.guild.name)}", color=CDTEmbed.get_color_value(ctx))
                # show member roles relevant to alliance
                role_info = []
                for key, r in cfg.get("roles", {}).items():
                    if isinstance(r, dict):
                        role_obj = ctx.guild.get_role(r.get("id"))
                        if role_obj and role_obj in member.roles:
                            role_info.append(f"{key}: {role_obj.name}")
                if role_info:
                    emb.add_field(name="Roles", value="\n".join(role_info), inline=False)
                # membership metadata
                emb.add_field(name="Member ID", value=str(member.id), inline=True)
                emb.set_thumbnail(url=member.avatar.url)
                await ctx.send(embed=emb)
                return
            else:
                # public profile: show which alliances the user is in (across configured guilds)
                # We'll search current guilds config for membership
                found = []
                data = []
                # iterate all configured guilds (read alliances file via helper)
                # get_guild_config only returns per-guild; iterate known guilds by checking bot.guilds
                for g in self.bot.guilds:
                    cfg = get_guild_config(g.id)
                    if not cfg:
                        continue
                    mids = cfg.get("member_ids", [])
                    if member.id in mids:
                        found.append((g, cfg))
                if not found:
                    await ctx.send(f"{member.display_name} is not recorded in any configured alliance.")
                    return
                pages = []
                for g, cfg in found:
                    emb = CDTEmbed.embed(ctx, title=cfg.get("info", {}).get("name", g.name), color=CDTEmbed.get_color_value(ctx))
                    if cfg.get("info", {}).get("tag"):
                        emb.add_field(name="Tag", value=cfg.get("info", {}).get("tag"), inline=False)
                    # show member's role in that guild if available
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
                # paginate results
                menu = PaginatorView(pages, ctx.author, timeout=120)
                await menu.start(ctx)
                return
        except Exception:
            log.exception("Failed to build profile for member %s", getattr(member, "id", None))
            await ctx.send("Failed to fetch profile. Check logs.")
            return

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

        if not is_leader_or_officer(ctx.author, ctx.guild):
            await ctx.send("Only alliance leaders or officers can set alliance info.")
            return

        val = value.strip() if value else None
        if val == "":
            val = None

        ok = set_alliance_info_field(ctx.guild.id, field, val)
        if ok:
            await ctx.send(f"Set `{field}` to `{val}`." if val is not None else f"Cleared `{field}`.")
        else:
            await ctx.send("Failed to update alliance info. Check logs.")

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

        rid = role_id_for_key(cfg, role_key)
        role_obj = ctx.guild.get_role(rid) if rid else None
        if not role_obj:
            await ctx.send(f"No role configured or role not found for key `{role_key}`.")
            return

        try:
            await member.add_roles(role_obj, reason="Promoted via mcoc promote")
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

    def _safe_add(cmd_name):
        def _decorator(func):
            try:
                if group.get_command(cmd_name):
                    log.debug("Command %s already exists; skipping", cmd_name)
                    return func
            except Exception:
                pass
            group.command(name=cmd_name)(func)
            return func
        return _decorator

    # wrappers reuse the alliance_helpers API
    @_safe_add("info")
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

    @_safe_add("create")
    async def _create(ctx, type_: str, *, name: str):
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; alliance unavailable.")
            return
        from ..common.alliance_helpers import register_alliance
        ok = await register_alliance(ctx.guild, name, type_=type_)
        await ctx.send(f"Alliance **{name}** registered." if ok else "Failed to register alliance.")

    @_safe_add("join")
    async def _join(ctx):
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; alliance unavailable.")
            return
        from ..common.alliance_helpers import join_alliance
        ok, msg = await join_alliance(ctx.author, ctx.guild, role_key="members")
        await ctx.send(msg)

    @_safe_add("leave")
    async def _leave(ctx):
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; alliance unavailable.")
            return
        from ..common.alliance_helpers import leave_alliance
        ok, msg = await leave_alliance(ctx.author, ctx.guild)
        await ctx.send(msg)

    # inside register_with_group for alliance_prefix.py (use same _safe_add decorator you already have)

    @_safe_add("manage")
    async def _manage(ctx):
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; alliance unavailable.")
            return
        from ..common.alliance_helpers import get_guild_config, is_alliance_manager
        if not is_alliance_manager(ctx.author, ctx.guild):
            await ctx.send("You do not have permission to manage this alliance.")
            return
        cfg = get_guild_config(ctx.guild.id)
        if not cfg:
            await ctx.send("No alliance configured for this guild.")
            return
        roles = cfg.get("roles", {})
        keys = ["alliance", "leader", "officers", "members", "bg1", "bg2", "bg3", "aqbg1", "awbg1", "managers"]
        lines = ["**Alliance management**", f"Name: {cfg.get('info', {}).get('name','Not set')}", f"Type: {cfg.get('type','Not set')}", "", "**Configured role keys:**"]
        for k in keys:
            v = roles.get(k)
            lines.append(f"{k}: {v.get('name') if isinstance(v, dict) else (v or 'not set')}")
        lines.append("")
        lines.append("**Quick actions**:")
        lines.append("`///mcoc alliance setrole <key> <@role>` — link an existing role to a key")
        lines.append("`///mcoc alliance settype <simple|complex>` — create battlegroup/leader roles (admins only)")
        lines.append("`///mcoc alliance setinfo <field> <value>` — set profile fields (leader/officer)")
        lines.append("`///mcoc alliance unregister <remove_roles>` — unregister alliance (admins only)")
        await ctx.send("\n".join(lines))

    @_safe_add("setrole")
    async def _setrole(ctx, key: str, role: Optional[commands.RoleConverter] = None):
        if role is None:
            await ctx.send("Usage: ///mcoc alliance setrole <key> <@role>")
            return
        from ..common.alliance_helpers import create_or_link_role
        mapped = await create_or_link_role(ctx.guild, role.name, key, role_obj=role)
        await ctx.send(f"Linked role `{role.name}` to key `{key}`." if mapped else "Failed to link role.")

    @_safe_add("settype")
    async def _settype(ctx, type_: str):
        from ..common.alliance_helpers import set_alliance_type
        ok = set_alliance_type(ctx.guild.id, type_, guild_obj=ctx.guild)
        await ctx.send(f"Alliance type set to `{type_}`." if ok else "Failed to set alliance type.")

    @_safe_add("setinfo")
    async def _setinfo(ctx, field: str, *, value: str = None):
        from ..common.alliance_helpers import is_leader_or_officer, set_alliance_info_field
        allowed = {"name","tag","invite","about","started","poster","wartool"}
        if field not in allowed:
            await ctx.send("Invalid field. Allowed: " + ", ".join(sorted(allowed)))
            return
        if not is_leader_or_officer(ctx.author, ctx.guild):
            await ctx.send("Only alliance leaders or officers can set alliance info.")
            return
        val = value.strip() if value else None
        if val == "":
            val = None
        ok = set_alliance_info_field(ctx.guild.id, field, val)
        await ctx.send(f"Set `{field}` to `{val}`." if ok else "Failed to update alliance info.")

    @_safe_add("addofficer")
    async def _addofficer(ctx, member: Optional[commands.MemberConverter] = None):
        from ..common.alliance_helpers import is_leader, _role_obj_for_key, add_officer_by_id
        if not is_leader(ctx.author, ctx.guild):
            await ctx.send("Only the alliance leader can add officers.")
            return
        if member is None:
            await ctx.send("Usage: ///mcoc alliance addofficer @member")
            return
        cfg = get_guild_config(ctx.guild.id)
        officers_role = _role_obj_for_key(cfg, ctx.guild, "officers") if cfg else None
        try:
            if officers_role:
                await member.add_roles(officers_role, reason="Promoted to alliance officer")
            add_officer_by_id(ctx.guild.id, member.id)
            await ctx.send(f"{member.display_name} is now an officer.")
        except Exception:
            await ctx.send("Failed to add officer. Check bot permissions and role hierarchy.")

    @_safe_add("removeofficer")
    async def _removeofficer(ctx, member: Optional[commands.MemberConverter] = None):
        from ..common.alliance_helpers import is_leader, _role_obj_for_key, remove_officer_by_id
        if not is_leader(ctx.author, ctx.guild):
            await ctx.send("Only the alliance leader can remove officers.")
            return
        if member is None:
            await ctx.send("Usage: ///mcoc alliance removeofficer @member")
            return
        cfg = get_guild_config(ctx.guild.id)
        officers_role = _role_obj_for_key(cfg, ctx.guild, "officers") if cfg else None
        try:
            if officers_role and officers_role in member.roles:
                await member.remove_roles(officers_role, reason="Demoted from alliance officer")
            remove_officer_by_id(ctx.guild.id, member.id)
            await ctx.send(f"{member.display_name} is no longer an officer.")
        except Exception:
            await ctx.send("Failed to remove officer. Check bot permissions and role hierarchy.")

    @_safe_add("promote")
    async def _promote(ctx, member: Optional[commands.MemberConverter] = None, role_key: str = "members"):
        from ..common.alliance_helpers import is_leader, role_id_for_key, set_guild_config, get_guild_config
        if not is_leader(ctx.author, ctx.guild):
            await ctx.send("Only the alliance leader can promote members.")
            return
        if member is None:
            await ctx.send("Usage: ///mcoc alliance promote @member <role_key>")
            return
        cfg = get_guild_config(ctx.guild.id)
        rid = role_id_for_key(cfg, role_key)
        role_obj = ctx.guild.get_role(rid) if rid else None
        if not role_obj:
            await ctx.send(f"No role configured or role not found for key `{role_key}`.")
            return
        try:
            await member.add_roles(role_obj, reason="Promoted via mcoc promote")
            mids = cfg.setdefault("member_ids", [])
            if member.id not in mids:
                mids.append(member.id)
                set_guild_config(ctx.guild.id, cfg)
            await ctx.send(f"Promoted {member.display_name} to `{role_key}`.")
        except Exception:
            await ctx.send("Failed to promote. Check bot permissions and role hierarchy.")

    @_safe_add("demote")
    async def _demote(ctx, member: Optional[commands.MemberConverter] = None, role_key: str = "members"):
        from ..common.alliance_helpers import is_leader, get_guild_config, set_guild_config
        if not is_leader(ctx.author, ctx.guild):
            await ctx.send("Only the alliance leader can demote members.")
            return
        if member is None:
            await ctx.send("Usage: ///mcoc alliance demote @member <role_key>")
            return
        cfg = get_guild_config(ctx.guild.id)
        target = cfg.get("roles", {}).get(role_key)
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
            if role_key == "members":
                mids = cfg.get("member_ids", [])
                if member.id in mids:
                    mids.remove(member.id)
                    cfg["member_ids"] = mids
                    set_guild_config(ctx.guild.id, cfg)
            await ctx.send(f"Demoted {member.display_name} from `{role_key}`.")
        except Exception:
            await ctx.send("Failed to demote. Check bot permissions and role hierarchy.")

    @_safe_add("listmembers")
    async def _listmembers(ctx):
        cfg = get_guild_config(ctx.guild.id)
        if not cfg:
            await ctx.send("No alliance configured for this guild.")
            return
        mids = cfg.get("member_ids", [])
        from ..common.alliance_helpers import is_leader_or_officer
        if is_leader_or_officer(ctx.author, ctx.guild):
            mentions = []
            for uid in mids:
                member = ctx.guild.get_member(uid)
                mentions.append(member.mention if member else str(uid))
            await ctx.send(f"Members ({len(mentions)}): {', '.join(mentions)}" if mentions else "No members recorded.")
        else:
            await ctx.send(f"Alliance member count: {len(mids)}")

    @_safe_add("reconcile")
    async def _reconcile(ctx, apply: bool = False):
        cfg = get_guild_config(ctx.guild.id)
        if not cfg:
            await ctx.send("No alliance configured.")
            return
        missing = []
        for key, entry in cfg.get("roles", {}).items():
            rid = entry.get("id") if isinstance(entry, dict) else None
            if rid is None or ctx.guild.get_role(rid) is None:
                missing.append(key)
        if not missing:
            await ctx.send("All configured roles exist on this server.")
            return
        if not apply:
            await ctx.send("Missing role keys: " + ", ".join(missing) + ". Run with `apply=True` to attempt fixes.")
            return
        created = []
        for k in missing:
            mapped = await create_or_link_role(ctx.guild, f"{cfg.get('info', {}).get('name','Alliance')} {k.capitalize()}", k)
            if mapped:
                created.append(k)
        await ctx.send(f"Created/linked roles: {', '.join(created) if created else 'none (check logs)'}")

    @_safe_add("unregister")
    async def _unregister(ctx, remove_roles: bool = False):
        prompt = "Are you sure you want to unregister this alliance? Reply `yes` to confirm."
        confirmed, _ = await ConfirmView.confirm(ctx.bot, ctx, prompt, timeout=20.0)
        if not confirmed:
            await ctx.send("Cancelled.")
            return
        ok = await unregister_alliance(ctx.guild, remove_roles=remove_roles)
        await ctx.send("Alliance unregistered." if ok else "Failed to unregister; check logs.")

    @_safe_add("export")
    async def _export(ctx):
        await ctx.send("Export not implemented in this build. Use the export utility when available.")


    @_safe_add("settings")
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
