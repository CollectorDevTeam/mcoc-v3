from redbot.core import commands, Config
import asyncio

from .api import MCOCHubAPI
from .cache import CacheManager

# Slash groups
from .champions import ChampionSlash
from .roster import RosterSlash
from .admin import AdminSlash


class MCOC(commands.Cog):
    """CollectorBot: MCOC data, roster tools, and admin controls."""

    def __init__(self, bot):
        self.bot = bot

        # API client (initialized in cog_load)
        self.api = None

        # Cache manager
        self.cache = CacheManager()

        # Persistent config
        self.config = Config.get_conf(self, identifier=9876543210)
        self.config.register_global(
            api_key=None,
            sync_interval=24,
            cache_version=0,
            collector_devteam_role=None
        )

        # Slash command groups
        self.champions_slash = ChampionSlash(self)
        self.roster_slash = RosterSlash(self)
        self.admin_slash = AdminSlash(self)

        # Background sync task placeholder
        self.sync_task = None

    # ---------------------------------------------------------
    # Cog Load (async init)
    # ---------------------------------------------------------
    async def cog_load(self):
        api_key = await self.config.api_key()

        if api_key:
            # Live mode
            self.api = MCOCHubAPI(api_key)
            self.sync_task = self.bot.loop.create_task(self._sync_loop())
        else:
            # Offline mode
            self.api = None
            await self.bot.send_to_owners(
                "⚠️ MCOCHUB API key not set. CollectorBot is running in offline mode using local cache only."
            )

        # Register slash command groups
        self.bot.tree.add_command(self.champions_slash)
        self.bot.tree.add_command(self.roster_slash)
        self.bot.tree.add_command(self.admin_slash)

    # ---------------------------------------------------------
    # Background Sync Loop
    # ---------------------------------------------------------
    async def _sync_loop(self):
        await self.bot.wait_until_ready()

        while True:
            api_key = await self.config.api_key()
            if not api_key:
                # Offline mode → skip syncing
                await asyncio.sleep(3600)
                continue

            interval = await self.config.sync_interval()
            await self.sync_data()
            await asyncio.sleep(interval * 3600)

    # ---------------------------------------------------------
    # Sync Data from MCOCHUB
    # ---------------------------------------------------------
    async def sync_data(self):
        if not self.api:
            return False  # offline mode

        if not self.api:
            return False  # offline mode

        champions = await self.api.get_champions()
        abilities = await self.api.get_abilities()
        tags = await self.api.get_tags()
        immunities = await self.api.get_immunities()

        self.cache._diff_and_save("champions", champions)
        self.cache._diff_and_save("abilities", abilities)
        self.cache._diff_and_save("tags", tags)
        self.cache._diff_and_save("immunities", immunities)

        self.cache._save_metadata()
        return True


async def setup(bot):
    await bot.add_cog(CollectorBot(bot))
