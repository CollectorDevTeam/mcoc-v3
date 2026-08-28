# mcoc/prefix/account.py
"""
Prefix command handlers for account/profile management.

This module is intentionally thin: it resolves the command context and target member (when applicable),
delegates profile logic to mcoc.common.account helpers, and sends results using safe_send_ctx.

Supported commands (examples):
  ///mcoc account set mcoc-name jjw
  ///mcoc account set start-date Oct. 15, 2015
  ///mcoc account set region US
  ///mcoc account set timezone America/Chicago

  ///mcoc account profile @member
  ///mcoc account @member            -> redirects to profile
  ///mcoc profile @member           -> alias for account profile

  ///mcoc account settings         -> show saved preferences
  ///mcoc account set              -> show attractive list of settable properties
  ///mcoc account set mcoc-name "" -> clear the setting
"""

from typing import Any, Optional, Dict
import logging
import asyncio

from redbot.core import commands

from ..common.componentsV2 import CDTEmbed, CDTConfirm, CDTPagesMenu
from ..common.prefix_utils import get_runtime_prefix, safe_send_ctx
from ..common.roster import ensure_user_manager, _ensure_hook_registered
from ..common.account import (
    ALLOWED_PROFILE_FIELDS,
    FIELD_CANONICAL,
    validate_profile_field,
    get_profile_settings,
    link_account as helper_link_account,
    unlink_account as helper_unlink_account,
    delete_user_profile as helper_delete_user_profile,
    build_profile_display,
    get_profile,
    set_profile_field,
)

log = logging.getLogger("red.mcoc.prefix.account")


# Try to import a flexible date parser from prefix_utils if available.
# If not present, we'll store the raw string as-is.
try:
    from ..common.prefix_utils import parse_flexible_date  # type: ignore
except Exception:
    parse_flexible_date = None  # type: ignore


