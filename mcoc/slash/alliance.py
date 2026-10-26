# Path: mcoc/slash/alliance.py
"""Slash alliance commands and lightweight guild status helpers."""

import logging
from typing import Any, Optional

import discord
from redbot.core import app_commands, commands

from ..common.components.componentsV2 import CDTAutoCleanupView
from ..common.helpers import alliance as Alliance

log = logging.getLogger("red.mcoc.slash.alliance")


def _core_for(bot: Any) -> Any:
    core = getattr(bot, "mcoc_core", None)
    if core is not None:
        return core
    get_cog = getattr(bot, "get_cog", None)
    if callable(get_cog):
        return get_cog("MCOC") or get_cog("MCOCPrefix") or bot
    return bot


def _is_alliance_admin(member: discord.Member, guild: discord.Guild) -> bool:
    try:
        return bool(getattr(member, "guild_permissions", None) and member.guild_permissions.manage_guild) or Alliance.is_alliance_manager(member, guild)
    except Exception:
        return False


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


class _AllianceRootView(CDTAutoCleanupView):
    def __init__(self, cog: "AllianceSlashCog", target: Optional[discord.Member]):
        super().__init__(timeout=180)
        self.cog = cog
        self.target = target

    async def _refresh(self, interaction: discord.Interaction, status: Optional[str] = None):
        content = self.cog._build_root_message(interaction, self.target, status=status)
        try:
            await interaction.response.edit_message(content=content, view=self)
        except Exception:
            try:
                await interaction.edit_original_response(content=content, view=self)
            except Exception:
                pass

    @discord.ui.button(label="CREATE SIMPLE", style=discord.ButtonStyle.primary)
    async def create_simple(self, interaction: discord.Interaction, _button: discord.ui.Button):
        ok, msg = await self.cog._create_alliance(interaction, "simple")
        await self._refresh(interaction, status=msg if ok else msg)

    @discord.ui.button(label="CREATE ADVANCED", style=discord.ButtonStyle.primary)
    async def create_advanced(self, interaction: discord.Interaction, _button: discord.ui.Button):
        ok, msg = await self.cog._create_alliance(interaction, "advanced")
        await self._refresh(interaction, status=msg if ok else msg)

    @discord.ui.button(label="JOIN", style=discord.ButtonStyle.success)
    async def join(self, interaction: discord.Interaction, _button: discord.ui.Button):
        ok, msg = await self.cog._join_self(interaction)
        await self._refresh(interaction, status=msg if ok else msg)

    @discord.ui.button(label="PROFILE", style=discord.ButtonStyle.secondary)
    async def profile(self, interaction: discord.Interaction, _button: discord.ui.Button):
        ok, msg = await self.cog._profile_for_target(interaction, self.target)
        await self._refresh(interaction, status=msg if ok else msg)

    @discord.ui.button(label="MANAGE TARGET", style=discord.ButtonStyle.secondary)
    async def manage_target(self, interaction: discord.Interaction, _button: discord.ui.Button):
        guild = getattr(interaction, "guild", None)
        if guild is None:
            await self._refresh(interaction, status="This action can only be used in a server.")
            return
        if not _is_alliance_admin(interaction.user, guild):
            await self._refresh(interaction, status="You do not have alliance management permissions.")
            return
        if self.target is None:
            await self._refresh(interaction, status="Select a target user with `/alliance @user` before using MANAGE TARGET.")
            return
        try:
            from .contextmenu import _AllianceManageMemberView

            view = _AllianceManageMemberView(self.cog.core, interaction.user, self.target)
            await interaction.response.edit_message(
                content=f"Alliance manage for {self.target.mention}. Choose an action:",
                view=view,
            )
            await view.bind_to_interaction_response(interaction)
        except Exception:
            log.exception("Failed to open alliance manage target workflow")
            await self._refresh(interaction, status="Unable to open manage workflow right now.")

    @discord.ui.button(label="TYPE SIMPLE", style=discord.ButtonStyle.secondary)
    async def set_type_simple(self, interaction: discord.Interaction, _button: discord.ui.Button):
        ok, msg = await self.cog._set_alliance_type(interaction, "simple")
        await self._refresh(interaction, status=msg if ok else msg)

    @discord.ui.button(label="TYPE ADVANCED", style=discord.ButtonStyle.secondary)
    async def set_type_advanced(self, interaction: discord.Interaction, _button: discord.ui.Button):
        ok, msg = await self.cog._set_alliance_type(interaction, "advanced")
        await self._refresh(interaction, status=msg if ok else msg)

    @discord.ui.button(label="DIAGNOSTICS", style=discord.ButtonStyle.success)
    async def diagnostics(self, interaction: discord.Interaction, _button: discord.ui.Button):
        ok, msg = await self.cog._run_diagnostics(interaction)
        await self._refresh(interaction, status=msg if ok else msg)

    @discord.ui.button(label="DELETE", style=discord.ButtonStyle.danger)
    async def delete(self, interaction: discord.Interaction, _button: discord.ui.Button):
        ok, msg = await self.cog._delete_alliance(interaction)
        await self._refresh(interaction, status=msg if ok else msg)


