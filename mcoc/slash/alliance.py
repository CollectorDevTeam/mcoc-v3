# Path: mcoc/slash/alliance.py
"""Slash alliance profile/settings workflows."""

import logging
import re
import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

import discord
from redbot.core import app_commands, commands

from ..common.components.componentsV2 import CDTAutoCleanupView
from ..common.helpers import alliance as Alliance
from ..common.helpers.account import user_has_collectorverse_premium
from ..common.helpers.roster import ensure_user_manager

log = logging.getLogger("red.mcoc.slash.alliance")

_DISCORD_INVITE_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?(?:discord\.gg|discord(?:app)?\.com/invite)/([A-Za-z0-9-]{2,64})/?$",
    re.IGNORECASE,
)
_DISCORD_INVITE_CODE_RE = re.compile(r"^[A-Za-z0-9-]{2,64}$")


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
    user_id = getattr(getattr(interaction, "user", None), "id", None)
    guild_id = getattr(getattr(interaction, "guild", None), "id", None)
    try:
        is_done = bool(response and hasattr(response, "is_done") and response.is_done())
    except Exception:
        log.debug("alliance _edit_or_send: failed to inspect response state", exc_info=True)
        is_done = False
    if is_done:
        try:
            await interaction.edit_original_response(content=content, embed=embed, view=view)
            log.debug("alliance _edit_or_send: edited original response (guild=%s user=%s)", guild_id, user_id)
            return
        except Exception:
            log.debug("alliance _edit_or_send: edit_original_response failed", exc_info=True)
        if hasattr(interaction, "followup"):
            try:
                await interaction.followup.send(content=content, embed=embed, view=view, ephemeral=ephemeral)
                log.debug("alliance _edit_or_send: sent followup message (guild=%s user=%s)", guild_id, user_id)
                return
            except Exception:
                log.debug("alliance _edit_or_send: followup.send failed", exc_info=True)

    if getattr(interaction, "message", None) is not None and response and hasattr(response, "edit_message"):
        try:
            await response.edit_message(content=content, embed=embed, view=view)
            log.debug("alliance _edit_or_send: edited interaction message (guild=%s user=%s)", guild_id, user_id)
            return
        except Exception:
            log.debug("alliance _edit_or_send: response.edit_message failed", exc_info=True)

    if response and hasattr(response, "send_message"):
        try:
            await response.send_message(content=content, embed=embed, view=view, ephemeral=ephemeral)
            log.debug("alliance _edit_or_send: sent initial response message (guild=%s user=%s)", guild_id, user_id)
            return
        except Exception:
            log.debug("alliance _edit_or_send: response.send_message failed", exc_info=True)

    if hasattr(interaction, "followup"):
        try:
            await interaction.followup.send(content=content, embed=embed, view=view, ephemeral=ephemeral)
            log.debug("alliance _edit_or_send: sent terminal followup fallback (guild=%s user=%s)", guild_id, user_id)
        except Exception:
            log.exception("alliance _edit_or_send: all response strategies failed (guild=%s user=%s)", guild_id, user_id)


async def _defer_or_send(
    interaction: discord.Interaction,
    *,
    content: Optional[str] = None,
    embed: Optional[discord.Embed] = None,
    view: Optional[discord.ui.View] = None,
    ephemeral: bool = True,
) -> None:
    try:
        await interaction.response.defer(ephemeral=ephemeral)
    except Exception:
        pass
    await _edit_or_send(interaction, content=content, embed=embed, view=view, ephemeral=ephemeral)


async def _safe_ephemeral_error(interaction: discord.Interaction, message: str) -> None:
    response = getattr(interaction, "response", None)
    try:
        done = bool(response and hasattr(response, "is_done") and response.is_done())
    except Exception:
        done = False
    try:
        if done and hasattr(interaction, "followup"):
            await interaction.followup.send(message, ephemeral=True)
            return
        if response and hasattr(response, "send_message"):
            await response.send_message(message, ephemeral=True)
            return
    except Exception:
        log.exception("alliance _safe_ephemeral_error failed")


def _build_alliance_profile_text(cfg: dict, guild: discord.Guild, member: Optional[discord.Member] = None) -> str:
    info = cfg.get("info", {})
    name = info.get("name") or guild.name
    type_name = Alliance.normalize_alliance_type(cfg.get("type", "simple"))
    roles = cfg.get("roles", {})
    lines = [
        f"**{name}**",
        f"Type: {type_name}",
    ]
    if info.get("tag"):
        lines.append(f"Tag: {info.get('tag')}")
    if info.get("description"):
        lines.append(f"Description: {info.get('description')}")
    if info.get("invite"):
        lines.append(f"Discord Invite: {info.get('invite')}")
    if info.get("founded"):
        lines.append(f"Alliance Founded: {info.get('founded')}")

    keys = ["alliance", "officers", "members", "leader", "managers"] + Alliance.expected_battlegroup_keys(type_name)
    for key in keys:
        role_cfg = roles.get(key)
        if not role_cfg:
            continue
        role_name = role_cfg.get("name") if isinstance(role_cfg, dict) else str(role_cfg)
        lines.append(f"{key}: {role_name}")

    if member is not None and member.id in cfg.get("member_ids", []):
        lines.append("Membership: active on this guild")
    return "\n".join(lines)


