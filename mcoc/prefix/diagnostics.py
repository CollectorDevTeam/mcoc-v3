# diagnostics.py
import logging
import asyncio
from discord import Object, app_commands
from redbot.core import commands

log = logging.getLogger("red.diagnostics")

class Diagnostics(commands.Cog):
    """Prefix diagnostics for app command registration and tree state."""

    def __init__(self, bot):
        self.bot = bot

    # -----------------------
    # Helper utilities
    # -----------------------
    def _short_map_sample(self, mapping, limit=50):
        if not mapping:
            return []
        try:
            return list(mapping.keys())[:limit]
        except Exception:
            return []

    # -----------------------
    # Main status command
    # -----------------------
    @commands.command(name="diag status")
    @commands.is_owner()
    async def diag_status(self, ctx):
        """Show high level diagnostics about app command registration."""
        bot = self.bot
        tree = bot.tree
        info = await bot.application_info()
        guilds = list(bot.guilds)[:20]
        out = []
        out.append(f"**Application id**: {info.id}")
        out.append(f"**Application owner**: {getattr(info, 'owner', None)}")
        out.append(f"**Bot user id**: {bot.user.id}")
        out.append(f"**Guilds count**: {len(bot.guilds)} (sample: {[g.id for g in guilds]})")
        top = [c.name for c in tree.get_commands()]
        out.append(f"**Tree top-level commands**: {top}")
        out.append(f"**_global_commands sample**: {self._short_map_sample(getattr(tree, '_global_commands', {}))}")
        out.append(f"**_disabled_global_commands sample**: {self._short_map_sample(getattr(tree, '_disabled_global_commands', {}))}")
        await ctx.send("\n".join(out))

    # -----------------------
    # Inspect group object
    # -----------------------
    @commands.command(name="diag group")
    @commands.is_owner()
    async def diag_group(self, ctx, group_name: str):
        """Inspect a group object on the cog by attribute name (e.g., champions_slash)."""
        cog = self.bot.get_cog("MCOC")
        if not cog:
            await ctx.send("MCOC cog not loaded")
            return
        grp = getattr(cog, group_name, None)
        if not grp:
            await ctx.send(f"No attribute `{group_name}` on MCOC cog")
            return
        try:
            children = getattr(grp, "children", None) or getattr(grp, "commands", None) or []
            names = [getattr(ch, "name", None) for ch in children]
            await ctx.send(f"Group `{group_name}` name: {getattr(grp, 'name', None)}; children_count: {len(children)}; children: {names}")
        except Exception as e:
            await ctx.send(f"Error inspecting group: {type(e).__name__} {e}")

    # -----------------------
    # Tree sync diagnostics
    # -----------------------
    @commands.command(name="diag sync")
    @commands.is_owner()
    async def diag_sync(self, ctx, guild_id: int = None):
        """Attempt a guild sync and report results. Pass guild id to sync that guild."""
        tree = self.bot.tree
        try:
            if guild_id:
                res = await tree.sync(guild=Object(id=guild_id))
            else:
                res = await tree.sync()
            # res may be list of commands or int
            if hasattr(res, "__len__"):
                names = [c.name for c in res]
                await ctx.send(f"Sync returned {len(res)} commands: {names[:50]}")
            else:
                await ctx.send(f"Sync returned: {res}")
        except Exception as e:
            await ctx.send(f"Sync failed: {type(e).__name__} {e}")

    # -----------------------
    # Test add minimal group
    # -----------------------
    @commands.command(name="diag testgroup")
    @commands.is_owner()
    async def diag_testgroup(self, ctx, guild_id: int = None):
        """Add a tiny test group and attempt a guild sync. Cleans up after itself."""
        tree = self.bot.tree
        GID = guild_id
        test_name = "mcoc_test_tmp"
        test_group = app_commands.Group(name=test_name, description="temporary test group")
        try:
            try:
                tree.remove_command(test_name)
            except Exception:
                pass
            tree.add_command(test_group)
            if GID:
                res = await tree.sync(guild=Object(id=GID))
            else:
                res = await tree.sync()
            if hasattr(res, "__len__"):
                names = [c.name for c in res]
                await ctx.send(f"Test group sync returned {len(res)} commands: {names[:50]}")
            else:
                await ctx.send(f"Test group sync returned: {res}")
        except Exception as e:
            await ctx.send(f"Failed to add/sync test group: {type(e).__name__} {e}")
        finally:
            try:
                tree.remove_command(test_name)
            except Exception:
                pass

    # -----------------------
    # Clear disabled entries
    # -----------------------
    @commands.command(name="diag clear_disabled")
    @commands.is_owner()
    async def diag_clear_disabled(self, ctx, *names: str):
        """Remove entries from tree._disabled_global_commands. Pass names or none to show current keys."""
        tree = self.bot.tree
        disabled = getattr(tree, "_disabled_global_commands", None)
        if not disabled:
            await ctx.send("No _disabled_global_commands map found")
            return
        if not names:
            await ctx.send(f"Disabled keys sample: {list(disabled.keys())[:200]}")
            return
        removed = []
        for n in names:
            try:
                if n in disabled:
                    disabled.pop(n, None)
                    removed.append(n)
            except Exception as e:
                await ctx.send(f"Error removing {n}: {type(e).__name__} {e}")
        await ctx.send(f"Removed disabled keys: {removed}")

    # -----------------------
    # Show application info
    # -----------------------
    @commands.command(name="diag appinfo")
    @commands.is_owner()
    async def diag_appinfo(self, ctx):
        """Show application info and owner details."""
        info = await self.bot.application_info()
        await ctx.send(f"Application id: {info.id}\nOwner: {getattr(info, 'owner', None)}\nBot id: {self.bot.user.id}")

    # -----------------------
    # Show permissions and guild membership
    # -----------------------
    @commands.command(name="diag perms")
    @commands.is_owner()
    async def diag_perms(self, ctx, guild_id: int = None):
        """Show whether bot has Manage Guild and Use Application Commands in a guild."""
        if not guild_id:
            await ctx.send("Pass a guild id")
            return
        guild = self.bot.get_guild(guild_id)
        if not guild:
            await ctx.send("Bot is not in that guild")
            return
        me = guild.get_member(self.bot.user.id)
        if not me:
            await ctx.send("Bot member not found in guild")
            return
        perms = me.guild_permissions
        await ctx.send(f"Guild {guild_id} perms for bot: manage_guild={perms.manage_guild}, use_application_commands={perms.use_application_commands}, administrator={perms.administrator}")

def setup(bot):
    bot.add_cog(Diagnostics(bot))
