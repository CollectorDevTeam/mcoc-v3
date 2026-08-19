# mcoc/core.py
from redbot.core import commands, Config
import asyncio
import logging

from .api import MCOCHubAPI, UnauthenticatedError, RateLimitedError
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
        log.info("MCOC cog_load starting")
        log.debug("TRACE: cog_load started")

        # Create slash groups now (avoid import-time side effects)
        from .champions import ChampionSlash
        from .roster import RosterSlash
        from .admin import AdminSlash

        log.debug("Instantiating slash groups")

        self.champions_slash = ChampionSlash(self)
        if self.champions_slash and not getattr(self.champions_slash, "_init_failed", False):
            self.bot.tree.add_command(self.champions_slash)
        else:
            log.warning("ChampionSlash not added due to init failure")

        self.roster_slash = RosterSlash(self)
        if self.roster_slash and not getattr(self.roster_slash, "_init_failed", False):
            self.bot.tree.add_command(self.roster_slash)
        else:
            log.warning("RosterSlash not added due to init failure")

        self.admin_slash = AdminSlash(self)
        if self.admin_slash and not getattr(self.admin_slash, "_init_failed", False):
            self.bot.tree.add_command(self.admin_slash)
        else:
            log.warning("AdminSlash not added due to init failure")
        log.debug("Slash groups instantiated")

        log.debug("Prefix Commands backup")
        from .prefix import MCOCPrefix
        # register prefix commands as a separate cog, passing self so it reuses api/cache
        self.prefix_cog = MCOCPrefix(self)
        await self.bot.add_cog(self.prefix_cog)
        log.debug("Prefix Commands cog added to bot")

        # Key getter that reads Red's shared API tokens
        async def _get_mcochub_key():
            try:
                shared = await self.bot.get_shared_api_tokens()
                log.debug("bot.get_shared_api_tokens returned type=%s", type(shared).__name__)
                if isinstance(shared, dict):
                    # use the exact service name you set with ///set api <service> <token>
                    token = shared.get("mcochub")
                    log.debug("Shared token present: %s", bool(token))
                    return token
            except Exception:
                log.exception("Failed to read shared API tokens")
            return None

        # Create API client that resolves the key at request time
        self.api = MCOCHubAPI(key_getter=_get_mcochub_key)
        log.info("MCOCHubAPI client created (key_getter attached)")

        # If a token exists now, start the sync loop; otherwise do not start it
        token_now = await _get_mcochub_key()
        if token_now:
            log.info("MCOCHUB token found; starting background sync task")
            self.sync_task = self.bot.loop.create_task(self._sync_loop())
        else:
            log.warning("MCOCHUB API token not found in shared tokens; running in offline mode")
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
            log.info("Application command tree sync completed; %d entries", len(res) if hasattr(res, "__len__") else 0)
        except Exception:
            log.exception("Error during tree.sync()")

    # ---------------------------------------------------------
    # Cog Unload (cleanup)
    # ---------------------------------------------------------
    async def cog_unload(self):
        log.info("Unloading MCOC cog; cleaning up background tasks and sessions")

        # Cancel background task
        if self.sync_task:
            log.debug("Cancelling sync_task")
            self.sync_task.cancel()
            try:
                await asyncio.wait_for(self.sync_task, timeout=10)
                log.debug("sync_task finished cleanly")
            except asyncio.TimeoutError:
                log.warning("sync_task did not finish within timeout; continuing unload.")
            except asyncio.CancelledError:
                log.debug("sync_task cancelled")
            except Exception:
                log.exception("Exception while awaiting sync_task during unload")

        # Close API session if present
        if self.api:
            try:
                log.debug("Closing MCOCHubAPI session")
                await self.api.close()
                log.debug("MCOCHubAPI session closed")
            except Exception:
                log.exception("Error closing MCOCHubAPI session")
            finally:
                self.api = None

        # remove prefix cog if present
        try:
            if getattr(self, "prefix_cog", None):
                await self.bot.remove_cog(self.prefix_cog.__class__.__name__)
                log.info("MCOC prefix commands cog removed")
        except Exception:
            log.exception("Failed to remove prefix cog during unload")

    # ---------------------------------------------------------
    # Background Sync Loop
    # ---------------------------------------------------------
    async def _sync_loop(self):
        log.info("Sync loop starting")
        await self.bot.wait_until_ready()
        log.debug("Bot ready; entering sync loop")

        while True:
            try:
                log.debug("Sync loop iteration starting")
                if not self.api:
                    log.debug("No API client available; sleeping 1 hour")
                    await asyncio.sleep(3600)
                    continue

                try:
                    log.debug("Invoking cache.sync()")
                    updated = await self.cache.sync(self.api)
                    log.debug("cache.sync() returned: %s", updated)
                except UnauthenticatedError:
                    log.error("Stopping sync loop: unauthenticated API key.")
                    # notify owners once
                    try:
                        await self.bot.send_to_owners("MCOCHub API key unauthenticated; sync loop stopped.")
                    except Exception:
                        log.exception("Failed to notify owners about unauthenticated key")
                    break
                except RateLimitedError:
                    log.warning("Rate limited by MCOCHub; backing off for 1 hour.")
                    await asyncio.sleep(3600)
                    continue

                if updated:
                    log.info("Cache updated by sync loop.")
                else:
                    log.debug("No update performed this iteration.")

            except asyncio.CancelledError:
                log.debug("Sync loop cancelled.")
                break
            except Exception:
                log.exception("Unexpected error in sync loop; sleeping 1 hour.")
                await asyncio.sleep(3600)

            # Normal interval wait
            try:
                interval = await self.config.sync_interval()
                log.debug("Sleeping for %s hours until next sync", interval)
                await asyncio.sleep(interval * 3600)
            except asyncio.CancelledError:
                log.debug("Sync loop cancelled during sleep.")
                break

    # ---------------------------------------------------------
    # Sync Data from MCOCHUB
    # ---------------------------------------------------------
    async def sync_data(self):
        if not self.api:
            log.debug("sync_data called but API client is not available")
            return False  # offline mode

        log.debug("Manual sync_data invoked")
        champions = await self.api.get_champions()
        abilities = await self.api.get_abilities()
        tags = await self.api.get_tags()
        immunities = await self.api.get_immunities()

        self.cache._diff_and_save("champions", champions)
        self.cache._diff_and_save("abilities", abilities)
        self.cache._diff_and_save("tags", tags)
        self.cache._diff_and_save("immunities", immunities)

        self.cache._save_metadata()
        log.info("Manual sync_data completed")
        return True


async def setup(bot):
    await bot.add_cog(MCOC(bot))