def _is_guild_admin(author: discord.Member, guild: discord.Guild) -> bool:
    perms = getattr(author, "guild_permissions", None)
    if guild.owner_id == author.id:
        return True
    if perms is None:
        return False
    return bool(getattr(perms, "administrator", False) or getattr(perms, "manage_guild", False))


def _is_alliance_member(author: discord.Member, guild: discord.Guild, cfg: dict) -> bool:
    mids = set(cfg.get("member_ids") or [])
    if author.id in mids:
        return True
    role_cfg = (cfg.get("roles") or {}).get("alliance")
    if isinstance(role_cfg, dict):
        role_obj = guild.get_role(role_cfg.get("id"))
        if role_obj and role_obj in author.roles:
            return True
    return False


def _is_premium_user(author: discord.Member) -> bool:
    return user_has_collectorverse_premium(author)


def _caps_for(author: discord.Member, guild: discord.Guild, cfg: Optional[dict]) -> Set[str]:
    caps: Set[str] = set()
    is_owner = bool(getattr(guild, "owner_id", None) == getattr(author, "id", None))
    is_admin_or_owner = _is_guild_admin(author, guild)

    if not cfg:
        if is_owner:
            caps.add("create")
        return caps

    has_alliance = _is_alliance_member(author, guild, cfg)
    is_manager = bool(has_alliance and Alliance.is_alliance_manager(author, guild))

    if is_manager:
        caps.update({"reports", "settings", "assign"})
    if has_alliance and is_admin_or_owner:
        caps.add("delete")
    return caps


def _required_role_keys(type_name: str) -> List[str]:
    type_norm = Alliance.normalize_alliance_type(type_name)
    if type_norm == Alliance.ALLIANCE_TYPE_ADVANCED:
        return ["alliance", "officers", "aqbg1", "aqbg2", "aqbg3", "awbg1", "awbg2", "awbg3"]
    return ["alliance", "officers", "bg1", "bg2", "bg3"]


