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

        # API client will be initialized in cog_load()
        self.api = None

        # Cache manager
        self.cache = CacheManager()

        # Persistent config
        self.config = Config.get_conf(self, identifier=9876543210)
        self.config.register_global(
            api_key=None,                 # <-- API key stored here
            sync_interval=24,             # hours
            cache_version=0,
            collector_devteam_role=None
        )

        # Submodules
        self.champions = ChampionsCommands(self)
        self.roster = RosterCommands(self)
        self.admin = AdminCommands(self)
        self.alliance = AllianceCommands(self)

        # Background sync task placeholder
        self.sync_task = None


    # ---------------------------------------------------------
    # Cog Load (async init)
    # ---------------------------------------------------------
    async def cog_load(self):
        # Load API key
        api_key = await self.config.api_key()
        if not api_key:
            raise RuntimeError(
                "MCOCHUB API key is not set. Use: [mcocadmin setapikey YOURKEY]"
            )

        # Initialize API client
        self.api = MCOCHubAPI(api_key)

        # Start background sync loop
        self.sync_task = self.bot.loop.create_task(self._sync_loop())

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


    # ---------------------------------------------------------
    # Background Sync Loop
    # ---------------------------------------------------------
    async def _sync_loop(self):
        await self.bot.wait_until_ready()

        while True:
            interval = await self.config.sync_interval()
            await self.sync_data()
            await asyncio.sleep(interval * 3600)


    # ---------------------------------------------------------
    # Sync Data from MCOCHUB
    # ---------------------------------------------------------
    async def sync_data(self):
        champions = await self.api.get_champions()
        abilities = await self.api.get_abilities()
        tags = await self.api.get_tags()
        immunities = await self.api.get_immunities()

        # Version-based diff + save
        self.cache._diff_and_save("champions", champions)
        self.cache._diff_and_save("abilities", abilities)
        self.cache._diff_and_save("tags", tags)
        self.cache._diff_and_save("immunities", immunities)

        self.cache._save_metadata()
        return True


    # ---------------------------------------------------------
    # Command Groups
    # ---------------------------------------------------------
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
