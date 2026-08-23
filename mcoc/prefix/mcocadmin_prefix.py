# mcoc/prefix/mcocadmin_prefix.py
import logging
from redbot.core import commands

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
