# Path: mcoc/slash/contextmenu.py
"""User context-menu commands for profile, roster, and alliance workflows."""

import logging
from typing import Any, Optional

import discord
from redbot.core import app_commands, commands

from ..common.components.componentsV2 import CDTAutoCleanupView
from ..common.helpers import account as Account
from ..common.helpers import alliance as Alliance
from ..common.helpers.roster import make_roster_pager
from .account import _AccountManagerView

log = logging.getLogger("red.mcoc.slash.contextmenu")


def _core_for(bot: Any) -> Any:
    core = getattr(bot, "mcoc_core", None)
    if core is not None:
        return core
    get_cog = getattr(bot, "get_cog", None)
    if callable(get_cog):
        return get_cog("MCOC") or get_cog("MCOCPrefix") or bot
    return bot


class _AllianceManageMemberView(CDTAutoCleanupView):
    def __init__(self, core: Any, manager: discord.Member, target: discord.Member):
        super().__init__(timeout=180)
        self.core = core
        self.manager = manager
        self.target = target

        self.add_item(_AllianceMemberRoleButton("Set Member", "members"))
        self.add_item(_AllianceMemberRoleButton("Set Officer", "officers"))
        self.add_item(_AllianceMemberRoleButton("Set Leader", "leader"))

        guild = getattr(manager, "guild", None)
        cfg = Alliance.get_guild_config(guild.id) if guild is not None else {}
        type_norm = Alliance.normalize_alliance_type((cfg or {}).get("type", "simple"))
        if type_norm == Alliance.ALLIANCE_TYPE_ADVANCED:
            for label, key in (
                ("Set AQBG1", "aqbg1"),
                ("Set AQBG2", "aqbg2"),
                ("Set AQBG3", "aqbg3"),
                ("Set AWBG1", "awbg1"),
                ("Set AWBG2", "awbg2"),
                ("Set AWBG3", "awbg3"),
            ):
                self.add_item(_AllianceMemberRoleButton(label, key))
        else:
            for label, key in (("Set BG1", "bg1"), ("Set BG2", "bg2"), ("Set BG3", "bg3")):
                self.add_item(_AllianceMemberRoleButton(label, key))

        self.add_item(_AllianceMemberRoleButton("Set Manager", "managers"))
        self.add_item(_AllianceMemberRoleButton("Remove", "remove"))

    async def apply_action(self, interaction: discord.Interaction, action: str):
        guild = getattr(interaction, "guild", None)
        if guild is None:
            await interaction.response.send_message("This action can only be used in a server.", ephemeral=True)
            return
        if not Alliance.is_alliance_manager(interaction.user, guild):
            await interaction.response.send_message("You do not have alliance management permissions.", ephemeral=True)
            return

        if action == "remove":
            ok, message = await Alliance.leave_alliance(self.target, guild)
            Alliance.remove_officer_by_id(guild.id, self.target.id)
            await interaction.response.edit_message(content=message if ok else message, view=self)
            return

        if action == "members":
            ok, message = await Alliance.join_alliance(self.target, guild, role_key="members")
            if ok:
                Alliance.remove_officer_by_id(guild.id, self.target.id)
            await interaction.response.edit_message(content=message, view=self)
            return

        cfg = Alliance.get_guild_config(guild.id)
        if not cfg:
            await interaction.response.send_message("No alliance is configured for this guild.", ephemeral=True)
            return

        assignment_keys = {
            "members",
            "officers",
            "leader",
            "bg1",
            "bg2",
            "bg3",
            "aqbg1",
            "aqbg2",
            "aqbg3",
            "awbg1",
            "awbg2",
            "awbg3",
            "managers",
        }
        if action not in assignment_keys:
            await interaction.response.send_message("Unknown alliance assignment action.", ephemeral=True)
            return

        if action != "managers":
            ok, message = await Alliance.join_alliance(self.target, guild, role_key="members")
            if not ok:
                await interaction.response.edit_message(content=message, view=self)
                return

        cleanup_keys = {"leader", "officers", "bg1", "bg2", "bg3", "aqbg1", "aqbg2", "aqbg3", "awbg1", "awbg2", "awbg3", "managers"}
        for key in cleanup_keys:
            if key == action:
                continue
            role_cfg = (cfg.get("roles") or {}).get(key)
            if not isinstance(role_cfg, dict):
                continue
            role_obj = guild.get_role(role_cfg.get("id"))
            if role_obj and role_obj in self.target.roles:
                try:
                    await self.target.remove_roles(role_obj, reason=f"Alliance context manage: clear {key}")
                except Exception:
                    log.exception("Failed to remove alliance role %s from user %s", key, self.target.id)

        if action in cleanup_keys:
            role_cfg = (cfg.get("roles") or {}).get(action)
            if not isinstance(role_cfg, dict):
                await interaction.response.edit_message(content=f"Alliance role key `{action}` is not configured.", view=self)
                return
            role_obj = guild.get_role(role_cfg.get("id"))
            if role_obj is None:
                await interaction.response.edit_message(content=f"Role for `{action}` is missing on this server.", view=self)
                return
            if action in {"bg1", "bg2", "bg3", "aqbg1", "aqbg2", "aqbg3", "awbg1", "awbg2", "awbg3"}:
                if self.target not in role_obj.members and len(role_obj.members) >= 10:
                    await interaction.response.edit_message(content=f"Role `{action}` is full (10/10).", view=self)
                    return
            if role_obj not in self.target.roles:
                try:
                    await self.target.add_roles(role_obj, reason=f"Alliance context manage: {action}")
                except Exception:
                    log.exception("Failed to add alliance managed role %s to user %s", action, self.target.id)
                    await interaction.response.edit_message(content=f"Failed to assign `{action}` to {self.target.mention}.", view=self)
                    return

        if action in {"officers", "leader"}:
            Alliance.add_officer_by_id(guild.id, self.target.id)
        else:
            Alliance.remove_officer_by_id(guild.id, self.target.id)

        await interaction.response.edit_message(content=f"Updated {self.target.mention} role to `{action}`.", view=self)


