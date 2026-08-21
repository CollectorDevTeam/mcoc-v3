# mcoc/api.py
import aiohttp
import asyncio
import logging
from typing import Optional, Callable, Awaitable

log = logging.getLogger("red.mcoc.api")

class UnauthenticatedError(Exception):
    """Raised when API returns unauthenticated / invalid key (401 or body message)."""

class RateLimitedError(Exception):
    """Raised when API indicates rate limiting (429 or Too Many Attempts)."""

class MCOCHubAPI:
    BASE_URL = "https://mcochub.insaneskull.com/api/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        key_getter: Optional[Callable[[], Awaitable[Optional[str]]]] = None,
        session: Optional[aiohttp.ClientSession] = None,
        timeout: int = 30,        
    ):
        """
        - api_key: direct API key string (optional).
        - key_getter: async callable returning the API key (optional).
        - session: optional aiohttp.ClientSession to reuse (optional).
        - timeout: request timeout in seconds.
        """
        self._static_key = api_key
        self._key_getter = key_getter
        self._external_session = session is not None
        self._session = session
        self._timeout = timeout
        self._request_semaphore = asyncio.Semaphore(5)  # Limit concurrent requests to avoid rate limiting
        # self._session = session or aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout))

        log.info("MCOCHubAPI initialized (external_session=%s)", self._external_session)
        if self._static_key:
            log.debug("MCOCHubAPI created with static api_key provided (REDACTED)")
        else:
            log.debug("MCOCHubAPI created with key_getter=%s", bool(self._key_getter))

    async def _ensure_session(self):
        if self._session is None:
            # create session lazily when the loop is running
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self._timeout))
            log.debug("Created internal aiohttp ClientSession")
        return self._session

    async def _resolve_key(self) -> Optional[str]:
        # Prefer static key if provided
        if self._static_key:
            log.debug("Using static API key (REDACTED)")
            return str(self._static_key)

        if self._key_getter:
            try:
                key = await self._key_getter()
                log.debug("key_getter returned type=%s", type(key).__name__)
            except Exception as e:
                log.exception("Error while fetching MCOCHub API key from key_getter: %s", e)
                return None

            # If the getter returned None, bail
            if not key:
                log.debug("key_getter returned no key")
                return None

            # If it's already a string/number, return it
            if isinstance(key, (str, int, float)):
                log.debug("Resolved API key from key_getter (REDACTED)")
                return str(key)

            # If it's a dict, try common shapes: {"api": "token"}, {"token": "..."}, {"key": "..."}
            if isinstance(key, dict):
                for candidate in ("api", "token", "key", "value"):
                    if candidate in key and isinstance(key[candidate], (str, int, float)):
                        log.debug("Extracted API key from dict using candidate '%s' (REDACTED)", candidate)
                        return str(key[candidate])
                # If dict has a single value that's a string, return it
                vals = [v for v in key.values() if isinstance(v, (str, int, float))]
                if len(vals) == 1:
                    log.debug("Extracted API key from single-value dict (REDACTED)")
                    return str(vals[0])

            # Last resort: try to stringify (not ideal, but prevents crash)
            try:
                s = str(key)
                log.debug("Coerced API key to string from unexpected type (REDACTED)")
                return s
            except Exception:
                log.warning("Unable to coerce MCOCHub API key to string; got type %s", type(key))
                return None

        log.debug("No static key and no key_getter available")
        return None


    # -----------------------------
    # Generic fetch helper
    # -----------------------------
    import random, asyncio

    async def _fetch(self, endpoint: str):
        url = f"{self.BASE_URL}/{endpoint}"
        api_key = await self._resolve_key()
        if not api_key:
            log.warning("MCOCHub API key not available; skipping request to %s", url)
            return None

        headers = {"Accept": "application/json"}
        params = {"api_key": api_key}
        log.debug("MCOCHub request GET %s params=%s", url, {"api_key": "REDACTED"})

        # small retry loop for transient errors
        attempts = 2
        backoff_base = 0.5
        for attempt in range(1, attempts + 1):
            try:
                session = await self._ensure_session()
                # limit concurrency to avoid bursts
                async with self._request_semaphore:
                    async with session.get(url, headers=headers, params=params) as resp:
                        text = await resp.text()
                        if resp.status == 401 or "Unauthenticated" in text:
                            log.error("MCOCHUB API unauthenticated for %s; status=%s body=%s", url, resp.status, text[:200])
                            raise UnauthenticatedError("Unauthenticated")
                        if resp.status == 429 or "Too Many Attempts" in text:
                            log.warning("MCOCHUB API rate limited for %s; status=%s", url, resp.status)
                            raise RateLimitedError("Rate limited")
                        if resp.status != 200:
                            log.warning("MCOCHUB API error %s for %s: %s", resp.status, url, text[:200])
                            return None
                        try:
                            result = await resp.json()
                            if isinstance(result, dict):
                                log.debug("MCOCHUB API success for %s: returned keys=%s", url, list(result.keys()))
                            else:
                                log.debug("MCOCHUB API success for %s: returned type=%s", url, type(result).__name__)
                            return result
                        except Exception:
                            log.exception("Failed to parse JSON from %s: %s", url, text[:200])
                            # fall through to retry if attempt remains
            except asyncio.CancelledError:
                log.debug("Request to %s cancelled", url)
                raise
            except UnauthenticatedError:
                raise
            except RateLimitedError:
                raise
            except Exception as e:
                log.exception("MCOCHUB API exception for %s on attempt %d: %s", url, attempt, e)
            # backoff before retry
            if attempt < attempts:
                delay = backoff_base * (2 ** (attempt - 1)) + random.random() * 0.1
                log.debug("Retrying %s after %.2fs", url, delay)
                await asyncio.sleep(delay)
        return None

    # -----------------------------
    # Champions (full list only)
    # -----------------------------
    async def get_champions(self):
        log.debug("Fetching champions from MCOCHub")
        return await self._fetch("champions")

    # -----------------------------
    # Tags
    # -----------------------------
    async def get_tags(self):
        log.debug("Fetching tags from MCOCHub")
        return await self._fetch("tags")

    # -----------------------------
    # Abilities
    # -----------------------------
    async def get_abilities(self):
        log.debug("Fetching abilities from MCOCHub")
        return await self._fetch("abilities")

    # -----------------------------
    # Immunities
    # -----------------------------
    async def get_immunities(self):
        log.debug("Fetching immunities from MCOCHub")
        return await self._fetch("immunities")

    # -----------------------------
    # Cleanup
    # -----------------------------
    async def close(self):
        log.info("Closing MCOCHubAPI session (external=%s)", self._external_session)
        if not self._external_session and getattr(self, "_session", None) and not self._session.closed:
            try:
                await self._session.close()
                log.debug("aiohttp ClientSession closed")
            except Exception:
                log.exception("Error closing aiohttp ClientSession")
        self._session = None
        log.debug("MCOCHubAPI.close() complete")

