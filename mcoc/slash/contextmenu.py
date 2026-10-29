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
from . import account as AccountSlash
from . import alliance as AllianceSlash
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


async def _edit_or_send(
    interaction: discord.Interaction,
    *,
    content: Optional[str] = None,
    embed: Optional[discord.Embed] = None,
    view: Optional[discord.ui.View] = None,
    ephemeral: bool = True,
) -> None:
    response = getattr(interaction, "response", None)
    if getattr(interaction, "message", None) is not None and response and hasattr(response, "edit_message"):
        try:
            await response.edit_message(content=content, embed=embed, view=view)
            return
        except Exception:
            pass
    if response and hasattr(response, "send_message"):
        await response.send_message(content=content, embed=embed, view=view, ephemeral=ephemeral)


class _MCOCAuthorLockedView(CDTAutoCleanupView):
    """Context-menu views restricted to the invoking user."""

    def __init__(self, actor_id: int, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor_id = actor_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        allowed = await super().interaction_check(interaction)
        if not allowed:
            return False
        if getattr(interaction.user, "id", None) == self.actor_id:
            return True
        await _edit_or_send(interaction, content="Only the message author can use these buttons.", ephemeral=True)
        return False


class _AllianceManageMemberView(_MCOCAuthorLockedView):
    def __init__(self, core: Any, manager: discord.Member, target: discord.Member):
        super().__init__(getattr(manager, "id", 0), timeout=180)
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
            await _edit_or_send(interaction, content="This action can only be used in a server.", view=self)
            return
        if not Alliance.is_alliance_manager(interaction.user, guild):
            await _edit_or_send(interaction, content="You do not have alliance management permissions.", view=self)
            return

        if action == "remove":
            ok, message = await Alliance.leave_alliance(self.target, guild)
            Alliance.remove_officer_by_id(guild.id, self.target.id)
            await _edit_or_send(interaction, content=message if ok else message, view=self)
            return

        if action == "members":
            ok, message = await Alliance.join_alliance(self.target, guild, role_key="members")
            if ok:
                Alliance.remove_officer_by_id(guild.id, self.target.id)
            await _edit_or_send(interaction, content=message, view=self)
            return

        cfg = Alliance.get_guild_config(guild.id)
        if not cfg:
            await _edit_or_send(interaction, content="No alliance is configured for this guild.", view=self)
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
            await _edit_or_send(interaction, content="Unknown alliance assignment action.", view=self)
            return

        if action != "managers":
            ok, message = await Alliance.join_alliance(self.target, guild, role_key="members")
            if not ok:
                await _edit_or_send(interaction, content=message, view=self)
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
                await _edit_or_send(interaction, content=f"Alliance role key `{action}` is not configured.", view=self)
                return
            role_obj = guild.get_role(role_cfg.get("id"))
            if role_obj is None:
                await _edit_or_send(interaction, content=f"Role for `{action}` is missing on this server.", view=self)
                return
            if action in {"bg1", "bg2", "bg3", "aqbg1", "aqbg2", "aqbg3", "awbg1", "awbg2", "awbg3"}:
                if self.target not in role_obj.members and len(role_obj.members) >= 10:
                    await _edit_or_send(interaction, content=f"Role `{action}` is full (10/10).", view=self)
                    return
            if role_obj not in self.target.roles:
                try:
                    await self.target.add_roles(role_obj, reason=f"Alliance context manage: {action}")
                except Exception:
                    log.exception("Failed to add alliance managed role %s to user %s", action, self.target.id)
                    await _edit_or_send(interaction, content=f"Failed to assign `{action}` to {self.target.mention}.", view=self)
                    return

        if action in {"officers", "leader"}:
            Alliance.add_officer_by_id(guild.id, self.target.id)
        else:
            Alliance.remove_officer_by_id(guild.id, self.target.id)

        await _edit_or_send(interaction, content=f"Updated {self.target.mention} role to `{action}`.", view=self)


class _AllianceMemberRoleButton(discord.ui.Button):
    def __init__(self, label: str, action: str):
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.action = action

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if isinstance(view, _AllianceManageMemberView):
            await view.apply_action(interaction, self.action)
            return
        await _edit_or_send(interaction, content="This action is no longer available.")


class _MCOCActionButton(discord.ui.Button):
    def __init__(self, label: str, action: str, *, style: discord.ButtonStyle = discord.ButtonStyle.secondary):
        super().__init__(label=label, style=style)
        self.action = action

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if isinstance(view, _MCOCMainView):
            await view.navigate(interaction, self.action)
            return
        if isinstance(view, _MCOCUserSectionView):
            await view.handle(interaction, self.action)
            return
        if isinstance(view, _MCOCRosterSectionView):
            await view.handle(interaction, self.action)
            return
        if isinstance(view, _MCOCAllianceSectionView):
            await view.handle(interaction, self.action)
            return
        if isinstance(view, _MCOCAccountSettingsView):
            await view.handle(interaction, self.action)
            return
        await _edit_or_send(interaction, content="This action is no longer available.")


class _MCOCBackButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="BACK", style=discord.ButtonStyle.secondary, row=4)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if isinstance(view, _MCOCSectionViewBase):
            await view.go_back(interaction)
            return
        await _edit_or_send(interaction, content="This action is no longer available.")