class _AllianceMemberRoleButton(discord.ui.Button):
    def __init__(self, label: str, action: str):
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.action = action

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if isinstance(view, _AllianceManageMemberView):
            await view.apply_action(interaction, self.action)
            return
        await interaction.response.send_message("This action is no longer available.", ephemeral=True)


class ContextMenuSlashCog(commands.Cog):
    def __init__(self, bot: Any):
        self.bot = bot
        self.core = _core_for(bot)
        self._registered_menus: list[app_commands.ContextMenu] = []

    async def _send_profile(self, interaction: discord.Interaction, target: discord.User):
        try:
            await interaction.response.defer(ephemeral=False)
        except Exception:
            pass

        emb, text = Account.build_profile_display(
            self.core,
            interaction,
            getattr(target, "id", None),
            viewer_id=getattr(interaction.user, "id", None),
            prefer_embed=True,
        )

        if emb is not None:
            await interaction.followup.send(embed=emb, ephemeral=False)
            return
        await interaction.followup.send(text or "No profile found for that user.", ephemeral=True)

    async def _send_roster(self, interaction: discord.Interaction, target: discord.User):
        try:
            await interaction.response.defer(ephemeral=False)
        except Exception:
            pass

        pager = await make_roster_pager(self.core, target, raw_input="", parsed_filters={}, author_for_controls=interaction.user)
        if not pager or not getattr(pager, "pages", None):
            await interaction.followup.send("No roster entries found for that user.", ephemeral=True)
            return

        msg = await interaction.followup.send(embed=pager.pages[0], view=pager, wait=True)
        try:
            pager.message = msg
        except Exception:
            pass

    async def _ctx_profile(self, interaction: discord.Interaction, user: discord.Member):
        await self._send_profile(interaction, user)

    async def _ctx_profile_settings(self, interaction: discord.Interaction, user: discord.Member):
        if user.id != getattr(interaction.user, "id", None):
            await interaction.response.send_message("You can only edit your own profile settings from this menu.", ephemeral=True)
            return

        view = _AccountManagerView(self.core, user.id)
        await interaction.response.send_message(
            "Manage your CollectorVerse account settings and privacy.",
            view=view,
            ephemeral=True,
        )
        await view.bind_to_interaction_response(interaction)

    async def _ctx_roster(self, interaction: discord.Interaction, user: discord.Member):
        await self._send_roster(interaction, user)

    async def _ctx_roster_add(self, interaction: discord.Interaction, user: discord.Member):
        if user.id != getattr(interaction.user, "id", None):
            await interaction.response.send_message("Roster add workflow is only available from your own user context menu.", ephemeral=True)
            return

        roster_cog = self.bot.get_cog("RosterSlashCog")
        group = getattr(roster_cog, "group", None) if roster_cog else None
        if group is None or not hasattr(group, "_start_operation_picker"):
            await interaction.response.send_message("Roster workflow is not available right now.", ephemeral=True)
            return

        started = await group._start_operation_picker(interaction, "add")
        if not started:
            await interaction.response.send_message("Unable to open the roster add workflow right now.", ephemeral=True)

    async def _ctx_roster_remove(self, interaction: discord.Interaction, user: discord.Member):
        if user.id != getattr(interaction.user, "id", None):
            await interaction.response.send_message("Roster remove workflow is only available from your own user context menu.", ephemeral=True)
            return

        roster_cog = self.bot.get_cog("RosterSlashCog")
        group = getattr(roster_cog, "group", None) if roster_cog else None
        if group is None or not hasattr(group, "_start_remove_picker"):
            await interaction.response.send_message("Roster workflow is not available right now.", ephemeral=True)
            return

        started = await group._start_remove_picker(interaction)
        if not started:
            await interaction.response.send_message("Unable to open the roster remove workflow right now.", ephemeral=True)

    async def _ctx_alliance_invite(self, interaction: discord.Interaction, user: discord.Member):
        guild = getattr(interaction, "guild", None)
        if guild is None:
            await interaction.response.send_message("This action can only be used in a server.", ephemeral=True)
            return
        if user.id == getattr(interaction.user, "id", None):
            await interaction.response.send_message("Use `/alliance join` to join your alliance.", ephemeral=True)
            return

        cfg = Alliance.get_guild_config(guild.id)
        if not cfg:
            await interaction.response.send_message("No alliance is configured for this guild.", ephemeral=True)
            return
        if getattr(interaction.user, "id", None) not in (cfg.get("member_ids") or []) and not Alliance.is_alliance_manager(interaction.user, guild):
            await interaction.response.send_message("You must be part of this alliance to invite other users.", ephemeral=True)
            return

        ok, message = await Alliance.join_alliance(user, guild, role_key="members")
        if ok:
            await interaction.response.send_message(f"Invited {user.mention} to the alliance.", ephemeral=True)
            return
        await interaction.response.send_message(message, ephemeral=True)

    async def _ctx_alliance_manage(self, interaction: discord.Interaction, user: discord.Member):
        guild = getattr(interaction, "guild", None)
        if guild is None:
            await interaction.response.send_message("This action can only be used in a server.", ephemeral=True)
            return
        if user.bot:
            await interaction.response.send_message("Alliance management is only available for human members.", ephemeral=True)
            return
        if not Alliance.is_alliance_manager(interaction.user, guild):
            await interaction.response.send_message("You do not have alliance management permissions.", ephemeral=True)
            return

        cfg = Alliance.get_guild_config(guild.id)
        if not cfg:
            await interaction.response.send_message("No alliance is configured for this guild.", ephemeral=True)
            return

        view = _AllianceManageMemberView(self.core, interaction.user, user)
        await interaction.response.send_message(
            f"Alliance manage for {user.mention}. Choose an action:",
            view=view,
            ephemeral=True,
        )
        await view.bind_to_interaction_response(interaction)

    async def cog_load(self):
        menus = [
            app_commands.ContextMenu(name="CollectorVerse Profile", callback=self._ctx_profile),
            app_commands.ContextMenu(name="Profile Settings", callback=self._ctx_profile_settings),
            app_commands.ContextMenu(name="CollectorVerse Roster", callback=self._ctx_roster),
            app_commands.ContextMenu(name="Roster Add", callback=self._ctx_roster_add),
            app_commands.ContextMenu(name="Roster Remove", callback=self._ctx_roster_remove),
            app_commands.ContextMenu(name="Alliance Invite", callback=self._ctx_alliance_invite),
            app_commands.ContextMenu(name="Alliance Manage", callback=self._ctx_alliance_manage),
        ]

        for menu in menus:
            try:
                self.bot.tree.remove_command(menu.name, type=menu.type)
            except Exception:
                pass
            try:
                self.bot.tree.add_command(menu, override=True)
                self._registered_menus.append(menu)
            except Exception:
                log.exception("Failed to register context menu: %s", menu.name)

    async def cog_unload(self):
        for menu in self._registered_menus:
            try:
                self.bot.tree.remove_command(menu.name, type=menu.type)
            except Exception:
                pass
        self._registered_menus = []


async def setup(bot):
    try:
        await bot.add_cog(ContextMenuSlashCog(bot))
    except Exception:
        log.exception("Failed to add ContextMenuSlashCog")
