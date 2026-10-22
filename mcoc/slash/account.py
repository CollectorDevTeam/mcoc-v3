# Path: mcoc/slash/account.py
# File-Version: 1.0
# File-Id: a9e96eb4-5f38-491f-a059-200bfc72f6e1
# Purpose: Provide slash command handler for MCOC account/profile commands.
# Public-API: _AccountGroup
# Last-Modified: 2026-10-22
# Used-By: mcoc/slash/core.py
# Changelog:
#   1.0 2026-10-22  Initial slash account surface aligned to prefix account backend helpers.

import logging
from typing import Optional, Any

import discord
from discord import app_commands
from redbot.core import commands

from ..common.components.componentsV2 import CDTPagesMenu
from ..common.helpers import account as Account

log = logging.getLogger("red.mcoc.slash.account")


class _AccountGroup(app_commands.Group):
    def __init__(self, core: Any):
        super().__init__(name="account", description="Manage your MCOC account profile")
        self.core = core

    def _user_id(self, interaction: discord.Interaction) -> int:
        return getattr(interaction.user, "id", 0)

    @app_commands.command(name="profile", description="View an account profile")
    async def profile(self, interaction: discord.Interaction, user: Optional[discord.User] = None):
        target = user or interaction.user
        emb, text = Account.build_profile_display(
            self.core,
            interaction,
            getattr(target, "id", None),
            viewer_id=getattr(interaction.user, "id", None),
            prefer_embed=True,
        )
        if emb is not None:
            await interaction.response.send_message(embed=emb, ephemeral=False)
            return
        await interaction.response.send_message(text or "No profile found for that user.", ephemeral=True)

    @app_commands.command(name="settings", description="View account settings")
    async def settings(self, interaction: discord.Interaction, user: Optional[discord.User] = None):
        target = user or interaction.user
        pages = Account.build_settings_pages(
            self.core,
            interaction,
            getattr(target, "id", None),
            title_prefix=f"{getattr(target, 'display_name', 'User')} Account",
        )
        if not pages:
            await interaction.response.send_message("No account settings found.", ephemeral=True)
            return
        if len(pages) == 1:
            await interaction.response.send_message(embed=pages[0], ephemeral=False)
            return
        await interaction.response.send_message(embed=pages[0], view=CDTPagesMenu(pages, author=interaction.user), ephemeral=False)

    @app_commands.command(name="select", description="View or set your active roster")
    async def select(self, interaction: discord.Interaction, roster: Optional[str] = None):
        user_id = self._user_id(interaction)
        if roster:
            ok, msg = Account.select_active_roster(self.core, user_id, roster)
            await interaction.response.send_message(msg, ephemeral=not ok)
            return

        roster_ids, active_id = Account.get_selectable_rosters(self.core, user_id)
        if not roster_ids:
            await interaction.response.send_message("No rosters are available yet. Import or add champions first.", ephemeral=True)
            return

        if len(roster_ids) == 1 and active_id != roster_ids[0]:
            ok, msg = Account.select_active_roster(self.core, user_id, roster_ids[0])
            await interaction.response.send_message(msg, ephemeral=not ok)
            return

        current = active_id or "not set"
        await interaction.response.send_message(
            f"Active roster: {current}\nAvailable rosters: {', '.join(roster_ids)}",
            ephemeral=True,
        )

    @app_commands.command(name="privacy", description="View or set your privacy mode")
    @app_commands.describe(mode="private | guild | alliance | public")
    async def privacy(self, interaction: discord.Interaction, mode: Optional[str] = None):
        user_id = self._user_id(interaction)
        modes = {"private", "guild", "alliance", "public"}
        if mode is None:
            profile = Account.get_profile(self.core, user_id) or {}
            current = profile.get("privacy_mode") or "private"
            await interaction.response.send_message(f"Current privacy mode: {current}", ephemeral=True)
            return

        lowered = mode.lower().strip()
        if lowered not in modes:
            await interaction.response.send_message("Allowed privacy modes: private, guild, alliance, public.", ephemeral=True)
            return

        ok = Account.set_profile_field(self.core, user_id, "privacy_mode", lowered)
        await interaction.response.send_message("Privacy mode updated." if ok else "Failed to update privacy mode.", ephemeral=not ok)

    @app_commands.command(name="link", description="Associate your MCOC ID to this Discord account")
    async def link(self, interaction: discord.Interaction, mcoc_id: str):
        ok, msg = Account.link_account(self.core, self._user_id(interaction), mcoc_id)
        await interaction.response.send_message(msg if ok else f"Failed to link account: {msg}", ephemeral=not ok)

    @app_commands.command(name="unlink", description="Remove your linked MCOC ID")
    async def unlink(self, interaction: discord.Interaction):
        ok, msg = Account.unlink_account(self.core, self._user_id(interaction))
        await interaction.response.send_message(msg if ok else f"Failed to unlink account: {msg}", ephemeral=not ok)

    @app_commands.command(name="agree", description="Agree to CollectorBot terms and conditions")
    async def agree(self, interaction: discord.Interaction):
        _ok, msg = await Account.handle_consent_response(self.core, interaction, self._user_id(interaction), True)
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="decline", description="Decline CollectorBot terms and conditions")
    async def decline(self, interaction: discord.Interaction):
        _ok, msg = await Account.handle_consent_response(self.core, interaction, self._user_id(interaction), False)
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="create", description="Start account enrollment and show policy links")
    async def create(self, interaction: discord.Interaction):
        ok, msg = await Account.enroll_command_handler(self.core, interaction, self._user_id(interaction))
        await interaction.response.send_message(msg if ok else f"Failed to start enrollment: {msg}", ephemeral=True)


class AccountSlashCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._group: Optional[_AccountGroup] = None

    async def cog_load(self):
        core = getattr(self.bot, "mcoc_core", None) or self.bot.get_cog("MCOC") or self.bot.get_cog("MCOCPrefix")
        try:
            self._group = _AccountGroup(core or self.bot)
            try:
                self.bot.tree.add_command(self._group)
            except Exception:
                log.exception("Failed to add Account group to tree")
        except Exception:
            log.exception("Failed to initialize Account group")

    async def cog_unload(self):
        try:
            if self._group:
                self.bot.tree.remove_command(self._group.name)
        except Exception:
            log.exception("Failed to remove Account group from tree")


async def setup(bot):
    try:
        await bot.add_cog(AccountSlashCog(bot))
    except Exception:
        log.exception("Failed to add AccountSlashCog")
