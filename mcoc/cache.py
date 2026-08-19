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
        try:
            if not self.metadata_file.exists():
                return {
                    "versions": {
                        "champions": None,
                        "tags": None,
                        "abilities": None,
                        "immunities": None,
                    },
                    "last_sync": None
                }
            data = json.load(open(self.metadata_file, "r"))
            # Defensive: ensure structure
            if not isinstance(data, dict):
                raise ValueError("metadata.json malformed")
            data.setdefault("versions", {
                "champions": None,
                "tags": None,
                "abilities": None,
                "immunities": None,
            })
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
                "last_sync": None
            }
        
    def _save_metadata(self):
        if not isinstance(self.metadata, dict):
            self.metadata = {
                "versions": {
                    "champions": None,
                    "tags": None,
                    "abilities": None,
                    "immunities": None,
                },
                "last_sync": None
            }
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
    # Data Shape Helpers
    # -----------------------------
    def _make_key_from_item(self, item, fallback_index):
        if not isinstance(item, dict):
            return str(fallback_index)
        if item.get("id"):
            return str(item["id"])
        if item.get("name"):
            return item["name"].lower()
        # stable fallback
        return hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest()[:12]

    def normalize_list_payload(self, payload, list_key):
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

        mapped = {}
        for i, item in enumerate(items):
            key = self._make_key_from_item(item, i)
            mapped[str(key)] = item

        return {"version": version, "updated_at": updated_at, list_key: mapped}

    def normalize_champions_payload(self, payload):
        return self.normalize_list_payload(payload, "champions")

    def normalize_abilities_payload(self, payload):
        return self.normalize_list_payload(payload, "abilities")

    def normalize_immunities_payload(self, payload):
        return self.normalize_list_payload(payload, "immunities")

    def normalize_tags_payload(self, payload):
        return self.normalize_list_payload(payload, "tags")

    # -----------------------------
    # Diff + Save
    # -----------------------------
    def _diff_and_save(self, name, new_data):
        if not new_data:
            log.warning("No data returned for %s; skipping save.", name)
            return False

        # Normalize list-shaped payloads into canonical dicts
        if name == "champions":
            new_data = self.normalize_champions_payload(new_data)
        elif name == "abilities":
            new_data = self.normalize_abilities_payload(new_data)
        elif name in ("immunity", "immunities"):
            # normalize and canonicalize metadata key to 'immunities'
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

        # Atomic write
        try:
            self._atomic_write_json(CACHE_DIR / f"{name}.json", new_data)
        except Exception:
            log.exception("Failed to write cache file for %s", name)
            return False

        # Update metadata only after successful write
        self.metadata.setdefault("versions", {})
        self.metadata["versions"][name] = new_version
        self.metadata["last_sync"] = datetime.datetime.utcnow().isoformat()
        self._save_metadata()

        log.info("Updated cache for %s.", name)

        # Rebuild index (defensive)
        try:
            self.index.rebuild()
        except Exception:
            log.exception("CacheIndex rebuild failed after updating %s", name)

        return True


    # -----------------------------
    # Public sync method
    # -----------------------------
    async def sync(self, api):
        """
        Syncs champions, tags, abilities, immunities from the API.
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

            immunities = await api.get_immunities()
            if immunities is None:
                log.warning("Immunities endpoint returned no data; aborting sync.")
                return False

            # Only reach here if all calls returned non-None
            updated |= self._diff_and_save("champions", champions)
            updated |= self._diff_and_save("tags", tags)
            updated |= self._diff_and_save("abilities", abilities)
            updated |= self._diff_and_save("immunities", immunities)

            if updated:
                log.info("Cache sync complete.")
            else:
                log.info("Cache unchanged; metadata not updated.")

            # Rebuild index after sync
            self.index.rebuild()
            return updated

        except Exception as e:
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
    def get_champion(self, id_or_name: str):
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

    def get_all_tags(self) -> list[dict]:
        data = self._load_file("tags")
        tags = data.get("tags", {})
        if isinstance(tags, dict):
            return list(tags.values())
        return tags or []

    def get_all_abilities(self) -> list[dict]:
        data = self._load_file("abilities")
        abilities = data.get("abilities", {})
        if isinstance(abilities, dict):
            return list(abilities.values())
        return abilities or []

    def get_all_immunities(self) -> list[dict]:
        data = self._load_file("immunities")
        immunities = data.get("immunities", {})
        if isinstance(immunities, dict):
            return list(immunities.values())
        return immunities or []

    def get_all_champions(self) -> list[dict]:
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
    def _load_file(self, name):
        path = CACHE_DIR / f"{name}.json"
        if not path.exists():
            return {}
        try:
            return json.load(open(path, "r"))
        except Exception:
            log.exception("Failed to load cache file %s", path)
            return {}


