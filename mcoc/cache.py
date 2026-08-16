import json
import hashlib
import pathlib
import datetime
import logging

log = logging.getLogger("red.mcoc.cache")

CACHE_DIR = pathlib.Path("data/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

class CacheManager:
    def __init__(self):
        self.metadata_file = CACHE_DIR / "metadata.json"
        self.metadata = self._load_metadata()

    # -----------------------------
    # Metadata
    # -----------------------------
    def _load_metadata(self):
        if not self.metadata_file.exists():
            return {
                "version": 0,
                "last_sync": None,
                "hashes": {
                    "champions": None,
                    "tags": None,
                    "abilities": None,
                    "immunity": None,
                }
            }
        return json.load(open(self.metadata_file, "r"))

    def _save_metadata(self):
        json.dump(self.metadata, open(self.metadata_file, "w"), indent=2)

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
        new_version = new_data.get("version")
        old_version = self.metadata["versions"].get(name)

        if new_version == old_version:
            log.info(f"No changes detected for {name}.")
            return False

        # Write new cache file
        json.dump(new_data, open(CACHE_DIR / f"{name}.json", "w"), indent=2)

        # Update metadata
        self.metadata["versions"][name] = new_version
        self.metadata["last_sync"] = datetime.datetime.utcnow().isoformat()

        log.info(f"Updated cache for {name}.")
        return True


    # -----------------------------
    # Public sync method
    # -----------------------------
    async def sync(self, api):
        """
        api: instance of MCOCHubAPI
        """
        updated = False

        champions = await api.get_champions()
        tags = await api.get_tags()
        abilities = await api.get_abilities()
        immunity = await api.get_immunity()

        updated |= self._diff_and_save("champions", champions)
        updated |= self._diff_and_save("tags", tags)
        updated |= self._diff_and_save("abilities", abilities)
        updated |= self._diff_and_save("immunity", immunity)

        if updated:
            self._save_metadata()
            log.info("Cache sync complete.")
        else:
            log.info("Cache unchanged; metadata not updated.")

        return updated

    # -----------------------------
    # Lookup helpers
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


    def get_all_champions(self):
        return list(self._load_file("champions").get("champions", {}).values())

    def _load_file(self, name):
        path = CACHE_DIR / f"{name}.json"
        if not path.exists():
            return {}
        return json.load(open(path, "r"))
