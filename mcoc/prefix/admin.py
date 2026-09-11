# Path: mcoc/prefix/mcocadmin_prefix.py
# File-Version: 1.0
# File-Id: e9125f87-dc2e-4f32-8d4d-e6de376c6555
# Purpose: Provide prefix command handler for MCOC admin (development / fallback).
# Public-API: MCOCAdminPrefix
# Internal: _require_parent
# Last-Modified: 2026-09-01
# Used-By: mcoc/common/__init__.py, mcoc/common/components/cache_status.py, mcoc/common/components/help_utils.py, mcoc/common/components/prefix_utils.py, mcoc/slash/__init__.py
"""
Prefix commands for MCOC admin (development / fallback).

This cog exposes a small set of owner-only admin utilities and also provides
a `register_with_group` function so the same commands can be attached to the
main ///mcoc group via the registrar pattern.
"""

from typing import Any, Dict, List, Optional
import io
import json
import re
import datetime
import asyncio
import logging
from pathlib import Path

import discord
from redbot.core import commands
from mcoc.common import Core
from mcoc.slash import admin
Embed = Core.Embed
PagesMenu = Core.PagesMenu
Confirm = Core.Confirm
Entitlements = Core.Entitlements

from mcoc.common.components.cache_status import CacheStatusPoster
from mcoc.common.components.help_utils import send_or_brand_help
from mcoc.common.components.prefix_utils import safe_send_ctx
from mcoc.common.helpers.admin_status import collect_admin_status_snapshot, build_admin_status_page_specs
from mcoc.common.adapters import cocpit_to_internal, mcochub_to_internal, mcoc_app_tierlist_to_internal



log = logging.getLogger("red.mcoc.prefix")


class CacheHealthCleanupView(discord.ui.View):
    def __init__(self, cache: Any, *, status_message: str = "Cleanup cache"):
        super().__init__(timeout=60)
        self.cache = cache
        self.status_message = status_message
        cleanup_button = discord.ui.Button(label="Cleanup Cache", style=discord.ButtonStyle.danger)
        cleanup_button.callback = self._cleanup_callback
        self.add_item(cleanup_button)

    async def _cleanup_callback(self, interaction: discord.Interaction):
        try:
            result = self.cache.cleanup_stale_cache()
            removed = result.get("removed", 0)
            if removed:
                message = f"Cleaned up {removed} stale cache file(s)."
            else:
                message = "Cache health looks good; no cleanup needed."
            await interaction.response.edit_message(content=message, view=None)
        except Exception as exc:
            log.exception("Cache cleanup action failed")
            await interaction.response.edit_message(content=f"Cleanup failed: {exc}", view=None)


