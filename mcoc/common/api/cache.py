# Path: mcoc/common/api/cache.py
# File-Version: 1.0
# File-Id: 323a0d98-8434-4e30-8ee6-d07b7eef8f73
# Purpose: Short one-line purpose describing responsibilities and public API
# Public-API: CacheManager
# Last-Modified: 2026-09-01
# Changelog:
#   1.0 2026-09-01  Initial stabilized API header

import json
import hashlib
import pathlib
import datetime
import logging
import tempfile
import os
import asyncio
from typing import Optional, Callable, Awaitable, Any, Dict, List, Tuple
from .cacheindex import CacheIndex
from pathlib import Path
from redbot.core import data_manager
from mcoc.common.helpers.types import normalize_champion_progression

log = logging.getLogger("red.mcoc.cache")
# near other constants/imports
PRESTIGE_VERSIONS_URL = "https://mcochub.insaneskull.com/data/versions.json"
PRESTIGE_ENDPOINT = "https://mcochub.insaneskull.com/data/prestige.json"
TIERS = [2, 3, 4, 5, 6, 7]
RANKS = [1, 2, 3, 4, 5]
ASCENSIONS = [0, 1, 2]


# Do NOT create directories at import time. Create them when CacheManager is instantiated.
DEFAULT_CACHE_DIR = pathlib.Path("data") / "cache"

