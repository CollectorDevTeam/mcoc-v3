# mcoc/common/prestige.py
import aiohttp
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

log = logging.getLogger("red.mcoc.prestige")

VERSIONS_URL = "https://mcochub.insaneskull.com/data/versions.json"
PRESTIGE_URL = "https://mcochub.insaneskull.com/data/prestige.json"

# All combinations we want to cache
TIERS = [2, 3, 4, 5, 6, 7]
RANKS = [1, 2, 3, 4, 5]
ASCENSIONS = [0, 1, 2]

DEFAULT_PERSIST_FILENAME = "mcoc_prestige_cache.json"
ONE_DAY = timedelta(days=1)


class PrestigeManager:
    def __init__(self, bot, persist_path: Optional[Path] = None, session: Optional[aiohttp.ClientSession] = None):
        self.bot = bot
        self._session = session
        self._external_session = session is not None
        self.persist_path = Path(persist_path) if persist_path else Path.cwd() / DEFAULT_PERSIST_FILENAME
        self._cache: Dict[str, Dict[str, Any]] = {}  # key -> {"version": str, "payload": dict}
        self._meta: Dict[str, Any] = {"versions": {}, "last_checked": None}
        self._lock = asyncio.Lock()
        self._ensure_session_lock = asyncio.Lock()

        # load persisted cache if present
        try:
            self._load_from_disk()
            log.debug("PrestigeManager loaded cache from %s", self.persist_path)
        except Exception:
            log.exception("Failed to load prestige cache from disk")

    # -------------------------
    # Session helpers
    # -------------------------
    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            async with self._ensure_session_lock:
                if self._session is None:
                    self._session = aiohttp.ClientSession()
                    log.debug("PrestigeManager created internal aiohttp ClientSession")
        return self._session

    # -------------------------
    # Persistence
    # -------------------------
    def _load_from_disk(self) -> None:
        if not self.persist_path.exists():
            return
        try:
            with self.persist_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            self._meta = data.get("meta", self._meta)
            self._cache = data.get("data", {})
        except Exception:
            log.exception("Error loading prestige cache file")

    def _save_to_disk(self) -> None:
        try:
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            with self.persist_path.open("w", encoding="utf-8") as fh:
                json.dump({"meta": self._meta, "data": self._cache}, fh, ensure_ascii=False, indent=2)
            log.debug("Prestige cache saved to %s", self.persist_path)
        except Exception:
            log.exception("Error saving prestige cache to disk")

    # -------------------------
    # Key helpers
    # -------------------------
    @staticmethod
    def _key_for(tier: int, rank: int, asc: int) -> str:
        return f"{tier}|{rank}|{asc}"

    # -------------------------
    # Fetching helpers
    # -------------------------
    async def _fetch_json(self, url: str, params: Optional[Dict[str, Any]] = None, timeout: int = 30) -> Optional[Dict[str, Any]]:
        session = await self._ensure_session()
        try:
            async with session.get(url, params=params, timeout=timeout) as resp:
                text = await resp.text()
                if resp.status == 429:
                    raise RuntimeError("Rate limited")
                if resp.status != 200:
                    log.warning("Fetch %s returned status %s: %s", url, resp.status, text[:200])
                    return None
                return await resp.json()
        except Exception as e:
            log.exception("HTTP fetch failed for %s: %s", url, e)
            return None

    async def fetch_versions(self) -> Optional[Dict[str, str]]:
        """Fetch versions.json and return the dict, or None on failure."""
        data = await self._fetch_json(VERSIONS_URL)
        if not data:
            return None
        # versions.json is expected to be a mapping
        return data

    async def fetch_prestige_payload(self, tier: int, rank: int, asc: int, version: str) -> Optional[Dict[str, Any]]:
        """Fetch a single prestige payload for the given combination and version."""
        params = {"tier": tier, "rank": rank, "ascension": asc, "v": version}
        payload = await self._fetch_json(PRESTIGE_URL, params=params)
        return payload

    # -------------------------
    # Public update/check API
    # -------------------------
    async def check_and_update_all(self, force: bool = False) -> Tuple[bool, str]:
        """
        Check versions.json and update any prestige payloads whose version changed.
        Returns (changed, message).
        Respects once-per-day unless force=True.
        """
        async with self._lock:
            # once-per-day guard
            last_checked = self._meta.get("last_checked")
            if last_checked:
                try:
                    last_dt = datetime.fromisoformat(last_checked)
                except Exception:
                    last_dt = None
                if last_dt and not force:
                    if datetime.now(timezone.utc) - last_dt < ONE_DAY:
                        return False, "Checked recently; skipping (once-per-day)."

            versions = await self.fetch_versions()
            if not versions:
                return False, "Failed to fetch versions.json"

            prestige_version = versions.get("prestige")
            if not prestige_version:
                return False, "No prestige version in versions.json"

            # If cached meta version matches and not forced, skip full fetch
            cached_version = self._meta.get("versions", {}).get("prestige")
            if cached_version == prestige_version and not force:
                # update last_checked timestamp and persist
                self._meta["last_checked"] = datetime.now(timezone.utc).isoformat()
                self._save_to_disk()
                return False, "Prestige version unchanged; no update needed."

            # iterate all combos and fetch payloads where version differs
            updated = False
            for tier in TIERS:
                for rank in RANKS:
                    for asc in ASCENSIONS:
                        key = self._key_for(tier, rank, asc)
                        # If we already have this key and version matches, skip
                        existing = self._cache.get(key)
                        if existing and existing.get("version") == prestige_version:
                            continue
                        # fetch payload
                        try:
                            payload = await self.fetch_prestige_payload(tier, rank, asc, prestige_version)
                            if payload:
                                # store
                                self._cache[key] = {"version": prestige_version, "payload": payload}
                                updated = True
                                log.info("Prestige payload updated for %s (v=%s)", key, prestige_version)
                            else:
                                log.warning("No payload for %s (v=%s)", key, prestige_version)
                        except Exception:
                            log.exception("Failed to fetch prestige for %s", key)
                            # continue to next combo

            # update meta and persist
            self._meta.setdefault("versions", {})["prestige"] = prestige_version
            self._meta["last_checked"] = datetime.now(timezone.utc).isoformat()
            self._save_to_disk()

            return updated, "Update complete."

    # -------------------------
    # Query helpers
    # -------------------------
    def get_prestige_table(self, tier: int, rank: int, asc: int) -> Optional[Dict[str, Any]]:
        """Return the raw payload for the given combo, or None."""
        key = self._key_for(tier, rank, asc)
        entry = self._cache.get(key)
        if not entry:
            return None
        return entry.get("payload")

    def get_prestige_value(self, slug: str, tier: int, rank: int, asc: int, sig: int = 0) -> Optional[int]:
        """
        Return the prestige integer for the champion slug at the given sig level.
        If exact sig not present, attempt nearest lower sig key (e.g., 40 -> 40, else 20, else 0).
        """
        payload = self.get_prestige_table(tier, rank, asc)
        if not payload:
            return None
        rows = payload.get("rows") or []
        # find row by slug
        for r in rows:
            if (r.get("slug") or "").lower() == slug.lower() or (r.get("name") or "").lower() == slug.lower():
                sigs = r.get("sigs") or {}
                # sig keys are strings like "0","20","40"... choose best match
                if str(sig) in sigs:
                    return int(sigs[str(sig)])
                # fallback: find highest key <= sig
                keys = sorted([int(k) for k in sigs.keys() if k.isdigit()])
                best = None
                for k in keys:
                    if k <= sig:
                        best = k
                    else:
                        break
                if best is not None:
                    return int(sigs[str(best)])
                # final fallback: try 0
                if "0" in sigs:
                    return int(sigs["0"])
                return None
        return None

    # -------------------------
    # Cleanup
    # -------------------------
    async def close(self) -> None:
        if not self._external_session and getattr(self, "_session", None):
            try:
                await self._session.close()
            except Exception:
                log.exception("Error closing session")
            self._session = None
