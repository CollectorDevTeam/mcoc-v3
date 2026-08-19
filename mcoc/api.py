# mcoc/api.py
import aiohttp
import asyncio
import logging
from typing import Optional, Callable, Awaitable

log = logging.getLogger("red.mcoc.api")

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
        if self._static_key:
            return self._static_key
        if self._key_getter:
            try:
                key = await self._key_getter()
                return key
            except Exception as e:
                log.exception("Error while fetching MCOCHub API key from key_getter: %s", e)
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

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }

        try:
            async with self.session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    log.warning("MCOCHUB API error %s for %s: %s", resp.status, url, text)
                    return None
                return await resp.json()
        except asyncio.CancelledError:
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