class _MCOCSectionViewBase(_MCOCAuthorLockedView):
    def __init__(self, cog: "ContextMenuSlashCog", actor: discord.Member, target: discord.Member, *, timeout: float = 180):
        super().__init__(getattr(actor, "id", 0), timeout=timeout)
        self.cog = cog
        self.actor = actor
        self.target = target

    async def go_back(self, interaction: discord.Interaction):
        main = _MCOCMainView(self.cog, self.actor, self.target)
        await _edit_or_send(interaction, content=f"MCOC > {self.target.mention}", view=main, ephemeral=True)
        await main.bind_to_interaction_response(interaction)


class _ViewBackButton(discord.ui.Button):
    def __init__(self, callback):
        super().__init__(label="BACK", style=discord.ButtonStyle.secondary, row=4)
        self._callback = callback

    async def callback(self, interaction: discord.Interaction):
        await self._callback(interaction)


class _CollectorVerseUserActionView(CDTAutoCleanupView):
    """Compatibility wrapper kept for legacy tests and older menu entry points."""

    def __init__(self, cog: "ContextMenuSlashCog", actor: discord.Member, target: discord.Member):
        super().__init__(timeout=180)
        self.cog = cog
        self.actor = actor
        self.target = target

    @discord.ui.button(label="Profile", style=discord.ButtonStyle.primary, row=0)
    async def profile(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self.cog._send_profile(interaction, self.target)

    @discord.ui.button(label="Roster", style=discord.ButtonStyle.primary, row=0)
    async def roster(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self.cog._send_roster(interaction, self.target)

    @discord.ui.button(label="Profile Settings", style=discord.ButtonStyle.secondary, row=0)
    async def profile_settings(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self.cog._ctx_profile_settings(interaction, self.target, edit_existing=True)

    @discord.ui.button(label="Roster Add", style=discord.ButtonStyle.secondary, row=1)
    async def roster_add(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self.cog._ctx_roster_add(interaction, self.target, edit_existing=True)

    @discord.ui.button(label="Roster Remove", style=discord.ButtonStyle.secondary, row=1)
    async def roster_remove(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self.cog._ctx_roster_remove(interaction, self.target, edit_existing=True)

    @discord.ui.button(label="Alliance Invite", style=discord.ButtonStyle.success, row=1)
    async def alliance_invite(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self.cog._ctx_alliance_invite(interaction, self.target, edit_existing=True)

    @discord.ui.button(label="Alliance Manage", style=discord.ButtonStyle.success, row=1)
    async def alliance_manage(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self.cog._ctx_alliance_manage(interaction, self.target, edit_existing=True)


class _MCOCMainView(_MCOCAuthorLockedView):
    def __init__(self, cog: "ContextMenuSlashCog", actor: discord.Member, target: discord.Member):
        super().__init__(getattr(actor, "id", 0), timeout=180)
        self.cog = cog
        self.actor = actor
        self.target = target
        self.add_item(_MCOCActionButton("USER", "user", style=discord.ButtonStyle.secondary))
        self.add_item(_MCOCActionButton("ROSTER", "roster", style=discord.ButtonStyle.green))
        self.add_item(_MCOCActionButton("ALLIANCE", "alliance", style=discord.ButtonStyle.primary))

    async def navigate(self, interaction: discord.Interaction, action: str):
        if action == "user":
            view = _MCOCUserSectionView(self.cog, self.actor, self.target)
            await _edit_or_send(interaction, content=f"MCOC > USER for {self.target.mention}", view=view, ephemeral=True)
            await view.bind_to_interaction_response(interaction)
            return
        if action == "roster":
            view = _MCOCRosterSectionView(self.cog, self.actor, self.target)
            await _edit_or_send(interaction, content=f"MCOC > ROSTER for {self.target.mention}", view=view, ephemeral=True)
            await view.bind_to_interaction_response(interaction)
            return
        if action == "alliance":
            view = _MCOCAllianceSectionView(self.cog, self.actor, self.target)
            await _edit_or_send(interaction, content=view.build_intro_text(), view=view, ephemeral=True)
            await view.bind_to_interaction_response(interaction)
            return


class _MCOCUserSectionView(_MCOCSectionViewBase):
    def __init__(self, cog: "ContextMenuSlashCog", actor: discord.Member, target: discord.Member):
        super().__init__(cog, actor, target, timeout=180)
        self.add_item(_MCOCActionButton("SETTINGS", "settings", style=discord.ButtonStyle.secondary))
        self.add_item(_MCOCBackButton())

    async def handle(self, interaction: discord.Interaction, action: str):
        if action == "settings":
            await self.cog._ctx_profile_settings(interaction, self.target, edit_existing=True)
            return


class _MCOCRosterSectionView(_MCOCSectionViewBase):
    def __init__(self, cog: "ContextMenuSlashCog", actor: discord.Member, target: discord.Member):
        super().__init__(cog, actor, target, timeout=180)
        self.add_item(_MCOCActionButton("ADD", "add", style=discord.ButtonStyle.green))
        self.add_item(_MCOCActionButton("REMOVE", "remove", style=discord.ButtonStyle.red))
        self.add_item(_MCOCActionButton("SETTINGS", "settings", style=discord.ButtonStyle.secondary))
        self.add_item(_MCOCActionButton("LIST", "list", style=discord.ButtonStyle.primary))
        self.add_item(_MCOCBackButton())

    async def handle(self, interaction: discord.Interaction, action: str):
        if action == "add":
            await self.cog._ctx_roster_add(interaction, self.target, edit_existing=True)
            return
        if action == "remove":
            await self.cog._ctx_roster_remove(interaction, self.target, edit_existing=True)
            return
        if action == "settings":
            if self.target.id != getattr(interaction.user, "id", None):
                await _edit_or_send(interaction, content="Roster settings are only available for your own roster.")
                return
            await self.cog._ctx_roster_edit_settings(interaction, self.target)
            return
        if action == "list":
            await self.cog._send_roster(interaction, self.target)
            return


class _MCOCAllianceSectionView(_MCOCSectionViewBase):
    def __init__(self, cog: "ContextMenuSlashCog", actor: discord.Member, target: discord.Member):
        super().__init__(cog, actor, target, timeout=180)

        self.guild = getattr(actor, "guild", None)
        self.cfg = Alliance.get_guild_config(self.guild.id) if self.guild is not None else None
        self.user_has_alliance = bool(
            self.guild is not None
            and self.cfg
            and AllianceSlash._is_alliance_member(actor, self.guild, self.cfg)
        )
        self.is_manager = bool(self.guild is not None and Alliance.is_alliance_manager(actor, self.guild))

        self.clear_items()
        if self.user_has_alliance:
            self.add_item(_MCOCActionButton("PROFILE", "profile", style=discord.ButtonStyle.primary))
        if self.user_has_alliance and self.is_manager:
            self.add_item(_MCOCActionButton("REPORTS", "reports", style=discord.ButtonStyle.primary))
            self.add_item(_MCOCActionButton("SETTINGS", "settings", style=discord.ButtonStyle.secondary))
            self.add_item(_MCOCActionButton("ASSIGN ROLE", "assign", style=discord.ButtonStyle.secondary))
        self.add_item(_MCOCBackButton())

    def build_intro_text(self) -> str:
        if self.guild is None:
            return f"MCOC > ALLIANCE for {self.target.mention}"
        if not self.cfg:
            return (
                f"MCOC > ALLIANCE for {self.target.mention}\n"
                "No alliance is configured for this server."
            )
        if not self.user_has_alliance:
            return (
                f"MCOC > ALLIANCE for {self.target.mention}\n"
                "You are not a member of this server's alliance."
            )
        return f"MCOC > ALLIANCE for {self.target.mention}"

    async def handle(self, interaction: discord.Interaction, action: str):
        if action == "reports":
            guild = getattr(interaction, "guild", None)
            if guild is None:
                await _edit_or_send(interaction, content="This action can only be used in a server.")
                return
            cfg = Alliance.get_guild_config(guild.id)
            if not cfg:
                await _edit_or_send(interaction, content="No alliance is configured for this guild.")
                return
            if not AllianceSlash._is_alliance_member(interaction.user, guild, cfg) or not Alliance.is_alliance_manager(interaction.user, guild):
                await _edit_or_send(interaction, content="You do not have alliance management permissions.")
                return
            await self.cog._ctx_alliance_reports_workflow(interaction)
            return
        if action == "settings":
            guild = getattr(interaction, "guild", None)
            if guild is None:
                await _edit_or_send(interaction, content="This action can only be used in a server.")
                return
            cfg = Alliance.get_guild_config(guild.id)
            if not cfg:
                await _edit_or_send(interaction, content="No alliance is configured for this guild.")
                return
            if not AllianceSlash._is_alliance_member(interaction.user, guild, cfg) or not Alliance.is_alliance_manager(interaction.user, guild):
                await _edit_or_send(interaction, content="You do not have alliance management permissions.")
                return
            await self.cog._ctx_alliance_settings_manage_workflow(interaction)
            return
        if action == "assign":
            guild = getattr(interaction, "guild", None)
            if guild is None:
                await _edit_or_send(interaction, content="This action can only be used in a server.")
                return
            cfg = Alliance.get_guild_config(guild.id)
            if not cfg:
                await _edit_or_send(interaction, content="No alliance is configured for this guild.")
                return
            if not AllianceSlash._is_alliance_member(interaction.user, guild, cfg) or not Alliance.is_alliance_manager(interaction.user, guild):
                await _edit_or_send(interaction, content="You do not have alliance management permissions.")
                return
            await self.cog._ctx_alliance_manage(interaction, self.target, edit_existing=True)
            return
        if action == "profile":
            guild = getattr(interaction, "guild", None)
            if guild is None:
                await _edit_or_send(interaction, content="This action can only be used in a server.")
                return
            cfg = Alliance.get_guild_config(guild.id)
            if not cfg:
                await _edit_or_send(interaction, content="No alliance is configured for this guild.")
                return
            if not AllianceSlash._is_alliance_member(interaction.user, guild, cfg):
                await _edit_or_send(interaction, content="You are not a member of this server's alliance.")
                return
            await self.cog._send_alliance_profile(interaction, self.actor, self.target)
            return


class _MCOCAccountSettingsView(_MCOCSectionViewBase):
    def __init__(self, cog: "ContextMenuSlashCog", actor: discord.Member, target: discord.Member):
        super().__init__(cog, actor, target, timeout=180)
        self.add_item(_MCOCActionButton("VIEW", "view", style=discord.ButtonStyle.primary))
        self.add_item(_MCOCActionButton("EDIT", "edit", style=discord.ButtonStyle.primary))
        self.add_item(_MCOCActionButton("PRIVACY", "privacy", style=discord.ButtonStyle.secondary))
        self.add_item(_MCOCBackButton())

    async def _go_to_user_settings_root(self, interaction: discord.Interaction):
        view = _MCOCAccountSettingsView(self.cog, self.actor, self.target)
        await _edit_or_send(
            interaction,
            content="MCOC > USER > Manage your CollectorVerse account settings and privacy.",
            view=view,
            ephemeral=True,
        )
        await view.bind_to_interaction_response(interaction)

    def _attach_back_and_author_guard(self, view: CDTAutoCleanupView):
        actor_id = getattr(self.actor, "id", 0)

        original_check = getattr(view, "interaction_check", None)

        async def _guard(interaction: discord.Interaction):
            if callable(original_check):
                ok = await original_check(interaction)
                if not ok:
                    return False
            if getattr(interaction.user, "id", None) != actor_id:
                await _edit_or_send(interaction, content="Only the message author can use these buttons.", ephemeral=True)
                return False
            return True

        view.interaction_check = _guard  # type: ignore[attr-defined]
        view.add_item(_ViewBackButton(self._go_to_user_settings_root))

    async def handle(self, interaction: discord.Interaction, action: str):
        if action == "view":
            profile = Account.get_profile(self.cog.core, self.target.id) or {}
            view = AccountSlash._ProfilePageSelectorView(
                self.cog.core,
                self.target.id,
                profile,
                mode="view",
                member=interaction.user,
            )
            self._attach_back_and_author_guard(view)
            await _edit_or_send(interaction, content="MCOC > USER > VIEW > Choose the profile page you want to view.", view=view, ephemeral=True)
            await view.bind_to_interaction_response(interaction)
            return
        if action == "edit":
            profile = Account.get_profile(self.cog.core, self.target.id) or {}
            view = AccountSlash._ProfilePageSelectorView(
                self.cog.core,
                self.target.id,
                profile,
                mode="edit",
                member=interaction.user,
            )
            self._attach_back_and_author_guard(view)
            await _edit_or_send(interaction, content="MCOC > USER > EDIT > Choose the section to edit.", view=view, ephemeral=True)
            await view.bind_to_interaction_response(interaction)
            return
        if action == "privacy":
            profile = Account.get_profile(self.cog.core, self.target.id) or {}
            current = profile.get("privacy_mode") or "public"
            view = AccountSlash._AccountPrivacyView(self.cog.core, self.target.id)
            self._attach_back_and_author_guard(view)
            await _edit_or_send(
                interaction,
                content=f"MCOC > USER > PRIVACY > Current privacy mode: {current}\nChoose your visibility below.",
                view=view,
                ephemeral=True,
            )
            await view.bind_to_interaction_response(interaction)
            return


class ContextMenuSlashCog(commands.Cog):
    def __init__(self, bot: Any):
        self.bot = bot
        self.core = _core_for(bot)
        self._registered_menus: list[app_commands.ContextMenu] = []

    async def _send_profile(self, interaction: discord.Interaction, target: discord.User):
        emb, text = Account.build_profile_display(
            self.core,
            interaction,
            getattr(target, "id", None),
            viewer_id=getattr(interaction.user, "id", None),
            prefer_embed=True,
        )

        if emb is not None:
            await _edit_or_send(interaction, content=None, embed=emb, ephemeral=False)
            return
        await _edit_or_send(interaction, content=text or "No profile found for that user.", ephemeral=True)

    async def _send_roster(self, interaction: discord.Interaction, target: discord.User):
        pager = await make_roster_pager(self.core, target, raw_input="", parsed_filters={}, author_for_controls=interaction.user)
        if not pager or not getattr(pager, "pages", None):
            await _edit_or_send(interaction, content="No roster entries found for that user.", ephemeral=True)
            return

        await _edit_or_send(interaction, content=None, embed=pager.pages[0], view=pager, ephemeral=False)
        try:
            pager.message = getattr(interaction, "message", None) or await interaction.original_response()
        except Exception:
            pass

    async def _send_alliance_profile(self, interaction: discord.Interaction, actor: discord.Member, target: discord.Member):
        guild = getattr(interaction, "guild", None)
        if guild is None:
            await _edit_or_send(interaction, content="This action can only be used in a server.", ephemeral=True)
            return

        cfg = Alliance.get_guild_config(guild.id)
        if not cfg:
            await _edit_or_send(interaction, content="No alliance is configured for this guild.", ephemeral=True)
            return

        info = cfg.get("info", {}) or {}
        alliance_name = str(info.get("name") or guild.name)
        tag = str(info.get("tag") or "").strip()
        description = str(info.get("description") or "").strip() or "No alliance description configured."
        invite_url = str(info.get("invite") or "").strip()
        founded = str(info.get("founded") or "").strip() or "Unknown"

        title = alliance_name
        if tag:
            title = f"{alliance_name} [{tag}]"

        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.blurple(),
            url=invite_url or None,
        )
        embed.add_field(name="Alliance Founded", value=founded, inline=True)
        embed.add_field(name="Server", value=guild.name, inline=True)
        if invite_url:
            embed.add_field(name="Discord Invite", value=invite_url, inline=False)

        view = _MCOCAllianceSectionView(self, actor, target)
        if invite_url:
            view.add_item(discord.ui.Button(label="JOIN NOW", style=discord.ButtonStyle.link, url=invite_url, row=3))

        await _edit_or_send(interaction, content="MCOC > ALLIANCE > PROFILE", embed=embed, view=view, ephemeral=True)
        await view.bind_to_interaction_response(interaction)

    async def _ctx_profile(self, interaction: discord.Interaction, user: discord.Member):
        await self._send_profile(interaction, user)

    async def _ctx_profile_settings(self, interaction: discord.Interaction, user: discord.Member, *, edit_existing: bool = False):
        if user.id != getattr(interaction.user, "id", None):
            await _edit_or_send(interaction, content="You can only edit your own profile settings from this menu.")
            return

        view = _MCOCAccountSettingsView(self, interaction.user, user)
        await _edit_or_send(
            interaction,
            content=f"MCOC > USER > Manage your CollectorVerse account settings and privacy.",
            view=view,
            ephemeral=True,
        )
        await view.bind_to_interaction_response(interaction)

    async def _ctx_roster(self, interaction: discord.Interaction, user: discord.Member):
        if user.id == getattr(interaction.user, "id", None):
            view = _CollectorVerseUserActionView(self, interaction.user, user)
            await _edit_or_send(interaction, content="CollectorVerse roster actions for you.", view=view, ephemeral=True)
            await view.bind_to_interaction_response(interaction)
            return

        await self._send_roster(interaction, user)

    async def _ctx_roster_add(self, interaction: discord.Interaction, user: discord.Member, *, edit_existing: bool = False):
        if user.id != getattr(interaction.user, "id", None):
            await _edit_or_send(interaction, content="Roster add workflow is only available from your own user context menu.")
            return

        roster_cog = self.bot.get_cog("RosterSlashCog")
        group = getattr(roster_cog, "group", None) if roster_cog else None
        if group is None or not hasattr(group, "_start_operation_picker"):
            await _edit_or_send(interaction, content="Roster workflow is not available right now.")
            return

        started = await group._start_operation_picker(interaction, "add")
        if not started:
            await _edit_or_send(interaction, content="Unable to open the roster add workflow right now.")

    async def _ctx_roster_remove(self, interaction: discord.Interaction, user: discord.Member, *, edit_existing: bool = False):
        if user.id != getattr(interaction.user, "id", None):
            await _edit_or_send(interaction, content="Roster remove workflow is only available from your own user context menu.")
            return

        roster_cog = self.bot.get_cog("RosterSlashCog")
        group = getattr(roster_cog, "group", None) if roster_cog else None
        if group is None or not hasattr(group, "_start_remove_picker"):
            await _edit_or_send(interaction, content="Roster workflow is not available right now.")
            return

        started = await group._start_remove_picker(interaction)
        if not started:
            await _edit_or_send(interaction, content="Unable to open the roster remove workflow right now.")

    async def _ctx_alliance_invite(self, interaction: discord.Interaction, user: discord.Member, *, edit_existing: bool = False):
        guild = getattr(interaction, "guild", None)
        if guild is None:
            await _edit_or_send(interaction, content="This action can only be used in a server.")
            return
        if user.id == getattr(interaction.user, "id", None):
            await _edit_or_send(interaction, content="Use `/alliance join` to join your alliance.")
            return

        cfg = Alliance.get_guild_config(guild.id)
        if not cfg:
            await _edit_or_send(interaction, content="No alliance is configured for this guild.")
            return
        if getattr(interaction.user, "id", None) not in (cfg.get("member_ids") or []) and not Alliance.is_alliance_manager(interaction.user, guild):
            await _edit_or_send(interaction, content="You must be part of this alliance to invite other users.")
            return

        ok, message = await Alliance.join_alliance(user, guild, role_key="members")
        if ok:
            await _edit_or_send(interaction, content=f"Invited {user.mention} to the alliance.")
            return
        await _edit_or_send(interaction, content=message)

    async def _ctx_alliance_manage(self, interaction: discord.Interaction, user: discord.Member, *, edit_existing: bool = False):
        guild = getattr(interaction, "guild", None)
        if guild is None:
            await _edit_or_send(interaction, content="This action can only be used in a server.")
            return
        if user.bot:
            await _edit_or_send(interaction, content="Alliance management is only available for human members.")
            return
        if not Alliance.is_alliance_manager(interaction.user, guild):
            await _edit_or_send(interaction, content="You do not have alliance management permissions.")
            return

        cfg = Alliance.get_guild_config(guild.id)
        if not cfg:
            await _edit_or_send(interaction, content="No alliance is configured for this guild.")
            return

        view = _AllianceManageMemberView(self.core, interaction.user, user)
        await _edit_or_send(interaction, content=f"Alliance manage for {user.mention}. Choose an action:", view=view)
        await view.bind_to_interaction_response(interaction)

    async def _ctx_alliance(self, interaction: discord.Interaction, user: discord.Member):
        view = _MCOCMainView(self, interaction.user, user)
        await _edit_or_send(interaction, content=f"MCOC > {user.mention}", view=view, ephemeral=True)
        await view.bind_to_interaction_response(interaction)

    async def _send_alliance_reports(self, interaction: discord.Interaction, guild: discord.Guild):
        cfg = Alliance.get_guild_config(guild.id)
        if not cfg:
            await _edit_or_send(interaction, content="No alliance is configured for this guild.")
            return
        if not Alliance.is_alliance_manager(interaction.user, guild):
            await _edit_or_send(interaction, content="You do not have alliance management permissions.")
            return
        await self._ctx_alliance_reports_workflow(interaction)

    async def _ctx_alliance_reports_workflow(self, interaction: discord.Interaction):
        guild = getattr(interaction, "guild", None)
        if guild is None:
            await _edit_or_send(interaction, content="This action can only be used in a server.")
            return
        alliance_cog = self.bot.get_cog("AllianceSlashCog")
        if alliance_cog is None:
            await _edit_or_send(interaction, content="Alliance workflow is not available right now.")
            return
        view = AllianceSlash._AllianceReportsView(alliance_cog)
        await _edit_or_send(interaction, content=f"MCOC > ALLIANCE > REPORTS\n{view.build_menu_text(guild)}", view=view, ephemeral=True)
        await view.bind_to_interaction_response(interaction)

    async def _ctx_alliance_settings_manage_workflow(self, interaction: discord.Interaction):
        guild = getattr(interaction, "guild", None)
        if guild is None:
            await _edit_or_send(interaction, content="This action can only be used in a server.")
            return
        alliance_cog = self.bot.get_cog("AllianceSlashCog")
        if alliance_cog is None:
            await _edit_or_send(interaction, content="Alliance workflow is not available right now.")
            return
        cfg = Alliance.get_guild_config(guild.id)
        caps = AllianceSlash._caps_for(interaction.user, guild, cfg)
        if "manage" not in caps:
            await _edit_or_send(interaction, content="You do not have alliance management permissions.")
            return
        if not cfg:
            await _edit_or_send(interaction, content="No alliance is configured for this guild.")
            return
        info = cfg.get("info", {}) or {}
        state = AllianceSlash._AllianceCreateState(
            guild_id=guild.id,
            author_id=getattr(interaction.user, "id", 0),
            name=str(info.get("name") or guild.name),
            tag=str(info.get("tag") or ""),
            description=str(info.get("description") or ""),
            invite_url=str(info.get("invite") or ""),
            interview_channel_id=int(info.get("interview_channel_id")) if str(info.get("interview_channel_id") or "").isdigit() else None,
            type_name=Alliance.normalize_alliance_type(cfg.get("type", Alliance.ALLIANCE_TYPE_SIMPLE)),
            role_map={
                key: int(role_cfg.get("id"))
                for key, role_cfg in (cfg.get("roles") or {}).items()
                if isinstance(role_cfg, dict) and role_cfg.get("id")
            },
        )
        view = AllianceSlash._AllianceManageRoleMapView(alliance_cog, state)
        await _edit_or_send(interaction, content=view.build_summary_text(), view=view, ephemeral=True)
        await view.bind_to_interaction_response(interaction)

    async def _ctx_roster_edit_settings(self, interaction: discord.Interaction, user: discord.Member):
        if user.id != getattr(interaction.user, "id", None):
            await _edit_or_send(interaction, content="Roster settings are only available for your own roster.")
            return
        view = _AccountManagerView(self.core, user.id)
        await _edit_or_send(interaction, content="Manage your MCOC roster settings.", view=view)
        await view.bind_to_interaction_response(interaction)

    async def cog_load(self):
        menus = [
            app_commands.ContextMenu(name="MCOC", callback=self._ctx_alliance),
        ]

        legacy_names = [
            "CollectorVerse",
            "CollectorVerse Profile",
            "Profile Settings",
            "CollectorVerse Roster",
            "CollectorVerse Alliance",
            "MCOC Roster",
            "MCOC Alliance",
            "Roster Add",
            "Roster Remove",
            "Alliance Invite",
            "Alliance Manage",
        ]

        for legacy_name in legacy_names:
            try:
                self.bot.tree.remove_command(legacy_name, type=discord.AppCommandType.user)
            except Exception:
                pass

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
