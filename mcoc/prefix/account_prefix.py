# mcoc/prefix/account_prefix.py
import logging
from typing import Any, Optional, Callable, Dict

from redbot.core import commands

log = logging.getLogger("red.mcoc.prefix.account")

from ..common.embeds import cdt_embed
from ..common.champion_helpers import safe_send_ctx
from ..common.roster_helpers import ensure_user_manager
from ..common.roster_helpers import _ensure_hook_registered
from ..common.prefix_utils import get_runtime_prefix
from ..common.account_helpers import (
    ALLOWED_PROFILE_FIELDS,
    FIELD_CANONICAL,
    format_profile_embed,
    validate_profile_field,
    link_account as helper_link_account,
    unlink_account as helper_unlink_account,
    delete_user_profile as helper_delete_user_profile,
)

from ..common.pagination import PagesMenu

ACCOUNT_GROUP_HELP = "Account commands: info, view, set, link, unlink, delete, privacy, settings"

class AccountPrefix(commands.Cog):
    """
    Prefix commands for user account/profile management.
    """

    def __init__(self, bot_or_parent: Any):
        if hasattr(bot_or_parent, "bot") and hasattr(bot_or_parent, "cache"):
            self.parent = bot_or_parent
            self.bot = bot_or_parent.bot
        else:
            self.parent = None
            self.bot = bot_or_parent

        try:
            _ensure_hook_registered(self.parent)
        except Exception:
            pass

    async def _require_parent(self, ctx) -> bool:
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

    @commands.group(name="account", invoke_without_command=True)
    async def account(self, ctx):
        """Top-level account group help"""
        await safe_send_ctx(ctx, ACCOUNT_GROUP_HELP)

    @account.command(name="help")
    async def account_help(self, ctx):
        """Show account help and allowed fields"""
        prefix = get_runtime_prefix(ctx, default="///")
        lines = [
            ACCOUNT_GROUP_HELP,
            "",
            "**Fields you can set (allowed):**",
        ]
        # ALLOWED_PROFILE_FIELDS may be a dict mapping field->meta
        for field, meta in ALLOWED_PROFILE_FIELDS.items():
            desc = meta.get("desc") if isinstance(meta, dict) else str(meta)
            lines.append(f"**{field}**: {desc}")
        lines.append("")
        lines.append("Examples:")
        lines.append(f"- `{prefix}mcoc account set display_name \"Jason W\"`")
        lines.append(f"- `{prefix}mcoc account set mcoc_id 123456`")
        lines.append(f"- `{prefix}mcoc account settings`  — show your saved settings")
        lines.append(f"- `{prefix}mcoc account view @User`  — view another user's profile (subject to privacy)")
        await safe_send_ctx(ctx, "\n".join(lines))


    @account.command(name="info")
    async def account_info(self, ctx):
        """Show a short summary of your account and linked status."""
        if not await self._require_parent(ctx):
            return
        users = ensure_user_manager(self.parent)
        profile = users.get_profile(ctx.author.id) or {}
        linked = profile.get("linked", False)
        mcoc_id = profile.get("mcoc_id") or "Not linked"
        await safe_send_ctx(ctx, f"Account summary: linked={linked}, mcoc_id={mcoc_id}")

    @account.command(name="view")
    async def account_view(self, ctx, member: Optional[Any] = None):
        """View a user's profile. If no member is provided, view your own.

        This builds a Collector-style profile embed: linked status, mcoc id,
        prestige summary and Top 5 champions (by persisted prestige if available),
        plus the common profile fields.
        """
        if not await self._require_parent(ctx):
            return

        users = ensure_user_manager(self.parent)
        _ensure_hook_registered(self.parent)

        # Resolve target id robustly: Member object, mention, or raw id
        try:
            if member is None:
                target_id = ctx.author.id
            else:
                target_id = getattr(member, "id", None)
                if target_id is None:
                    # strip mention formatting like <@!123456>
                    s = str(member).strip()
                    s = s.strip("<@!>")
                    target_id = int(s)
            target_id = int(target_id)
        except Exception:
            await safe_send_ctx(ctx, "Invalid user specified.")
            return

        # Permission check (use users.can_view_profile if available)
        guild_id = getattr(ctx.guild, "id", None)
        viewer_alliance = None
        try:
            if hasattr(users, "can_view_profile"):
                allowed = users.can_view_profile(ctx.author.id, target_id, guild_id=guild_id, viewer_alliance=viewer_alliance)
                if not allowed:
                    await safe_send_ctx(ctx, "You do not have permission to view that profile.")
                    return
        except Exception:
            if ctx.author.id != target_id:
                await safe_send_ctx(ctx, "You do not have permission to view that profile.")
                return

        # Fetch profile
        try:
            profile = users.get_profile(target_id) or {}
        except Exception:
            profile = {}

        if not profile:
            await safe_send_ctx(ctx, "No profile found for that user.")
            return

        # Try to build a rich embed with roster summary (Top 5 + prestige)
        try:
            import discord
        except Exception:
            discord = None

        # Resolve display name (prefer canonical mapping)
        display_name = profile.get(FIELD_CANONICAL.get("display_name", "mcoc_name")) or profile.get("display_name") or profile.get("mcoc_name") or getattr(ctx.guild.get_member(target_id), "display_name", None) if ctx.guild else None
        if not display_name:
            # fallback to discord username if possible
            try:
                member_obj = ctx.guild.get_member(target_id) if ctx.guild else None
                display_name = member_obj.display_name if member_obj else str(target_id)
            except Exception:
                display_name = str(target_id)

        # Gather roster and prestige info (best-effort)
        prestige_map = {}
        top5_names = []
        total_prestige = None
        try:
            # prefer persisted prestige_map in profile
            prestige_map = profile.get("prestige_map", {}) or {}
        except Exception:
            prestige_map = {}

        # load roster (sync or async)
        roster = []
        try:
            if asyncio.iscoroutinefunction(getattr(users, "list_roster", None)):
                roster = await users.list_roster(target_id)
            else:
                roster = users.list_roster(target_id) or []
        except Exception:
            roster = []

        # Resolve champion names and prestige values
        cache = getattr(self.parent, "cache", None)
        entries: list = []
        for e in roster:
            try:
                slug = str(e.get("champion") or "").strip()
                stars = int(e.get("rarity") or e.get("stars") or 0)
                # prestige lookup: try persisted map first
                key = f"{slug}|{stars}"
                p = None
                if key in prestige_map and prestige_map.get(key) is not None:
                    try:
                        p = int(prestige_map.get(key))
                    except Exception:
                        p = None
                # fallback: try cache.get_prestige_value if available
                if p is None and cache and hasattr(cache, "get_prestige_value"):
                    try:
                        p = cache.get_prestige_value(slug, stars, int(e.get("rank") or 1), int(e.get("ascended") or 0), int(e.get("sig") or 0))
                    except Exception:
                        p = None
                # resolve champion display name
                champ_name = None
                if cache:
                    try:
                        cobj = cache.get_champion(slug)
                        if cobj:
                            champ_name = cobj.get("name") or cobj.get("slug") or slug
                    except Exception:
                        champ_name = None
                if not champ_name:
                    champ_name = slug or (e.get("name") if isinstance(e.get("name"), str) else None) or "Unknown"
                entries.append({"name": champ_name, "prestige": p or 0})
            except Exception:
                continue

        # sort by prestige desc, then take top 5
        try:
            entries.sort(key=lambda x: (-int(x.get("prestige") or 0), x.get("name")))
        except Exception:
            pass
        top5 = entries[:5]
        top5_names = [f"{i+1}. {it['name']} [{it['prestige']}]" for i, it in enumerate(top5)]
        try:
            total_prestige = sum(int(it.get("prestige") or 0) for it in entries)
        except Exception:
            total_prestige = None

        # Build embed
        try:
            if discord:
                emb = cdt_embed(ctx, title=f"{display_name} — Profile", colour=discord.Color.blue())
                # author / thumbnail
                try:
                    member_obj = ctx.guild.get_member(target_id) if ctx.guild else None
                    if member_obj and getattr(member_obj, "avatar_url", None):
                        emb.set_author(name=f"{display_name}", icon_url=member_obj.avatar_url)
                        emb.set_thumbnail(url=member_obj.avatar_url)
                    else:
                        emb.set_author(name=f"{display_name}")
                except Exception:
                    emb.set_author(name=f"{display_name}")

                # linked / mcoc id
                linked = profile.get("linked", False)
                mcoc_id = profile.get("mcoc_id") or profile.get("mcoc_name") or profile.get("mcoc_id")
                emb.add_field(name="Linked", value=str(bool(linked)), inline=True)
                emb.add_field(name="MCoc ID", value=str(mcoc_id) if mcoc_id else "Not linked", inline=True)

                # Prestige summary
                if total_prestige is not None:
                    emb.add_field(name="Prestige (sum)", value=str(total_prestige), inline=False)
                if top5_names:
                    emb.add_field(name="Top 5 Champions", value="\n".join(top5_names), inline=False)
                else:
                    emb.add_field(name="Top 5 Champions", value="No roster or prestige data available.", inline=False)

                # Add other profile fields from FIELD_CANONICAL in a sensible order
                for user_field, stored_key in FIELD_CANONICAL.items():
                    # skip display_name and mcoc_id already shown
                    if user_field in ("display_name", "mcoc_id"):
                        continue
                    val = profile.get(stored_key)
                    if val is None:
                        # try alternate keys
                        val = profile.get(user_field)
                    if val is not None:
                        emb.add_field(name=user_field.replace("_", " ").title(), value=str(val), inline=True)

                emb.set_footer(text="Profile generated by MCOC")
                await ctx.send(embed=emb)
                return
        except Exception:
            # fall through to text fallback
            pass

        # Text fallback: stable, readable output
        lines = []
        lines.append(f"Profile — {display_name}")
        linked = profile.get("linked", False)
        mcoc_id = profile.get("mcoc_id") or profile.get("mcoc_name")
        lines.append(f"Linked: {linked}")
        lines.append(f"MCoc ID: {mcoc_id or 'Not linked'}")
        if total_prestige is not None:
            lines.append(f"Prestige (sum): {total_prestige}")
        if top5_names:
            lines.append("Top 5 Champions:")
            lines.extend(top5_names)
        else:
            lines.append("Top 5 Champions: none")
        # include canonical settings
        try:
            settings = {user_field: profile.get(stored_key) for user_field, stored_key in FIELD_CANONICAL.items()}
            lines.append("")
            lines.append("Profile fields:")
            lines.append(str(settings))
        except Exception:
            pass

        await safe_send_ctx(ctx, "\n".join(lines))
        
    @account.command(name="set")
    async def account_set(self, ctx, field: str, *, value: str):
        """Set a profile field. Example: ///mcoc account set mcoc_name Jason"""
        if not await self._require_parent(ctx):
            return

        if not validate_profile_field(field):
            allowed = ", ".join(sorted(ALLOWED_PROFILE_FIELDS.keys()))
            await safe_send_ctx(ctx, f"Invalid field. Allowed fields: {allowed}")
            return
        users = ensure_user_manager(self.parent)
        _ensure_hook_registered(self.parent)

        try:
            stored_key = FIELD_CANONICAL.get(field, field)
            users.set_profile_field(ctx.author.id, stored_key, value)
            await safe_send_ctx(ctx, f"Set **{field}** to `{value}`.")
        except Exception:
            log.exception("Failed to set profile field")
            await safe_send_ctx(ctx, "Failed to update profile.")

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
            prompt = "Are you sure you want to delete your profile and roster? Reply with `yes` to confirm."
            confirmed, _ = await PagesMenu.confirm(self.bot, ctx, prompt, timeout=20.0)
            if not confirmed:
                await safe_send_ctx(ctx, "Deletion cancelled.")
                return

            ok, msg = helper_delete_user_profile(self.parent, ctx.author.id)
            await safe_send_ctx(ctx, msg)
        except Exception:
            log.exception("Failed to delete user data")
            await safe_send_ctx(ctx, "Failed to delete profile.")

    @account.command(name="settings")
    async def account_settings(self, ctx):
        """Show your current saved profile settings (editable fields)."""
        if not await self._require_parent(ctx):
            return
        users = ensure_user_manager(self.parent)
        try:
            profile = users.get_profile(ctx.author.id) or {}
            settings = {user_field: profile.get(stored_key) for user_field, stored_key in FIELD_CANONICAL.items()}
            await safe_send_ctx(ctx, f"Your settings: ```json\n{settings}\n```")
        except Exception:
            log.exception("Failed to fetch settings")
            await safe_send_ctx(ctx, "Failed to fetch settings.")

    @account.group(name="privacy", invoke_without_command=True)
    async def account_privacy(self, ctx):
        await safe_send_ctx(ctx, "Privacy commands: mode, allow_guild, revoke_guild")

    @account_privacy.command(name="mode")
    async def privacy_mode(self, ctx, mode: str):
        """Set privacy mode: private | guild | alliance | public"""
        if not await self._require_parent(ctx):
            return
        mode = mode.lower()
        try:
            users = ensure_user_manager(self.parent)
            users.set_privacy_mode(ctx.author.id, mode)
            await safe_send_ctx(ctx, f"Privacy mode set to **{mode}**.")
        except ValueError:
            await safe_send_ctx(ctx, "Invalid privacy mode. Choose one of: private, guild, alliance, public.")
        except Exception:
            log.exception("Failed to set privacy mode")
            await safe_send_ctx(ctx, "Failed to update privacy settings.")

    @account_privacy.command(name="allow_guild")
    async def privacy_allow_guild(self, ctx, guild_id: int):
        """Allow sharing with a specific guild (by id)."""
        if not await self._require_parent(ctx):
            return
        users = ensure_user_manager(self.parent)
        try:
            users.allow_guild(ctx.author.id, guild_id)
            await safe_send_ctx(ctx, f"Allowed sharing with guild `{guild_id}`.")
        except Exception:
            log.exception("Failed to allow guild")
            await safe_send_ctx(ctx, "Failed to update privacy settings.")

    @account_privacy.command(name="revoke_guild")
    async def privacy_revoke_guild(self, ctx, guild_id: int):
        """Revoke sharing with a specific guild (by id)."""
        if not await self._require_parent(ctx):
            return
        users = ensure_user_manager(self.parent)
        try:
            users.revoke_guild(ctx.author.id, guild_id)
            await safe_send_ctx(ctx, f"Revoked sharing with guild `{guild_id}`.")
        except Exception:
            log.exception("Failed to revoke guild")
            await safe_send_ctx(ctx, "Failed to update privacy settings.")


