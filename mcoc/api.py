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
        self.session = session or aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout))

    async def _resolve_key(self) -> Optional[str]:
        # Prefer static key if provided
        if self._static_key:
            return str(self._static_key)

        if self._key_getter:
            try:
                key = await self._key_getter()
            except Exception as e:
                log.exception("Error while fetching MCOCHub API key from key_getter: %s", e)
                return None

            # If the getter returned None, bail
            if not key:
                return None

            # If it's already a string/number, return it
            if isinstance(key, (str, int, float)):
                return str(key)

            # If it's a dict, try common shapes: {"api": "token"}, {"token": "..."}, {"key": "..."}
            if isinstance(key, dict):
                for candidate in ("api", "token", "key", "value"):
                    if candidate in key and isinstance(key[candidate], (str, int, float)):
                        return str(key[candidate])
                # If dict has a single value that's a string, return it
                vals = [v for v in key.values() if isinstance(v, (str, int, float))]
                if len(vals) == 1:
                    return str(vals[0])

            # Last resort: try to stringify (not ideal, but prevents crash)
            try:
                return str(key)
            except Exception:
                log.warning("Unable to coerce MCOCHub API key to string; got type %s", type(key))
                return None

        return None


    # -----------------------------
    # Generic fetch helper
    # -----------------------------
    async def _fetch(self, endpoint: str):
        url = f"{self.BASE_URL}/{endpoint}"
        api_key = await self._resolve_key()
        if not api_key:
            log.warning("MCOCHub API key not available; skipping request to %s", url)
            return None

        headers = {"Accept": "application/json"}
        params = {"api_key": api_key}

        try:
            async with self.session.get(url, headers=headers, params=params) as resp:
                text = await resp.text()
                # Explicit auth / rate-limit handling
                if resp.status == 401 or "Unauthenticated" in text:
                    log.warning("MCOCHUB API unauthenticated for %s", url)
                    raise UnauthenticatedError("Unauthenticated")
                if resp.status == 429 or "Too Many Attempts" in text:
                    log.warning("MCOCHUB API rate limited for %s", url)
                    raise RateLimitedError("Rate limited")

                if resp.status != 200:
                    log.warning("MCOCHUB API error %s for %s: %s", resp.status, url, text)
                    return None

                try:
                    return await resp.json()
                except Exception:
                    log.exception("Failed to parse JSON from %s: %s", url, text)
                    return None

        except asyncio.CancelledError:
            raise
        except UnauthenticatedError:
            raise
        except RateLimitedError:
            raise
        except Exception as e:
            log.exception("MCOCHUB API exception for %s: %s", url, e)
            return None

    # -----------------------------
    # Champions (full list only)
    # -----------------------------
    async def get_champions(self):
        return await self._fetch("champions")

    # -----------------------------
    # Tags
    # -----------------------------
    async def get_tags(self):
        return await self._fetch("tags")

    # -----------------------------
    # Abilities
    # -----------------------------
    async def get_abilities(self):
        return await self._fetch("abilities")

    # -----------------------------
    # Immunities
    # -----------------------------
    async def get_immunities(self):
        return await self._fetch("immunities")

    # -----------------------------
    # Cleanup
    # -----------------------------
    async def close(self):
        if not self._external_session and self.session and not self.session.closed:
            await self.session.close()
