# mcoc/prefix/mcocadmin_prefix.py  (replace the __init__ and class header)
import logging
from redbot.core import commands

log = logging.getLogger("red.mcoc.prefix")

class MCOCAdminPrefix(commands.Cog):
    """Prefix commands for MCOC admin (development / fallback)."""
    is_mcoc_prefix = True
    mcoc_version = "3.0.0"

    def __init__(self, bot_or_parent):
        """
        Accept either:
          - parent_cog (the main mcoc core object) OR
          - bot (discord.Bot / Red instance)
        If a bot is passed, we attempt to find a parent core on it (bot.cogs or attribute).
        """
        # If a parent cog was passed (has .bot), use it
        if hasattr(bot_or_parent, "bot") and hasattr(bot_or_parent, "cache"):
            self.parent = bot_or_parent
            self.bot = bot_or_parent.bot
        else:
            # assume a Bot/Red instance was passed
            self.bot = bot_or_parent
            # try to find a parent mcoc core cog on the bot
            self.parent = None
            # common heuristics: attribute or cog name
            self.parent = getattr(self.bot, "mcoc_core", None) or self.bot.get_cog("MCOC") or self.bot.get_cog("MCOCPrefix")
            # parent may be None in standalone mode; code must handle that


    # Top-level group
    @commands.group(name="mcocadmin", invoke_without_command=True)
    async def mcocadmin(self, ctx):
        """MCOC admin commands (owner only)."""
        await ctx.send("Use subcommands: `status`, `sync`, `force-sync`, `dump`, `verbose`.")
    @commands.is_owner()
    async def mcoc(self, ctx):
        """MCOC data management commands (owner only)."""
        await ctx.send("Use subcommands: `status`, `sync`, `force-sync`, `dump`, `verbose`.")

    # Status
    @mcocadmin.command(name="status")
    @commands.is_owner()
    async def mcocadmin_status(self, ctx):
        # inside mcoc_status and other methods that use parent
        if not getattr(self, "parent", None):
            await ctx.send("MCOC core not attached; cache and API unavailable.")
            return
       
        try:
            cache = self.parent.cache
            meta = cache.metadata or {}
            last = meta.get("last_sync")
            versions = meta.get("versions", {})
            champs_count = len(cache.get_all_champions())
            abilities_count = len(cache.get_all_abilities())
            tags_count = len(cache.get_all_tags())
            immunities_count = len(cache.get_all_immunities())

            msg = (
                f"**MCOC cache status**\n"
                f"Last sync: {last}\n"
                f"Versions: {versions}\n"
                f"Champions: {champs_count}\n"
                f"Abilities: {abilities_count}\n"
                f"Tags: {tags_count}\n"
                f"Immunities: {immunities_count}\n"
                f"API client present: {bool(self.parent.api)}\n"
                f"Sync task running: {bool(self.parent.sync_task and not self.parent.sync_task.done())}"
            )
            await ctx.send(msg)
        except Exception:
            log.exception("mcoc status failed")
            await ctx.send("Failed to get status; check logs.")

    # Sync (auto respects recency; force bypasses recency)
    @mcocadmin.command(name="sync")
    @commands.is_owner()
    async def mcocadmin_sync(self, ctx, mode: str = "auto"):
        # inside mcoc_status and other methods that use parent
        if not getattr(self, "parent", None):
            await ctx.send("MCOC core not attached; cache and API unavailable.")
            return
        await ctx.trigger_typing()
        if not self.parent.api:
            await ctx.send("API client not available (offline mode).")
            return

        try:
            if mode.lower() in ("force", "forced"):
                await ctx.send("Forcing fetch from MCOCHub (this may consume API quota).")
                champions = await self.parent.api.get_champions()
                tags = await self.parent.api.get_tags()
                abilities = await self.parent.api.get_abilities()
                immunities = await self.parent.api.get_immunities()

                if champions is None or tags is None or abilities is None or immunities is None:
                    await ctx.send("One or more endpoints returned no data; aborting forced sync. Check logs.")
                    return

                self.parent.cache._diff_and_save("champions", champions)
                self.parent.cache._diff_and_save("tags", tags)
                self.parent.cache._diff_and_save("abilities", abilities)
                self.parent.cache._diff_and_save("immunities", immunities)
                self.parent.cache._save_metadata()
                await ctx.send("Forced sync complete; cache updated.")
                log.info("Manual forced sync completed by owner.")
                return

            # default: call cache.sync which respects recency
            updated = await self.parent.cache.sync(self.parent.api)
            if updated:
                await ctx.send("Sync completed and cache updated.")
            else:
                await ctx.send("No update performed (cache recent or no changes).")
        except self.parent.api.__class__.UnauthenticatedError:
            await ctx.send("API key unauthenticated. Fix shared token and reload cog.")
            log.error("Owner attempted mcocadmin sync but API key unauthenticated.")
        except self.parent.api.__class__.RateLimitedError:
            await ctx.send("API rate limited. Backing off; try again later.")
            log.warning("Owner attempted mcocadmin sync but API rate limited.")
        except Exception:
            log.exception("mcocadmin sync failed")
            await ctx.send("Sync failed; check logs for details.")

    # Dump sample of a cache file
    @mcocadmin.command(name="dump")
    @commands.is_owner()
    async def mcocadmin_dump(self, ctx, which: str = "champions"):# inside mcoc_status and other methods that use parent
        if not getattr(self, "parent", None):
            await ctx.send("MCOC core not attached; cache and API unavailable.")
            return
            
        which = which.lower()
        if which not in ("champions", "abilities", "tags", "immunities"):
            await ctx.send("Invalid target. Choose champions, abilities, tags, or immunities.")
            return

        try:
            data = self.parent.cache._load_file(which)
            if not data:
                await ctx.send(f"{which} cache file is empty or missing.")
                return

            version = data.get("version")
            updated_at = data.get("updated_at")
            items = data.get(which, {})
            if isinstance(items, dict):
                sample_items = list(items.values())[:3]
            elif isinstance(items, list):
                sample_items = items[:3]
            else:
                sample_items = [items]

            text = f"**{which}** version={version} updated_at={updated_at}\n"
            for i, it in enumerate(sample_items, 1):
                text += f"\n**Item {i}**\n```\n{it}\n```\n"

            if len(text) > 1900:
                await ctx.send(file=discord.File(fp=io.StringIO(text), filename=f"{which}_sample.txt"))
            else:
                await ctx.send(text)
        except Exception:
            log.exception("mcoc dump failed")
            await ctx.send("Failed to dump cache; check logs.")

    # Toggle verbose logging
    @mcocadmin.command(name="verbose")
    @commands.is_owner()
    async def mcocadmin_verbose(self, ctx, on_off: str):
        val = on_off.lower() in ("1", "true", "on", "yes")
        level = logging.DEBUG if val else logging.INFO
        logging.getLogger("red.mcoc").setLevel(level)
        logging.getLogger("red.mcoc.core").setLevel(level)
        logging.getLogger("red.mcoc.api").setLevel(level)
        logging.getLogger("red.mcoc.cache").setLevel(level)
        logging.getLogger("red.mcoc.cacheindex").setLevel(level)
        await ctx.send(f"Verbose logging {'enabled' if val else 'disabled'}.")
        log.info("Owner set verbose logging to %s", val)

    @mcocadmin.command(name="debug")
    @commands.is_owner()
    async def mcocadmin_debug(self, ctx, guild_id: int = None):
        """Print local tree and optionally sync to a guild."""
        out = []
        out.append(f"Local commands: {[c.name for c in self.bot.tree.get_commands()]}")
        for c in self.bot.tree.get_commands():
            children = getattr(c, "children", None) or getattr(c, "commands", None)
            out.append(f"{c.name} -> {[ch.name for ch in children] if children else []}")
        if guild_id:
            res = await self.bot.tree.sync(guild=discord.Object(id=guild_id))
            out.append(f"Synced to guild {guild_id}: {len(res)} commands")
        await ctx.send("```\n" + "\n".join(out) + "\n```")

async def setup(bot):
    """
    Allow this file to be loaded as a standalone cog by Red.
    If you have a separate core cog, prefer loading that instead.
    """
    try:
        await bot.add_cog(MCOCAdminPrefix(bot))
    except Exception:
        import logging
        logging.getLogger("red.mcoc.prefix").exception("Failed to add MCOCAdminPrefix")

def register_with_group(group: commands.Group, parent_getter):
    # status
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

        msg = (
            f"**MCOC cache status**\n"
            f"Last sync: {last}\n"
            f"Versions: {versions}\n"
            f"Champions: {champs_count}\n"
            f"Abilities: {abilities_count}\n"
            f"Tags: {tags_count}\n"
            f"Immunities: {immunities_count}\n"
            f"API client present: {bool(parent.api)}"
        )
        await ctx.send(msg)

    # sync
    @group.command(name="sync")
    @commands.is_owner()
    async def _sync(ctx, mode: str = "auto"):
        parent = parent_getter()
        if not parent:
            await ctx.send("MCOC core not attached; cache and API unavailable.")
            return

        updated = await parent.cache.sync(parent.api)
        await ctx.send("Sync complete." if updated else "No update performed.")

    # force-sync
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
