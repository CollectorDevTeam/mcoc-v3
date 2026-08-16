from redbot.core import commands, Config
import discord
import asyncio
from .api import MCOCHubAPI
from .cache import CacheManager
from .champions import ChampionsCommands
from .roster import RosterCommands
from .admin import AdminCommands
from .alliance import AllianceCommands

class CollectorBot(commands.Cog):
    """CollectorBot: MCOC data, roster tools, and admin controls."""

    def __init__(self, bot):
        self.bot = bot
        self.api = MCOCHubAPI()
        self.cache = CacheManager()
        self.config = Config.get_conf(self, identifier=9876543210)
        self.config.register_global(
            sync_interval=24,
            cache_version=0,
            collector_devteam_role=None
        )

        # Load submodules
        self.champions = ChampionsCommands(self)
        self.roster = RosterCommands(self)
        self.admin = AdminCommands(self)
        self.alliance = AllianceCommands(self)

        # Background sync
        self.sync_task = bot.loop.create_task(self._sync_loop())

    async def _sync_loop(self):
        await self.bot.wait_until_ready()
        while True:
            interval = await self.config.sync_interval()
            await self.sync_data()
            await asyncio.sleep(interval * 3600)

    async def sync_data(self):
        # TODO: call API client, diff, update cache
        champions = await self.api.get_champions()
        abilities = await self.api.get_abilities()
        tags = await self.api.get_tags()
        synergies = await self.api.get_synergies()

        #TODO: diff + cache updates
        self.cache._diff_and_save("champions", champions)
        self.cache._diff_and_save("abilities", abilities)
        self.cache._diff_and_save("tags", tags)
        self.cache._diff_and_save("synergies", synergies)
        self.cache._save_metadata()
        return True

    async def cog_load(self):
            # Register slash commands
            self.bot.tree.add_command(self.champions.info)
            self.bot.tree.add_command(self.champions.abilities)
            self.bot.tree.add_command(self.champions.synergies)
            self.bot.tree.add_command(self.champions.tags)
            self.bot.tree.add_command(self.champions.stats)

            self.bot.tree.add_command(self.roster.add)
            self.bot.tree.add_command(self.roster.remove)
            self.bot.tree.add_command(self.roster.update)
            self.bot.tree.add_command(self.roster.list)
            self.bot.tree.add_command(self.roster.export)
            self.bot.tree.add_command(self.roster.clear)

    # Slash command groups
    @commands.group()
    async def mcoc(self, ctx):
        """MCOC commands."""
        pass

    @commands.group()
    async def mcocadmin(self, ctx):
        """Admin commands."""
        pass

async def setup(bot):
    await bot.add_cog(CollectorBot(bot))
