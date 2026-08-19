# mcoc/core.py
from redbot.core import commands, Config
import asyncio
import logging

from .api import MCOCHubAPI
from .cache import CacheManager

log = logging.getLogger("red.mcoc.core")

class MCOC(commands.Cog):
    """CollectorBot: MCOC data, roster tools, and admin controls."""

    def __init__(self, bot):
        self.bot = bot

        # API client (initialized in cog_load via shared token getter)
        self.api = None

        # Cache manager
        self.cache = CacheManager()

        # We keep the cog config for other settings, but NOT for the API key
        self.config = Config.get_conf(self, identifier=9876543210)
        self.config.register_global(
            sync_interval=24,
            cache_version=0,
            collector_devteam_role=None
        )

        # Slash command groups (created in cog_load)
        self.champions_slash = None
        self.roster_slash = None
        self.admin_slash = None

        # Background sync task placeholder
        self.sync_task = None

    # ---------------------------------------------------------
    # Cog Load (async init)
    # ---------------------------------------------------------
    async def cog_load(self):
        # Minimal trace for debugging
        log.debug("TRACE: cog_load started")

        # Create slash groups now (avoid import-time side effects)
        from .champions import ChampionSlash
        from .roster import RosterSlash
        from .admin import AdminSlash

        self.champions_slash = ChampionSlash(self)
        self.roster_slash = RosterSlash(self)
        self.admin_slash = AdminSlash(self)

        # Key getter that reads Red's shared API tokens
        async def _get_mcochub_key():
            try:
                shared = await self.bot.get_shared_api_tokens()
                if isinstance(shared, dict):
                    # use the exact service name you set with ///set api <service> <token>
                    return shared.get("mcochub")
            except Exception:
                log.exception("Failed to read shared API tokens")
            return None

        # Create API client that resolves the key at request time
        self.api = MCOCHubAPI(key_getter=_get_mcochub_key)

        # If a token exists now, start the sync loop; otherwise do not start it
        token_now = await _get_mcochub_key()
        if token_now:
            self.sync_task = self.bot.loop.create_task(self._sync_loop())
        else:
            await self.bot.send_to_owners(
                "⚠️ MCOCHUB API token not found in Red shared API tokens. Use `///set api mcochub <token>` to provide it."
            )

        # Register slash groups
        for name, group in [
            ("champ", self.champions_slash),
            ("roster", self.roster_slash),
            ("admin", self.admin_slash),
        ]:
            try:
                self.bot.tree.add_command(group)
                log.debug("TRACE: added slash group %s", name)
            except Exception:
                log.exception("Failed to add slash group %s", name)

        # Force a sync and capture errors
        try:
            res = await self.bot.tree.sync()
            log.debug("TRACE: tree sync completed; result: %s", res)
        except Exception:
            log.exception("Error during tree.sync()")

    # ---------------------------------------------------------
    # Cog Unload (cleanup)
    # ---------------------------------------------------------
    async def cog_unload(self):
        # Cancel background task
        if self.sync_task:
            self.sync_task.cancel()
            try:
                await self.sync_task
            except asyncio.CancelledError:
                pass

        # Close API session if owned by the API client
        if self.api:
            try:
                await self.api.close()
            except Exception:
                log.exception("Error closing MCOCHubAPI session")

    # ---------------------------------------------------------
    # Background Sync Loop
    # ---------------------------------------------------------
    async def _sync_loop(self):
        await self.bot.wait_until_ready()

        while True:
            try:
                # If API client is None, try to create or skip
                if not self.api:
                    log.debug("No API client available; skipping sync loop iteration.")
                    await asyncio.sleep(3600)
                    continue

                # Attempt a sync; this may raise UnauthenticatedError or RateLimitedError
                updated = await self.cache.sync(self.api)
                if updated:
                    log.info("Cache updated by sync loop.")
                else:
                    log.debug("No update performed this iteration.")

            except UnauthenticatedError:
                # Stop the loop permanently until token is fixed
                log.error("Stopping sync loop: API key unauthenticated. Fix token and reload cog.")
                break

            except RateLimitedError:
                # Back off aggressively: wait 1 hour before retrying
                log.warning("Rate limited by MCOCHub; backing off for 1 hour.")
                await asyncio.sleep(3600)
                continue

            except Exception:
                log.exception("Unexpected error in sync loop; sleeping 1 hour before retry.")
                await asyncio.sleep(3600)
                continue

            # Normal interval wait
            interval = await self.config.sync_interval()
            await asyncio.sleep(interval * 3600)

    # ---------------------------------------------------------
    # Sync Data from MCOCHUB
    # ---------------------------------------------------------
    async def sync_data(self):
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
    await bot.add_cog(MCOC(bot))