class AllianceSlashCog(commands.Cog):
    def __init__(self, bot: Any):
        self.bot = bot
        self.core = _core_for(bot)

    @property
    def group(self):
        # Keep a registerable surface for slash-core compatibility checks.
        return self.alliance

    def _build_root_message(self, interaction: discord.Interaction, target: Optional[discord.Member], *, status: Optional[str] = None) -> str:
        guild = getattr(interaction, "guild", None)
        if guild is None:
            base = "Alliance commands are available in servers only."
        else:
            cfg = Alliance.get_guild_config(guild.id)
            target_display = getattr(target, "mention", None) or getattr(interaction.user, "mention", "you")
            if cfg:
                base = _build_alliance_profile_text(cfg, guild, target or interaction.user)
            else:
                base = f"No alliance is configured for this guild yet. Target: {target_display}."
            base += "\n\nUse the buttons below to run the alliance workflow from this message."
        if status:
            base += f"\n\nStatus: {status}"
        return base

    async def _create_alliance(self, interaction: discord.Interaction, type_name: str) -> tuple[bool, str]:
        guild = getattr(interaction, "guild", None)
        if guild is None:
            return False, "This action can only be used in a server."
        if not getattr(interaction.user, "guild_permissions", None) or not interaction.user.guild_permissions.manage_guild:
            return False, "You need Manage Server permissions to create an alliance."
        cfg = Alliance.get_guild_config(guild.id)
        if cfg:
            return False, "An alliance is already configured for this guild."
        name = (guild.name or "Alliance").strip()
        type_norm = Alliance.normalize_alliance_type(type_name)
        ok = await Alliance.register_alliance(guild, name, alliance_tag=None, type_=type_norm)
        if ok:
            return True, f"Alliance **{name}** created as `{type_norm}`."
        return False, "Failed to create alliance. Check bot permissions and logs."

    async def _set_alliance_type(self, interaction: discord.Interaction, type_name: str) -> tuple[bool, str]:
        guild = getattr(interaction, "guild", None)
        if guild is None:
            return False, "This action can only be used in a server."
        if not _is_alliance_admin(interaction.user, guild):
            return False, "You do not have alliance management permissions."
        cfg = Alliance.get_guild_config(guild.id)
        if not cfg:
            return False, "No alliance is configured for this guild."
        type_norm = Alliance.normalize_alliance_type(type_name)
        ok = Alliance.set_alliance_type(guild.id, type_norm, guild_obj=guild)
        if ok:
            return True, f"Alliance type set to `{type_norm}`."
        return False, "Failed to set alliance type."

    async def _run_diagnostics(self, interaction: discord.Interaction) -> tuple[bool, str]:
        guild = getattr(interaction, "guild", None)
        if guild is None:
            return False, "This action can only be used in a server."
        if not _is_alliance_admin(interaction.user, guild):
            return False, "You do not have alliance management permissions."
        report = Alliance.get_alliance_diagnostics(guild)
        lines = report.get("lines") or []
        if not lines:
            return False, "No diagnostics data is available."
        header = "Alliance diagnostics: PASS" if report.get("ok") else "Alliance diagnostics: FAIL"
        body = "\n".join(str(line) for line in lines[:20])
        if len(lines) > 20:
            body += "\n..."
        return bool(report.get("ok")), f"{header}\n{body}"

    async def _join_self(self, interaction: discord.Interaction) -> tuple[bool, str]:
        guild = getattr(interaction, "guild", None)
        if guild is None:
            return False, "This action can only be used in a server."
        return await Alliance.join_alliance(interaction.user, guild, role_key="members")

    async def _profile_for_target(self, interaction: discord.Interaction, target: Optional[discord.Member]) -> tuple[bool, str]:
        guild = getattr(interaction, "guild", None)
        if guild is None:
            return False, "This action can only be used in a server."
        cfg = Alliance.get_guild_config(guild.id)
        if not cfg:
            return False, "No alliance is configured for this guild."
        member = target or interaction.user
        return True, _build_alliance_profile_text(cfg, guild, member)

    async def _delete_alliance(self, interaction: discord.Interaction) -> tuple[bool, str]:
        guild = getattr(interaction, "guild", None)
        if guild is None:
            return False, "This action can only be used in a server."
        if not _is_alliance_admin(interaction.user, guild):
            return False, "You do not have permission to delete this alliance."
        cfg = Alliance.get_guild_config(guild.id)
        if not cfg:
            return False, "No alliance is configured for this guild."
        ok = await Alliance.unregister_alliance(guild, remove_roles=False)
        if ok:
            return True, "Alliance unregistered."
        return False, "Failed to unregister alliance."

    @app_commands.command(name="alliance", description="Run the alliance workflow for yourself or a selected member")
    @app_commands.describe(user="Optional member target for profile/manage workflows")
    async def alliance(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        view = _AllianceRootView(self, user)
        content = self._build_root_message(interaction, user)
        await interaction.response.send_message(content, view=view, ephemeral=True)
        await view.bind_to_interaction_response(interaction)

    async def cog_load(self):
        try:
            self.bot.tree.remove_command("alliance")
        except Exception:
            pass
        try:
            self.bot.tree.add_command(self.alliance, override=True)
            log.info("Alliance slash root command registered")
        except Exception:
            log.exception("Failed to register alliance slash root command")

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