# Path: mcoc/common/api/cache.py
# File-Version: 1.0
# File-Id: 323a0d98-8434-4e30-8ee6-d07b7eef8f73
# Purpose: Short one-line purpose describing responsibilities and public API
# Public-API: CacheManager
# Last-Modified: 2026-09-01
# Used-By: mcoc/common/api/api.py, mcoc/common/api/cacheindex.py, mcoc/common/helpers/types.py, mcoc/common/models/__init__.py
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
from typing import Optional, Callable, Awaitable, Any, Dict, List, Tuple, Mapping
from .cacheindex import CacheIndex
from pathlib import Path
from redbot.core import data_manager
from mcoc.common.helpers.types import CHAMPION_TIER_LIMITS, normalize_champion_progression
from mcoc.common.models import (
    AbilityList,
    ChampionList,
    ChampionAutocompleteList,
    CocpitChampionData,
    CollectorBotAccount,
    ImmunityList,
    MCOCHubAbility,
    MCOCHubChampion,
    MCOCHubImmunity,
    MCOCHubTag,
    TagList,
    TierList,
)

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
                        "cocpit_abilities": None,
                        "cocpit_champions": None,
                        "champions_map": None,
                        "champstats": None,
                        "glossary": None,
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
                        "cocpit_abilities": None,
                        "cocpit_champions": None,
                        "champions_map": None,
                        "champstats": None,
                        "glossary": None,
                        "immunities": None,
                        "prestige": None,
                        "tags": None,
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
                    "cocpit_abilities": None,
                    "cocpit_champions": None,
                    "champions_map": None,
                    "champstats": None,
                    "glossary": None,
                    "immunities": None,
                    "prestige": None,
                    "tags": None,
                },
            )
            versions = data.get("versions")
            if isinstance(versions, dict):
                versions.setdefault("cocpit_abilities", None)
                versions.setdefault("cocpit_champions", None)
            data.setdefault("last_sync", None)
            return data
        except Exception:
            log.exception("Failed to load metadata.json; resetting metadata")
            return {
                "versions": {
                    "abilities": None,
                    "aw": None,
                    "champions": None,
                    "cocpit_abilities": None,
                    "cocpit_champions": None,
                    "champions_map": None,
                    "champstats": None,
                    "glossary": None,
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
                    "cocpit_abilities": None,
                    "cocpit_champions": None,
                    "champions_map": None,
                    "champstats": None,
                    "glossary": None,
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

    def _validate_model_payload(self, model: Any, payload: Any, *, list_key: Optional[str] = None) -> Any:
        """Validate a raw API payload against the typed model and return the original payload on success."""
        if payload is None:
            return None
        try:
            if list_key and isinstance(payload, dict):
                candidate = payload.get(list_key, [])
                model.model_validate({list_key: candidate})
            else:
                model.model_validate(payload)
            return payload
        except Exception:
            log.exception("Failed to validate payload with %s", getattr(model, "__name__", type(model).__name__))
            return None

    def normalize_champions_payload(self, payload: Any) -> Optional[Dict[str, Any]]:
        validated = self._validate_model_payload(ChampionList, payload, list_key="champions")
        if validated is None:
            return None
        return self.normalize_list_payload(payload, "champions")

    def normalize_abilities_payload(self, payload: Any) -> Optional[Dict[str, Any]]:
        validated = self._validate_model_payload(AbilityList, payload, list_key="abilities")
        if validated is None:
            return None
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
        validated = self._validate_model_payload(ImmunityList, payload, list_key="immunities")
        if validated is None:
            return None
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
        validated = self._validate_model_payload(TagList, payload, list_key="tags")
        if validated is None:
            return None
        return self.normalize_list_payload(payload, "tags")

    def normalize_tierlist_payload(self, payload: Any) -> Optional[Dict[str, Any]]:
        """Canonicalize the mcoc.app tierlist document while preserving useful metadata.

        The live payload is a document root containing the champion list plus support
        metadata such as tier ordering, tag labels, and immunity/debuff maps. We keep
        the helpful subset here and intentionally discard prestige-only payloads.
        """
        if not payload:
            return None
        if not isinstance(payload, dict):
            return None
        if self._validate_model_payload(TierList, payload) is None:
            return None

        champions = payload.get("champions")
        if not isinstance(champions, list):
            return None

        useful_keys = [
            "tag_labels",
            "immunity_map",
            "immunity_types",
            "debuff_map",
            "debuff_types",
            "by_class",
            "tier_order",
            "tier_colors",
            "class_colors",
            "awakening_data",
            "sig_stones_data",
            "last_updated",
            "total_champions",
        ]
        metadata = {key: payload[key] for key in useful_keys if key in payload}

        version_payload = {
            "champions": champions,
            **metadata,
        }
        version = self._hash(version_payload)

        normalized = {
            "version": version,
            "champions": champions,
        }
        normalized.update(metadata)
        return normalized

    @staticmethod
    def _cocpit_sig_levels(max_sig: int) -> List[int]:
        values = {0}
        if max_sig >= 1:
            values.add(1)
        value = 10
        while value <= max_sig:
            values.add(value)
            value += 10
        if max_sig > 0 and max_sig not in values:
            values.add(max_sig)
        return sorted(values)

    def normalize_cocpit_champion_stats_payload(self, payload: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(payload, dict):
            return None

        entries = payload.get("entries") or []
        if not isinstance(entries, list):
            return None

        normalized_entries: List[Dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            champion_id = entry.get("champion_id") or entry.get("championId") or entry.get("id")
            if not champion_id:
                continue
            normalized_entries.append({
                "champion_id": str(champion_id),
                "champion_name": entry.get("champion_name") or entry.get("championName") or entry.get("name"),
                "rarity": int(entry.get("rarity", payload.get("rarity") or 0) or 0),
                "rank": int(entry.get("rank", payload.get("rank") or 0) or 0),
                "sig_level": int(entry.get("sig_level", payload.get("sig_level") or 0) or 0),
                "ascension_level": int(entry.get("ascension_level", payload.get("ascension_level") or 0) or 0),
                "attack": entry.get("attack"),
                "health": entry.get("health"),
                "prestige": entry.get("prestige"),
            })

        if not normalized_entries:
            return None

        total_count = int(payload.get("total_count") or len(normalized_entries))
        return {
            "version": self._hash(payload),
            "rarity": int(payload.get("rarity") or 0),
            "rank": int(payload.get("rank") or 0),
            "sig_level": int(payload.get("sig_level") or 0),
            "ascension_level": int(payload.get("ascension_level") or 0),
            "page": int(payload.get("page") or 1),
            "page_size": int(payload.get("page_size") or len(normalized_entries)),
            "has_more": bool(payload.get("has_more", False)),
            "entries": normalized_entries,
            "totals": {
                "total_count": total_count,
                "page_count": int(payload.get("page_count") or 1),
                "has_more": bool(payload.get("has_more", False)),
            },
        }

    def normalize_cocpit_champions_payload(self, payload: Any) -> Optional[Dict[str, Any]]:
        if isinstance(payload, dict):
            items = payload.get("champions")
        else:
            items = payload
        if not isinstance(items, list):
            return None

        model = ChampionAutocompleteList.from_list(items)
        champions: List[Dict[str, Any]] = []
        for champ in model.champions:
            data = champ.model_dump(by_alias=True, exclude_none=True)
            champ_id = str(data.get("id") or "").strip()
            if not champ_id:
                continue
            name = str(data.get("name") or "").strip()
            slug = self._normalize_lookup_token(champ_id or name)
            champions.append({
                "id": champ_id,
                "slug": slug,
                "name": name,
                "aliases": [str(v).strip() for v in (data.get("aliases") or []) if str(v).strip()],
                "img": data.get("img"),
                "class_name": data.get("className") or data.get("class_name"),
                "available_rarities": [int(v) for v in (data.get("availableRarities") or data.get("available_rarities") or []) if str(v).isdigit()],
                "ascension_max_by_rarity": data.get("ascensionMaxByRarity") or data.get("ascension_max_by_rarity") or {},
            })

        if not champions:
            return None

        return {
            "version": self._hash(champions),
            "updated_at": datetime.datetime.utcnow().isoformat(),
            "champions": champions,
        }

    def normalize_cocpit_champion_abilities_payload(self, champion: Mapping[str, Any], payload: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(champion, Mapping) or not isinstance(payload, dict):
            return None

        model = CocpitChampionData.model_validate(payload)
        champion_id = str(champion.get("id") or "").strip()
        champion_name = str(champion.get("name") or champion_id).strip()
        champion_slug = str(champion.get("slug") or self._normalize_lookup_token(champion_id or champion_name)).strip()

        core_out: List[Dict[str, Any]] = []
        for section, entries in (model.coreAbilities or {}).items():
            for index, entry in enumerate(entries or []):
                if not entry:
                    continue
                text = str(getattr(entry, "text", "") or "").strip()
                if not text:
                    continue
                entry_id = getattr(entry, "id", None) or f"{champion_slug}_{self._normalize_lookup_token(section)}_{index}"
                core_out.append({
                    "id": str(entry_id),
                    "title": str(section),
                    "text": text,
                    "iconFilename": getattr(entry, "icon_filename", None),
                })

        sig_out: List[Dict[str, Any]] = []
        for section, entries in (model.sigAbilities or {}).items():
            for index, entry in enumerate(entries or []):
                if not entry:
                    continue
                text = str(getattr(entry, "text", "") or "").strip()
                if not text:
                    continue
                entry_id = getattr(entry, "id", None) or f"{champion_slug}_sig_{self._normalize_lookup_token(section)}_{index}"
                sig_out.append({
                    "id": str(entry_id),
                    "title": str(section),
                    "text": text,
                    "iconFilename": getattr(entry, "icon_filename", None),
                })

        return {
            "champion_id": champion_id,
            "champion_slug": champion_slug,
            "champion_name": champion_name,
            "sig_ability_display_name": model.sigAbilityDisplayName,
            "core_abilities": core_out,
            "signature_abilities": sig_out,
            "raw": payload,
        }

    async def harvest_cocpit_champions(self, api: Any, *, progress: Optional[Callable[[str], Awaitable[None]]] = None) -> Dict[str, Any]:
        async def _report(msg: str):
            if progress:
                try:
                    await progress(msg)
                except Exception:
                    log.exception("Progress callback failed while harvesting Cocpit champions")

        if api is None or not hasattr(api, "get_cocpit_champion_autocomplete"):
            return {"count": 0, "updated": False, "files": [], "error": "api missing get_cocpit_champion_autocomplete"}

        payload = await api.get_cocpit_champion_autocomplete()
        normalized = self.normalize_cocpit_champions_payload(payload)
        if not normalized:
            # Fallback path: synthesize champion list from existing champstats rows.
            stats_doc = self._load_file("champstats") or {}
            stats_rows = stats_doc.get("entries", []) if isinstance(stats_doc, dict) else []
            if isinstance(stats_rows, list) and stats_rows:
                seen: Dict[str, Dict[str, Any]] = {}
                for row in stats_rows:
                    if not isinstance(row, dict):
                        continue
                    champ_id = str(row.get("champion_id") or "").strip().lower()
                    if not champ_id:
                        continue
                    item = seen.setdefault(
                        champ_id,
                        {
                            "id": champ_id,
                            "slug": champ_id,
                            "name": str(row.get("champion_name") or champ_id).strip(),
                            "aliases": [],
                            "img": None,
                            "class_name": None,
                            "available_rarities": [],
                            "ascension_max_by_rarity": {},
                        },
                    )
                    try:
                        rarity = int(row.get("rarity") or 0)
                    except Exception:
                        rarity = 0
                    try:
                        ascension_level = int(row.get("ascension_level") or 0)
                    except Exception:
                        ascension_level = 0
                    if rarity and rarity not in item["available_rarities"]:
                        item["available_rarities"].append(rarity)
                    if rarity:
                        rarity_key = str(rarity)
                        current_max = int(item["ascension_max_by_rarity"].get(rarity_key) or 0)
                        if ascension_level > current_max:
                            item["ascension_max_by_rarity"][rarity_key] = ascension_level

                champions = list(seen.values())
                for entry in champions:
                    entry["available_rarities"] = sorted(set(entry.get("available_rarities") or []))

                if champions:
                    normalized = {
                        "version": self._hash(champions),
                        "updated_at": datetime.datetime.utcnow().isoformat(),
                        "champions": champions,
                    }
                    await _report(f"Cocpit champions fallback from champstats: {len(champions)} champions")

        if not normalized:
            return {"count": 0, "updated": False, "files": [], "error": "invalid cocpit champion payload"}

        release_date = None
        if hasattr(api, "get_cocpit_release_date"):
            try:
                release_date = await api.get_cocpit_release_date()
            except Exception:
                log.exception("Failed to read Cocpit release date while harvesting champions")
        if release_date:
            normalized["version"] = release_date

        self._atomic_write_json_blocking(self.cache_dir / "cocpit_champions.json", normalized)
        self.metadata.setdefault("versions", {})["cocpit_champions"] = normalized.get("version")
        self.metadata["last_sync"] = datetime.datetime.utcnow().isoformat()
        try:
            self._atomic_write_json_blocking(self.metadata_file, self.metadata)
        except Exception:
            log.exception("Failed to write metadata after Cocpit champions harvest")

        await _report(f"Cocpit champions harvested: {len(normalized.get('champions', []))} champions")
        return {"count": len(normalized.get("champions", [])), "updated": True, "files": ["cocpit_champions.json"], "version": normalized.get("version")}

    async def harvest_cocpit_champion_abilities(self, api: Any, *, progress: Optional[Callable[[str], Awaitable[None]]] = None) -> Dict[str, Any]:
        async def _report(msg: str):
            if progress:
                try:
                    await progress(msg)
                except Exception:
                    log.exception("Progress callback failed while harvesting Cocpit abilities")

        if api is None or not hasattr(api, "get_cocpit_champion_data"):
            return {"count": 0, "updated": False, "files": [], "error": "api missing get_cocpit_champion_data"}

        champions_doc = self._load_file("cocpit_champions")
        champions = champions_doc.get("champions") if isinstance(champions_doc, dict) else None
        if not isinstance(champions, list) or not champions:
            return {"count": 0, "updated": False, "files": [], "error": "cocpit champions cache missing"}

        rows: List[Dict[str, Any]] = []
        for idx, champion in enumerate(champions, start=1):
            champ_id = str(champion.get("id") or "").strip()
            if not champ_id:
                continue
            rarities = [int(v) for v in (champion.get("available_rarities") or []) if isinstance(v, int) or str(v).isdigit()]
            if not rarities:
                rarities = [7, 6, 5, 4]

            payload = None
            for rarity in sorted(set(rarities), reverse=True):
                limits = CHAMPION_TIER_LIMITS.get(int(rarity))
                candidates = [(1, 0, 0)]
                if limits:
                    candidates.append((int(limits.max_rank), int(limits.max_sig), int(limits.max_ascended)))
                for rank, sig, asc in candidates:
                    try:
                        maybe = await api.get_cocpit_champion_data(champ_id, int(rarity), int(rank), int(sig), int(asc))
                    except Exception:
                        continue
                    if isinstance(maybe, dict) and ((maybe.get("coreAbilities") or maybe.get("sigAbilities") or maybe.get("baseStats"))):
                        payload = maybe
                        break
                if payload is not None:
                    break

            if payload is None:
                log.warning("Failed to fetch Cocpit champion abilities for %s", champ_id)
                continue
            normalized = self.normalize_cocpit_champion_abilities_payload(champion, payload)
            if normalized is None:
                continue
            rows.append(normalized)
            if idx % 25 == 0:
                await _report(f"Cocpit abilities progress: {idx}/{len(champions)} champions")

        release_date = None
        if hasattr(api, "get_cocpit_release_date"):
            try:
                release_date = await api.get_cocpit_release_date()
            except Exception:
                log.exception("Failed to read Cocpit release date while harvesting abilities")
        if not release_date:
            release_date = datetime.datetime.utcnow().strftime("%Y.%m.%d")

        artifact = {
            "version": release_date,
            "updated_at": datetime.datetime.utcnow().isoformat(),
            "entries": rows,
        }
        self._atomic_write_json_blocking(self.cache_dir / "cocpit_abilities.json", artifact)
        self.metadata.setdefault("versions", {})["cocpit_abilities"] = artifact.get("version")
        self.metadata["last_sync"] = datetime.datetime.utcnow().isoformat()
        try:
            self._atomic_write_json_blocking(self.metadata_file, self.metadata)
        except Exception:
            log.exception("Failed to write metadata after Cocpit abilities harvest")

        await _report(f"Cocpit abilities harvested: {len(rows)} champions")
        return {"count": len(rows), "updated": True, "files": ["cocpit_abilities.json"], "version": artifact.get("version")}

    async def harvest_cocpit_champion_stats(self, api: Any, *, progress: Optional[Callable[[str], Awaitable[None]]] = None) -> Dict[str, Any]:
        async def _report(msg: str):
            if progress:
                try:
                    await progress(msg)
                except Exception:
                    log.exception("Progress callback failed while harvesting Cocpit stats")

        if api is None or not hasattr(api, "get_cocpit_champion_stats"):
            return {"count": 0, "updated": False, "files": [], "error": "api missing get_cocpit_champion_stats"}

        rows: List[Dict[str, Any]] = []
        seen: set[str] = set()

        for rarity, limits in CHAMPION_TIER_LIMITS.items():
            for rank in range(1, int(limits.max_rank) + 1):
                for ascension_level in range(0, int(limits.max_ascended) + 1):
                    for sig_level in self._cocpit_sig_levels(int(limits.max_sig)):
                        page = 1
                        while True:
                            payload = await api.get_cocpit_champion_stats(
                                rarity=rarity,
                                rank=rank,
                                sig_level=sig_level,
                                ascension_level=ascension_level,
                                page=page,
                                page_size=50,
                            )
                            if not payload:
                                break

                            normalized = self.normalize_cocpit_champion_stats_payload(payload)
                            if normalized is None:
                                break

                            for item in normalized["entries"]:
                                key = "|".join([
                                    str(item.get("champion_id") or "").strip().lower(),
                                    str(item.get("rarity") or ""),
                                    str(item.get("rank") or ""),
                                    str(item.get("sig_level") or ""),
                                    str(item.get("ascension_level") or ""),
                                ])
                                if not key or key in seen:
                                    continue
                                seen.add(key)
                                rows.append(item)

                            if not normalized.get("has_more") or not normalized.get("totals", {}).get("has_more"):
                                break
                            page += 1
                            if page > 20:
                                break

        release_date = None
        if hasattr(api, "get_cocpit_release_date"):
            try:
                release_date = await api.get_cocpit_release_date()
            except Exception:
                log.exception("Failed to read Cocpit release date for champstats version stamp")
        if not release_date:
            release_date = datetime.datetime.utcnow().strftime("%Y.%m.%d")

        version = release_date
        artifact = {
            "version": version,
            "updated_at": datetime.datetime.utcnow().isoformat(),
            "entries": rows,
        }
        output_path = self.cache_dir / "champstats.json"
        self._atomic_write_json_blocking(output_path, artifact)
        self.metadata.setdefault("versions", {})["champstats"] = version
        self.metadata["last_sync"] = datetime.datetime.utcnow().isoformat()
        try:
            self._atomic_write_json_blocking(self.metadata_file, self.metadata)
        except Exception:
            log.exception("Failed to write metadata after Cocpit stats harvest")

        await _report(f"Cocpit champion stats harvested: {len(rows)} champions")
        return {"count": len(rows), "updated": True, "files": ["champstats.json"], "version": version}

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

    def normalize_glossary_payload(self, payload: Any) -> Optional[Dict[str, Any]]:
        """
        Canonicalize Kabam glossary payload into:
        { "version": <hash>, "glossary": {id: item, ...}, ...metadata }
        """
        if not isinstance(payload, dict):
            return None

        items = payload.get("glossary")
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

        return {
            "version": self._hash(items),
            "title": ((payload.get("title") or {}).get("rendered") if isinstance(payload.get("title"), dict) else payload.get("title")),
            "date_time": payload.get("date_time"),
            "permalink": payload.get("permalink"),
            "glossary": mapped,
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
        elif name == "champstats":
            new_data = self.normalize_cocpit_champion_stats_payload(new_data)
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
        elif name == "glossary":
            new_data = self.normalize_glossary_payload(new_data)


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

        # If we synced recently, skip full network calls but still backfill missing Cocpit artifacts.
        if self.is_recent(hours=24):
            await _report("Cache was synced within the last 24 hours; checking Cocpit artifacts before skipping.")
            updated_recent = False

            try:
                cocpit_champions_payload = self._load_file("cocpit_champions")
                cocpit_abilities_payload = self._load_file("cocpit_abilities")
                cocpit_champions_ok = self._is_valid_cache_file("cocpit_champions", cocpit_champions_payload)
                cocpit_abilities_ok = self._is_valid_cache_file("cocpit_abilities", cocpit_abilities_payload)

                if (not cocpit_champions_ok) and hasattr(api, "get_cocpit_champion_autocomplete"):
                    await _report("Backfilling missing Cocpit champions cache...")
                    result = await self.harvest_cocpit_champions(api, progress=_report)
                    updated_recent |= bool(result.get("updated"))

                if (not cocpit_abilities_ok) and hasattr(api, "get_cocpit_champion_data"):
                    await _report("Backfilling missing Cocpit abilities cache...")
                    result = await self.harvest_cocpit_champion_abilities(api, progress=_report)
                    updated_recent |= bool(result.get("updated"))
            except Exception:
                log.exception("Failed to backfill Cocpit artifacts during recent-sync short-circuit")

            if not updated_recent:
                await _report("Cache was synced recently and Cocpit artifacts are unchanged; skipping API requests.")

            try:
                await asyncio.to_thread(self.index.rebuild)
            except Exception:
                log.exception("Index rebuild failed during short-circuit")
            return updated_recent

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

                if hasattr(api, "get_cocpit_champion_autocomplete"):
                    await _report("Harvesting Cocpit champions...")
                    cocpit_champions_result = await self.harvest_cocpit_champions(api, progress=_report)
                    updated |= bool(cocpit_champions_result.get("updated"))

                if hasattr(api, "get_cocpit_champion_data"):
                    await _report("Harvesting Cocpit champion abilities...")
                    cocpit_abilities_result = await self.harvest_cocpit_champion_abilities(api, progress=_report)
                    updated |= bool(cocpit_abilities_result.get("updated"))

                if hasattr(api, "get_cocpit_champion_stats"):
                    await _report("Harvesting Cocpit champion stats...")
                    stats_result = await self.harvest_cocpit_champion_stats(api, progress=_report)
                    updated |= bool(stats_result.get("updated"))

                await _report("Fetching glossary...")
                glossary = await api.get_glossary()
                if glossary is None:
                    await _report("Glossary endpoint returned no data; skipping glossary update.")
                else:
                    await _report("Saving glossary...")
                    updated |= await self._diff_and_save("glossary", glossary)

                
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

    def get_all_cocpit_champions(self) -> list:
        data = self._load_file("cocpit_champions")
        champs = data.get("champions", []) if isinstance(data, dict) else []
        if isinstance(champs, list):
            return champs
        return []

    def get_cocpit_champion(self, id_or_name: str) -> Optional[Dict[str, Any]]:
        if id_or_name is None:
            return None
        raw = str(id_or_name).strip()
        if not raw:
            return None
        needle = self._normalize_lookup_token(raw)

        for champ in self.get_all_cocpit_champions():
            if not isinstance(champ, dict):
                continue
            candidates = [
                champ.get("id"),
                champ.get("slug"),
                champ.get("name"),
                *(champ.get("aliases") or []),
            ]
            for candidate in candidates:
                if candidate is None:
                    continue
                if self._normalize_lookup_token(candidate) == needle:
                    return champ
        return None

    def get_cocpit_abilities(self, id_or_name: str) -> Optional[Dict[str, Any]]:
        champion = self.get_cocpit_champion(id_or_name)
        if not champion:
            return None
        champ_id = str(champion.get("id") or "").strip().lower()
        champ_slug = str(champion.get("slug") or "").strip().lower()
        champ_name_norm = self._normalize_lookup_token(champion.get("name") or "")

        data = self._load_file("cocpit_abilities")
        rows = data.get("entries", []) if isinstance(data, dict) else []
        if not isinstance(rows, list):
            return None
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_id = str(row.get("champion_id") or "").strip().lower()
            row_slug = str(row.get("champion_slug") or "").strip().lower()
            row_name_norm = self._normalize_lookup_token(row.get("champion_name") or "")
            if row_id == champ_id or row_slug == champ_slug or row_name_norm == champ_name_norm:
                return row
        return None

    def get_cocpit_champion_stats(self, id_or_name: str, rarity: int, rank: int, sig_level: int, ascension_level: int = 0) -> Optional[Dict[str, Any]]:
        champion = self.get_cocpit_champion(id_or_name)
        if not champion:
            return None

        champ_id = str(champion.get("id") or "").strip().lower()
        data = self._load_file("champstats")
        rows = data.get("entries", []) if isinstance(data, dict) else []
        if not isinstance(rows, list):
            return None

        requested_sig = int(sig_level)
        exact: Optional[Dict[str, Any]] = None
        nearest: Optional[Tuple[int, Dict[str, Any]]] = None
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_id = str(row.get("champion_id") or "").strip().lower()
            if row_id != champ_id:
                continue
            if int(row.get("rarity") or 0) != int(rarity):
                continue
            if int(row.get("rank") or 0) != int(rank):
                continue
            if int(row.get("ascension_level") or 0) != int(ascension_level):
                continue

            row_sig = int(row.get("sig_level") or 0)
            if row_sig == requested_sig:
                exact = row
                break
            distance = abs(row_sig - requested_sig)
            if nearest is None or distance < nearest[0]:
                nearest = (distance, row)

        if exact is not None:
            return exact
        return nearest[1] if nearest is not None else None

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

    @staticmethod
    def _normalize_glossary_lookup(value: Any) -> str:
        text = str(value or "").strip().lower().replace("-", "_")
        return "".join(ch for ch in text if ch.isalnum() or ch == "_")

    def get_all_glossary_terms(self) -> list:
        data = self._load_file("glossary")
        glossary = data.get("glossary", {})
        if isinstance(glossary, dict):
            return list(glossary.values())
        if isinstance(glossary, list):
            return glossary
        return []

    def get_glossary_term(self, term_id_or_name: str) -> Optional[Dict[str, Any]]:
        if term_id_or_name is None:
            return None
        raw = str(term_id_or_name).strip()
        if not raw:
            return None

        lookup = self._normalize_glossary_lookup(raw)
        data = self._load_file("glossary")
        glossary = data.get("glossary", {})
        if isinstance(glossary, dict):
            for key, item in glossary.items():
                if not isinstance(item, dict):
                    continue
                candidates = [key, item.get("id"), item.get("word")]
                for candidate in candidates:
                    if candidate is not None and self._normalize_glossary_lookup(candidate) == lookup:
                        return item
        elif isinstance(glossary, list):
            for item in glossary:
                if not isinstance(item, dict):
                    continue
                for candidate in (item.get("id"), item.get("word")):
                    if candidate is not None and self._normalize_glossary_lookup(candidate) == lookup:
                        return item
        return None

    def get_glossary_icon_url(self, term_id_or_name: str) -> Optional[str]:
        item = self.get_glossary_term(term_id_or_name)
        if not isinstance(item, dict):
            return None
        term_id = self._normalize_glossary_lookup(item.get("id"))
        if not term_id:
            return None
        return f"https://playcontestofchampions.com/wp-content/uploads/glossary/glossary-{term_id}.svg"

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

    def _cache_file_schema(self, name: str) -> Optional[str]:
        return {
            "champions": "champions",
            "cocpit_champions": "champions",
            "cocpit_abilities": "entries",
            "champstats": "entries",
            "abilities": "abilities",
            "tags": "tags",
            "immunities": "immunities",
            "aw": "aw",
            "tierlist": "champions",
            "champions_map": "champions_map",
            "glossary": "glossary",
            "prestige": "rows",
        }.get(name)

    def _is_valid_cache_file(self, name: str, payload: Any) -> bool:
        if payload is None:
            return False
        schema_key = self._cache_file_schema(name)
        if schema_key is None:
            return True

        if not isinstance(payload, dict):
            return False

        if name == "prestige":
            rows = payload.get("rows")
            return isinstance(rows, list)

        if name == "tierlist":
            champions = payload.get("champions")
            return isinstance(champions, list)

        if name == "cocpit_champions":
            champions = payload.get("champions")
            return isinstance(champions, list)

        if name == "cocpit_abilities":
            entries = payload.get("entries")
            return isinstance(entries, list)

        if name == "aw":
            aw_payload = payload.get("aw")
            return isinstance(aw_payload, dict)

        value = payload.get(schema_key)
        if isinstance(value, dict):
            return bool(value)
        if isinstance(value, list):
            return True
        return False

    def health_check(self) -> Dict[str, Any]:
        issues: List[str] = []
        checked: List[str] = []
        details: Dict[str, Dict[str, Any]] = {}
        for name in [
            "champions",
            "cocpit_champions",
            "cocpit_abilities",
            "champstats",
            "abilities",
            "tags",
            "immunities",
            "aw",
            "tierlist",
            "champions_map",
            "glossary",
            "prestige",
        ]:
            path = self.cache_dir / f"{name}.json"
            entry = {"exists": path.exists(), "valid": False, "count": 0, "kind": None}
            if not path.exists():
                details[name] = entry
                continue
            checked.append(name)
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    payload = json.load(handle)
            except Exception as exc:
                issues.append(f"{name}.json is unreadable: {exc}")
                entry["valid"] = False
                entry["kind"] = "unreadable"
                details[name] = entry
                continue

            valid = self._is_valid_cache_file(name, payload)
            entry["valid"] = valid
            entry["kind"] = type(payload).__name__
            if isinstance(payload, dict):
                schema_key = self._cache_file_schema(name)
                value = payload.get(schema_key) if schema_key else payload
                if isinstance(value, dict):
                    entry["count"] = len(value)
                elif isinstance(value, list):
                    entry["count"] = len(value)
            elif isinstance(payload, list):
                entry["count"] = len(payload)
            if not valid:
                issues.append(f"{name}.json has a malformed cache payload.")
            details[name] = entry

        return {
            "ok": not issues,
            "issues": issues,
            "checked": checked,
            "details": details,
        }

    def wipe_cache(self) -> Dict[str, Any]:
        """Delete all cached CDT JSON files and reset the in-memory metadata state.

        This is a destructive operation and is intended for explicit admin use when
        the bot needs to rebuild its cache from a clean slate.
        """
        removed: List[str] = []
        if self.cache_dir is not None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            for path in sorted(self.cache_dir.glob("*.json")):
                try:
                    path.unlink()
                    removed.append(path.name)
                except Exception:
                    log.exception("Failed to delete cache file %s during full wipe", path)

        self.metadata = {"versions": {}, "last_sync": None}
        metadata_file = getattr(self, "metadata_file", self.cache_dir / "metadata.json")
        if metadata_file.exists():
            try:
                metadata_file.unlink()
            except Exception:
                log.exception("Failed to delete metadata file %s during full wipe", metadata_file)

        return {
            "removed": len(removed),
            "files": removed,
            "metadata_reset": True,
        }

    def cleanup_stale_cache(self) -> Dict[str, Any]:
        health = self.health_check()
        removed: List[str] = []

        for name in health.get("checked", []):
            path = self.cache_dir / f"{name}.json"
            if not path.exists():
                continue
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    payload = json.load(handle)
            except Exception:
                try:
                    path.unlink()
                    removed.append(name)
                except Exception:
                    log.exception("Failed to delete unreadable cache file %s", path)
                continue

            if not self._is_valid_cache_file(name, payload):
                try:
                    path.unlink()
                    removed.append(name)
                except Exception:
                    log.exception("Failed to delete malformed cache file %s", path)

        versions = self.metadata.setdefault("versions", {})
        for name in removed:
            if isinstance(versions, dict):
                versions.pop(name, None)

        if removed:
            try:
                self._save_metadata()
            except Exception:
                log.exception("Failed to save metadata after cache cleanup")

        return {
            "healthy": not self.health_check()["issues"],
            "removed": len(removed),
            "files": removed,
            "issues": health["issues"],
        }
