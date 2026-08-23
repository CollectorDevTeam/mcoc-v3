# mcoc/api.py
import aiohttp
import asyncio
import logging
import random
from typing import Optional, Callable, Awaitable, Any
from yarl import URL


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
        if self._static_key:
            api_key = str(self._static_key)
            log.debug(f"[MCOCHubAPI] Resolved static API key starts with: {api_key[:5]}")
            return api_key

        if self._key_getter:
            tokens = await self._key_getter()
            if not tokens:
                log.warning("[MCOCHubAPI] No shared tokens for 'mcochub'.")
                return None

            api_key = tokens.get("apikey")
            if not api_key:
                log.warning("[MCOCHubAPI] 'mcochub' has no 'apikey' set.")
                return None

            log.debug(f"[MCOCHubAPI] Resolved shared API key starts with: {api_key[:5]}")
            return api_key

        log.warning("[MCOCHubAPI] No API key available. Use: ///set api mcochub apikey,<yourkey>")
        return None
        
    # -----------------------------
    # Generic fetch helper
    # -----------------------------
    async def _fetch_bearer(self, endpoint: str) -> Optional[Any]:
        api_key = await self._resolve_key()
        if not api_key:
            return None
        log.debug(f"Bearer mode using key starting with: {api_key[:5]}")

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
        log.debug(f"Param mode using key starting with: {api_key[:5]}")

        # Build raw URL manually
        raw_url = f"{self.BASE_URL}/{endpoint}?api_key={api_key}"

        # Prevent aiohttp from re-encoding the pipe character
        url = URL(raw_url, encoded=True)

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
                    log.warning("Param mode error %s for %s: %s", resp.status, url, text[:200])
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
