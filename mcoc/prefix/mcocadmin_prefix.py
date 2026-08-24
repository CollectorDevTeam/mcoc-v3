# mcoc/prefix/mcocadmin_prefix.py
import logging
# inside mcoc/prefix/mcocadmin_prefix.py (or similar admin cog)
import io
import json
from discord import File
from redbot.core import commands
from pathlib import Path

log = logging.getLogger("red.mcoc.prefix")

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

# NO top-level commands here.

def register_with_group(group: commands.Group, parent_getter):

    @group.command(name="status")
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

        # Prestige status
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

    @group.command(name="key")
    @commands.is_owner()
    async def _key(ctx):
        """
        Show whether the shared MCOCHub API key is set and its first few characters.
        """
        # Use Red's shared API tokens: service 'mcochub', key 'apikey'
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

    @group.command(name="sync")
    @commands.is_owner()
    async def _sync(ctx):
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; cache and API unavailable.")
            return

        updated = await parent.cache.sync(parent.api)
        await ctx.send("Sync complete." if updated else "No update performed.")

    @group.command(name="force-sync")
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
        await ctx.send("Forced sync complete.")

    @commands.is_owner()
    @group.command(name="prestige_sync")
    async def _prestige_sync(ctx, force: bool = False):
        """Force update prestige cache from MCOCHub (admin only)."""
        core = getattr(ctx.bot, "mcoc_core", None)  # adjust to your actual attribute
        if not core or not getattr(core, "cache", None) or not getattr(core, "api", None):
            await ctx.send("Core/cache/api not available.")
            return
        await ctx.send("Starting prestige update (this may take a while)...")
        try:
            updated = await core.cache.check_update_prestige(core.api, force=force)
            await ctx.send(f"Prestige update complete. Updated: {updated}")
        except Exception as e:
            await ctx.send(f"Prestige update failed: {e}")


    @group.command(name="dump", aliases=["raw", "json"])
    @commands.is_owner()
    async def _dump(ctx, kind: str, *, key: str):
        """
        Dump raw JSON for a single entry from the local cache.

        kind: one of 'champion', 'ability', 'immunity', 'tag'
        key: id, slug, or name (case-insensitive)
        Examples:
        ///mcoc admin dump champion blackbolt
        ///mcoc admin dump ability armor-break
        ///mcoc admin dump tag poison-immunity
        """
        kind = kind.lower()
        core = getattr(ctx.bot, "mcoc_core", None)
        if not core or not getattr(core, "cache", None):
            await ctx.send("MCOC cache not initialized.")
            return

        cache = core.cache

        # Resolve the requested object
        obj = None
        if kind in ("champion", "champ", "ch"):
            # try cache API first, then fallback scan
            try:
                obj = cache.get_champion(key)
            except Exception:
                obj = None
            if obj is None:
                # fallback: scan all champions
                for c in cache.get_all_champions() or []:
                    if str(c.get("id") or c.get("slug") or "").lower() == key.lower() or str(c.get("name") or "").lower() == key.lower():
                        obj = c
                        break

        elif kind in ("ability", "abilities", "abilitys"):
            try:
                # if cache exposes get_ability or similar
                obj = cache.get_ability(key)
            except Exception:
                # fallback: scan
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

        # Pretty-print JSON
        try:
            payload = json.dumps(obj, indent=2, ensure_ascii=False)
        except Exception:
            # fallback: best-effort string conversion
            payload = str(obj)

        # If small, send inline; otherwise send as file
        MAX_INLINE = 1500
        if len(payload) <= MAX_INLINE:
            # wrap in codeblock for readability
            await ctx.send(f"```json\n{payload}\n```")
        else:
            bio = io.BytesIO(payload.encode("utf-8"))
            bio.seek(0)
            filename = f"{kind}-{key}.json"
            try:
                await ctx.send(file=File(bio, filename=filename))
            except Exception:
                # last resort: send first chunk inline and attach remainder as file
                await ctx.send(f"Large payload; sending first {MAX_INLINE} chars:\n```json\n{payload[:MAX_INLINE]}\n```")
                bio.seek(0)
                await ctx.send(file=File(bio, filename=filename))