def _normalize_lookup_key(value: Any) -> str:
    """Normalize names/ids for fuzzy lookup across spaces, hyphens, and punctuation."""
    if value is None:
        return ""
    text = str(value).lower().strip()
    text = text.replace("_", "-")
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def _dedupe_strings(values: List[Any]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for value in values or []:
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _champion_candidates(champ: Dict[str, Any]) -> List[str]:
    values = [
        champ.get("id"),
        champ.get("slug"),
        champ.get("name"),
        champ.get("title"),
    ]
    out: List[str] = []
    for value in values:
        if value is None:
            continue
        out.append(_normalize_lookup_key(value))
    return [item for item in out if item]


def _progression_value(champ: Dict[str, Any], key: str, default: int) -> int:
    try:
        return int(champ.get(key) if champ.get(key) is not None else default)
    except Exception:
        return default


class MCOCAdminPrefix(commands.Cog):
    """Prefix commands for MCOC admin (development / fallback)."""

    is_mcoc_prefix = True
    mcoc_version = "3.0.0"

    def __init__(self, bot_or_parent: Any):
        if hasattr(bot_or_parent, "bot") and hasattr(bot_or_parent, "cache"):
            # constructed with core-like parent
            self.parent = bot_or_parent
            self.bot = bot_or_parent.bot
        else:
            # constructed with bot instance
            self.bot = bot_or_parent
            # prefer explicit mcoc_core, then MCOC cog, then MCOCPrefix
            self.parent = getattr(self.bot, "mcoc_core", None) or self.bot.get_cog("MCOC") or self.bot.get_cog("MCOCPrefix")

    # ADMIN COMMANDS GROUP
    @commands.is_owner()
    @commands.group(name="mcocadmin", aliases=["admin"], invoke_without_command=True)
    async def admin(self, ctx, *args):
        """Admin commands for MCOC (development / fallback)."""
        if args and str(args[0]).lower() in {"help", "?"}:
            subcommands = [
                "status",
                "sync",
                "force-sync",
                "prestige_sync",
                "key",
                "features",
                "feature-enable",
                "feature-disable",
                "dump",
                "inspect",
                "export-champions",
            ]
            emb = Embed.embed(ctx, title="MCOC Admin Help", description="Owner/admin utilities for the MCOC bot.")
            Embed.add_field(ctx, emb=emb, name="Available Commands", value="\n".join(f"• `{cmd}`" for cmd in subcommands), inline=False)
            Embed.add_field(ctx, emb=emb, name="Usage", value="`///mcocadmin status`\n`///mcocadmin sync`\n`///mcocadmin help`", inline=False)
            await safe_send_ctx(ctx, None, embed=emb)
            return

        if not args:
            subcommands = ["status", "sync", "force-sync", "prestige_sync", "key", "features", "export-champions"]
            emb = Embed.embed(ctx, title="MCOC Admin", description="Owner/admin utilities for the MCOC bot.")
            Embed.add_field(ctx, emb=emb, name="Common Commands", value="\n".join(f"• `{cmd}`" for cmd in subcommands), inline=False)
            Embed.add_field(ctx, emb=emb, name="Example", value="`///mcocadmin status`", inline=False)
            await safe_send_ctx(ctx, None, embed=emb)
            return

        await safe_send_ctx(ctx, f"Unknown admin command: `{args[0]}`. Use `///mcocadmin help`.")

    # -------------------------
    # Owner-only utilities
    # -------------------------
    @admin.command(name="features")
    async def features(self, ctx):
        """List all features and their status for this guild."""
        guild_cfg = Entitlements.get_guild_config(ctx.guild.id)

        emb = Embed.embed(ctx, title="Feature Flags")

        for fname, meta in Entitlements.FEATURES.items():
            enabled = guild_cfg.feature_flags.get(fname, False)
            tier = meta["tier"]
            desc = meta["description"]
            Embed.add_field(
                ctx,
                emb=emb,
                name=f"{fname} ({tier})",
                value=f"{'ENABLED' if enabled else 'disabled'}\n{desc}",
                inline=False
            )

        await safe_send_ctx(ctx, None, embed=emb)

    @admin.command(name="feature-enable")
    async def feature_enable(self, ctx, feature: str):
        """Enable a feature for this guild."""
        guild_cfg = Entitlements.get_guild_config(ctx.guild.id)

        if feature not in Entitlements.FEATURES:
            await safe_send_ctx(ctx, f"Unknown feature: {feature}")
            return

        guild_cfg.set_flag(feature, True)
        Entitlements.log_action(guild_cfg, ctx.author.id, "enable_feature", feature)

        await safe_send_ctx(ctx, f"Feature `{feature}` enabled.")

    @admin.command(name="feature-disable")
    async def feature_disable(self, ctx, feature: str):
        """Disable a feature for this guild."""
        guild_cfg = Entitlements.get_guild_config(ctx.guild.id)

        if feature not in Entitlements.FEATURES:
            await safe_send_ctx(ctx, f"Unknown feature: {feature}")
            return

        guild_cfg.set_flag(feature, False)
        Entitlements.log_action(guild_cfg, ctx.author.id, "disable_feature", feature)

        await safe_send_ctx(ctx, f"Feature `{feature}` disabled.")

    @admin.command(name="feature-map-roles")
    @commands.has_permissions(administrator=True)
    async def feature_map_roles(self, ctx, feature: str, *roles: discord.Role):
        if feature not in Entitlements.FEATURES:
            await safe_send_ctx(ctx, f"Unknown feature: {feature}")
            return
        guild_cfg = Entitlements.get_guild_config(ctx.guild.id)
        for role in roles:
            key = f"role:{role.id}"
            ent = guild_cfg.entitlements.get(key) or {}
            tier = Entitlements.FEATURES[feature]["tier"]
            if tier == "subscriber":
                ent["subscriber"] = True
            if tier == "guild_owner_plus":
                ent["guild_owner_plus"] = True
            guild_cfg.entitlements[key] = ent
            Entitlements.log_action(guild_cfg, ctx.author.id, "map_role_feature", f"{role.id} -> {feature}")
        Entitlements.set_guild_config(ctx.guild.id, guild_cfg)
        await safe_send_ctx(ctx, f"Mapped roles {[r.name for r in roles]} to {feature}")

    @commands.is_owner()
    @admin.command(name="status")
    async def status(self, ctx):
        """Show comprehensive cache / API status for debugging."""
        parent = getattr(self, "parent", None)
        if not parent:
            await safe_send_ctx(ctx, "MCOC core not attached; cache and API unavailable.")
            return
        cache = getattr(parent, "cache", None)
        if not cache:
            await safe_send_ctx(ctx, "Cache not available on core.")
            return

        try:
            health = getattr(cache, "health_check", None)
            health_summary = health() if callable(health) else {"ok": True, "issues": [], "details": {}}
            snapshot = await collect_admin_status_snapshot(parent, cache, health_summary)
            specs = build_admin_status_page_specs(snapshot)
            color = discord.Color.gold() if bool(health_summary.get("ok", True)) else discord.Color.orange()
            total_pages = len(specs)
            pages = []
            for index, spec in enumerate(specs, start=1):
                emb = Embed.embed(ctx, title=spec.get("title", "MCOC Status"), description=spec.get("description", ""), color=color)
                try:
                    Embed.set_footer(ctx, emb, text=f"Page {index} of {total_pages} | Collector | Admin Status")
                except Exception:
                    pass
                pages.append(emb)
            cleanup_view = CacheHealthCleanupView(cache) if not bool(health_summary.get("ok", True)) else None
            try:
                pager = PagesMenu(pages, author=ctx.author)
                if cleanup_view and hasattr(pager, "add_item"):
                    for item in getattr(cleanup_view, "children", []):
                        try:
                            pager.add_item(item)
                        except Exception:
                            continue
                await pager.start(ctx)
                return
            except Exception:
                first = pages[0] if pages else None
                await safe_send_ctx(ctx, None, embed=first, view=cleanup_view)
        except Exception:
            log.exception("Failed to build status")
            await safe_send_ctx(ctx, "Failed to fetch status. Check logs.")

    @commands.is_owner()
    @admin.command(name="key")
    async def key(self, ctx):
        """Show whether shared API key for mcochub is set (owner only)."""
        try:
            tokens = await ctx.bot.get_shared_api_tokens("mcochub")
            # tokens may be dict-like
            api_key = None
            if isinstance(tokens, dict):
                api_key = tokens.get("apikey") or tokens.get("api_key") or tokens.get("key")
            elif isinstance(tokens, str):
                api_key = tokens
            if not api_key:
                await ctx.send(
                    "Shared API key for **mcochub** is NOT set.\n"
                    "Set it with:\n"
                    "```"
                    "///set api mcochub apikey,<your_key_here>"
                    "```"
                )
                return
            await ctx.send(f"Shared API key for **mcochub** is set. Starts with: `{api_key[:5]}` (rest hidden).")
        except Exception:
            log.exception("Failed to fetch shared API tokens")
            await safe_send_ctx(ctx, "Failed to fetch shared API tokens.")

    # -------------------------
    # Sync using CacheStatusPoster
    # -------------------------
    @commands.is_owner()
    @admin.command(name="sync")
    async def sync(self, ctx):
        """Trigger a full cache sync (owner only)."""
        parent = getattr(self, "parent", None)
        if not parent:
            await safe_send_ctx(ctx, "MCOC core not attached; cache and API unavailable.")
            return
        if not getattr(parent, "api", None):
            await safe_send_ctx(ctx, "API not available. Set API key first.")
            return

        poster = CacheStatusPoster(ctx, title="MCOC Full Sync")
        await poster.post_initial()

        # reporter used by cache.sync to provide progress updates
        async def reporter(text: str):
            try:
                await poster.update_section("Progress", text)
            except Exception:
                log.exception("Reporter failed to update poster")

        try:
            await poster.update_section("Overall", "Starting full sync…")
            updated = await parent.cache.sync(parent.api, progress=reporter)
            
            # Gather sync results for summary
            meta = parent.cache.metadata or {}
            versions = meta.get("versions", {})
            
            # Check all synced data
            champs_count = len(parent.cache.get_all_champions() or [])
            abilities_count = len(parent.cache.get_all_abilities() or [])
            tags_count = len(parent.cache.get_all_tags() or [])
            immunities_count = len(parent.cache.get_all_immunities() or [])
            aw_count = len(parent.cache.get_all_aw() or [])
            champions_map_count = len(parent.cache.get_all_champions_map() or [])
            glossary_count = len(parent.cache.get_all_glossary_terms() or [])
            tierlist_data = parent.cache._load_file("tierlist") or {}
            tierlist_count = len(tierlist_data.get("champions", []))
            
            # Build summary embed
            emb = Embed.embed(ctx, title="✅ Sync Complete" if updated else "⏭️ Sync Skipped", color=discord.Color.green() if updated else discord.Color.greyple())
            
            sync_status = "Updated" if updated else "No changes (cache was current)"
            Embed.add_field(ctx, emb=emb, name="Status", value=sync_status, inline=False)
            Embed.add_field(ctx, emb=emb, name="Completed At", value=datetime.datetime.utcnow().isoformat(), inline=False)
            
            # Core data summary
            core_summary = (
                f"• Champions: **{champs_count}**\n"
                f"• Abilities: **{abilities_count}**\n"
                f"• Tags: **{tags_count}**\n"
                f"• Immunities: **{immunities_count}**"
            )
            Embed.add_field(ctx, emb=emb, name="Core Data", value=core_summary, inline=True)
            
            # Extended data summary
            extended_summary = (
                f"• Alliance War: **{aw_count}**\n"
                f"• Champions Map: **{champions_map_count}**\n"
                f"• Glossary: **{glossary_count}**\n"
                f"• Tierlist: **{tierlist_count}**"
            )
            Embed.add_field(ctx, emb=emb, name="Extended Data", value=extended_summary, inline=True)
            
            # Version info
            if versions:
                version_summary = "\n".join([f"• {k}: `{v[:12]}...`" for k, v in versions.items()])
            else:
                version_summary = "No versions cached."
            Embed.add_field(ctx, emb=emb, name="Cached Versions", value=version_summary, inline=False)
            
            await poster.finalize("Full sync complete")
            await safe_send_ctx(ctx, None, embed=emb)
        except Exception as e:
            log.exception("Sync failed")
            try:
                await poster.update_section("Overall", f"Sync failed: {e}")
            except Exception:
                pass
            await safe_send_ctx(ctx, f"❌ Sync failed: {e}")

    @commands.is_owner()
    @admin.command(name="force-sync")
    async def force_sync(self, ctx):
        """Force a full fetch from the API and update all cache data (owner only)."""
        parent = getattr(self, "parent", None)
        if not parent:
            await safe_send_ctx(ctx, "MCOC core not attached; cache and API unavailable.")
            return
        if not getattr(parent, "api", None):
            await safe_send_ctx(ctx, "API not available. Set API key first.")
            return

        poster = CacheStatusPoster(ctx, title="MCOC Force Sync")
        await poster.post_initial()

        results = {}

        def _count_payload_items(payload: Any, key: Optional[str] = None) -> int:
            if payload is None:
                return 0
            if isinstance(payload, dict):
                if key and key in payload and isinstance(payload.get(key), list):
                    return len(payload[key])
                if "champions" in payload and isinstance(payload.get("champions"), list):
                    return len(payload["champions"])
                if "abilities" in payload and isinstance(payload.get("abilities"), list):
                    return len(payload["abilities"])
                if "tags" in payload and isinstance(payload.get("tags"), list):
                    return len(payload["tags"])
                if "immunities" in payload and isinstance(payload.get("immunities"), list):
                    return len(payload["immunities"])
                if "aw" in payload and isinstance(payload.get("aw"), dict):
                    return len(payload["aw"].get("defense", {})) + len(payload["aw"].get("attack", {})) + 1
                return len(payload)
            if isinstance(payload, list):
                return len(payload)
            return 0

        try:
            await poster.update_section("Overall", "Forcing full sync from API…")

            # Core data fetches
            await poster.update_section("Champions", "fetching...")
            champions = await parent.api.get_champions()
            results["champions"] = _count_payload_items(champions, "champions")
            await poster.update_section("Champions", f"fetched: {results['champions']}")

            await poster.update_section("Abilities", "fetching...")
            abilities = await parent.api.get_abilities()
            results["abilities"] = _count_payload_items(abilities, "abilities")
            await poster.update_section("Abilities", f"fetched: {results['abilities']}")

            await poster.update_section("Tags", "fetching...")
            tags = await parent.api.get_tags()
            results["tags"] = _count_payload_items(tags, "tags")
            await poster.update_section("Tags", f"fetched: {results['tags']}")

            await poster.update_section("Immunities", "fetching...")
            immunities = await parent.api.get_immunities()
            results["immunities"] = _count_payload_items(immunities, "immunities")
            await poster.update_section("Immunities", f"fetched: {results['immunities']}")

            await poster.update_section("Alliance War", "fetching...")
            aw = await parent.api.get_aw()
            results["aw"] = _count_payload_items(aw, "aw")
            await poster.update_section("Alliance War", f"fetched: {results['aw']}")

            # Extended data
            await poster.update_section("Champions Map", "fetching...")
            champions_map = await parent.api.get_champions_map()
            results["champions_map"] = len(champions_map) if champions_map else 0
            await poster.update_section("Champions Map", f"fetched: {results['champions_map']}")

            await poster.update_section("Glossary", "fetching...")
            glossary = await parent.api.get_glossary()
            results["glossary"] = len(glossary) if glossary else 0
            await poster.update_section("Glossary", f"fetched: {results['glossary']}")

            # Tierlist (from mcochub)
            await poster.update_section("Tierlist", "fetching...")
            tierlist = await parent.api.get_tierlist() if hasattr(parent.api, 'get_tierlist') else None
            results["tierlist"] = len(tierlist.get("champions", [])) if tierlist and isinstance(tierlist, dict) else 0
            await poster.update_section("Tierlist", f"fetched: {results['tierlist']}")

            # Save all to cache
            await poster.update_section("Saving", "writing to cache...")
            await parent.cache._diff_and_save("champions", champions)
            await parent.cache._diff_and_save("abilities", abilities)
            await parent.cache._diff_and_save("tags", tags)
            await parent.cache._diff_and_save("immunities", immunities)
            await parent.cache._diff_and_save("aw", aw)
            await parent.cache._diff_and_save("champions_map", champions_map)
            await parent.cache._diff_and_save("glossary", glossary)
            if tierlist:
                await parent.cache._diff_and_save("tierlist", tierlist)
            await poster.update_section("Saving", "✅ saved to cache")

            # Update prestige
            try:
                await poster.update_section("Prestige", "checking/updating...")
                async def prestige_reporter(text: str):
                    try:
                        await poster.update_prestige_line(text)
                    except Exception:
                        log.exception("Prestige reporter failed")
                await parent.cache.check_update_prestige(parent.api, force=False, progress=prestige_reporter)
                results["prestige"] = "Updated"
                await poster.update_section("Prestige", "✅ completed")
            except Exception:
                log.exception("Prestige check during sync failed")
                results["prestige"] = "Failed"
                await poster.update_section("Prestige", "❌ failed (see logs)")

            # Build comprehensive summary embed
            emb = Embed.embed(ctx, title="✅ Force Sync Complete", color=discord.Color.green())
            Embed.add_field(ctx, emb=emb, name="Completed At", value=datetime.datetime.utcnow().isoformat(), inline=False)
            
            core_summary = (
                f"• Champions: **{results.get('champions', 0)}**\n"
                f"• Abilities: **{results.get('abilities', 0)}**\n"
                f"• Tags: **{results.get('tags', 0)}**\n"
                f"• Immunities: **{results.get('immunities', 0)}**"
            )
            Embed.add_field(ctx, emb=emb, name="Core Data", value=core_summary, inline=True)
            
            extended_summary = (
                f"• Alliance War: **{results.get('aw', 0)}**\n"
                f"• Champions Map: **{results.get('champions_map', 0)}**\n"
                f"• Glossary: **{results.get('glossary', 0)}**\n"
                f"• Tierlist: **{results.get('tierlist', 0)}**"
            )
            Embed.add_field(ctx, emb=emb, name="Extended Data", value=extended_summary, inline=True)
            
            Embed.add_field(ctx, emb=emb, name="Prestige Status", value=f"**{results.get('prestige', 'Unknown')}**", inline=False)

            await poster.finalize("Forced sync complete")
            await safe_send_ctx(ctx, None, embed=emb)
        except Exception as e:
            log.exception("force-sync failed")
            try:
                await poster.update_section("Overall", f"❌ Sync failed: {e}")
            except Exception:
                pass
            await safe_send_ctx(ctx, f"❌ Forced sync failed: {e}")

    @commands.is_owner()
    @admin.command(name="prestige_sync")
    async def prestige_sync(self, ctx, force: bool = False):
        """Update prestige data (owner only)."""
        core = getattr(ctx.bot, "mcoc_core", None)
        if not core or not getattr(core, "cache", None) or not getattr(core, "api", None):
            await safe_send_ctx(ctx, "Core/cache/api not available.")
            return

        poster = CacheStatusPoster(ctx, title="Prestige Update")
        await poster.post_initial()
        await poster.update_section("Prestige", "starting...")

        async def reporter(text: str):
            try:
                # prestige progress lines are appended
                await poster.update_prestige_line(text)
            except Exception:
                log.exception("Prestige reporter failed to update poster")

        try:
            updated = await core.cache.check_update_prestige(core.api, force=force, progress=reporter)
            await poster.update_section("Prestige", f"complete. Updated: {updated}")
            try:
                close_fn = getattr(core.api, "close", None)
                if callable(close_fn):
                    if asyncio.iscoroutinefunction(close_fn):
                        await close_fn()
                    else:
                        res = close_fn()
                        if asyncio.iscoroutine(res):
                            await res
            except Exception:
                log.exception("Failed to close api session after prestige update")
            await poster.finalize("Prestige update complete")
        except Exception as e:
            log.exception("Prestige update failed")
            try:
                await poster.update_section("Prestige", f"failed: {e}")
            except Exception:
                pass
            await safe_send_ctx(ctx, f"Prestige update failed: {e}")

    def _lookup_cache_object(self, cache: Any, kind: str, key: str):
        """Resolve a champion/ability/immunity/tag by exact or normalized lookup."""
        if not cache or not key:
            return None
        normalized = _normalize_lookup_key(key)

        if kind in ("champion", "champ", "ch"):
            items = cache.get_all_champions() or []
            for item in items:
                candidates = [
                    item.get("id"), item.get("slug"), item.get("name"), item.get("title"),
                    item.get("champion_id"), item.get("key"), item.get("slug_name")
                ]
                if any(_normalize_lookup_key(candidate) == normalized for candidate in candidates if candidate is not None):
                    return item
                for candidate in candidates:
                    if candidate is None:
                        continue
                    cand_norm = _normalize_lookup_key(candidate)
                    if cand_norm and normalized and (cand_norm in normalized or normalized in cand_norm):
                        return item
            try:
                return cache.get_champion(key)
            except Exception:
                return None

        if kind in ("ability", "abilities", "abilitys"):
            items = cache.get_all_abilities() or []
            for item in items:
                candidates = [item.get("id"), item.get("slug"), item.get("name"), item.get("title")]
                if any(_normalize_lookup_key(candidate) == normalized for candidate in candidates if candidate is not None):
                    return item
            try:
                return cache.get_ability(key)
            except Exception:
                return None

        if kind in ("immunity", "immunities"):
            items = cache.get_all_immunities() or []
            for item in items:
                candidates = [item.get("id"), item.get("slug"), item.get("name"), item.get("title")]
                if any(_normalize_lookup_key(candidate) == normalized for candidate in candidates if candidate is not None):
                    return item
            try:
                return cache.get_immunity(key)
            except Exception:
                return None

        if kind in ("tag", "tags"):
            items = cache.get_all_tags() or []
            for item in items:
                candidates = [item.get("id"), item.get("slug"), item.get("name"), item.get("title")]
                if any(_normalize_lookup_key(candidate) == normalized for candidate in candidates if candidate is not None):
                    return item
            try:
                return cache.get_tag(key)
            except Exception:
                return None

        return None

    @commands.is_owner()
    @admin.command(name="dump")
    async def dump(self, ctx, kind: str, *, key: str):
        """Dump a cache object (champion, ability, immunity, tag) with flexible resolved lookup."""
        kind = kind.lower()
        core = getattr(ctx.bot, "mcoc_core", None)
        if not core or not getattr(core, "cache", None):
            await safe_send_ctx(ctx, "MCOC cache not initialized.")
            return
        cache = core.cache
        obj = self._lookup_cache_object(cache, kind, key)

        if not obj:
            await safe_send_ctx(ctx, f"No {kind} found for `{key}`.")
            return

        try:
            payload = json.dumps(obj, indent=2, ensure_ascii=False)
        except Exception:
            payload = str(obj)

        MAX_INLINE = 1500
        if len(payload) <= MAX_INLINE:
            await ctx.send(f"```json\n{payload}\n```")
        else:
            bio = io.BytesIO(payload.encode("utf-8"))
            bio.seek(0)
            filename = f"{kind}-{key}.json"
            try:
                await ctx.send(file=discord.File(bio, filename=filename))
            except Exception:
                await ctx.send(f"Large payload; sending first {MAX_INLINE} chars:\n```json\n{payload[:MAX_INLINE]}\n```")
                bio.seek(0)
                try:
                    await ctx.send(file=discord.File(bio, filename=filename))
                except Exception:
                    log.exception("Failed to send dump file")

    @commands.is_owner()
    @admin.command(name="inspect")
    async def inspect(self, ctx, kind: str, *, key: str):
        """Alias for the dump command, kept for quick raw object inspection."""
        await self.dump(ctx, kind, key=key)

    @commands.is_owner()
    @admin.command(name="export-champions")
    async def export_champions(self, ctx):
        """Export merged canonical champion records for offline review."""
        core = getattr(ctx.bot, "mcoc_core", None)
        if not core or not getattr(core, "cache", None):
            await safe_send_ctx(ctx, "MCOC cache not initialized.")
            return

        cache = core.cache
        champions = cache.get_all_champions() or []
        tierlist_doc = cache._load_file("tierlist") if hasattr(cache, "_load_file") else {}
        tierlist_rows = tierlist_doc.get("champions", []) if isinstance(tierlist_doc, dict) else []
        tier_index: Dict[str, Dict[str, Any]] = {}
        for row in tierlist_rows:
            if not isinstance(row, dict):
                continue
            for key in _champion_candidates(row):
                tier_index[key] = row

        api = getattr(core, "api", None)
        cocpit_semaphore = asyncio.Semaphore(8)

        async def _build_record(champ: Dict[str, Any]) -> Dict[str, Any]:
            base = mcochub_to_internal(champ).model_dump(by_alias=True, exclude_none=True)
            base.pop("class_", None)
            base.setdefault("ability_tags", [])
            base.setdefault("synergies", [])

            tier_entry = None
            for key in _champion_candidates(champ):
                if key in tier_index:
                    tier_entry = tier_index[key]
                    break
            if tier_entry:
                try:
                    tier_model = mcoc_app_tierlist_to_internal(tier_entry, tierlist_doc)
                    tier_data = tier_model.model_dump(by_alias=True, exclude_none=True)
                    base["tier"] = tier_data.get("tier") or base.get("tier")
                    base["tags"] = _dedupe_strings((base.get("tags") or []) + (tier_data.get("tags") or []))
                    inflict_tags = [
                        str(item.get("name"))
                        for item in (tier_data.get("abilities") or [])
                        if isinstance(item, dict) and item.get("name")
                    ]
                    base["ability_tags"] = _dedupe_strings((base.get("ability_tags") or []) + inflict_tags)
                    base.setdefault("raw_sources", {})
                    base.setdefault("source_map", {})
                    base["raw_sources"]["mcoc_app"] = tier_entry
                    base["source_map"]["mcoc_app"] = tier_data.get("name") or tier_entry.get("name")
                except Exception:
                    log.exception("Failed to merge tierlist data into champion export for %s", champ.get("id") or champ.get("name"))

            if api is not None and hasattr(api, "get_cocpit_champion_data"):
                champ_ref = str(champ.get("id") or champ.get("slug") or "").strip()
                if champ_ref:
                    rarity = _progression_value(champ, "rarity", _progression_value(champ, "stars", 6))
                    rank = _progression_value(champ, "rank", 1)
                    sig = _progression_value(champ, "sig", 0)
                    asc = _progression_value(champ, "ascended", 0)
                    try:
                        async with cocpit_semaphore:
                            cocpit_raw = await api.get_cocpit_champion_data(champ_ref, rarity, rank, sig, asc)
                        if isinstance(cocpit_raw, dict) and cocpit_raw:
                            cocpit_model = cocpit_to_internal(cocpit_raw)
                            cocpit_data = cocpit_model.model_dump(by_alias=True, exclude_none=True)
                            base["abilities"] = cocpit_data.get("abilities") or base.get("abilities") or []
                            base["synergies"] = cocpit_data.get("synergies") or []
                            base["signature"] = cocpit_data.get("signature")
                            if cocpit_data.get("rotation_data") is not None:
                                base["rotation_data"] = cocpit_data.get("rotation_data")
                            ability_names = [
                                str(item.get("name"))
                                for item in (base.get("abilities") or [])
                                if isinstance(item, dict) and item.get("name")
                            ]
                            signature_names = [
                                str(item.get("name"))
                                for item in ((base.get("signature") or {}).get("abilities") or [])
                                if isinstance(item, dict) and item.get("name")
                            ]
                            base["ability_tags"] = _dedupe_strings((base.get("ability_tags") or []) + ability_names + signature_names)
                            base.setdefault("raw_sources", {})
                            base.setdefault("source_map", {})
                            base["raw_sources"]["cocpit"] = cocpit_raw
                            base["source_map"]["cocpit"] = champ_ref
                    except Exception:
                        log.exception("Failed Cocpit enrich for champion export: %s", champ_ref)

            return base

        await safe_send_ctx(ctx, "Building canonical champion export (MCOCHub + tierlist + Cocpit)…")
        records = await asyncio.gather(*[_build_record(champ) for champ in champions if isinstance(champ, dict)])
        with_signature = sum(1 for item in records if isinstance(item.get("signature"), dict) and item.get("signature"))
        with_synergies = sum(1 for item in records if item.get("synergies"))
        with_rotation = sum(1 for item in records if item.get("rotation_data") is not None)

        payload = {
            "exported_at": datetime.datetime.utcnow().isoformat(),
            "count": len(records),
            "champions": records,
            "source_coverage": {
                "mcochub": len(records),
                "tierlist": len(tier_index),
                "cocpit_signature": with_signature,
                "cocpit_synergies": with_synergies,
                "cocpit_rotation": with_rotation,
            },
        }

        try:
            body = json.dumps(payload, indent=2, ensure_ascii=False)
        except Exception as exc:
            await safe_send_ctx(ctx, f"Failed to serialize champion export: {exc}")
            return

        bio = io.BytesIO(body.encode("utf-8"))
        bio.seek(0)
        await ctx.send(file=discord.File(bio, filename="cdt-champions-export.json"))

# Cog setup for Red (async setup)
async def setup(bot):
    await bot.add_cog(MCOCAdminPrefix(bot))
    log.debug("MCOCAdminPrefix loaded")


# Legacy registrar support (attach admin commands onto another group)
def register_with_group(group: commands.Group, parent_getter):
    """
    Register admin prefix commands onto the provided group in a safe, idempotent way.
    Uses _safe_add to avoid CommandRegistrationError when a command already exists.
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

    @_safe_add("status")
    @commands.is_owner()
    async def _status(ctx):
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; cache and API unavailable.")
            return
        cache = getattr(parent, "cache", None)
        if not cache:
            await ctx.send("Cache not available on core.")
            return
        try:
            meta = getattr(cache, "metadata", {}) or {}
            last = meta.get("last_sync")
            versions = meta.get("versions", {})
            champs_count = len(cache.get_all_champions() or [])
            abilities_count = len(cache.get_all_abilities() or [])
            tags_count = len(cache.get_all_tags() or [])
            immunities_count = len(cache.get_all_immunities() or [])
            prestige_version = versions.get("prestige")
            prestige_file = getattr(cache, "cache_dir", Path("data")) / "prestige.json"
            prestige_exists = prestige_file.exists()
            prestige_rows_count = 0
            try:
                prestige_data = cache._load_file("prestige") or {}
                prestige_rows = prestige_data.get("rows", []) if isinstance(prestige_data, dict) else []
                prestige_rows_count = len(prestige_rows)
            except Exception:
                prestige_rows_count = 0

            msg = (
                f"**MCOC cache status**\n"
                f"Last sync: {last}\n"
                f"Versions: {versions}\n"
                f"Champions: {champs_count}\n"
                f"Abilities: {abilities_count}\n"
                f"Tags: {tags_count}\n"
                f"Immunities: {immunities_count}\n"
                f"API client present: {bool(getattr(parent, 'api', None))}\n\n"
                f"**Prestige data**\n"
                f"Prestige version (metadata): {prestige_version}\n"
                f"Prestige file present: {prestige_exists}\n"
                f"Prestige rows (aggregated): {prestige_rows_count}\n"
            )
            await ctx.send(msg)
        except Exception:
            log.exception("Admin status failed")
            await ctx.send("Failed to fetch status.")
