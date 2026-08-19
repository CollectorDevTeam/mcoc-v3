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
    # Deferred post-load sync task
    # ---------------------------------------------------------
    async def _deferred_post_load_sync(self, delay: float = 1.0):
        """
        Run a short delayed sync off the main load path so console I/O doesn't block the event loop.
        Stored on self._post_load_sync_task so it can be cancelled on unload.
        """
        try:
            await asyncio.sleep(delay)  # give the bot a moment to finish startup
            log.debug("Deferred sync: starting tree.sync() after delay=%s", delay)
            try:
                res = await self.bot.tree.sync()
                count = len(res) if hasattr(res, "__len__") else 0
                log.info("Deferred Application command tree sync completed; %d entries", count)
                # If global sync returned nothing, attempt a targeted guild sync for verification
                if count == 0:
                    try:
                        from discord import Object as DiscordObject
                        GID = 215271081517383682  # CDT test guild
                        log.debug("Deferred sync: global returned 0; attempting guild sync to %s", GID)
                        gres = await self.bot.tree.sync(guild=DiscordObject(id=GID))
                        log.info("Deferred post-load guild sync result: %d entries", len(gres) if hasattr(gres, "__len__") else 0)
                    except Exception:
                        log.exception("Deferred post-load guild sync attempt failed")
            except Exception:
                log.exception("Deferred tree.sync() failed")
        except asyncio.CancelledError:
            log.debug("Deferred post-load sync task was cancelled")
        except Exception:
            log.exception("Unexpected error in deferred post-load sync")


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
        from .prefix.commands import MCOCPrefix

        log.debug("Instantiating slash groups")

        # Instantiate groups defensively (do not let constructor exceptions bubble)
        try:
            self.champions_slash = ChampionSlash(self)
            if getattr(self.champions_slash, "_init_failed", False):
                log.warning("ChampionSlash reported init failure during construction")
                self.champions_slash = None
        except Exception:
            log.exception("ChampionSlash constructor raised; skipping slash group")
            self.champions_slash = None

        try:
            self.roster_slash = RosterSlash(self)
            if getattr(self.roster_slash, "_init_failed", False):
                log.warning("RosterSlash reported init failure during construction")
                self.roster_slash = None
        except Exception:
            log.exception("RosterSlash constructor raised; skipping slash group")
            self.roster_slash = None

        try:
            self.admin_slash = AdminSlash(self)
            if getattr(self.admin_slash, "_init_failed", False):
                log.warning("AdminSlash reported init failure during construction")
                self.admin_slash = None
        except Exception:
            log.exception("AdminSlash constructor raised; skipping slash group")
            self.admin_slash = None

        log.debug("Slash groups instantiated")

        # Register prefix commands cog (reuses this cog's api/cache)
        try:
            self.prefix_cog = MCOCPrefix(self)
            await self.bot.add_cog(self.prefix_cog)
            log.debug("Prefix Commands cog added to bot")
        except Exception:
            log.exception("Failed to add prefix commands cog")

        # Key getter that reads Red's shared API tokens
        async def _get_mcochub_key():
            try:
                shared = await self.bot.get_shared_api_tokens()
                log.debug("bot.get_shared_api_tokens returned type=%s", type(shared).__name__)
                if isinstance(shared, dict):
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
            try:
                await self.bot.send_to_owners(
                    "⚠️ MCOCHUB API token not found in Red shared API tokens. Use `///set api mcochub <token>` to provide it."
                )
            except Exception:
                log.exception("Failed to notify owners about missing API token")

        # Register slash groups safely: remove any existing registration first to avoid duplicates
        for name, group in [
            ("champ", self.champions_slash),
            ("roster", self.roster_slash),
            ("mcocadmin", self.admin_slash),
        ]:
            if not group:
                log.debug("Slash group %s is None; skipping add", name)
                continue

            try:
                existing = None
                try:
                    existing = self.bot.tree.get_command(name)
                except Exception:
                    existing = None

                if existing:
                    try:
                        log.info("Removing previously registered app command '%s' before re-adding", name)
                        self.bot.tree.remove_command(name)
                    except Exception:
                        log.exception("Failed to remove existing app command %s; skipping add", name)
                        continue

                # Add the group to the tree
                try:
                    self.bot.tree.add_command(group)
                    log.debug("TRACE: added slash group %s", name)
                except Exception:
                    log.exception("Failed to add slash group %s", name)
            except Exception:
                log.exception("Unexpected error while handling slash group %s", name)

        # Defensive cleanup: clear stale disabled entries for our groups if present
        try:
            disabled = getattr(self.bot.tree, "_disabled_global_commands", None)
            if disabled:
                for key in ("champ", "roster", "mcocadmin"):
                    if key in disabled:
                        log.debug("Found stale disabled entry for %s; removing from _disabled_global_commands", key)
                        try:
                            disabled.pop(key, None)
                        except Exception:
                            log.exception("Failed to pop %s from _disabled_global_commands", key)
                log.debug("_disabled_global_commands after cleanup: %s", list(disabled.keys()))
            else:
                log.debug("No _disabled_global_commands present at load time")
        except Exception:
            log.exception("Error while attempting to clean _disabled_global_commands during cog_load")

        # Debug: list what the tree currently exposes (top-level and counts) — concise output
        try:
            top_cmds = self.bot.tree.get_commands()
            top_names = [c.name for c in top_cmds]
            log.debug("Local tree top-level commands after add: count=%d names=%s", len(top_names), top_names[:10])
            for cmd in top_cmds:
                children = getattr(cmd, "children", None) or getattr(cmd, "commands", None)
                log.debug("About to sync command %s children_count=%d", cmd.name, len(children) if children else 0)
        except Exception:
            log.exception("Failed to enumerate bot.tree.get_commands() during cog_load debug")

        # Schedule a deferred sync task instead of awaiting it inline (prevents blocking)
        try:
            self._post_load_sync_task = self.bot.loop.create_task(self._deferred_post_load_sync(delay=3.0))
            log.debug("Scheduled deferred post-load tree sync task: %s", getattr(self, "_post_load_sync_task", None))
        except Exception:
            log.exception("Failed to schedule deferred post-load sync task")

    # ---------------------------------------------------------
    # Cog Unload (cleanup)
    # ---------------------------------------------------------
    async def cog_unload(self):
        log.info("Unloading MCOC cog; cleaning up background tasks and sessions")

        # Cancel background sync loop task
        if getattr(self, "sync_task", None):
            log.debug("Cancelling sync_task")
            try:
                self.sync_task.cancel()
            except Exception:
                log.exception("Error cancelling sync_task")
            try:
                await asyncio.wait_for(self.sync_task, timeout=10)
                log.debug("sync_task finished cleanly")
            except asyncio.TimeoutError:
                log.warning("sync_task did not finish within timeout; continuing unload.")
            except asyncio.CancelledError:
                log.debug("sync_task cancelled")
            except Exception:
                log.exception("Exception while awaiting sync_task during unload")
            finally:
                self.sync_task = None

        # Cancel deferred post-load sync task if present
        if getattr(self, "_post_load_sync_task", None):
            try:
                log.debug("Cancelling deferred post-load sync task")
                self._post_load_sync_task.cancel()
            except Exception:
                log.exception("Error cancelling deferred post-load sync task")
            try:
                await asyncio.wait_for(self._post_load_sync_task, timeout=5)
                log.debug("Deferred post-load sync task finished cleanly")
            except asyncio.TimeoutError:
                log.warning("Deferred post-load sync task did not finish within timeout; continuing unload.")
            except asyncio.CancelledError:
                log.debug("Deferred post-load sync task cancelled")
            except Exception:
                log.exception("Exception while awaiting deferred post-load sync task during unload")
            finally:
                self._post_load_sync_task = None

        # Close API session if present
        if getattr(self, "api", None):
            try:
                log.debug("Closing MCOCHubAPI session")
                await self.api.close()
                log.debug("MCOCHubAPI session closed")
            except Exception:
                log.exception("Error closing MCOCHubAPI session")
            finally:
                self.api = None

        # Remove app commands (slash groups) from the tree to avoid duplicates on reload
        try:
            tree = self.bot.tree
            for name in ("champ", "roster", "mcocadmin", "admin"):
                try:
                    # Remove from active global commands if present
                    try:
                        cmd = None
                        try:
                            cmd = tree.get_command(name)
                        except Exception:
                            cmd = None

                        if cmd:
                            try:
                                tree.remove_command(name)
                                log.info("Removed app command '%s' from tree during unload", name)
                            except Exception:
                                log.exception("Failed to remove app command %s during unload", name)
                    except Exception:
                        log.exception("Unexpected error while attempting to remove app command %s", name)

                    # Also remove from internal _global_commands map if present
                    try:
                        if getattr(tree, "_global_commands", None) and name in tree._global_commands:
                            tree._global_commands.pop(name, None)
                            log.debug("Popped %s from tree._global_commands during unload", name)
                    except Exception:
                        log.exception("Failed to pop %s from tree._global_commands", name)

                    # Also remove from internal _disabled_global_commands map if present
                    try:
                        if getattr(tree, "_disabled_global_commands", None) and name in tree._disabled_global_commands:
                            tree._disabled_global_commands.pop(name, None)
                            log.debug("Popped %s from tree._disabled_global_commands during unload", name)
                    except Exception:
                        log.exception("Failed to pop %s from tree._disabled_global_commands", name)

                except Exception:
                    log.exception("Unexpected error while cleaning app command %s", name)
        except Exception:
            log.exception("Error while cleaning up app commands during cog_unload")

        # remove prefix cog if present
        try:
            if getattr(self, "prefix_cog", None):
                try:
                    cog_name = self.prefix_cog.__class__.__name__
                    await self.bot.remove_cog(cog_name)
                    log.info("MCOC prefix commands cog removed")
                except Exception:
                    try:
                        await self.bot.remove_cog(self.prefix_cog)
                        log.info("MCOC prefix commands cog removed (fallback)")
                    except Exception:
                        log.exception("Failed to remove prefix cog during unload")
                finally:
                    self.prefix_cog = None
        except Exception:
            log.exception("Failed to remove prefix cog during unload (outer)")

        # Final debug: log remaining RedTree internal maps for post-unload inspection (concise)
        try:
            tree = self.bot.tree
            log.debug("Post-unload tree.get_commands(): count=%d", len(list(tree.get_commands())))
            log.debug("Post-unload _global_commands keys (sample): %s", list(getattr(tree, "_global_commands", {}) or {})[:10])
            log.debug("Post-unload _disabled_global_commands keys (sample): %s", list(getattr(tree, "_disabled_global_commands", {}) or {})[:10])
        except Exception:
            log.exception("Failed to inspect tree internals during cog_unload")

        log.info("MCOC cog_unload complete")

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
                log.debug("Sync loop sleep cancelled.")
                break
            except Exception:
                log.exception("Unexpected error during sync loop sleep; continuing.")
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
