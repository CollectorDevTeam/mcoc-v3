# mcoc/cache.py
import json
import hashlib
import pathlib
import datetime
import logging
import tempfile
import os
import asyncio
from typing import Optional, Any, Dict
from .cacheindex import CacheIndex
from pathlib import Path

log = logging.getLogger("red.mcoc.cache")


# Do NOT create directories at import time. Create them when CacheManager is instantiated.
DEFAULT_CACHE_DIR = pathlib.Path("data") / "cache"

from pathlib import Path
from redbot.core import data_manager

class CacheManager:
    def __init__(self, bot):
        self.bot = bot

        # Correct Red data directory for this cog
        base = data_manager.cog_data_path(raw_name="mcoc")
        self.cache_dir = base / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.metadata_file = self.cache_dir / "metadata.json"



    # -----------------------------
    # Metadata
    # -----------------------------
    @staticmethod
    def _read_json_file(path: pathlib.Path) -> Any:
        # helper for to_thread
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_metadata(self) -> Dict[str, Any]:
        try:
            if not self.metadata_file.exists():
                return {
                    "versions": {
                        "champions": None,
                        "tags": None,
                        "abilities": None,
                        "immunities": None,
                    },
                    "last_sync": None,
                }
            # synchronous read at startup is acceptable, but keep it safe
            try:
                data = self._read_json_file(self.metadata_file)
            except Exception:
                log.exception("Failed to read metadata.json; resetting metadata")
                return {
                    "versions": {
                        "champions": None,
                        "tags": None,
                        "abilities": None,
                        "immunities": None,
                    },
                    "last_sync": None,
                }

            if not isinstance(data, dict):
                raise ValueError("metadata.json malformed")
            data.setdefault(
                "versions",
                {
                    "champions": None,
                    "tags": None,
                    "abilities": None,
                    "immunities": None,
                },
            )
            data.setdefault("last_sync", None)
            return data
        except Exception:
            log.exception("Failed to load metadata.json; resetting metadata")
            return {
                "versions": {
                    "champions": None,
                    "tags": None,
                    "abilities": None,
                    "immunities": None,
                },
                "last_sync": None,
            }

    def _save_metadata(self) -> None:
        if not isinstance(self.metadata, dict):
            self.metadata = {
                "versions": {
                    "champions": None,
                    "tags": None,
                    "abilities": None,
                    "immunities": None,
                },
                "last_sync": None,
            }
        try:
            # schedule the async atomic write; prefer get_running_loop when available
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._atomic_write_json(self.metadata_file, self.metadata))
            except RuntimeError:
                # no running loop; fallback to blocking write
                self._atomic_write_json_blocking(self.metadata_file, self.metadata)
        except Exception:
            # fallback to blocking write if scheduling fails
            try:
                self._atomic_write_json_blocking(self.metadata_file, self.metadata)
            except Exception:
                log.exception("Failed to save metadata synchronously as fallback")

    # -----------------------------
    # Recency helper
    # -----------------------------
    def is_recent(self, hours: int = 24) -> bool:
        last = self.metadata.get("last_sync")
        if not last:
            return False
        try:
            last_dt = datetime.datetime.fromisoformat(last)
        except Exception:
            return False
        return (datetime.datetime.utcnow() - last_dt) < datetime.timedelta(hours=hours)

    # -----------------------------
    # Atomic write helper
    # -----------------------------
    @staticmethod
    def _atomic_write_json_blocking(path: pathlib.Path, data: Any) -> None:
        # blocking helper to be run in a thread
        fd, tmp = tempfile.mkstemp(dir=str(path.parent))
        try:
            # use os.fdopen to write to the fd safely
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            pathlib.Path(tmp).replace(path)
        except Exception:
            log.exception("Failed atomic write to %s", path)
            try:
                pathlib.Path(tmp).unlink()
            except Exception:
                pass

    async def _atomic_write_json(self, path: pathlib.Path, data: Any) -> None:
        # async wrapper that offloads the blocking write
        await asyncio.to_thread(self._atomic_write_json_blocking, path, data)

    # -----------------------------
    # Hash helper
    # -----------------------------
    def _hash(self, data: Any) -> str:
        raw = json.dumps(data, sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    # -----------------------------
    # Data Shape Helpers
    # -----------------------------
    def _make_key_from_item(self, item: Any, fallback_index: int) -> str:
        if not isinstance(item, dict):
            return str(fallback_index)
        if item.get("id"):
            return str(item["id"])
        if item.get("name"):
            return item["name"].lower()
        # stable fallback
        return hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest()[:12]

    def normalize_list_payload(self, payload: Optional[Dict[str, Any]], list_key: str) -> Optional[Dict[str, Any]]:
        """
        Generic normalizer for payloads that return a list under list_key.
        Returns canonical dict: {"version":..., "updated_at":..., "<list_key>": {id: item, ...}}
        """
        if not payload:
            return None
        version = payload.get("version")
        updated_at = payload.get("updated_at")
        items = payload.get(list_key, [])

        # If already canonical dict, return as-is
        if isinstance(items, dict):
            return {"version": version, "updated_at": updated_at, list_key: items}

        mapped: Dict[str, Any] = {}
        for i, item in enumerate(items):
            key = self._make_key_from_item(item, i)
            mapped[str(key)] = item

        return {"version": version, "updated_at": updated_at, list_key: mapped}

    def normalize_champions_payload(self, payload: Any) -> Optional[Dict[str, Any]]:
        return self.normalize_list_payload(payload, "champions")

    def normalize_abilities_payload(self, payload: Any) -> Optional[Dict[str, Any]]:
        return self.normalize_list_payload(payload, "abilities")

    def normalize_immunities_payload(self, payload: Any) -> Optional[Dict[str, Any]]:
        return self.normalize_list_payload(payload, "immunities")

    def normalize_tags_payload(self, payload: Any) -> Optional[Dict[str, Any]]:
        return self.normalize_list_payload(payload, "tags")

    # -----------------------------
    # Diff + Save
    # -----------------------------
    async def _diff_and_save(self, name: str, new_data: Any) -> bool:
        if not new_data:
            log.warning("No data returned for %s; skipping save.", name)
            return False

        # Normalize list-shaped payloads into canonical dicts
        if name == "champions":
            new_data = self.normalize_champions_payload(new_data)
        elif name == "abilities":
            new_data = self.normalize_abilities_payload(new_data)
        elif name in ("immunity", "immunities"):
            new_data = self.normalize_immunities_payload(new_data)
            name = "immunities"
        elif name == "tags":
            new_data = self.normalize_tags_payload(new_data)

        if not new_data:
            log.warning("Payload for %s could not be normalized; skipping.", name)
            return False

        new_version = new_data.get("version")
        old_version = self.metadata.get("versions", {}).get(name)

        if new_version == old_version:
            log.info("No changes detected for %s.", name)
            return False

        # Atomic write off the event loop
        try:
            await self._atomic_write_json(self.cache_dir / f"{name}.json", new_data)
        except Exception:
            log.exception("Failed to write cache file for %s", name)
            return False

        # Update metadata only after successful write
        self.metadata.setdefault("versions", {})
        self.metadata["versions"][name] = new_version
        self.metadata["last_sync"] = datetime.datetime.utcnow().isoformat()
        # save metadata off the loop as well
        try:
            await asyncio.to_thread(self._atomic_write_json_blocking, self.metadata_file, self.metadata)
        except Exception:
            log.exception("Failed to save metadata after updating %s", name)

        log.info("Updated cache for %s.", name)

        # Rebuild index off the event loop
        try:
            await asyncio.to_thread(self.index.rebuild)
        except Exception:
            log.exception("CacheIndex rebuild failed after updating %s", name)

        return True

    # -----------------------------
    # Public sync method
    # -----------------------------
    async def sync(self, api) -> bool:
        # If we synced recently, skip network calls
        if self.is_recent(hours=24):
            log.info("Cache was synced within the last 24 hours; skipping API requests.")
            # ensure index is built from existing files (offload if heavy)
            try:
                await asyncio.to_thread(self.index.rebuild)
            except Exception:
                log.exception("Index rebuild failed during short-circuit")
            return False

        updated = False

        # Prevent concurrent syncs
        async with self._sync_lock:
            try:
                champions = await api.get_champions()
                if champions is None:
                    log.warning("Champions endpoint returned no data; aborting sync to avoid waste.")
                    return False

                tags = await api.get_tags()
                if tags is None:
                    log.warning("Tags endpoint returned no data; aborting sync.")
                    return False

                abilities = await api.get_abilities()
                if abilities is None:
                    log.warning("Abilities endpoint returned no data; aborting sync.")
                    return False

                immunities = await api.get_immunities()
                if immunities is None:
                    log.warning("Immunities endpoint returned no data; aborting sync.")
                    return False

                # Only reach here if all calls returned non-None
                updated |= await self._diff_and_save("champions", champions)
                updated |= await self._diff_and_save("tags", tags)
                updated |= await self._diff_and_save("abilities", abilities)
                updated |= await self._diff_and_save("immunities", immunities)

                if updated:
                    log.info("Cache sync complete.")
                else:
                    log.info("Cache unchanged; metadata not updated.")

                # Rebuild index after sync (already done in _diff_and_save, but keep safe)
                try:
                    await asyncio.to_thread(self.index.rebuild)
                except Exception:
                    log.exception("Index rebuild failed after sync")
                return updated

            except Exception as e:
                from .api import UnauthenticatedError, RateLimitedError

                if isinstance(e, UnauthenticatedError):
                    log.error("Sync aborted: unauthenticated API key.")
                    raise
                if isinstance(e, RateLimitedError):
                    log.error("Sync aborted: rate limited by API.")
                    raise

                log.exception("Unexpected error during cache sync: %s", e)
                return False

    # -----------------------------
    # Lookup helpers (unchanged)
    # -----------------------------
    def get_champion(self, id_or_name: str) -> Optional[Dict[str, Any]]:
        id_or_name = id_or_name.lower()
        champs = self._load_file("champions").get("champions", {})

        # direct ID lookup
        if id_or_name in champs:
            return champs[id_or_name]

        # name lookup
        for champ in champs.values():
            try:
                if champ.get("name", "").lower() == id_or_name:
                    return champ
            except Exception:
                continue

        return None

    def get_all_tags(self) -> list:
        data = self._load_file("tags")
        tags = data.get("tags", {})
        if isinstance(tags, dict):
            return list(tags.values())
        return tags or []

    def get_all_abilities(self) -> list:
        data = self._load_file("abilities")
        abilities = data.get("abilities", {})
        if isinstance(abilities, dict):
            return list(abilities.values())
        return abilities or []

    def get_all_immunities(self) -> list:
        data = self._load_file("immunities")
        immunities = data.get("immunities", {})
        if isinstance(immunities, dict):
            return list(immunities.values())
        return immunities or []

    def get_all_champions(self) -> list:
        data = self._load_file("champions")
        champs = data.get("champions", {})
        if isinstance(champs, dict):
            return list(champs.values())
        if isinstance(champs, list):
            return champs
        return []

    # -----------------------------
    # File loader
    # -----------------------------
    async def _load_file_async(self, name: str) -> Dict[str, Any]:
        path = self.cache_dir / f"{name}.json"
        if not path.exists():
            return {}
        try:
            def _read():
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            return await asyncio.to_thread(_read)
        except Exception:
            log.exception("Failed to load cache file %s", path)
            return {}

    # Keep a synchronous wrapper for callers that expect sync behavior (e.g., command handlers)
    def _load_file(self, name: str) -> Dict[str, Any]:
        path = self.cache_dir / f"{name}.json"
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            log.exception("Failed to load cache file %s", path)
            return {}
