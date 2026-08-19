# mcoc/cache.py (imports unchanged)
import json
import hashlib
import pathlib
import datetime
import logging
import tempfile
from .cacheindex import CacheIndex

log = logging.getLogger("red.mcoc.cache")

CACHE_DIR = pathlib.Path("data/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class CacheManager:
    def __init__(self):
        self.metadata_file = CACHE_DIR / "metadata.json"
        self.metadata = self._load_metadata()

        # Build index AFTER metadata loads
        self.index = CacheIndex(self)

    # -----------------------------
    # Metadata
    # -----------------------------
    def _load_metadata(self):
        if not self.metadata_file.exists():
            return {
                "versions": {
                    "champions": None,
                    "tags": None,
                    "abilities": None,
                    "immunity": None,
                },
                "last_sync": None
            }
        try:
            return json.load(open(self.metadata_file, "r"))
        except Exception:
            log.exception("Failed to load metadata.json; resetting metadata")
            return {
                "versions": {
                    "champions": None,
                    "tags": None,
                    "abilities": None,
                    "immunity": None,
                },
                "last_sync": None
            }

    def _save_metadata(self):
        self._atomic_write_json(self.metadata_file, self.metadata)

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
    def _atomic_write_json(self, path: pathlib.Path, data):
        # write to temp file then replace to avoid partial writes
        fd, tmp = tempfile.mkstemp(dir=str(path.parent))
        try:
            with open(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            pathlib.Path(tmp).replace(path)
        except Exception:
            log.exception("Failed atomic write to %s", path)
            try:
                pathlib.Path(tmp).unlink()
            except Exception:
                pass

    # -----------------------------
    # Hash helper
    # -----------------------------
    def _hash(self, data):
        raw = json.dumps(data, sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    # -----------------------------
    # Diff + Save
    # -----------------------------
    def _diff_and_save(self, name, new_data):
        if not new_data:
            log.warning("No data returned for %s; skipping save.", name)
            return False

        new_version = new_data.get("version")
        old_version = self.metadata["versions"].get(name)

        if new_version == old_version:
            log.info(f"No changes detected for {name}.")
            return False

        # Write new cache file atomically
        self._atomic_write_json(CACHE_DIR / f"{name}.json", new_data)

        # Update metadata
        self.metadata["versions"][name] = new_version
        self.metadata["last_sync"] = datetime.datetime.utcnow().isoformat()

        log.info(f"Updated cache for {name}.")

        # Rebuild index
        self.index.rebuild()

        return True

    # -----------------------------
    # Public sync method
    # -----------------------------
    async def sync(self, api):
        """
        Syncs champions, tags, abilities, immunity from the API.
        - If last successful sync is within 24 hours, skip network calls.
        - If API returns UnauthenticatedError or RateLimitedError, abort immediately.
        """
        # If we synced recently, skip network calls
        if self.is_recent(hours=24):
            log.info("Cache was synced within the last 24 hours; skipping API requests.")
            # ensure index is built from existing files
            self.index.rebuild()
            return False

        updated = False

        try:
            # Serial requests: stop on auth/rate errors
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

            immunity = await api.get_immunities()
            if immunity is None:
                log.warning("Immunities endpoint returned no data; aborting sync.")
                return False

            # Only reach here if all calls returned non-None
            updated |= self._diff_and_save("champions", champions)
            updated |= self._diff_and_save("tags", tags)
            updated |= self._diff_and_save("abilities", abilities)
            updated |= self._diff_and_save("immunity", immunity)

            if updated:
                self._save_metadata()
                log.info("Cache sync complete.")
            else:
                log.info("Cache unchanged; metadata not updated.")

            # Rebuild index after sync
            self.index.rebuild()
            return updated

        except Exception as e:
            # Let caller decide what to do for auth/rate errors
            # Re-raise known API exceptions so caller can stop the loop
            from .api import UnauthenticatedError, RateLimitedError
            if isinstance(e, UnauthenticatedError):
                log.error("Sync aborted: unauthenticated API key.")
                raise
            if isinstance(e, RateLimitedError):
                log.error("Sync aborted: rate limited by API.")
                raise

            # For other exceptions, log and return False (no update)
            log.exception("Unexpected error during cache sync: %s", e)
            return False

    # -----------------------------
    # Lookup helpers (unchanged)
    # -----------------------------
    def get_champion(self, id_or_name):
        id_or_name = id_or_name.lower()
        champs = self._load_file("champions").get("champions", {})

        # direct ID lookup
        if id_or_name in champs:
            return champs[id_or_name]

        # name lookup
        for champ in champs.values():
            if champ["name"].lower() == id_or_name:
                return champ

        return None

    def get_all_tags(self):
        data = self._load_file("tags")
        return data.get("tags", [])

    def get_all_abilities(self):
        data = self._load_file("abilities")
        return data.get("abilities", [])

    def get_all_immunities(self):
        data = self._load_file("immunity")
        return data.get("immunity", [])

    def get_all_champions(self):
        data = self._load_file("champions")
        return list(data.get("champions", {}).values())

    # -----------------------------
    # File loader
    # -----------------------------
    def _load_file(self, name):
        path = CACHE_DIR / f"{name}.json"
        if not path.exists():
            return {}
        try:
            return json.load(open(path, "r"))
        except Exception:
            log.exception("Failed to load cache file %s", path)
            return {}