class CacheManager:
    def __init__(self, bot):
        self.bot = bot

        base = data_manager.cog_data_path(raw_name="mcoc")
        self.cache_dir = base / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.metadata_file = self.cache_dir / "metadata.json"

        # FIX: load metadata at startup
        self.metadata = self._load_metadata()

        # optional: create index
        self.index = CacheIndex(self)
        self._sync_lock = asyncio.Lock()

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
                        "abilities": None,
                        "aw": None,
                        "champions": None,
                        "champions_map": None,
                        "immunities": None,
                        "prestige": None,
                        "tags": None
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
                        "abilities": None,
                        "aw": None,
                        "champions": None,
                        "champions_map": None,
                        "immunities": None,
                        "prestige": None,
                        "tags": None
                    },
                    "last_sync": None,
                }

            if not isinstance(data, dict):
                raise ValueError("metadata.json malformed")
            data.setdefault(
                "versions",
                {
                    "abilities": None,
                    "aw": None,
                    "champions": None,
                    "champions_map": None,
                    "immunities": None,
                    "prestige": None,
                    "tags": None,
                },
            )
            data.setdefault("last_sync", None)
            return data
        except Exception:
            log.exception("Failed to load metadata.json; resetting metadata")
            return {
                "versions": {
                    "abilities": None,
                    "aw": None,
                    "champions": None,
                    "champions_map": None,
                    "immunities": None,
                    "prestige": None,
                    "tags": None,
                },
                "last_sync": None,
            }

    def _save_metadata(self) -> None:
        if not isinstance(self.metadata, dict):
            self.metadata = {
                "versions": {
                    "abilities": None,
                    "aw": None,
                    "champions": None,
                    "champions_map": None,
                    "immunities": None,
                    "prestige": None,
                    "tags": None,
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
    # Prestige update
    # -----------------------------
    async def check_update_prestige(self, api, force: bool = False, progress: Optional[Callable[[str], Awaitable[None]]] = None) -> bool:
        async def _report(msg: str):
            log.info(msg)
            if progress:
                try:
                    await progress(msg)
                except Exception:
                    log.exception("Progress callback failed")

        if self.is_recent(hours=24) and not force:
            await _report("Prestige check skipped: recent sync within 24h.")
            return False

        try:
            await _report("Fetching versions.json for prestige...")
            versions = await api.fetch_versions_public()
            if not versions:
                await _report("Failed to fetch versions.json for prestige.")
                return False
            prestige_version = versions.get("prestige")
            if not prestige_version:
                await _report("No prestige version in versions.json.")
                return False

            old_version = self.metadata.get("versions", {}).get("prestige")
            if old_version == prestige_version and not force:
                self.metadata.setdefault("versions", {})["prestige"] = prestige_version
                self.metadata["last_sync"] = datetime.datetime.utcnow().isoformat()
                self._save_metadata()
                await _report("Prestige version unchanged; skipping downloads.")
                return False

            await _report(f"Prestige version changed (new: {prestige_version}); fetching combos...")
            combined_rows = []
            total = len(TIERS) * len(RANKS) * len(ASCENSIONS)
            count = 0
            for tier in TIERS:
                for rank in RANKS:
                    for asc in ASCENSIONS:
                        count += 1
                        await _report(f"Fetching prestige data {count}/{total} (tier={tier}, rank={rank}, asc={asc})...")
                        payload = await api.fetch_prestige_public(tier, rank, asc, prestige_version)
                        if not payload:
                            log.warning("No prestige payload for %s|%s|%s", tier, rank, asc)
                            continue
                        rows = payload.get("rows", []) or []
                        for r in rows:
                            r["_tier"] = tier; r["_rank"] = rank; r["_asc"] = asc
                        combined_rows.extend(rows)

            normalized = {"version": prestige_version, "rows": combined_rows}
            await _report("Writing prestige.json to cache...")
            try:
                await self._atomic_write_json(self.cache_dir / "prestige.json", normalized)
            except Exception:
                log.exception("Failed to write prestige.json")
                await _report("Failed to write prestige.json")
                return False

            self.metadata.setdefault("versions", {})["prestige"] = prestige_version
            self.metadata["last_sync"] = datetime.datetime.utcnow().isoformat()
            await asyncio.to_thread(self._atomic_write_json_blocking, self.metadata_file, self.metadata)
            await _report("Prestige metadata updated.")

            try:
                await asyncio.to_thread(self.index.rebuild)
                await _report("Index rebuild complete after prestige update.")
            except Exception:
                log.exception("CacheIndex rebuild failed after prestige update")

            await _report(f"Prestige cache updated (version {prestige_version}).")
            return True

        except Exception:
            log.exception("check_update_prestige failed")
            await _report("Prestige update failed (see logs).")
            return False
    def get_prestige_table(self, tier: int, rank: int, asc: int) -> Optional[dict]:
        data = self._load_file("prestige")
        if not data:
            return None
        rows = [r for r in (data.get("rows") or []) if r.get("_tier")==tier and r.get("_rank")==rank and r.get("_asc")==asc]
        if not rows:
            return None
        return {"version": data.get("version"), "rows": rows}

    def _smooth_sig_value(self, sigs_map: dict, sig: int) -> Optional[int]:
        """
        sigs_map: dict of string keys '0','20',... -> int prestige
        sig: requested signature (0..200)
        Returns integer prestige via nearest exact or linear interpolation between surrounding keys.
        """
        if not sigs_map:
            return None
        # convert keys to sorted ints
        keys = sorted([int(k) for k in sigs_map.keys() if k.isdigit()])
        if not keys:
            return None
        # exact match
        if sig in keys:
            return int(sigs_map[str(sig)])
        # if below smallest key, return smallest
        if sig < keys[0]:
            return int(sigs_map[str(keys[0])])
        # if above largest key, return largest
        if sig > keys[-1]:
            return int(sigs_map[str(keys[-1])])
        # find surrounding keys
        lower = None
        upper = None
        for k in keys:
            if k < sig:
                lower = k
            elif k > sig:
                upper = k
                break
        if lower is None:
            return int(sigs_map[str(upper)])
        if upper is None:
            return int(sigs_map[str(lower)])
        # linear interpolation
        v_low = float(sigs_map[str(lower)])
        v_high = float(sigs_map[str(upper)])
        t = (sig - lower) / (upper - lower)
        val = v_low + (v_high - v_low) * t
        return int(round(val))

    # in mcoc/cache.py (CacheManager)
    def smooth_sig_value(self, sigs_map: dict, sig: int) -> Optional[int]:
        """Public wrapper for smoothing/interpolating prestige values by signature."""
        return self._smooth_sig_value(sigs_map, sig)

    def get_prestige_value(self, slug: str, tier: int, rank: int, asc: int, sig: int = 0) -> Optional[int]:
        table = self.get_prestige_table(tier, rank, asc)
        slug = (slug or "").strip().lower()
        if not table:
            return None
        for r in table.get("rows", []):
            if (r.get("slug") or "").lower() == slug.lower() or (r.get("name") or "").lower() == slug.lower():
                sigs = r.get("sigs") or {}
                # smoothing
                return self._smooth_sig_value(sigs, sig)
        return None

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

    def normalize_aw_payload(self, payload: Any) -> Optional[Dict[str, Any]]:
        """
        Canonicalize AW payload into:
        {
            "version": ...,
            "updated_at": ...,
            "aw": { ... }   # entire AW object preserved
        }
        """
        if not payload:
            return None

        version = payload.get("version")
        updated_at = payload.get("updated_at")
        aw = payload.get("aw")

        if not isinstance(aw, dict):
            return None

        return {
            "version": version,
            "updated_at": updated_at,
            "aw": aw
        }


    def normalize_hargs_by_tier(self, stars: int, rank: int, sig: int, asc: int) -> Tuple[int, int, int, int]:
        """Clamp progression values using the shared champion tier limits."""
        return normalize_champion_progression(stars, rank, sig, asc)


    def normalize_immunities_payload(self, payload: Any) -> Optional[Dict[str, Any]]:
        return self.normalize_list_payload(payload, "immunities")

    def normalize_prestige_payload(self, payload: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Canonicalize prestige payload into {"version":..., "rows": [...]}
        If payload already looks canonical, return as-is.
        """
        if not payload:
            return None
        version = payload.get("version")
        rows = payload.get("rows") or payload.get("prestige") or []
        # ensure rows is a list
        if isinstance(rows, dict):
            # some endpoints might return dict keyed by slug; convert to list
            rows = list(rows.values())
        return {"version": version, "rows": rows}



    def normalize_tags_payload(self, payload: Any) -> Optional[Dict[str, Any]]:
        return self.normalize_list_payload(payload, "tags")

    def normalize_tierlist_payload(self, payload: Any) -> Optional[Dict[str, Any]]:
        """
        Canonicalize tierlist payload into:
        { "version": <hash>, "champions": [...] }
        """
        if not payload:
            return None

        champions = payload.get("champions")
        if not isinstance(champions, list):
            return None

        # Create a stable version hash from the data
        version = self._hash(champions)

        return {
            "version": version,
            "champions": champions
        }

    def normalize_champions_map_payload(self, payload: Any) -> Optional[Dict[str, Any]]:
        """
        Canonicalize champions_map payload into:
        { "version": <hash>, "champions_map": {id: item, ...} }

        Keeps the raw max prestige feed separate from the current prestige rows.
        """
        if not payload:
            return None

        items = payload if isinstance(payload, list) else payload.get("champions_map")
        if not isinstance(items, list):
            return None

        mapped: Dict[str, Any] = {}
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            key = str(item.get("id") or self._make_key_from_item(item, index)).strip().lower()
            if not key:
                continue
            mapped[key] = item

        if not mapped:
            return None

        version = self._hash(items)
        return {
            "version": version,
            "champions_map": mapped,
        }


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
        elif name == "aw":
            new_data = self.normalize_aw_payload(new_data)
        elif name in ("immunity", "immunities"):
            new_data = self.normalize_immunities_payload(new_data)
            name = "immunities"
        elif name == "tags":
            new_data = self.normalize_tags_payload(new_data)
        elif name == "tierlist":
            new_data = self.normalize_tierlist_payload(new_data)
        elif name == "champions_map":
            new_data = self.normalize_champions_map_payload(new_data)


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
    async def sync(self, api, progress: Optional[Callable[[str], Awaitable[None]]] = None) -> bool:
        """
        Sync champions/tags/abilities/immunities from API.
        If `progress` is provided, call it with short status strings to update UI.
        """
        async def _report(msg: str):
            log.info(msg)
            if progress:
                try:
                    await progress(msg)
                except Exception:
                    log.exception("Progress callback failed")

        # If we synced recently, skip network calls
        if self.is_recent(hours=24):
            await _report("Cache was synced within the last 24 hours; skipping API requests.")
            try:
                await asyncio.to_thread(self.index.rebuild)
            except Exception:
                log.exception("Index rebuild failed during short-circuit")
            return False

        updated = False

        async with self._sync_lock:
            try:
                await _report("Starting cache sync: fetching champions...")
                champions = await api.get_champions()
                if champions is None:
                    await _report("Champions endpoint returned no data; aborting sync.")
                    return False

                await _report("Fetching tags...")
                tags = await api.get_tags()
                if tags is None:
                    await _report("Tags endpoint returned no data; aborting sync.")
                    return False

                await _report("Fetching abilities...")
                abilities = await api.get_abilities()
                if abilities is None:
                    await _report("Abilities endpoint returned no data; aborting sync.")
                    return False

                await _report("Fetchign AW Season")
                aw = await api.get_aw()
                if aw is None:
                    await _report("AW Season endpoint returned no data; aborting sync.")
                    return False

                await _report("Fetching tierlist...")
                tierlist = await api.get_tierlist()
                if tierlist is None:
                    await _report("Tierlist endpoint returned no data; aborting sync.")
                    return False

                await _report("Saving tierlist...")
                updated |= await self._diff_and_save("tierlist", tierlist)

                await _report("Fetching champions_map...")
                champions_map = await api.get_champions_map()
                if champions_map is None:
                    await _report("Champions map endpoint returned no data; aborting sync.")
                    return False

                await _report("Saving champions_map...")
                updated |= await self._diff_and_save("champions_map", champions_map)

                
                await _report("Fetching immunities...")
                immunities = await api.get_immunities()
                if immunities is None:
                    await _report("Immunities endpoint returned no data; aborting sync.")
                    return False

                # Only reach here if all calls returned non-None
                await _report("Saving champions...")
                updated |= await self._diff_and_save("champions", champions)
                await _report("Saving tags...")
                updated |= await self._diff_and_save("tags", tags)
                await _report("Saving abilities...")
                updated |= await self._diff_and_save("abilities", abilities)
                await _report("Saving immunities...")
                updated |= await self._diff_and_save("immunities", immunities)

                if updated:
                    await _report("Cache sync complete.")
                else:
                    await _report("Cache unchanged; metadata not updated.")

                try:
                    await asyncio.to_thread(self.index.rebuild)
                    await _report("Index rebuild complete.")
                except Exception:
                    log.exception("Index rebuild failed after sync")

                api._prefer_bearer = True
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
                await _report(f"Sync failed: {e}")
                return False
    # -----------------------------
    # Supplemental champion metadata
    # -----------------------------
    @staticmethod
    def _normalize_lookup_token(value: Any) -> str:
        if value is None:
            return ""
        text = str(value).lower().strip().replace("_", "-")
        text = text.replace("&", " and ")
        text = ''.join(ch for ch in text if ch.isalnum())
        return text

    def _get_champion_overrides(self) -> Dict[str, Any]:
        path = self.cache_dir / "champion_overrides.json"
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception:
            log.exception("Failed to read champion override file %s", path)
        return {}

    def _save_champion_overrides(self, data: Dict[str, Any]) -> None:
        path = self.cache_dir / "champion_overrides.json"
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, sort_keys=True)
        except Exception:
            log.exception("Failed to write champion override file %s", path)

    def _champion_key_candidates(self, champ: Any) -> List[str]:
        if not isinstance(champ, dict):
            return []
        raw_candidates = [
            champ.get("id"), champ.get("slug"), champ.get("name"), champ.get("title"),
            champ.get("shortname"), *(champ.get("aliases") or [])
        ]
        seen = set()
        out = []
        for value in raw_candidates:
            if value is None:
                continue
            token = str(value).strip().lower()
            if token and token not in seen:
                seen.add(token)
                out.append(token)
        return out

    def _merge_champion_overrides(self, champ: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(champ, dict):
            return champ
        merged = dict(champ)
        override_map = self._get_champion_overrides()
        if not override_map:
            return merged

        keys = self._champion_key_candidates(champ)
        for key in keys:
            note = override_map.get(key) or override_map.get(self._normalize_lookup_token(key))
            if not isinstance(note, dict):
                continue
            for field in ("aliases", "shortname"):
                if field in note and note[field] is not None:
                    merged[field] = note[field]
            break
        return merged

    # -----------------------------
    # Lookup helpers (unchanged)
    # -----------------------------
    def get_champion(self, id_or_name: str) -> Optional[Dict[str, Any]]:
        if id_or_name is None:
            return None

        raw = str(id_or_name).strip()
        if not raw:
            return None

        lookup = raw.lower()
        normalized_lookup = self._normalize_lookup_token(raw)
        override_map = self._get_champion_overrides()
        champs = self._load_file("champions").get("champions", {})

        if isinstance(champs, dict):
            def find_key_for_lookup() -> Optional[str]:
                for key, champ in champs.items():
                    if not isinstance(champ, dict):
                        continue
                    if str(key).lower() == lookup:
                        return key
                    if self._normalize_lookup_token(key) == normalized_lookup:
                        return key
                    for candidate in self._champion_key_candidates(champ):
                        if candidate == lookup or self._normalize_lookup_token(candidate) == normalized_lookup:
                            return key
                    note = override_map.get(str(key).lower()) or override_map.get(self._normalize_lookup_token(key))
                    if isinstance(note, dict):
                        for alias in (note.get("aliases") or []):
                            if str(alias).lower() == lookup or self._normalize_lookup_token(alias) == normalized_lookup:
                                return key
                        short = note.get("shortname")
                        if short and (str(short).lower() == lookup or self._normalize_lookup_token(short) == normalized_lookup):
                            return key
                return None

            direct = find_key_for_lookup()
            if direct is not None:
                return self._merge_champion_overrides(champs[direct])

        # fallback to list-based data shape
        if isinstance(champs, list):
            for champ in champs:
                if not isinstance(champ, dict):
                    continue
                candidates = [
                    champ.get("id"), champ.get("slug"), champ.get("name"), champ.get("title"),
                    *(champ.get("aliases") or []),
                    champ.get("shortname"),
                ]
                for candidate in candidates:
                    if candidate is None:
                        continue
                    cand_text = str(candidate)
                    if cand_text.lower() == lookup or self._normalize_lookup_token(cand_text) == normalized_lookup:
                        return self._merge_champion_overrides(champ)

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

    def get_all_aw(self) -> list:
        data = self._load_file("aw")
        aw = data.get("aw", {})
        if isinstance(aw, dict):
            return list(aw.values())
        return aw or []

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

    def get_all_champions_map(self) -> list:
        data = self._load_file("champions_map")
        champs = data.get("champions_map", {})
        if isinstance(champs, dict):
            return list(champs.values())
        if isinstance(champs, list):
            return champs
        return []

    def get_champion_map_entry(self, id_or_name: str) -> Optional[Dict[str, Any]]:
        if id_or_name is None:
            return None
        raw = str(id_or_name).strip()
        if not raw:
            return None

        lookup = self._normalize_lookup_token(raw)
        data = self._load_file("champions_map")
        champs = data.get("champions_map", {})
        if isinstance(champs, dict):
            for key, item in champs.items():
                if not isinstance(item, dict):
                    continue
                candidates = [key, item.get("id"), item.get("en")]
                for candidate in candidates:
                    if candidate is None:
                        continue
                    if self._normalize_lookup_token(candidate) == lookup:
                        return item
        elif isinstance(champs, list):
            for item in champs:
                if not isinstance(item, dict):
                    continue
                for candidate in (item.get("id"), item.get("en")):
                    if candidate is not None and self._normalize_lookup_token(candidate) == lookup:
                        return item
        return None

    def get_champion_max_prestige(self, id_or_name: str) -> Optional[int]:
        item = self.get_champion_map_entry(id_or_name)
        if not isinstance(item, dict):
            return None
        try:
            value = item.get("max_prestige")
            return int(value) if value is not None else None
        except Exception:
            return None

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