class AccountPrefix(commands.Cog):
    """Prefix commands for user account/profile management."""

    def __init__(self, bot_or_parent: Any):
        if hasattr(bot_or_parent, "bot") and hasattr(bot_or_parent, "cache"):
            self.parent = bot_or_parent
            self.bot = bot_or_parent.bot
        else:
            self.parent = None
            self.bot = bot_or_parent

        # ensure prestige hook registered if parent available
        try:
            _ensure_hook_registered(self.parent)
        except Exception:
            pass

    async def _require_parent(self, ctx) -> bool:
        """Ensure the core/parent is attached; send a helpful message if not."""
        if not getattr(self, "parent", None):
            core = getattr(self.bot, "mcoc_core", None) or self.bot.get_cog("MCOC")
            if core:
                self.parent = core
                try:
                    _ensure_hook_registered(self.parent)
                except Exception:
                    pass
                return True
            await safe_send_ctx(ctx, "MCOC core not attached; account commands unavailable.")
            return False
        return True



    # -----------------------------
    # Group and aliases
    # -----------------------------
    @commands.group(name="account", names=["profile"], invoke_without_command=True)
    async def account(self, ctx, member: Optional[Any] = None):
        """
        Top-level account command.
        If a member is provided, redirect to profile display for that member.
        """
        if member is not None:
            # redirect to profile display
            await self.account_profile(ctx, member=member)
            return
        prefix = get_runtime_prefix(ctx, default="///")
        await safe_send_ctx(ctx, f"Account commands: info, profile, set, link, unlink, delete, privacy, settings. Use `{prefix}mcoc account help` for details.")

    @account.command(name="help")
    async def account_help(self, ctx):
        """Show account help and allowed fields (attractive embed)."""
        if not await self._require_parent(ctx):
            return
        prefix = get_runtime_prefix(ctx, default="///")

        # Build an attractive embed listing settable fields with short descriptions and examples
        try:
            emb = CDTEmbed.embed(ctx.author, title="Account Settings — What you can set", description="Set your public profile fields. Use `///mcoc account set <field> <value>` to update. Use an empty string `\"\"` to clear a value.", footer_text=f"Examples: {prefix}mcoc account set mcoc-name jjw • {prefix}mcoc account set start-date \"Oct. 15, 2015\"{CDTEmbed._footer_tag() if hasattr(CDTEmbed, '_footer_tag') else ''}")
        except Exception:
            # fallback simple embed construction
            try:
                emb = CDTEmbed(ctx.author, title="Account Settings — What you can set")
            except Exception:
                emb = None

        # If we have an embed object, add fields in a compact, attractive layout
        if emb is not None:
            # group fields into categories for readability
            personal = ["display_name", "mcoc_name", "mcoc_id", "about", "website", "invite"]
            meta = ["alliance", "job", "timezone", "region", "age", "gender", "started"]
            privacy = ["roster_public", "privacy_mode", "linked"]

            def add_field_list(name, keys):
                lines = []
                for k in keys:
                    meta_info = ALLOWED_PROFILE_FIELDS.get(k) or {}
                    desc = meta_info.get("desc", "")
                    lines.append(f"**{k}** — {desc}")
                try:
                    emb.add_field(name=name, value="\n".join(lines), inline=False)
                except Exception:
                    pass

            add_field_list("Personal", personal)
            add_field_list("Meta / Play", meta)
            add_field_list("Privacy / Flags", privacy)

            # compact examples field
            examples = [
                f"`{prefix}mcoc account set mcoc-name \"jjw\"`",
                f"`{prefix}mcoc account set start-date \"Oct 15, 2015\"`",
                f"`{prefix}mcoc account set timezone \"America/Chicago\"`",
                f"`{prefix}mcoc account set region \"US\"`",
            ]
            try:
                emb.add_field(name="Quick examples", value="\n".join(examples), inline=False)
            except Exception:
                pass

            try:
                await safe_send_ctx(ctx, None, embed=emb)
                return
            except Exception:
                # fall through to text fallback
                pass

        # Text fallback (readable)
        lines = ["Account fields you can set:"]
        for field, meta in ALLOWED_PROFILE_FIELDS.items():
            desc = meta.get("desc") if isinstance(meta, dict) else str(meta)
            lines.append(f"- **{field}**: {desc}")
        lines.append("")
        lines.append("Examples:")
        lines.append(f"- `{prefix}mcoc account set mcoc-name jjw`")
        lines.append(f"- `{prefix}mcoc account set start-date \"Oct. 15, 2015\"`")
        lines.append(f"- `{prefix}mcoc account set timezone \"America/Chicago\"`")
        await safe_send_ctx(ctx, "\n".join(lines))

    # -----------------------------
    # Profile display
    # -----------------------------
    @account.command(name="profile")
    async def account_profile(self, ctx, member: Optional[Any] = None):
        """
        Show a branded profile embed for a member (or yourself if omitted).
        """
        if not await self._require_parent(ctx):
            return

        # resolve target id
        try:
            if member is None:
                target_id = ctx.author.id
            else:
                target_id = getattr(member, "id", None)
                if target_id is None:
                    s = str(member).strip()
                    s = s.strip("<@!>")
                    target_id = int(s)
            target_id = int(target_id)
        except Exception:
            await safe_send_ctx(ctx, "Invalid user specified.")
            return

        # build display via common.account helper
        try:
            # viewer id for privacy checks
            viewer_id = getattr(ctx.author, "id", None)
            emb, text = build_profile_display(self.parent, ctx, target_id, viewer_id=viewer_id, prefer_embed=True)
            if emb is not None:
                await safe_send_ctx(ctx, None, embed=emb)
                return
            if text:
                await safe_send_ctx(ctx, text)
                return
            await safe_send_ctx(ctx, "No profile available.")
        except Exception:
            log.exception("Failed to build profile display for %s", target_id)
            await safe_send_ctx(ctx, "Failed to display profile.")

    # Shortcut: ///mcoc account (with member) already handled by group invoke_without_command

    # -----------------------------
    # Settings / show saved preferences
    # -----------------------------
    @account.command(name="settings")
    async def account_settings(self, ctx):
        """Show your current saved profile settings (editable fields)."""
        if not await self._require_parent(ctx):
            return
        try:
            users = ensure_user_manager(self.parent)
            profile = users.get_profile(ctx.author.id) or {}
            settings = get_profile_settings(profile)
            # present attractively
            try:
                emb = CDTEmbed.embed(ctx.author, title="Your Account Settings", description="Current saved preferences")
                # add fields in two columns where possible
                for k, v in settings.items():
                    try:
                        emb.add_field(name=k.replace("_", " ").title(), value=str(v) if v is not None else "Not set", inline=True)
                    except Exception:
                        pass
                await safe_send_ctx(ctx, None, embed=emb)
                return
            except Exception:
                pass
            # fallback text
            await safe_send_ctx(ctx, f"Your settings: ```json\n{settings}\n```")
        except Exception:
            log.exception("Failed to fetch settings")
            await safe_send_ctx(ctx, "Failed to fetch settings.")

    # -----------------------------
    # Set a profile field
    # -----------------------------
    @account.command(name="set")
    async def account_set(self, ctx, field: Optional[str] = None, *, value: Optional[str] = None):
        """
        Set a profile field. Use an empty string "" to clear a setting.

        Examples:
          ///mcoc account set mcoc-name jjw
          ///mcoc account set start-date "Oct 15, 2015"
          ///mcoc account set timezone "America/Chicago"
          ///mcoc account set mcoc-name ""
        """
        if not await self._require_parent(ctx):
            return

        # If no args, show the attractive settable fields help
        if not field:
            await self.account_help(ctx)
            return

        field = (field or "").strip()
        # normalize common aliases (allow hyphens and underscores)
        canonical_field = field.replace("-", "_")
        # map user-visible names to stored keys if present
        stored_key = FIELD_CANONICAL.get(canonical_field, canonical_field)

        if not validate_profile_field(canonical_field) and stored_key not in FIELD_CANONICAL.values():
            allowed = ", ".join(sorted(ALLOWED_PROFILE_FIELDS.keys()))
            await safe_send_ctx(ctx, f"Invalid field. Allowed fields: {allowed}")
            return

        # allow clearing with explicit empty string
        if value is None:
            await safe_send_ctx(ctx, f"No value provided. To clear a field use `{get_runtime_prefix(ctx, default='///')}mcoc account set {field} \"\"`.")
            return

        # interpret empty string as clear
        if value == "" or value.strip() == '""':
            new_val = None
        else:
            new_val = value.strip()

        # special handling for some fields
        if canonical_field in ("start_date", "started", "start-date", "startdate"):
            # try flexible date parsing if available
            if new_val is None:
                parsed_date = None
            elif parse_flexible_date:
                try:
                    parsed_date = parse_flexible_date(new_val)
                    # store ISO date string if parse succeeded
                    new_val = parsed_date.isoformat() if parsed_date else new_val
                except Exception:
                    # fallback to raw string
                    pass
        if canonical_field == "timezone":
            # no validation here; store raw string (caller may validate later)
            pass

        # persist via common.account helper
        try:
            ok = set_profile_field(self.parent, ctx.author.id, stored_key, new_val)
            if ok:
                if new_val is None:
                    await safe_send_ctx(ctx, f"Cleared **{field}**.")
                else:
                    await safe_send_ctx(ctx, f"Set **{field}** to `{new_val}`.")
            else:
                await safe_send_ctx(ctx, "Failed to update profile. Try again later.")
        except Exception:
            log.exception("Failed to set profile field %s for %s", stored_key, ctx.author.id)
            await safe_send_ctx(ctx, "Failed to update profile. Try again later.")

    # -----------------------------
    # Link / unlink / delete
    # -----------------------------
    @account.command(name="link")
    async def account_link(self, ctx, mcoc_id: Optional[str] = None):
        """Link your Discord account to an in-game account. Example: ///mcoc account link 123456789"""
        if not await self._require_parent(ctx):
            return
        if mcoc_id is None:
            prefix = get_runtime_prefix(ctx, default="///")
            await safe_send_ctx(ctx, f"Usage: `{prefix}mcoc account link <mcoc_id>`")
            return
        try:
            ok, msg = helper_link_account(self.parent, ctx.author.id, str(mcoc_id).strip())
            await safe_send_ctx(ctx, msg)
        except Exception:
            log.exception("Failed to link account")
            await safe_send_ctx(ctx, "Failed to link account. Try again later.")

    @account.command(name="unlink")
    async def account_unlink(self, ctx):
        """Unlink your in-game account from your Discord profile."""
        if not await self._require_parent(ctx):
            return
        try:
            ok, msg = helper_unlink_account(self.parent, ctx.author.id)
            await safe_send_ctx(ctx, msg)
        except Exception:
            log.exception("Failed to unlink account")
            await safe_send_ctx(ctx, "Failed to unlink account. Try again later.")

    @account.command(name="delete")
    async def account_delete(self, ctx):
        """Delete your user data file. This is irreversible."""
        if not await self._require_parent(ctx):
            return
        try:
            view = CDTConfirm(timeout=20.0, confirm_label="Yes", cancel_label="No")
            await ctx.send("Are you sure you want to delete your profile and roster? Click Yes to confirm.", view=view)
            confirmed = await view.wait_result()
            if not confirmed:
                await safe_send_ctx(ctx, "Deletion cancelled.")
                return
            ok, msg = helper_delete_user_profile(self.parent, ctx.author.id)
            await safe_send_ctx(ctx, msg)
        except Exception:
            log.exception("Failed to delete user data")
            await safe_send_ctx(ctx, "Failed to delete profile.")

    # -----------------------------
    # Registrar helper for legacy registration (optional)
    # -----------------------------
    @staticmethod
    def register_with_group(group: commands.Group, parent_getter):
        """
        Attach account prefix commands to an existing group (legacy registrar).
        parent_getter is a callable returning the core/parent object.
        """
        # This function mirrors the registrar pattern used elsewhere.
        # It is provided for compatibility with older code that registers commands dynamically.
        def _safe_add(cmd_name: str):
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

        # Example: attach a simple 'info' alias
        @_safe_add("info")
        async def _info(ctx, member: Optional[Any] = None):
            parent = parent_getter()
            if not parent:
                await safe_send_ctx(ctx, "MCOC core not attached; account unavailable.")
                return
            users = ensure_user_manager(parent)
            try:
                target = ctx.author.id if member is None else getattr(member, "id", member)
                profile = users.get_profile(int(target)) or {}
                await safe_send_ctx(ctx, f"Profile: ```json\n{profile}\n```")
            except Exception:
                await safe_send_ctx(ctx, "Failed to fetch profile.")

        log.debug("Account registrar attached to group (legacy)")

# Cog setup for Red (if used as a cog)
async def setup(bot):
    bot.add_cog(AccountPrefix(bot))
