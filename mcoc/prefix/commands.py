# mcoc/prefix/commands.py
import discord
import io
import logging
from redbot.core import commands

log = logging.getLogger("red.mcoc.prefix")

class MCOCPrefix(commands.Cog):
    """Prefix commands for MCOC (development / fallback)."""

    def __init__(self, parent_cog):
        """
        parent_cog: instance of mcoc.core.MCOC
        We keep a reference to the main cog so we reuse its api/cache/index.
        """
        self.parent = parent_cog
        self.bot = parent_cog.bot

    # Top-level group
    @commands.group(name="mcoc", invoke_without_command=True)
    @commands.is_owner()
    async def mcoc(self, ctx):
        """MCOC data management commands (owner only)."""
        await ctx.send("Use subcommands: `status`, `sync`, `force-sync`, `dump`, `verbose`.")

    # Status
    @mcoc.command(name="status")
    @commands.is_owner()
    async def mcoc_status(self, ctx):
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
    @mcoc.command(name="sync")
    @commands.is_owner()
    async def mcoc_sync(self, ctx, mode: str = "auto"):
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
            log.error("Owner attempted sync but API key unauthenticated.")
        except self.parent.api.__class__.RateLimitedError:
            await ctx.send("API rate limited. Backing off; try again later.")
            log.warning("Owner attempted sync but API rate limited.")
        except Exception:
            log.exception("mcoc sync failed")
            await ctx.send("Sync failed; check logs for details.")

    # Dump sample of a cache file
    @mcoc.command(name="dump")
    @commands.is_owner()
    async def mcoc_dump(self, ctx, which: str = "champions"):
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
    @mcoc.command(name="verbose")
    @commands.is_owner()
    async def mcoc_verbose(self, ctx, on_off: str):
        val = on_off.lower() in ("1", "true", "on", "yes")
        level = logging.DEBUG if val else logging.INFO
        logging.getLogger("red.mcoc").setLevel(level)
        logging.getLogger("red.mcoc.core").setLevel(level)
        logging.getLogger("red.mcoc.api").setLevel(level)
        logging.getLogger("red.mcoc.cache").setLevel(level)
        logging.getLogger("red.mcoc.cacheindex").setLevel(level)
        await ctx.send(f"Verbose logging {'enabled' if val else 'disabled'}.")
        log.info("Owner set verbose logging to %s", val)

    @commands.command()
    @commands.is_owner()
    async def debug_tree(self, ctx, guild_id: int = None):
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