def _normalize_discord_invite(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    match = _DISCORD_INVITE_RE.match(raw)
    if match:
        return f"https://discord.gg/{match.group(1)}"
    if _DISCORD_INVITE_CODE_RE.match(raw):
        return f"https://discord.gg/{raw}"
    raise ValueError("Invalid Discord invite. Use a discord.gg link or invite code.")


def _bg_keys_for_type(type_name: str) -> List[str]:
    type_norm = Alliance.normalize_alliance_type(type_name)
    if type_norm == Alliance.ALLIANCE_TYPE_ADVANCED:
        return ["aqbg1", "aqbg2", "aqbg3", "awbg1", "awbg2", "awbg3"]
    return ["bg1", "bg2", "bg3"]


@dataclass
class _AllianceCreateState:
    guild_id: int
    author_id: int
    name: str = ""
    tag: str = ""
    description: str = ""
    invite_url: str = ""
    interview_channel_id: Optional[int] = None
    type_name: str = Alliance.ALLIANCE_TYPE_SIMPLE
    role_map: Dict[str, int] = field(default_factory=dict)


class _AllianceCreateModal(discord.ui.Modal, title="Alliance Setup: Page 1"):
    def __init__(self, cog: "AllianceSlashCog", state: _AllianceCreateState):
        super().__init__()
        self.cog = cog
        self.state = state

        self.name = discord.ui.TextInput(label="Name", required=True, max_length=60, default=state.name or "")
        self.tag = discord.ui.TextInput(label="Tag", required=False, max_length=15, default=state.tag or "")
        self.description = discord.ui.TextInput(label="Description", required=False, max_length=250, default=state.description or "", style=discord.TextStyle.paragraph)
        self.invite_url = discord.ui.TextInput(label="Discord Invite", required=False, max_length=200, default=state.invite_url or "")
        self.type_name = discord.ui.TextInput(label="Type (simple|advanced)", required=True, max_length=20, default=state.type_name)

        self.add_item(self.name)
        self.add_item(self.tag)
        self.add_item(self.description)
        self.add_item(self.invite_url)
        self.add_item(self.type_name)

    async def on_submit(self, interaction: discord.Interaction):
        self.state.name = str(self.name.value or "").strip()
        self.state.tag = str(self.tag.value or "").strip()
        self.state.description = str(self.description.value or "").strip()
        try:
            self.state.invite_url = _normalize_discord_invite(str(self.invite_url.value or "").strip())
        except ValueError as exc:
            await _edit_or_send(interaction, content=str(exc), ephemeral=True)
            return
        self.state.type_name = Alliance.normalize_alliance_type(str(self.type_name.value or "").strip())
        if not self.state.name:
            await _edit_or_send(interaction, content="Alliance name is required.", ephemeral=True)
            return

        view = _AllianceCreateRoleMapView(self.cog, self.state)
        await _edit_or_send(interaction, content=view.build_summary_text(), view=view, ephemeral=True)
        await view.bind_to_interaction_response(interaction)


class _RoleSlotSelect(discord.ui.Select):
    def __init__(self, view: "_AllianceCreateRoleMapView"):
        self.role_view = view
        options = [
            discord.SelectOption(label=key.upper(), value=key, description="Role slot to map")
            for key in _required_role_keys(view.state.type_name)
        ]
        super().__init__(placeholder="Choose role slot", min_values=1, max_values=1, options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        try:
            self.role_view.selected_slot = self.values[0]
            await _edit_or_send(interaction, content=self.role_view.build_summary_text(), view=self.role_view)
        except Exception:
            log.exception("Alliance role slot select callback failed")
            await _safe_ephemeral_error(interaction, "Role slot selection failed. Please try again.")


class _RolePicker(discord.ui.RoleSelect):
    def __init__(self, view: "_AllianceCreateRoleMapView"):
        self.role_view = view
        super().__init__(placeholder="Select role for chosen slot", min_values=1, max_values=1, row=1)

    async def callback(self, interaction: discord.Interaction):
        try:
            slot = self.role_view.selected_slot
            if not slot:
                await _edit_or_send(interaction, content="Pick a slot first.", ephemeral=True)
                return
            role = self.values[0]
            self.role_view.state.role_map[slot] = role.id
            await _edit_or_send(interaction, content=self.role_view.build_summary_text(), view=self.role_view)
        except Exception:
            log.exception("Alliance role picker callback failed")
            await _safe_ephemeral_error(interaction, "Role assignment failed. Please try again.")


class _InterviewChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, view: "_AllianceCreateRoleMapView"):
        self.role_view = view
        super().__init__(
            placeholder="Optional: Select interview channel for auto-invite",
            min_values=0,
            max_values=1,
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            if not self.values:
                self.role_view.state.interview_channel_id = None
                await _edit_or_send(interaction, content=self.role_view.build_summary_text(), view=self.role_view)
                return
            channel = self.values[0]
            self.role_view.state.interview_channel_id = int(getattr(channel, "id", 0) or 0) or None
            await _edit_or_send(interaction, content=self.role_view.build_summary_text(), view=self.role_view)
        except Exception:
            log.exception("Alliance interview channel select callback failed")
            await _safe_ephemeral_error(interaction, "Interview channel selection failed. Please try again.")


class _AllianceCreateRoleMapView(CDTAutoCleanupView):
    def __init__(self, cog: "AllianceSlashCog", state: _AllianceCreateState):
        super().__init__(timeout=240)
        self.cog = cog
        self.state = state
        self.selected_slot: Optional[str] = _required_role_keys(self.state.type_name)[0]

        self.add_item(_RoleSlotSelect(self))
        self.add_item(_RolePicker(self))
        self.add_item(_InterviewChannelSelect(self))

    def build_summary_text(self) -> str:
        lines = [
            "Alliance Setup: Page 2",
            f"Name: {self.state.name or '-'}",
            f"Tag: {self.state.tag or '-'}",
            f"Type: {self.state.type_name}",
            f"Description: {self.state.description or '-'}",
            f"Discord Invite: {self.state.invite_url or '-'}",
            "",
            "Required role mappings:",
        ]
        for key in _required_role_keys(self.state.type_name):
            rid = self.state.role_map.get(key)
            lines.append(f"- {key}: <@&{rid}>" if rid else f"- {key}: [auto-create/default]")
        if self.state.interview_channel_id:
            lines.append(f"\nInterview Channel: <#{self.state.interview_channel_id}> (invite auto-generated)")
        else:
            lines.append("\nInterview Channel: [none] (uses Discord Invite field)")
        lines.append("Choose a slot then select a role, or use AUTO CREATE MISSING.")
        return "\n".join(lines)

    @discord.ui.button(label="EDIT INFO", style=discord.ButtonStyle.primary, row=3)
    async def edit_info(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if isinstance(self, _AllianceManageRoleMapView):
            await interaction.response.send_modal(_AllianceManageInfoModal(self.cog, self.state))
            return
        await interaction.response.send_modal(_AllianceCreateModal(self.cog, self.state))

    @discord.ui.button(label="AUTO CREATE MISSING", style=discord.ButtonStyle.secondary, row=3)
    async def auto_create_missing(self, interaction: discord.Interaction, _button: discord.ui.Button):
        guild = getattr(interaction, "guild", None)
        if guild is None:
            await _edit_or_send(interaction, content="This action can only be used in a server.", view=self)
            return
        for key in _required_role_keys(self.state.type_name):
            if key in self.state.role_map:
                continue
            role_name = f"{self.state.name} {key.upper()}"
            mapped = await Alliance.create_or_link_role(guild, role_name, key)
            if isinstance(mapped, dict):
                rid = mapped.get("id")
                if rid:
                    self.state.role_map[key] = int(rid)
        await _edit_or_send(interaction, content=self.build_summary_text(), view=self)

    @discord.ui.button(label="NEXT (CONFIRM)", style=discord.ButtonStyle.success, row=3)
    async def next_confirm(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if not str(self.state.name or "").strip():
            await _edit_or_send(interaction, content="Alliance name is required. Use EDIT INFO first.", view=self)
            return
        view = _AllianceCreateConfirmView(self.cog, self.state)
        await _edit_or_send(interaction, content=view.build_text(), view=view)
        await view.bind_to_interaction_response(interaction)

    @discord.ui.button(label="CANCEL", style=discord.ButtonStyle.danger, row=3)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await _edit_or_send(interaction, content="Alliance setup cancelled.", view=None)


class _AllianceCreateConfirmView(CDTAutoCleanupView):
    def __init__(self, cog: "AllianceSlashCog", state: _AllianceCreateState):
        super().__init__(timeout=180)
        self.cog = cog
        self.state = state

    def build_text(self) -> str:
        lines = [
            "Alliance Setup: Page 3",
            "Confirm Settings?",
            f"Name: {self.state.name}",
            f"Tag: {self.state.tag or '-'}",
            f"Type: {self.state.type_name}",
            f"Description: {self.state.description or '-'}",
            f"Invite: {self.state.invite_url or '-'}",
            f"Interview Channel: {f'<#{self.state.interview_channel_id}>' if self.state.interview_channel_id else '-'}",
            "",
            "Assigned role slots:",
        ]
        for key in _required_role_keys(self.state.type_name):
            rid = self.state.role_map.get(key)
            lines.append(f"- {key}: <@&{rid}>" if rid else f"- {key}: auto-create")
        lines.append("")
        lines.append("Press YES to apply, or NO to cancel.")
        return "\n".join(lines)

    @discord.ui.button(label="YES", style=discord.ButtonStyle.success)
    async def yes(self, interaction: discord.Interaction, _button: discord.ui.Button):
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            pass
        ok, msg = await self.cog._apply_create_settings(interaction, self.state)
        try:
            await interaction.followup.send(msg, ephemeral=True)
        except Exception:
            try:
                await interaction.edit_original_response(content=msg)
            except Exception:
                await _edit_or_send(interaction, content=msg, view=None)
        if not ok:
            log.warning("Alliance create workflow failed: %s", msg)

    @discord.ui.button(label="NO", style=discord.ButtonStyle.danger)
    async def no(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await _edit_or_send(interaction, content="Alliance setup cancelled.", view=None)


class _AllianceManageInfoModal(discord.ui.Modal, title="Alliance Manage: Page 1"):
    def __init__(self, cog: "AllianceSlashCog", state: _AllianceCreateState):
        super().__init__()
        self.cog = cog
        self.state = state

        self.name = discord.ui.TextInput(label="Name", required=True, max_length=60, default=state.name or "")
        self.tag = discord.ui.TextInput(label="Tag", required=False, max_length=15, default=state.tag or "")
        self.description = discord.ui.TextInput(label="Description", required=False, max_length=250, default=state.description or "", style=discord.TextStyle.paragraph)
        self.invite_url = discord.ui.TextInput(label="Discord Invite", required=False, max_length=200, default=state.invite_url or "")
        self.type_name = discord.ui.TextInput(label="Type (simple|advanced)", required=True, max_length=20, default=state.type_name)

        self.add_item(self.name)
        self.add_item(self.tag)
        self.add_item(self.description)
        self.add_item(self.invite_url)
        self.add_item(self.type_name)

    async def on_submit(self, interaction: discord.Interaction):
        self.state.name = str(self.name.value or "").strip()
        self.state.tag = str(self.tag.value or "").strip()
        self.state.description = str(self.description.value or "").strip()
        try:
            self.state.invite_url = _normalize_discord_invite(str(self.invite_url.value or "").strip())
        except ValueError as exc:
            await _edit_or_send(interaction, content=str(exc), ephemeral=True)
            return
        self.state.type_name = Alliance.normalize_alliance_type(str(self.type_name.value or "").strip())
        if not self.state.name:
            await _edit_or_send(interaction, content="Alliance name is required.", ephemeral=True)
            return

        view = _AllianceManageRoleMapView(self.cog, self.state)
        await _edit_or_send(interaction, content=view.build_summary_text(), view=view, ephemeral=True)
        await view.bind_to_interaction_response(interaction)


class _AllianceManageRoleMapView(_AllianceCreateRoleMapView):
    @discord.ui.button(label="NEXT (CONFIRM)", style=discord.ButtonStyle.success, row=3)
    async def next_confirm(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if not str(self.state.name or "").strip():
            await _edit_or_send(interaction, content="Alliance name is required. Use EDIT INFO first.", view=self)
            return
        view = _AllianceManageConfirmView(self.cog, self.state)
        await _edit_or_send(interaction, content=view.build_text(), view=view)
        await view.bind_to_interaction_response(interaction)


class _AllianceManageConfirmView(CDTAutoCleanupView):
    def __init__(self, cog: "AllianceSlashCog", state: _AllianceCreateState):
        super().__init__(timeout=180)
        self.cog = cog
        self.state = state

    def build_text(self) -> str:
        lines = [
            "Alliance Manage: Page 3",
            "Confirm Settings?",
            f"Name: {self.state.name}",
            f"Tag: {self.state.tag or '-'}",
            f"Type: {self.state.type_name}",
            f"Description: {self.state.description or '-'}",
            f"Invite: {self.state.invite_url or '-'}",
            f"Interview Channel: {f'<#{self.state.interview_channel_id}>' if self.state.interview_channel_id else '-'}",
            "",
            "Assigned role slots:",
        ]
        for key in _required_role_keys(self.state.type_name):
            rid = self.state.role_map.get(key)
            lines.append(f"- {key}: <@&{rid}>" if rid else f"- {key}: auto-create")
        lines.append("")
        lines.append("Press YES to apply, or NO to cancel.")
        return "\n".join(lines)

    @discord.ui.button(label="YES", style=discord.ButtonStyle.success)
    async def yes(self, interaction: discord.Interaction, _button: discord.ui.Button):
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            pass
        ok, msg = await self.cog._apply_manage_settings(interaction, self.state)
        try:
            await interaction.followup.send(msg, ephemeral=True)
        except Exception:
            try:
                await interaction.edit_original_response(content=msg)
            except Exception:
                await _edit_or_send(interaction, content=msg, view=None)
        if not ok:
            log.warning("Alliance manage workflow failed: %s", msg)

    @discord.ui.button(label="NO", style=discord.ButtonStyle.danger)
    async def no(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await _edit_or_send(interaction, content="Alliance manage cancelled.", view=None)


class _AllianceSettingsView(CDTAutoCleanupView):
    def __init__(self, cog: "AllianceSlashCog", caps: Set[str], guild: discord.Guild, author: discord.Member, cfg: Optional[dict]):
        super().__init__(timeout=180)
        self.cog = cog
        self.caps = caps
        self.guild = guild
        self.author = author
        self.cfg = cfg
        self.clear_items()

        has_alliance = bool(cfg)
        can_create = "create" in caps
        self.create_btn.disabled = not can_create
        self.reports_btn.disabled = "reports" not in caps or not has_alliance
        self.settings_btn.disabled = "settings" not in caps or not has_alliance
        self.assign_btn.disabled = "assign" not in caps or not has_alliance
        self.delete_btn.disabled = "delete" not in caps or not has_alliance

        if not has_alliance:
            if can_create:
                self.add_item(self.create_btn)
            return

        if "reports" in caps:
            self.add_item(self.reports_btn)
        if "settings" in caps:
            self.add_item(self.settings_btn)
        if "assign" in caps:
            self.add_item(self.assign_btn)
        if "delete" in caps:
            self.add_item(self.delete_btn)

    @discord.ui.button(label="CREATE", style=discord.ButtonStyle.primary)
    async def create_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        try:
            guild = getattr(interaction, "guild", None)
            if guild is None:
                await _edit_or_send(interaction, content="This action can only be used in a server.", view=self)
                return
            state = _AllianceCreateState(
                guild_id=guild.id,
                author_id=getattr(interaction.user, "id", 0),
                name=str(guild.name),
                type_name=Alliance.ALLIANCE_TYPE_SIMPLE,
            )
            view = _AllianceCreateRoleMapView(self.cog, state)
            await _edit_or_send(interaction, content=view.build_summary_text(), view=view)
            await view.bind_to_interaction_response(interaction)
        except Exception:
            log.exception("Alliance settings CREATE callback failed")
            await _safe_ephemeral_error(interaction, "Create workflow failed to open. Please try again.")

    @discord.ui.button(label="REPORTS", style=discord.ButtonStyle.success)
    async def reports_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        try:
            guild = getattr(interaction, "guild", None)
            if guild is None:
                await _edit_or_send(interaction, content="This action can only be used in a server.", view=self)
                return
            view = _AllianceReportsView(self.cog)
            await _edit_or_send(interaction, content=view.build_menu_text(guild), view=view)
            await view.bind_to_interaction_response(interaction)
        except Exception:
            log.exception("Alliance settings REPORTS callback failed")
            await _safe_ephemeral_error(interaction, "Reports workflow failed to open. Please try again.")

    @discord.ui.button(label="SETTINGS", style=discord.ButtonStyle.secondary)
    async def settings_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        try:
            guild = getattr(interaction, "guild", None)
            if guild is None:
                await _edit_or_send(interaction, content="This action can only be used in a server.", view=self)
                return
            # Role-map-first flow: _AllianceManageInfoModal remains available via EDIT INFO.
            cfg = Alliance.get_guild_config(guild.id)
            if not cfg:
                await _edit_or_send(interaction, content="No alliance is configured for this guild.", view=self)
                return
            info = cfg.get("info", {}) or {}
            state = _AllianceCreateState(
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
            view = _AllianceManageRoleMapView(self.cog, state)
            await _edit_or_send(interaction, content=view.build_summary_text(), view=view)
            await view.bind_to_interaction_response(interaction)
        except Exception:
            log.exception("Alliance settings SETTINGS callback failed")
            await _safe_ephemeral_error(interaction, "Settings workflow failed to open. Please try again.")

    @discord.ui.button(label="ASSIGN ROLE", style=discord.ButtonStyle.secondary)
    async def assign_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        try:
            await _edit_or_send(
                interaction,
                content=(
                    "Alliance role assignment is user-targeted.\n"
                    "Use Context Menu: MCOC > ALLIANCE > ASSIGN ROLE on the target member."
                ),
                view=self,
            )
        except Exception:
            log.exception("Alliance settings ASSIGN ROLE callback failed")
            await _safe_ephemeral_error(interaction, "Assign-role workflow failed to open. Please try again.")

    @discord.ui.button(label="DELETE", style=discord.ButtonStyle.danger)
    async def delete_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        try:
            view = _AllianceDeleteConfirmView(self.cog)
            await _edit_or_send(interaction, content="Delete this guild alliance configuration?", view=view)
            await view.bind_to_interaction_response(interaction)
        except Exception:
            log.exception("Alliance settings DELETE callback failed")
            await _safe_ephemeral_error(interaction, "Delete workflow failed to open. Please try again.")


class _AllianceDeleteConfirmView(CDTAutoCleanupView):
    def __init__(self, cog: "AllianceSlashCog"):
        super().__init__(timeout=90)
        self.cog = cog

    @discord.ui.button(label="YES", style=discord.ButtonStyle.danger)
    async def yes(self, interaction: discord.Interaction, _button: discord.ui.Button):
        ok, msg = await self.cog._delete_alliance(interaction)
        await _edit_or_send(interaction, content=msg, view=None)
        if not ok:
            log.warning("Alliance delete denied/failed: %s", msg)

    @discord.ui.button(label="NO", style=discord.ButtonStyle.secondary)
    async def no(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await _edit_or_send(interaction, content="Delete cancelled.", view=None)


class _AllianceReportsView(CDTAutoCleanupView):
    def __init__(self, cog: "AllianceSlashCog"):
        super().__init__(timeout=180)
        self.cog = cog
        self.bg_select = _AllianceBattlegroupReportSelect(cog)
        self.add_item(self.bg_select)

    def build_menu_text(self, guild: discord.Guild) -> str:
        cfg = Alliance.get_guild_config(guild.id)
        if not cfg:
            return "No alliance is configured for this guild."
        type_name = Alliance.normalize_alliance_type(cfg.get("type", Alliance.ALLIANCE_TYPE_SIMPLE))
        self.bg_select.refresh_options(type_name)
        return "\n".join(
            [
                "Alliance Reports workflow:",
                "- DIAGNOSTICS: health checks",
                "- ALLIANCE SUMMARY: members with prestige",
                "- BATTLEGROUP REPORT: select BG below for member prestige listing",
            ]
        )

    @discord.ui.button(label="DIAGNOSTICS", style=discord.ButtonStyle.success, row=1)
    async def diagnostics(self, interaction: discord.Interaction, _button: discord.ui.Button):
        _ok, msg = await self.cog._run_diagnostics(interaction)
        await _edit_or_send(interaction, content=msg, view=self)

    @discord.ui.button(label="ALLIANCE SUMMARY", style=discord.ButtonStyle.primary, row=1)
    async def alliance_summary(self, interaction: discord.Interaction, _button: discord.ui.Button):
        _ok, msg = await self.cog._run_alliance_summary_report(interaction)
        await _edit_or_send(interaction, content=msg, view=self)

    @discord.ui.button(label="BACK", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button):
        guild = getattr(interaction, "guild", None)
        if guild is None:
            await _edit_or_send(interaction, content="This action can only be used in a server.", view=self)
            return
        cfg = Alliance.get_guild_config(guild.id)
        caps = _caps_for(interaction.user, guild, cfg)
        view = _AllianceSettingsView(self.cog, caps, guild, interaction.user, cfg)
        await _edit_or_send(interaction, content="Alliance manage: choose a workflow.", view=view)
        await view.bind_to_interaction_response(interaction)


class _AllianceBattlegroupReportSelect(discord.ui.Select):
    def __init__(self, cog: "AllianceSlashCog"):
        self.cog = cog
        super().__init__(placeholder="Choose battlegroup report", min_values=1, max_values=1, options=[discord.SelectOption(label="BG1", value="bg1")], row=0)

    def refresh_options(self, type_name: str):
        keys = _bg_keys_for_type(type_name)
        self.options = [discord.SelectOption(label=key.upper(), value=key) for key in keys]

    async def callback(self, interaction: discord.Interaction):
        key = self.values[0] if self.values else ""
        _ok, msg = await self.cog._run_battlegroup_report(interaction, key)
        await _edit_or_send(interaction, content=msg, view=self.view)


class _AllianceGroup(app_commands.Group):
    def __init__(self, cog: "AllianceSlashCog"):
        super().__init__(name="alliance", description="Alliance profile and settings")
        self.cog = cog

    async def _open_workflow(self, interaction: discord.Interaction):
        guild = getattr(interaction, "guild", None)
        if guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        author = interaction.user
        cfg = Alliance.get_guild_config(guild.id)
        caps = _caps_for(author, guild, cfg)
        view = _AllianceSettingsView(self.cog, caps, guild, author, cfg)

        if not caps:
            await interaction.response.send_message(
                "You do not have alliance manage access here.\n"
                "Allowed roles:\n"
                "- Guild Owner: create (when no alliance exists)\n"
                "- Alliance Manager: reports/settings/assign role\n"
                "- Guild Owner/Admin + Alliance Member: delete",
                view=view,
                ephemeral=True,
            )
            await view.bind_to_interaction_response(interaction)
            return

        await interaction.response.send_message("Alliance manage: choose a workflow.", view=view, ephemeral=True)
        await view.bind_to_interaction_response(interaction)

    @app_commands.command(name="profile", description="Display alliance profile")
    @app_commands.describe(user="Optional member to evaluate membership against")
    async def profile(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        guild = getattr(interaction, "guild", None)
        if guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        cfg = Alliance.get_guild_config(guild.id)
        if not cfg:
            await interaction.response.send_message("No alliance is configured for this guild.", ephemeral=True)
            return
        target = user or interaction.user
        await interaction.response.send_message(_build_alliance_profile_text(cfg, guild, target), ephemeral=False)

    @app_commands.command(name="manage", description="Alliance management workflows")
    async def manage(self, interaction: discord.Interaction):
        await self._open_workflow(interaction)


class AllianceSlashCog(commands.Cog):
    def __init__(self, bot: Any):
        self.bot = bot
        self.core = _core_for(bot)
        self._group = _AllianceGroup(self)

    @property
    def group(self):
        return self._group

    async def _generate_invite_from_channel(self, guild: discord.Guild, channel_id: int) -> str:
        channel = guild.get_channel(int(channel_id)) if channel_id else None
        if channel is None:
            raise ValueError("Selected interview channel no longer exists.")

        perms = channel.permissions_for(guild.me) if getattr(guild, "me", None) is not None else None
        if perms is not None and not getattr(perms, "create_instant_invite", False):
            raise ValueError("Collector does not have permission to create invites for the selected channel.")

        try:
            invite = await channel.create_invite(max_age=0, max_uses=0, temporary=False, unique=True, reason="Alliance interview invite")
        except Exception as exc:
            raise ValueError(f"Could not create invite for selected channel: {exc}") from exc
        return str(getattr(invite, "url", "") or "")

    async def _apply_create_settings(self, interaction: discord.Interaction, state: _AllianceCreateState) -> tuple[bool, str]:
        guild = getattr(interaction, "guild", None)
        if guild is None:
            return False, "This action can only be used in a server."
        if guild.id != state.guild_id:
            return False, "Guild context changed; restart setup."
        if state.author_id != getattr(interaction.user, "id", None):
            return False, "Only the workflow initiator can confirm setup."
        if not _is_guild_admin(interaction.user, guild):
            return False, "You need Guild Owner/Admin permissions to create alliance settings."

        existing = Alliance.get_guild_config(guild.id)
        if existing:
            return False, "An alliance is already configured. Use MANAGE/DELETE as needed."

        type_norm = Alliance.normalize_alliance_type(state.type_name)
        ok = await Alliance.register_alliance(guild, state.name, alliance_tag=state.tag or None, type_=type_norm)
        if not ok:
            return False, "Failed to register alliance configuration."

        invite_url = state.invite_url or ""
        if state.interview_channel_id:
            try:
                invite_url = await self._generate_invite_from_channel(guild, state.interview_channel_id)
            except ValueError as exc:
                return False, str(exc)

        Alliance.set_alliance_info_field(guild.id, "description", state.description or None)
        Alliance.set_alliance_info_field(guild.id, "invite", invite_url or None)
        Alliance.set_alliance_info_field(guild.id, "interview_channel_id", str(state.interview_channel_id) if state.interview_channel_id else None)
        Alliance.set_alliance_info_field(guild.id, "founded", datetime.date.today().isoformat())

        for key, rid in (state.role_map or {}).items():
            role_obj = guild.get_role(int(rid))
            if role_obj is None:
                continue
            await Alliance.create_or_link_role(guild, role_obj.name, key, role_obj=role_obj)

        Alliance.set_alliance_type(guild.id, type_norm, guild_obj=guild)
        return True, "Alliance settings created successfully."

    async def _apply_manage_settings(self, interaction: discord.Interaction, state: _AllianceCreateState) -> tuple[bool, str]:
        guild = getattr(interaction, "guild", None)
        if guild is None:
            return False, "This action can only be used in a server."
        if guild.id != state.guild_id:
            return False, "Guild context changed; restart setup."
        if state.author_id != getattr(interaction.user, "id", None):
            return False, "Only the workflow initiator can confirm setup."

        cfg = Alliance.get_guild_config(guild.id)
        caps = _caps_for(interaction.user, guild, cfg)
        if "settings" not in caps:
            return False, "You do not have permission to manage alliance settings."
        if not cfg:
            return False, "No alliance is configured for this guild."

        type_norm = Alliance.normalize_alliance_type(state.type_name)
        invite_url = state.invite_url or ""
        if state.interview_channel_id:
            try:
                invite_url = await self._generate_invite_from_channel(guild, state.interview_channel_id)
            except ValueError as exc:
                return False, str(exc)

        Alliance.set_alliance_info_field(guild.id, "name", state.name)
        Alliance.set_alliance_info_field(guild.id, "tag", state.tag or None)
        Alliance.set_alliance_info_field(guild.id, "description", state.description or None)
        Alliance.set_alliance_info_field(guild.id, "invite", invite_url or None)
        Alliance.set_alliance_info_field(guild.id, "interview_channel_id", str(state.interview_channel_id) if state.interview_channel_id else None)
        Alliance.set_alliance_type(guild.id, type_norm, guild_obj=guild)

        for key in _required_role_keys(type_norm):
            role_id = (state.role_map or {}).get(key)
            if role_id:
                role_obj = guild.get_role(int(role_id))
                if role_obj is not None:
                    await Alliance.create_or_link_role(guild, role_obj.name, key, role_obj=role_obj)
                    continue
            role_name = f"{state.name} {key.upper()}"
            await Alliance.create_or_link_role(guild, role_name, key)

        return True, "Alliance settings updated successfully."

    def _compute_user_prestige(self, guild: discord.Guild, user_id: int) -> Optional[int]:
        users = ensure_user_manager(self.core)
        if not users or not hasattr(users, "list_roster"):
            return None
        try:
            roster = users.list_roster(user_id) or []
        except Exception:
            roster = []
        if not roster:
            return None

        cache = getattr(self.core, "cache", None)
        if cache is None:
            return None

        values: List[int] = []
        for entry in roster:
            slug = str(entry.get("champion") or "").strip().lower()
            if not slug:
                continue
            try:
                rarity = int(entry.get("rarity") or entry.get("stars") or 0)
                rank = int(entry.get("rank") or 1)
                sig = int(entry.get("sig") or 0)
                asc = int(entry.get("ascended") or 0)
            except Exception:
                continue
            try:
                p = cache.get_prestige_value(slug, rarity, rank, asc, sig)
            except Exception:
                p = None
            if isinstance(p, (int, float)):
                values.append(int(p))
        if not values:
            return None
        values.sort(reverse=True)
        top = values[:5]
        if not top:
            return None
        return int(round(sum(top) / len(top)))

    async def _run_alliance_summary_report(self, interaction: discord.Interaction) -> tuple[bool, str]:
        guild = getattr(interaction, "guild", None)
        if guild is None:
            return False, "This action can only be used in a server."
        cfg = Alliance.get_guild_config(guild.id)
        caps = _caps_for(interaction.user, guild, cfg)
        if "reports" not in caps:
            return False, "You do not have permission to view alliance reports."
        if not cfg:
            return False, "No alliance is configured for this guild."

        role_cfg = (cfg.get("roles") or {}).get("alliance")
        if not isinstance(role_cfg, dict):
            return False, "Alliance role is not configured."
        role_obj = guild.get_role(role_cfg.get("id"))
        if role_obj is None:
            return False, "Alliance role is missing on this server."

        lines = ["Alliance summary:", f"Members: {len(role_obj.members)}"]
        for member in sorted(role_obj.members, key=lambda m: (getattr(m, "display_name", "").lower(), m.id))[:50]:
            prestige = self._compute_user_prestige(guild, member.id)
            lines.append(f"- {member.display_name} | prestige: {prestige if prestige is not None else 'n/a'}")
        if len(role_obj.members) > 50:
            lines.append("...")
        return True, "\n".join(lines)

    async def _run_battlegroup_report(self, interaction: discord.Interaction, key: str) -> tuple[bool, str]:
        guild = getattr(interaction, "guild", None)
        if guild is None:
            return False, "This action can only be used in a server."
        cfg = Alliance.get_guild_config(guild.id)
        caps = _caps_for(interaction.user, guild, cfg)
        if "reports" not in caps:
            return False, "You do not have permission to view alliance reports."
        if not cfg:
            return False, "No alliance is configured for this guild."

        role_cfg = (cfg.get("roles") or {}).get(str(key or "").lower())
        if not isinstance(role_cfg, dict):
            return False, f"Battlegroup role `{key}` is not configured."
        role_obj = guild.get_role(role_cfg.get("id"))
        if role_obj is None:
            return False, f"Battlegroup role `{key}` is missing on this server."

        lines = [f"Battlegroup report: {str(key).upper()}", f"Members: {len(role_obj.members)}"]
        for member in sorted(role_obj.members, key=lambda m: (getattr(m, "display_name", "").lower(), m.id))[:50]:
            prestige = self._compute_user_prestige(guild, member.id)
            lines.append(f"- {member.display_name} | prestige: {prestige if prestige is not None else 'n/a'}")
        if len(role_obj.members) > 50:
            lines.append("...")
        return True, "\n".join(lines)

    async def _run_diagnostics(self, interaction: discord.Interaction) -> tuple[bool, str]:
        guild = getattr(interaction, "guild", None)
        if guild is None:
            return False, "This action can only be used in a server."
        cfg = Alliance.get_guild_config(guild.id)
        caps = _caps_for(interaction.user, guild, cfg)
        if "reports" not in caps:
            return False, "You do not have permission to view alliance reports."
        report = Alliance.get_alliance_diagnostics(guild)
        lines = report.get("lines") or []
        header = "Alliance diagnostics: PASS" if report.get("ok") else "Alliance diagnostics: FAIL"
        body = "\n".join(str(line) for line in lines[:25]) if lines else "No diagnostics data is available."
        if len(lines) > 25:
            body += "\n..."
        return bool(report.get("ok")), f"{header}\n{body}"

    async def _set_alliance_type(self, interaction: discord.Interaction, type_name: str) -> tuple[bool, str]:
        guild = getattr(interaction, "guild", None)
        if guild is None:
            return False, "This action can only be used in a server."
        cfg = Alliance.get_guild_config(guild.id)
        caps = _caps_for(interaction.user, guild, cfg)
        if "settings" not in caps:
            return False, "You do not have permission to manage alliance settings."
        if not cfg:
            return False, "No alliance is configured for this guild."
        type_norm = Alliance.normalize_alliance_type(type_name)
        ok = Alliance.set_alliance_type(guild.id, type_norm, guild_obj=guild)
        return (True, f"Alliance type set to `{type_norm}`.") if ok else (False, "Failed to set alliance type.")

    async def _delete_alliance(self, interaction: discord.Interaction) -> tuple[bool, str]:
        guild = getattr(interaction, "guild", None)
        if guild is None:
            return False, "This action can only be used in a server."
        cfg = Alliance.get_guild_config(guild.id)
        caps = _caps_for(interaction.user, guild, cfg)
        if "delete" not in caps:
            return False, "You do not have permission to delete this alliance."
        if not cfg:
            return False, "No alliance is configured for this guild."
        ok = await Alliance.unregister_alliance(guild, remove_roles=False)
        return (True, "Alliance unregistered.") if ok else (False, "Failed to unregister alliance.")

    async def cog_load(self):
        try:
            self.bot.tree.remove_command("alliance")
        except Exception:
            pass
        try:
            self.bot.tree.add_command(self._group, override=True)
            log.info("Alliance slash group registered")
        except Exception:
            log.exception("Failed to register alliance slash group")

    async def cog_unload(self):
        try:
            self.bot.tree.remove_command("alliance")
        except Exception:
            pass


async def setup(bot):
    try:
        await bot.add_cog(AllianceSlashCog(bot))
    except Exception:
        log.exception("Failed to add AllianceSlashCog")
