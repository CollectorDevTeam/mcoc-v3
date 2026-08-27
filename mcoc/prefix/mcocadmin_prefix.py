# mcoc/prefix/mcocadmin_prefix.py
import logging
# inside mcoc/prefix/mcocadmin_prefix.py (or similar admin cog)
import io
import json
import datetime
import asyncio
from discord import File
from redbot.core import commands
from pathlib import Path
from ..common.componentsV2 import CDTEmbed, CDTConfirm, CDTPagesMenu
log = logging.getLogger("red.mcoc.prefix")

from ..common.champion_helpers import safe_send_ctx as reporter


class MCOCAdminPrefix(commands.Cog):
    """Prefix commands for MCOC admin (development / fallback)."""
    is_mcoc_prefix = True
    mcoc_version = "3.0.0"

    def __init__(self, bot_or_parent):
        if hasattr(bot_or_parent, "bot") and hasattr(bot_or_parent, "cache"):
            self.parent = bot_or_parent
            self.bot = bot_or_parent.bot
        else:
            self.bot = bot_or_parent
            self.parent = getattr(self.bot, "mcoc_core", None) or self.bot.get_cog("MCOC") or self.bot.get_cog("MCOCPrefix")

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
                # if get_command fails for any reason, fall back to attempting to add
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
        cache = parent.cache
        meta = cache.metadata or {}
        last = meta.get("last_sync")
        versions = meta.get("versions", {})
        champs_count = len(cache.get_all_champions())
        abilities_count = len(cache.get_all_abilities())
        tags_count = len(cache.get_all_tags())
        immunities_count = len(cache.get_all_immunities())
        prestige_version = versions.get("prestige")
        prestige_file = cache.cache_dir / "prestige.json"
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
            f"API client present: {bool(parent.api)}\n\n"
            f"**Prestige data**\n"
            f"Prestige version (metadata): {prestige_version}\n"
            f"Prestige file present: {prestige_exists}\n"
            f"Prestige rows (aggregated): {prestige_rows_count}\n"
            f"Prestige last sync (metadata): {prestige_last_sync}\n"
        )
        await ctx.send(msg)

    @_safe_add("key")
    @commands.is_owner()
    async def _key(ctx):
        tokens = await ctx.bot.get_shared_api_tokens("mcochub")
        api_key = tokens.get("apikey")
        if not api_key:
            await ctx.send(
                "Shared API key for **mcochub** is NOT set.\n"
                "Set it with:\n"
                "```"
                "///set api mcochub apikey,3|dJIQqECDG..."
                "```"
            )
            return
        await ctx.send(
            f"Shared API key for **mcochub** is set.\n"
            f"Starts with: `{api_key[:5]}` (rest hidden)."
        )

    @_safe_add("sync")
    @commands.is_owner()
    async def _sync(ctx):
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; cache and API unavailable.")
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
            await update_queue.join()
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
            raise

    @_safe_add("force-sync")
    @commands.is_owner()
    async def _force_sync(ctx):
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; cache and API unavailable.")
            return
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
            await parent.cache.check_update_prestige(parent.api, force=False, progress=reporter)
        except Exception:
            log.exception("Prestige check during sync failed")
        await ctx.send("Forced sync complete.")

    @_safe_add("prestige_sync")
    @commands.is_owner()
    async def _prestige_sync(ctx, force: bool = False):
        core = getattr(ctx.bot, "mcoc_core", None)
        if not core or not getattr(core, "cache", None) or not getattr(core, "api", None):
            await ctx.send("Core/cache/api not available.")
            return
        status_msg = await ctx.send("Starting prestige update…")
        async def reporter(text: str):
            try:
                await status_msg.edit(content=text)
            except Exception:
                log.exception("Failed to edit prestige status message")
        try:
            updated = await core.cache.check_update_prestige(core.api, force=force, progress=reporter)
            await status_msg.edit(content=f"Prestige update complete. Updated: {updated}")
            try:
                await core.api.close()
            except Exception:
                log.exception("Failed to close api session after prestige update")
        except Exception as e:
            await status_msg.edit(content=f"Prestige update failed: {e}")
            await ctx.send(f"Prestige update failed: {e}")

    @_safe_add("dump")
    @commands.is_owner()
    async def _dump(ctx, kind: str, *, key: str):
        kind = kind.lower()
        core = getattr(ctx.bot, "mcoc_core", None)
        if not core or not getattr(core, "cache", None):
            await ctx.send("MCOC cache not initialized.")
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
                for a in cache.get_all_abilities() or []:
                    if str(a.get("id") or a.get("slug") or "").lower() == key.lower() or str(a.get("name") or "").lower() == key.lower():
                        obj = a
                        break
        elif kind in ("immunity", "immunities"):
            try:
                obj = cache.get_immunity(key)
            except Exception:
                for i in cache.get_all_immunities() or []:
                    if str(i.get("id") or i.get("slug") or "").lower() == key.lower() or str(i.get("name") or "").lower() == key.lower():
                        obj = i
                        break
        elif kind in ("tag", "tags"):
            try:
                obj = cache.get_tag(key)
            except Exception:
                for t in cache.get_all_tags() or []:
                    if str(t.get("id") or t.get("slug") or "").lower() == key.lower() or str(t.get("name") or "").lower() == key.lower():
                        obj = t
                        break
        else:
            await ctx.send("Unknown kind. Use one of: champion, ability, immunity, tag.")
            return
        if not obj:
            await ctx.send(f"No {kind} found for `{key}`.")
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
                await ctx.send(f"Large payload; sending first {MAX_INLINE} chars:\n```json\n{payload[:MAX_INLINE]}\n```")
                bio.seek(0)
                await ctx.send(file=File(bio, filename=filename))
