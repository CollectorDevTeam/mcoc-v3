# mcoc/prefix/mcocadmin_prefix.py
"""
Prefix commands for MCOC admin (development / fallback).

This cog exposes a small set of owner-only admin utilities and also provides
a `register_with_group` function so the same commands can be attached to the
main ///mcoc group via the registrar pattern.
"""

from typing import Any
import io
import json
import datetime
import asyncio
import logging
from pathlib import Path

from discord import File
from redbot.core import commands

from ..common.componentsV2 import CDTEmbed, CDTConfirm, CDTPagesMenu
from ..common.prefix_utils import safe_send_ctx

log = logging.getLogger("red.mcoc.prefix")


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
    @commands.group(name="mcocadmin", invoke_without_command=True)
    async def mcocadmin(self, ctx, *args):
        """Admin commands for MCOC (development / fallback)."""
        if not args:
            # show help for this group
            await ctx.send_help("mcocadmin")

    # -------------------------
    # Owner-only utilities
    # -------------------------
    @commands.is_owner()
    @mcocadmin.command(name="status")
    async def status(self, ctx):
        """Show cache / API status for debugging."""
        parent = getattr(self, "parent", None)
        if not parent:
            await safe_send_ctx(ctx, "MCOC core not attached; cache and API unavailable.")
            return
        cache = getattr(parent, "cache", None)
        if not cache:
            await safe_send_ctx(ctx, "Cache not available on core.")
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
            prestige_last_sync = None
            try:
                prestige_data = cache._load_file("prestige") or {}
                prestige_rows = prestige_data.get("rows", []) if isinstance(prestige_data, dict) else []
                prestige_rows_count = len(prestige_rows)
                prestige_last_sync = meta.get("last_sync")
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
                f"Prestige last sync (metadata): {prestige_last_sync}\n"
            )
            await ctx.send(msg)
        except Exception:
            log.exception("Failed to build status")
            await safe_send_ctx(ctx, "Failed to fetch status. Check logs.")

    @commands.is_owner()
    @mcocadmin.command(name="key")
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

    @commands.is_owner()
    @mcocadmin.command(name="sync")
    async def sync(self, ctx):
        """Trigger a full cache sync (owner only)."""
        parent = getattr(self, "parent", None)
        if not parent:
            await safe_send_ctx(ctx, "MCOC core not attached; cache and API unavailable.")
            return

        status_msg = await ctx.send("Starting full cache sync…")
        update_queue: "asyncio.Queue[str]" = asyncio.Queue()
        stop_worker = False

        async def _worker():
            last = 0.0
            min_interval = 1.0
            while True:
                try:
                    pending = await asyncio.wait_for(update_queue.get(), timeout=2.0)
                except asyncio.TimeoutError:
                    if stop_worker and update_queue.empty():
                        break
                    continue
                try:
                    # drain queue to latest
                    while True:
                        pending = update_queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                now = asyncio.get_event_loop().time()
                wait = max(0.0, min_interval - (now - last))
                if wait:
                    await asyncio.sleep(wait)
                try:
                    await status_msg.edit(content=pending)
                except Exception:
                    log.exception("Failed to edit status message")
                finally:
                    try:
                        update_queue.task_done()
                    except Exception:
                        pass
                last = asyncio.get_event_loop().time()

        worker_task = asyncio.create_task(_worker())

        async def reporter(text: str):
            try:
                if update_queue.qsize() > 10:
                    try:
                        _ = update_queue.get_nowait()
                    except Exception:
                        pass
                try:
                    update_queue.put_nowait(text)
                except asyncio.QueueFull:
                    pass
            except Exception:
                log.exception("Reporter enqueue failed")

        try:
            updated = await parent.cache.sync(parent.api, progress=reporter)
            final = "Sync complete." if updated else "No update performed."
            stop_worker = True
            try:
                await update_queue.join()
            except Exception:
                pass
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass
            try:
                await status_msg.edit(content=f"{final}\nLast update: {datetime.datetime.utcnow().isoformat()}")
            except Exception:
                log.exception("Failed to edit final status message")
            await ctx.send(final)
        except Exception as e:
            stop_worker = True
            try:
                await update_queue.join()
            except Exception:
                pass
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass
            try:
                await status_msg.edit(content=f"Sync failed: {e}")
            except Exception:
                log.exception("Failed to edit failure status message")
            log.exception("Sync failed")
            await safe_send_ctx(ctx, f"Sync failed: {e}")

    @commands.is_owner()
    @mcocadmin.command(name="force-sync")
    async def force_sync(self, ctx):
        """Force a full fetch from the API and update cache (owner only)."""
        parent = getattr(self, "parent", None)
        if not parent:
            await safe_send_ctx(ctx, "MCOC core not attached; cache and API unavailable.")
            return
        try:
            await ctx.send("Forcing full sync…")
            champions = await parent.api.get_champions()
            tags = await parent.api.get_tags()
            abilities = await parent.api.get_abilities()
            immunities = await parent.api.get_immunities()
            await parent.cache._diff_and_save("champions", champions)
            await parent.cache._diff_and_save("tags", tags)
            await parent.cache._diff_and_save("abilities", abilities)
            await parent.cache._diff_and_save("immunities", immunities)
            try:
                await parent.cache.check_update_prestige(parent.api, force=False, progress=safe_send_ctx)
            except Exception:
                log.exception("Prestige check during sync failed")
            await ctx.send("Forced sync complete.")
        except Exception:
            log.exception("force-sync failed")
            await safe_send_ctx(ctx, "Forced sync failed. Check logs.")

    @commands.is_owner()
    @mcocadmin.command(name="prestige_sync")
    async def prestige_sync(self, ctx, force: bool = False):
        """Update prestige data (owner only)."""
        core = getattr(ctx.bot, "mcoc_core", None)
        if not core or not getattr(core, "cache", None) or not getattr(core, "api", None):
            await safe_send_ctx(ctx, "Core/cache/api not available.")
            return
        status_msg = await ctx.send("Starting prestige update…")

        async def reporter(text: str):
            try:
                await status_msg.edit(content=text)
            except Exception:
                log.exception("Failed to edit prestige status message")

        try:
            updated = await core.cache.check_update_prestige(core.api, force=force, progress=reporter)
            try:
                await status_msg.edit(content=f"Prestige update complete. Updated: {updated}")
            except Exception:
                pass
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
        except Exception as e:
            log.exception("Prestige update failed")
            try:
                await status_msg.edit(content=f"Prestige update failed: {e}")
            except Exception:
                pass
            await safe_send_ctx(ctx, f"Prestige update failed: {e}")

    @commands.is_owner()
    @mcocadmin.command(name="dump")
    async def dump(self, ctx, kind: str, *, key: str):
        """Dump a cache object (champion, ability, immunity, tag)."""
        kind = kind.lower()
        core = getattr(ctx.bot, "mcoc_core", None)
        if not core or not getattr(core, "cache", None):
            await safe_send_ctx(ctx, "MCOC cache not initialized.")
            return
        cache = core.cache
        obj = None
        if kind in ("champion", "champ", "ch"):
            try:
                obj = cache.get_champion(key)
            except Exception:
                obj = None
            if obj is None:
                for c in cache.get_all_champions() or []:
                    if str(c.get("id") or c.get("slug") or "").lower() == key.lower() or str(c.get("name") or "").lower() == key.lower():
                        obj = c
                        break
        elif kind in ("ability", "abilities", "abilitys"):
            try:
                obj = cache.get_ability(key)
            except Exception:
                obj = None
            if obj is None:
                for a in cache.get_all_abilities() or []:
                    if str(a.get("id") or a.get("slug") or "").lower() == key.lower() or str(a.get("name") or "").lower() == key.lower():
                        obj = a
                        break
        elif kind in ("immunity", "immunities"):
            try:
                obj = cache.get_immunity(key)
            except Exception:
                obj = None
            if obj is None:
                for i in cache.get_all_immunities() or []:
                    if str(i.get("id") or i.get("slug") or "").lower() == key.lower() or str(i.get("name") or "").lower() == key.lower():
                        obj = i
                        break
        elif kind in ("tag", "tags"):
            try:
                obj = cache.get_tag(key)
            except Exception:
                obj = None
            if obj is None:
                for t in cache.get_all_tags() or []:
                    if str(t.get("id") or t.get("slug") or "").lower() == key.lower() or str(t.get("name") or "").lower() == key.lower():
                        obj = t
                        break
        else:
            await safe_send_ctx(ctx, "Unknown kind. Use one of: champion, ability, immunity, tag.")
            return

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
                await ctx.send(file=File(bio, filename=filename))
            except Exception:
                # fallback: send truncated inline then file
                await ctx.send(f"Large payload; sending first {MAX_INLINE} chars:\n```json\n{payload[:MAX_INLINE]}\n```")
                bio.seek(0)
                try:
                    await ctx.send(file=File(bio, filename=filename))
                except Exception:
                    log.exception("Failed to send dump file")

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
