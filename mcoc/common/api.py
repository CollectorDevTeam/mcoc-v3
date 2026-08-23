# mcoc/api.py
import aiohttp
import asyncio
import logging
import random
from typing import Optional, Callable, Awaitable, Any

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
        self._prefer_bearer = True


        log.info("MCOCHubAPI initialized (external_session=%s)", self._external_session)
        if self._static_key:
            log.debug("MCOCHubAPI created with static api_key provided (REDACTED)")
        else:
            log.debug("MCOCHubAPI created with key_getter=%s", bool(self._key_getter))

    async def _ensure_session(self) -> aiohttp.ClientSession:
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
            except Exception:
                log.exception("Error while fetching MCOCHub API key from key_getter")
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
    async def _fetch_bearer(self, endpoint: str) -> Optional[Any]:
        api_key = await self._resolve_key()
        if not api_key:
            return None

        url = f"{self.BASE_URL}/{endpoint}"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        session = await self._ensure_session()
        async with self._request_semaphore:
            async with session.get(url, headers=headers) as resp:
                text = await resp.text()

                if resp.status == 401 or "Unauthenticated" in text:
                    raise UnauthenticatedError("Bearer failed")

                if resp.status == 429:
                    raise RateLimitedError("Rate limited")

                if resp.status != 200:
                    return None

                return await resp.json()

    async def _fetch_param(self, endpoint: str) -> Optional[Any]:
        api_key = await self._resolve_key()
        if not api_key:
            return None

        # Build URL manually so aiohttp does NOT encode the pipe character
        url = f"{self.BASE_URL}/{endpoint}?api_key={api_key}"

        headers = {"Accept": "application/json"}

        session = await self._ensure_session()
        async with self._request_semaphore:
            async with session.get(url, headers=headers) as resp:
                text = await resp.text()

                if resp.status == 401 or "Unauthenticated" in text:
                    raise UnauthenticatedError("Param failed")

                if resp.status == 429:
                    raise RateLimitedError("Rate limited")

                if resp.status != 200:
                    return None

                return await resp.json()

    async def _fetch(self, endpoint: str) -> Optional[Any]:
        # Try bearer first if preferred
        if self._prefer_bearer:
            try:
                return await self._fetch_bearer(endpoint)
            except UnauthenticatedError:
                log.warning("Bearer auth failed; switching to param mode for this sync.")
                self._prefer_bearer = False
            except RateLimitedError:
                raise
            except Exception:
                log.exception("Bearer fetch failed unexpectedly")

        # Fallback to param mode
        try:
            return await self._fetch_param(endpoint)
        except RateLimitedError:
            raise
        except Exception:
            log.exception("Param fetch failed unexpectedly")
            return None

    # -----------------------------
    # Champions (full list only)
    # -----------------------------
    async def get_champions(self) -> Optional[Any]:
        log.debug("Fetching champions from MCOCHub")
        return await self._fetch("champions")

    # -----------------------------
    # Tags
    # -----------------------------
    async def get_tags(self) -> Optional[Any]:
        log.debug("Fetching tags from MCOCHub")
        return await self._fetch("tags")

    # -----------------------------
    # Abilities
    # -----------------------------
    async def get_abilities(self) -> Optional[Any]:
        log.debug("Fetching abilities from MCOCHub")
        return await self._fetch("abilities")

    # -----------------------------
    # Immunities
    # -----------------------------
    async def get_immunities(self) -> Optional[Any]:
        log.debug("Fetching immunities from MCOCHub")
        return await self._fetch("immunities")

    # -----------------------------
    # Cleanup
    # -----------------------------
    async def close(self) -> None:
        log.info("Closing MCOCHubAPI session (external=%s)", self._external_session)
        if not self._external_session and getattr(self, "_session", None) and not getattr(self._session, "closed", False):
            try:
                await self._session.close()
                log.debug("aiohttp ClientSession closed")
            except Exception:
                log.exception("Error closing aiohttp ClientSession")
        self._session = None
        log.debug("MCOCHubAPI.close() complete")
