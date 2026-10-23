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
from redbot.core import commands
from redbot.core import app_commands

from ..common.components.componentsV2 import CDTPagesMenu
from ..common.helpers import account as Account

log = logging.getLogger("red.mcoc.slash.account")


class _AccountActionView(discord.ui.View):
    def __init__(self, core: Any, user_id: int, *, can_create: bool = True, can_agree: bool = True):
        super().__init__(timeout=180)
        self.core = core
        self.user_id = user_id

        profile_btn = discord.ui.Button(label="Profile", style=discord.ButtonStyle.primary)
        settings_btn = discord.ui.Button(label="Settings", style=discord.ButtonStyle.secondary)
        create_btn = discord.ui.Button(label="Create", style=discord.ButtonStyle.success)
        agree_btn = discord.ui.Button(label="Agree", style=discord.ButtonStyle.danger)

        async def _profile_cb(interaction: discord.Interaction):
            target = interaction.user
            emb, text = Account.build_profile_display(
                core,
                interaction,
                getattr(target, "id", None),
                viewer_id=getattr(interaction.user, "id", None),
                prefer_embed=True,
            )
            if emb is not None:
                await interaction.response.send_message(embed=emb, ephemeral=False)
                return
            await interaction.response.send_message(text or "No profile found for that user.", ephemeral=True)

        async def _settings_cb(interaction: discord.Interaction):
            pages = Account.build_settings_pages(
                core,
                interaction,
                getattr(interaction.user, "id", None),
                title_prefix=f"{getattr(interaction.user, 'display_name', 'User')} Account",
            )
            if not pages:
                await interaction.response.send_message("No account settings found.", ephemeral=True)
                return
            if len(pages) == 1:
                await interaction.response.send_message(embed=pages[0], ephemeral=False)
                return
            await interaction.response.send_message(embed=pages[0], view=CDTPagesMenu(pages, author=interaction.user), ephemeral=False)

        async def _create_cb(interaction: discord.Interaction):
            ok, msg = await Account.enroll_command_handler(core, interaction, user_id)
            await interaction.response.send_message(msg if ok else f"Failed to start enrollment: {msg}", ephemeral=True)

        async def _agree_cb(interaction: discord.Interaction):
            _ok, msg = await Account.handle_consent_response(core, interaction, user_id, True)
            await interaction.response.send_message(msg, ephemeral=True)

        profile_btn.callback = _profile_cb
        settings_btn.callback = _settings_cb
        create_btn.callback = _create_cb
        agree_btn.callback = _agree_cb

        if can_create:
            self.add_item(create_btn)
        if can_agree:
            self.add_item(agree_btn)
        self.add_item(profile_btn)
        self.add_item(settings_btn)


class _AccountGroup(app_commands.Group):
    def __init__(self, core: Any):
        super().__init__(name="account", description="Manage your MCOC account profile")
        self.core = core

    def _user_id(self, interaction: discord.Interaction) -> int:
        return getattr(interaction.user, "id", 0)

    @app_commands.command(name="profile", description="View an account profile")
    async def profile(self, interaction: discord.Interaction, user: Optional[discord.User] = None):
        try:
            # Acknowledge immediately so slow profile assembly cannot time out the interaction.
            await interaction.response.defer(ephemeral=False)
        except Exception:
            pass

        target = user or interaction.user
        emb, text = Account.build_profile_display(
            self.core,
            interaction,
            getattr(target, "id", None),
            viewer_id=getattr(interaction.user, "id", None),
            prefer_embed=True,
        )
        sender = interaction.followup.send if getattr(interaction.response, "is_done", lambda: False)() else interaction.response.send_message
        if emb is not None:
            await sender(embed=emb, ephemeral=False)
            return
        await sender(text or "No profile found for that user.", ephemeral=True)

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

    @app_commands.command(name="set", description="Set a profile field value")
    @app_commands.describe(field="Profile field name", value="Value to store")
    async def set(self, interaction: discord.Interaction, field: str, value: Optional[str] = None):
        user_id = self._user_id(interaction)
        name = (field or "").strip().lower()
        if not name:
            await interaction.response.send_message("Provide a profile field name to update.", ephemeral=True)
            return

        canonical = Account.FIELD_CANONICAL.get(name, name)
        if not Account.validate_profile_field(name):
            await interaction.response.send_message(
                f"Unknown profile field: {field}. Allowed fields: {', '.join(sorted(Account.FIELD_CANONICAL.keys()))}",
                ephemeral=True,
            )
            return

        raw_value = value
        if raw_value is None or str(raw_value).strip() == "":
            stored_value = None
        else:
            text = str(raw_value).strip()
            lowered = text.lower()
            if lowered in {"clear", "none", "null", "unset"}:
                stored_value = None
            elif canonical in {"roster_public", "linked", "consent"}:
                stored_value = lowered in {"1", "true", "yes", "on"}
            else:
                stored_value = text

        ok = Account.set_profile_field(self.core, user_id, canonical, stored_value)
        pretty = "not set" if stored_value is None else Account.stringify_setting_value(stored_value)
        await interaction.response.send_message(f"Updated {canonical}: {pretty}" if ok else "Failed to update profile field.", ephemeral=True)

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

    @app_commands.command(name="account", description="Open your MCOC account flow")
    async def account(self, interaction: discord.Interaction):
        user_id = getattr(interaction.user, "id", None)
        bot = getattr(self, "bot", None)
        core = getattr(bot, "mcoc_core", None)
        if core is None:
            get_cog = getattr(bot, "get_cog", None)
            if callable(get_cog):
                core = get_cog("MCOC") or get_cog("MCOCPrefix")
        if core is None:
            core = bot
        profile = Account.get_profile(core, user_id) or {}
        consented = Account.user_has_consented(core, user_id)
        view = _AccountActionView(
            core,
            user_id,
            can_create=not bool(profile),
            can_agree=not consented,
        )
        await interaction.response.send_message(
            "Choose an account action below.",
            view=view,
            ephemeral=True,
        )

    async def cog_load(self):
        core = getattr(self.bot, "mcoc_core", None) or self.bot.get_cog("MCOC") or self.bot.get_cog("MCOCPrefix")
        try:
            self._group = _AccountGroup(core or self.bot)
        except Exception:
            log.exception("Failed to initialize Account group")

        try:
            self.bot.tree.remove_command("account")
        except Exception:
            pass
        try:
            self.bot.tree.add_command(self.account, override=True)
            log.info("Added root account command to slash tree")
        except Exception:
            log.exception("Failed to add root Account command to tree")

    async def cog_unload(self):
        try:
            self.bot.tree.remove_command("account")
        except Exception:
            pass
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
