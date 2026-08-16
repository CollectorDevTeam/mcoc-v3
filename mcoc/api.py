import aiohttp
import asyncio
import logging

log = logging.getLogger("red.mcoc.api")

class MCOCHubAPI:
    BASE_URL = "https://mcochub.insaneskull.com/api/v1"

    def __init__(self, api_key: str, session: aiohttp.ClientSession = None):
        self.api_key = api_key
        self.session = session or aiohttp.ClientSession()

    # -----------------------------
    # Generic fetch helper
    # -----------------------------
    async def _fetch(self, endpoint: str):
        url = f"{self.BASE_URL}/{endpoint}"

        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

        try:
            async with self.session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    log.warning(f"MCOCHUB API error {resp.status} for {url}")
                    return None
                return await resp.json()
        except Exception as e:
            log.error(f"MCOCHUB API exception for {url}: {e}")
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
        await self.session.close()