# -------------------------
# Registrar wrappers
# -------------------------
def register_with_group(group: commands.Group, parent_getter: Callable[[], Any]):
    """
    Attach account prefix commands to the provided `group`.
    parent_getter is a callable returning the core/parent object (or None).
    """
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

    # info alias for view
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

    @_safe_add("view")
    async def _view(ctx, member: Optional[Any] = None):
        parent = parent_getter()
        if not parent:
            await safe_send_ctx(ctx, "MCOC core not attached; account unavailable.")
            return
        users = ensure_user_manager(parent)

        # resolve target id
        try:
            target_id = ctx.author.id if member is None else getattr(member, "id", member)
            target_id = int(target_id)
        except Exception:
            await safe_send_ctx(ctx, "Invalid user specified.")
            return

        profile = users.get_profile(int(target_id)) or {}
        if not profile:
            await safe_send_ctx(ctx, "No profile found.")
            return

        # Prefer embed formatting via shared helper
        try:
            emb = format_profile_embed(ctx, profile, member)
            await ctx.send(embed=emb)
            return
        except Exception:
            # fallback to stable text output (canonical keys)
            settings = {user_field: profile.get(stored_key) for user_field, stored_key in FIELD_CANONICAL.items()}
            await safe_send_ctx(ctx, f"Profile: ```json\n{settings}\n```")

    @_safe_add("set")
    async def _set(ctx, field: str, *, value: str):
        """Set a profile field. Allowed: see ///mcoc account help"""
        parent = parent_getter()
        if not parent:
            await safe_send_ctx(ctx, "MCOC core not attached; account unavailable.")
            return

        field = (field or "").strip()
        # validate against user-visible allowed fields
        if not validate_profile_field(field):
            await safe_send_ctx(ctx, "Invalid field. Allowed: " + ", ".join(sorted(ALLOWED_PROFILE_FIELDS.keys())))
            return

        # normalize booleans and enums using ALLOWED_PROFILE_FIELDS metadata if available
        meta = ALLOWED_PROFILE_FIELDS.get(field, {})
        try:
            if isinstance(meta, dict) and meta.get("type") == "bool":
                val = str(value).strip().lower() in ("1", "true", "yes", "on")
            elif field == "privacy_mode":
                val = str(value).strip().lower()
                if val not in ("private", "guild", "alliance", "public"):
                    await safe_send_ctx(ctx, "Invalid privacy_mode. Allowed: private, guild, alliance, public.")
                    return
            else:
                val = value.strip()
        except Exception:
            val = value.strip()

        users = ensure_user_manager(parent)
        try:
            # map user-visible field to stored key
            stored_key = FIELD_CANONICAL.get(field, field)
            users.set_profile_field(ctx.author.id, stored_key, val)
            await safe_send_ctx(ctx, f"Set **{field}** to `{val}`.")
        except Exception:
            log.exception("Failed to set profile field")
            await safe_send_ctx(ctx, "Failed to set profile field.")

    @_safe_add("settings")
    async def _settings(ctx):
        """Show your current saved profile settings (editable fields)."""
        parent = parent_getter()
        if not parent:
            await safe_send_ctx(ctx, "MCOC core not attached; account unavailable.")
            return
        users = ensure_user_manager(parent)
        try:
            profile = users.get_profile(ctx.author.id) or {}
            # present user-visible keys mapped to stored keys
            settings = {user_field: profile.get(stored_key) for user_field, stored_key in FIELD_CANONICAL.items()}
            await safe_send_ctx(ctx, f"Your settings: ```json\n{settings}\n```")
        except Exception:
            log.exception("Failed to fetch settings")
            await safe_send_ctx(ctx, "Failed to fetch settings.")

    @_safe_add("link")
    async def _link(ctx, mcoc_id: Optional[str] = None):
        parent = parent_getter()
        if not parent:
            await safe_send_ctx(ctx, "MCOC core not attached; account unavailable.")
            return
        if mcoc_id is None:
            prefix = getattr(ctx, "prefix", None) or "///"
            await safe_send_ctx(ctx, f"Usage: {prefix}mcoc account link <mcoc_id>")
            return
        users = ensure_user_manager(parent)
        try:
            users.set_profile_field(ctx.author.id, "mcoc_id", str(mcoc_id).strip())
            users.set_profile_field(ctx.author.id, "linked", True)
            await safe_send_ctx(ctx, f"Linked your account to MCoc id `{mcoc_id}`.")
        except Exception:
            await safe_send_ctx(ctx, "Failed to link account.")

    @_safe_add("unlink")
    async def _unlink(ctx):
        parent = parent_getter()
        if not parent:
            await safe_send_ctx(ctx, "MCOC core not attached; account unavailable.")
            return
        users = ensure_user_manager(parent)
        try:
            users.set_profile_field(ctx.author.id, "mcoc_id", None)
            users.set_profile_field(ctx.author.id, "linked", False)
            await safe_send_ctx(ctx, "Unlinked your account.")
        except Exception:
            await safe_send_ctx(ctx, "Failed to unlink account.")

    @_safe_add("delete")
    async def _delete(ctx):
        parent = parent_getter()
        if not parent:
            await safe_send_ctx(ctx, "MCOC core not attached; account unavailable.")
            return
        users = ensure_user_manager(parent)
        try:
            prompt = "Are you sure you want to delete your profile and roster? Reply with `yes` to confirm."
            confirmed, _ = await PagesMenu.confirm(ctx.bot, ctx, prompt, timeout=20.0)
            if not confirmed:
                await safe_send_ctx(ctx, "Deletion cancelled.")
                return
            users.delete_user(ctx.author.id)
            await safe_send_ctx(ctx, "Deleted your profile.")
        except Exception:
            await safe_send_ctx(ctx, "Failed to delete profile.")

    @_safe_add("privacy")
    async def _privacy_group(ctx):
        await safe_send_ctx(ctx, "Privacy commands: mode, allow_guild, revoke_guild")

    @_safe_add("privacy mode")
    async def _privacy_mode(ctx, mode: str):
        parent = parent_getter()
        if not parent:
            await safe_send_ctx(ctx, "MCOC core not attached; account unavailable.")
            return
        users = ensure_user_manager(parent)
        try:
            users.set_privacy_mode(ctx.author.id, mode)
            await safe_send_ctx(ctx, f"Set privacy mode to `{mode}`.")
        except Exception:
            await safe_send_ctx(ctx, "Failed to update privacy settings.")

    @_safe_add("privacy allow_guild")
    async def _privacy_allow(ctx, guild_id: int):
        parent = parent_getter()
        if not parent:
            await safe_send_ctx(ctx, "MCOC core not attached; account unavailable.")
            return
        users = ensure_user_manager(parent)
        try:
            users.allow_guild(ctx.author.id, guild_id)
            await safe_send_ctx(ctx, f"Allowed sharing with guild `{guild_id}`.")
        except Exception:
            await safe_send_ctx(ctx, "Failed to update privacy settings.")

    @_safe_add("privacy revoke_guild")
    async def _privacy_revoke(ctx, guild_id: int):
        parent = parent_getter()
        if not parent:
            await safe_send_ctx(ctx, "MCOC core not attached; account unavailable.")
            return
        users = ensure_user_manager(parent)
        try:
            users.revoke_guild(ctx.author.id, guild_id)
            await safe_send_ctx(ctx, f"Revoked sharing with guild `{guild_id}`.")
        except Exception:
            await safe_send_ctx(ctx, "Failed to update privacy settings.")

    log.debug("Account registrar attached to group")
