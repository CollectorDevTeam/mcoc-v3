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


def _runtime_version_label() -> str:
    try:
        import subprocess
        result = subprocess.run(["git", "-C", __file__.rsplit("mcoc", 1)[0], "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False)
        if result.returncode == 0 and result.stdout.strip():
            return f"runtime: {result.stdout.strip()}"
    except Exception:
        pass
    return "runtime: local"


class _ViewProfileModal(discord.ui.Modal):
    def __init__(self, core: Any, user_id: int, profile: Optional[dict] = None):
        super().__init__(title="Your profile")
        self.core = core
        self.user_id = user_id
        profile_data = profile or Account.get_profile(core, user_id) or {}

        self.mcoc_name = discord.ui.TextInput(
            label="MCOC username",
            default=str(profile_data.get("mcoc_name") or "")[:100],
            required=False,
            max_length=100,
            disabled=True,
        )
        self.alliance = discord.ui.TextInput(
            label="Alliance",
            default=str(profile_data.get("alliance") or "")[:100],
            required=False,
            max_length=100,
            disabled=True,
        )
        self.timezone = discord.ui.TextInput(
            label="Timezone",
            default=str(profile_data.get("timezone") or "")[:100],
            required=False,
            max_length=100,
            disabled=True,
        )
        self.website = discord.ui.TextInput(
            label="Website",
            default=str(profile_data.get("website") or "")[:250],
            required=False,
            max_length=250,
            disabled=True,
        )
        self.privacy_mode = discord.ui.TextInput(
            label="Privacy",
            default=str(profile_data.get("privacy_mode") or "private")[:50],
            required=False,
            max_length=50,
            disabled=True,
        )
        self.about = discord.ui.TextInput(
            label="About",
            default=str(profile_data.get("about") or profile_data.get("notes") or "")[:1000],
            required=False,
            max_length=1000,
            style=discord.TextStyle.long,
            disabled=True,
        )
        for item in [self.mcoc_name, self.alliance, self.timezone, self.website, self.privacy_mode, self.about]:
            self.add_item(item)


class _ProfileSettingsModal(discord.ui.Modal):
    def __init__(self, core: Any, user_id: int, profile: Optional[dict] = None):
        super().__init__(title="Edit profile")
        self.core = core
        self.user_id = user_id
        self.profile = profile or {}

        profile_data = self.profile
        fields = [
            ("MCOC username", "mcoc_name", 100),
            ("Alliance", "alliance", 100),
            ("Timezone", "timezone", 100),
            ("Website", "website", 250),
            ("Privacy mode", "privacy_mode", 50),
            ("About", "about", 1000),
        ]
        self.inputs = {}
        for label, field_name, max_length in fields:
            default = profile_data.get(field_name) or ("about" if field_name == "about" else "")
            if field_name == "about":
                text_input = discord.ui.TextInput(
                    label=label,
                    default=str(default)[:max_length],
                    required=False,
                    max_length=max_length,
                    style=discord.TextStyle.long,
                )
            else:
                text_input = discord.ui.TextInput(
                    label=label,
                    default=str(default)[:max_length],
                    required=False,
                    max_length=max_length,
                )
            self.inputs[field_name] = text_input
            self.add_item(text_input)

    async def on_submit(self, interaction: discord.Interaction):
        permitted = {"private", "guild", "alliance", "public"}
        saved = []
        for field_name, input_obj in self.inputs.items():
            value = (input_obj.value or "").strip()
            if value == "":
                continue
            if field_name == "privacy_mode":
                lowered = value.lower()
                if lowered not in permitted:
                    await interaction.response.send_message(
                        "Privacy mode must be one of: private, guild, alliance, public.",
                        ephemeral=True,
                    )
                    return
                value = lowered
            Account.set_profile_field(self.core, self.user_id, field_name, value)
            saved.append(field_name)

        if not saved:
            await interaction.response.send_message("No profile fields were updated.", ephemeral=True)
            return

        await interaction.response.send_message(
            f"Updated profile fields: {', '.join(saved)}.",
            ephemeral=True,
        )


class _AccountConsentView(discord.ui.View):
    def __init__(self, core: Any, user_id: int):
        super().__init__(timeout=180)
        self.core = core
        self.user_id = user_id

        agree_btn = discord.ui.Button(label="AGREE", style=discord.ButtonStyle.success)
        decline_btn = discord.ui.Button(label="DECLINE", style=discord.ButtonStyle.danger)

        async def _agree_cb(interaction: discord.Interaction):
            _ok, msg = await Account.handle_consent_response(core, interaction, user_id, True)
            await interaction.response.send_message(msg, ephemeral=True)

        async def _decline_cb(interaction: discord.Interaction):
            _ok, msg = await Account.handle_consent_response(core, interaction, user_id, False)
            await interaction.response.send_message(msg, ephemeral=True)

        agree_btn.callback = _agree_cb
        decline_btn.callback = _decline_cb
        self.add_item(agree_btn)
        self.add_item(decline_btn)


class _AccountPrivacyView(discord.ui.View):
    def __init__(self, core: Any, user_id: int):
        super().__init__(timeout=180)
        self.core = core
        self.user_id = user_id
        self.current_mode = (Account.get_profile(core, user_id) or {}).get("privacy_mode") or "private"
        self.current_mode = str(self.current_mode).lower()

        def _style_for(mode: str) -> discord.ButtonStyle:
            return discord.ButtonStyle.green if self.current_mode == mode.lower() else discord.ButtonStyle.gray

        self.public_btn = discord.ui.Button(label="PUBLIC", style=_style_for("public"))
        self.alliance_btn = discord.ui.Button(label="ALLIANCE", style=_style_for("alliance"))
        self.guild_btn = discord.ui.Button(label="GUILD", style=_style_for("guild"))
        self.private_btn = discord.ui.Button(label="PRIVATE", style=_style_for("private"))
        self.delete_btn = discord.ui.Button(label="DELETE", style=discord.ButtonStyle.danger)

        self._refresh_styles()

        async def _set_mode(mode: str, interaction: discord.Interaction):
            ok = Account.set_profile_field(core, user_id, "privacy_mode", mode)
            if not ok:
                await interaction.response.send_message("Failed to update privacy mode.", ephemeral=True)
                return
            self.current_mode = mode.lower()
            self._refresh_styles()
            await interaction.response.edit_message(
                content=f"Current privacy mode: {self.current_mode}\nChoose your visibility below.",
                view=self,
            )

        async def _public_cb(interaction: discord.Interaction):
            await _set_mode("public", interaction)

        async def _alliance_cb(interaction: discord.Interaction):
            await _set_mode("alliance", interaction)

        async def _guild_cb(interaction: discord.Interaction):
            await _set_mode("guild", interaction)

        async def _private_cb(interaction: discord.Interaction):
            await _set_mode("private", interaction)

        async def _delete_cb(interaction: discord.Interaction):
            ok, msg = Account.delete_user_profile(core, user_id)
            await interaction.response.send_message(msg, ephemeral=True)

        self.public_btn.callback = _public_cb
        self.alliance_btn.callback = _alliance_cb
        self.guild_btn.callback = _guild_cb
        self.private_btn.callback = _private_cb
        self.delete_btn.callback = _delete_cb

        self.add_item(self.public_btn)
        self.add_item(self.alliance_btn)
        self.add_item(self.guild_btn)
        self.add_item(self.private_btn)
        self.add_item(self.delete_btn)

    def _refresh_styles(self):
        for button, mode in [
            (self.public_btn, "public"),
            (self.alliance_btn, "alliance"),
            (self.guild_btn, "guild"),
            (self.private_btn, "private"),
        ]:
            button.style = discord.ButtonStyle.green if self.current_mode == mode else discord.ButtonStyle.gray


class _AccountManagerView(discord.ui.View):
    def __init__(self, core: Any, user_id: int):
        super().__init__(timeout=180)
        self.core = core
        self.user_id = user_id
        self.profile = {}
        self.consented = False
        self.has_account = False
        self._refresh_state()

        view_btn = discord.ui.Button(label="VIEW", style=discord.ButtonStyle.primary)
        edit_btn = discord.ui.Button(label="EDIT", style=discord.ButtonStyle.primary)
        privacy_btn = discord.ui.Button(label="PRIVACY", style=discord.ButtonStyle.secondary)
        create_btn = discord.ui.Button(label="CREATE", style=discord.ButtonStyle.success)
        consent_btn = discord.ui.Button(label="CONSENT", style=discord.ButtonStyle.danger)

        def _refresh_state_and_get_profile():
            self._refresh_state()
            return self.profile

        async def _view_cb(interaction: discord.Interaction):
            profile = _refresh_state_and_get_profile()
            if not self.has_account:
                await interaction.response.send_message("No account found. Use CREATE first.", ephemeral=True)
                return
            try:
                await interaction.response.send_modal(_ViewProfileModal(core, user_id, profile))
            except Exception:
                await interaction.response.send_message("Unable to open the profile view right now.", ephemeral=True)

        async def _edit_cb(interaction: discord.Interaction):
            profile = _refresh_state_and_get_profile()
            if not self.has_account:
                await interaction.response.send_message("No account found. Use CREATE first.", ephemeral=True)
                return
            try:
                await interaction.response.send_modal(_ProfileSettingsModal(core, user_id, profile))
            except Exception:
                await interaction.response.send_message("Unable to open the editor right now.", ephemeral=True)

        async def _privacy_cb(interaction: discord.Interaction):
            profile = _refresh_state_and_get_profile()
            current = profile.get("privacy_mode") or "private"
            await interaction.response.send_message(
                f"Current privacy mode: {current}\nChoose your visibility below.",
                view=_AccountPrivacyView(core, user_id),
                ephemeral=True,
            )

        async def _create_cb(interaction: discord.Interaction):
            self._refresh_state()
            if self.has_account:
                await interaction.response.send_message("You already have an account configured.", ephemeral=True)
                return
            await interaction.response.send_message(
                "CollectorBot stores only account fields you explicitly set. We do not save Discord API metadata.\n\nPlease review the privacy policy and then continue.",
                view=_AccountConsentView(core, user_id),
                ephemeral=True,
            )

        async def _consent_cb(interaction: discord.Interaction):
            self._refresh_state()
            if self.consented:
                await interaction.response.send_message("You have already consented to the privacy policy.", ephemeral=True)
                return
            await interaction.response.send_message(
                "CollectorBot stores only the profile fields you explicitly enter. We do not save Discord account API metadata.\n\nReview the policy and choose your decision.",
                view=_AccountConsentView(core, user_id),
                ephemeral=True,
            )

        view_btn.callback = _view_cb
        edit_btn.callback = _edit_cb
        privacy_btn.callback = _privacy_cb
        create_btn.callback = _create_cb
        consent_btn.callback = _consent_cb

        if self.has_account:
            self.add_item(view_btn)
            self.add_item(edit_btn)
            self.add_item(privacy_btn)
            if not self.consented:
                self.add_item(consent_btn)
        else:
            self.add_item(create_btn)

    def _refresh_state(self):
        self.profile = Account.get_profile(self.core, self.user_id) or {}
        self.consented = Account.user_has_consented(self.core, self.user_id)
        self.has_account = Account.user_has_profile(self.core, self.user_id) if hasattr(Account, "user_has_profile") else bool(self.profile)


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

    @app_commands.command(name="account", description="Manage your private account settings")
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

        await interaction.response.send_message(
            f"Manage your CollectorVerse account settings and privacy.\n\n{_runtime_version_label()}",
            view=_AccountManagerView(core, user_id),
            ephemeral=True,
        )

    @app_commands.command(name="profile", description="View a public CollectorBot profile")
    @app_commands.describe(user="Optional profile owner")
    async def profile(self, interaction: discord.Interaction, user: Optional[discord.User] = None):
        try:
            await interaction.response.defer(ephemeral=False)
        except Exception:
            pass

        target = user or interaction.user
        bot = getattr(self, "bot", None)
        core = getattr(bot, "mcoc_core", None)
        if core is None:
            get_cog = getattr(bot, "get_cog", None)
            if callable(get_cog):
                core = get_cog("MCOC") or get_cog("MCOCPrefix")
        if core is None:
            core = bot

        emb, text = Account.build_profile_display(
            core,
            interaction,
            getattr(target, "id", None),
            viewer_id=getattr(interaction.user, "id", None),
            prefer_embed=True,
        )

        if emb is not None:
            try:
                await interaction.followup.send(embed=emb, ephemeral=False)
            except Exception:
                await interaction.response.send_message(embed=emb, ephemeral=False)
            return

        try:
            await interaction.followup.send(text or "No profile found for that user.", ephemeral=True)
        except Exception:
            await interaction.response.send_message(text or "No profile found for that user.", ephemeral=True)

    async def cog_load(self):
        try:
            self.bot.tree.remove_command("account")
        except Exception:
            pass
        try:
            self.bot.tree.remove_command("profile")
        except Exception:
            pass
        try:
            self.bot.tree.add_command(self.account, override=True)
            self.bot.tree.add_command(self.profile, override=True)
            log.info("Added account manager and profile commands to slash tree")
        except Exception:
            log.exception("Failed to add root account/profile commands to tree")

    async def cog_unload(self):
        try:
            self.bot.tree.remove_command("account")
        except Exception:
            pass
        try:
            self.bot.tree.remove_command("profile")
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
