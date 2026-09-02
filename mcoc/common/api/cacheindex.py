# Path: mcoc/common/api/cacheindex.py
# File-Version: 1.0
# File-Id: 0b0f96a2-0941-4dcc-b6cc-1c2ed0c32f4b
# Purpose: Provide an in-memory index for fast lookups of cache data, including champions, tags, abilities, and immunities.
# Public-API: CacheIndex
# Last-Modified: 2026-09-01
# Changelog:
#   1.0 2026-09-01  Initial stabilized API header

import logging
import threading
import asyncio
import re
from typing import Any, Dict, List, Optional

log = logging.getLogger("red.mcoc.cacheindex")


class CacheIndex:
    """
    Fast in-memory index built from CacheManager files.
    Provides instant lookup for champions, tags, abilities, immunities.

    Notes:
    - Import-neutral: no discord or bot access at module import time.
    - Construction is lightweight; call `rebuild()` or `await rebuild_async()` after instantiation.
    - If you want an automatic background build, call `start_background_build()` after creating the object.
    """

    def __init__(self, cache_manager, auto_build: bool = False):
        self.cache = cache_manager

        # Primary stores
        self.champions: List[Dict[str, Any]] = []
        self.tags: List[str] = []
        self.abilities: List[Dict[str, Any]] = []
        self.immunities: List[Dict[str, Any]] = []
        self.aw: Dict[str, Any] = {}
        self.aw_attack_champions: Dict[str, Any] = []
        self.aw_defense_champions: Dict[str, Any] = []
        self.tierlist = []
        self.tier_by_name = {}
        self.tier_by_slug = {}


        # Reverse lookup tables
        self.champions_by_id: Dict[str, Dict[str, Any]] = {}
        self.champions_by_name: Dict[str, Dict[str, Any]] = {}
        self.champions_by_tag: Dict[str, List[Dict[str, Any]]] = {}
        self.champions_by_ability: Dict[str, List[Dict[str, Any]]] = {}
        self.champions_by_immunity: Dict[str, List[Dict[str, Any]]] = {}
        # slug -> list of rows (each row: {"tier":..., "rank":..., "asc":..., "row": {...}})
        self.prestige_index: Dict[str, List[Dict[str, Any]]] = {}

        # Protect rebuilds from concurrent execution
        self._rebuild_lock = threading.RLock()

        # Lowercase tag cache for fast matching
        self._tags_lower: List[str] = []

        # Optionally start a background build; caller controls this
        if auto_build:
            try:
                self.start_background_build()
            except Exception:
                log.exception("Failed to start background build in __init__")

    def _normalize_name(self, name: str) -> str:
        """
        Normalize champion names for fuzzy matching.
        Removes punctuation, parentheses, hyphens, periods, and expands common abbreviations.
        """
        if not name:
            return ""

        n = name.lower()

        # Expand common abbreviations
        n = n.replace("mr.", "mister")
        n = n.replace("mr ", "mister ")
        n = n.replace("dr.", "doctor")
        n = n.replace("dr ", "doctor ")

        # Remove punctuation
        n = re.sub(r"[^\w\s]", "", n)

        # Collapse whitespace
        n = re.sub(r"\s+", " ", n).strip()

        return n

    def tierlist_best_match(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Return the best tierlist entry for a given champion name.
        Uses normalized name matching and fallback heuristics.
        """
        if not name:
            return None

        norm = self._normalize_name(name)

        # Exact normalized match
        if norm in self.tier_by_name:
            return self.tier_by_name[norm]

        # Fallback: try substring matches
        for k, v in self.tier_by_name.items():
            if norm in k or k in norm:
                return v

        # Fallback: try class_rank or tier similarity (optional)
        # Could add more heuristics here

        return None

    # ---------------------------------------------------------
    # Rebuild the entire index from cache files
    # ---------------------------------------------------------
    def rebuild(self) -> None:
        """
        Synchronous rebuild. Designed to be fast; callers that run this
        from async code should call rebuild_async() which offloads to a thread.
        """
        # Use a lock to avoid concurrent rebuilds
        if not self._rebuild_lock.acquire(blocking=False):
            # another thread is rebuilding; skip this call
            log.debug("rebuild() called while another rebuild is in progress; skipping")
            return

        try:
            load_file = getattr(self.cache, "_load_file", None)
            if load_file is None:
                log.error("CacheIndex.rebuild: cache manager has no _load_file method")
                return

            # Load raw files
            try:
                champions_raw = load_file("champions").get("champions", {})
            except Exception:
                log.exception("Failed to load champions file")
                champions_raw = {}

            # Normalize champions to dict keyed by id/name
            if isinstance(champions_raw, list):
                mapped: Dict[str, Any] = {}
                for i, item in enumerate(champions_raw):
                    if isinstance(item, dict):
                        key = item.get("id") or item.get("champion_id") or (item.get("name") or "").lower() or str(i)
                    else:
                        key = str(i)
                    mapped[str(key)] = item
                champions_raw = mapped

            if isinstance(champions_raw, dict):
                champions_list = [v for v in champions_raw.values() if isinstance(v, dict)]
            else:
                champions_list = []

            # Abilities
            try:
                abilities_raw = load_file("abilities").get("abilities", {})
            except Exception:
                log.exception("Failed to load abilities file")
                abilities_raw = {}
            if isinstance(abilities_raw, list):
                abilities_raw = {str(i): item for i, item in enumerate(abilities_raw)}
            abilities_list = list(abilities_raw.values()) if isinstance(abilities_raw, dict) else []

            # AW (Alliance War Tactics)
            try:
                aw_raw = load_file("aw") or {}
                aw_obj = aw_raw.get("aw") if isinstance(aw_raw, dict) else None
            except Exception:
                log.exception("Failed to load AW file")
                aw_obj = None

            self.aw = aw_obj or {}

            # Optional AW champion indexes
            aw_def_champs = []
            aw_atk_champs = []

            if aw_obj:
                try:
                    for c in aw_obj.get("defense", {}).get("champions", []) or []:
                        if isinstance(c, dict):
                            aw_def_champs.append(c)
                except Exception:
                    pass

                try:
                    for c in aw_obj.get("attack", {}).get("champions", []) or []:
                        if isinstance(c, dict):
                            aw_atk_champs.append(c)
                except Exception:
                    pass

            self.aw_defense_champions = aw_def_champs
            self.aw_attack_champions = aw_atk_champs

            # Optional AW tag → champions mapping
            aw_tag_map = {}
            if aw_obj:
                try:
                    def_tag = aw_obj.get("defense", {}).get("tag", {}).get("id")
                    if def_tag:
                        aw_tag_map[def_tag.lower()] = aw_def_champs
                except Exception:
                    pass

                try:
                    atk_tag = aw_obj.get("attack", {}).get("tag", {}).get("id")
                    if atk_tag:
                        aw_tag_map[atk_tag.lower()] = aw_atk_champs
                except Exception:
                    pass

            self.aw_tag_map = aw_tag_map

            # Tierlist
            try:
                tier_raw = load_file("tierlist") or {}
                tier_list = tier_raw.get("champions", []) if isinstance(tier_raw, dict) else []
            except Exception:
                log.exception("Failed to load tierlist file")
                tier_list = []

            self.tierlist = tier_list

            tier_by_name = {}
            tier_by_slug = {}

            for entry in tier_list:
                name = entry.get("name")
                if not isinstance(name, str):
                    continue

                norm = self._normalize_name(name)
                tier_by_name[norm] = entry

                slug = norm.replace(" ", "-")
                tier_by_slug[slug] = entry

            self.tier_by_name = tier_by_name
            self.tier_by_slug = tier_by_slug


            # Immunities
            try:
                immunities_raw = load_file("immunities").get("immunities", {})
            except Exception:
                log.exception("Failed to load immunities file")
                immunities_raw = {}
            if isinstance(immunities_raw, list):
                immunities_raw = {str(i): item for i, item in enumerate(immunities_raw)}
            immunities_list = list(immunities_raw.values()) if isinstance(immunities_raw, dict) else []

            # Tags
            try:
                tags_raw = load_file("tags").get("tags", {})
            except Exception:
                log.exception("Failed to load tags file")
                tags_raw = {}
            if isinstance(tags_raw, list):
                tags_list = [t for t in tags_raw if isinstance(t, str)]
            elif isinstance(tags_raw, dict):
                tags_list = []
                for k, t in tags_raw.items():
                    if isinstance(t, dict):
                        name = t.get("name")
                        if isinstance(name, str):
                            tags_list.append(name)
                        else:
                            tags_list.append(str(k))
                    elif isinstance(t, str):
                        tags_list.append(t)
                    else:
                        tags_list.append(str(k))
            else:
                tags_list = []

            # Prestige (optional file)
            try:
                prestige_raw = load_file("prestige") or {}
                prestige_rows = prestige_raw.get("rows", []) if isinstance(prestige_raw, dict) else []
            except Exception:
                log.exception("Failed to load prestige file")
                prestige_rows = []


            # Build new maps locally
            champions_by_id: Dict[str, Dict[str, Any]] = {}
            champions_by_name: Dict[str, Dict[str, Any]] = {}
            champions_by_tag: Dict[str, List[Dict[str, Any]]] = {}
            champions_by_ability: Dict[str, List[Dict[str, Any]]] = {}
            champions_by_immunity: Dict[str, List[Dict[str, Any]]] = {}

            for champ in champions_list:
                if not isinstance(champ, dict):
                    continue
                # id and name
                cid = champ.get("id")
                name = champ.get("name")
                if cid is not None:
                    champions_by_id[str(cid)] = champ
                if isinstance(name, str) and name:
                    champions_by_name[name.lower()] = champ

                # tags
                for tag in champ.get("tags", []) or []:
                    if not isinstance(tag, str):
                        continue
                    k = tag.lower()
                    champions_by_tag.setdefault(k, []).append(champ)

                # abilities: ability entries may be dicts or simple ids/names
                for ability in champ.get("abilities", []) or []:
                    if isinstance(ability, dict):
                        aid = ability.get("name") or ability.get("id")
                    else:
                        aid = ability
                    if aid is None:
                        continue
                    ak = str(aid).lower()
                    champions_by_ability.setdefault(ak, []).append(champ)

                # immunities
                for imm in champ.get("immunities", []) or []:
                    if isinstance(imm, dict):
                        iid = imm.get("name") or imm.get("id")
                    else:
                        iid = imm
                    if iid is None:
                        continue
                    ik = str(iid).lower()
                    champions_by_immunity.setdefault(ik, []).append(champ)

            # Build prestige index
            prestige_index: Dict[str, List[Dict[str, Any]]] = {}
            for row in prestige_rows:
                try:
                    slug = (row.get("slug") or "").lower()
                    if not slug:
                        continue
                    # store minimal useful info: tier/rank/asc and the row itself
                    prestige_index.setdefault(slug, []).append({
                        "tier": row.get("_tier"),
                        "rank": row.get("_rank"),
                        "asc": row.get("_asc"),
                        "row": row
                    })
                except Exception:
                    continue

            # Atomically swap in new stores
            self.champions = champions_list
            self.abilities = abilities_list
            self.immunities = immunities_list
            self.tags = tags_list
            self._tags_lower = [t.lower() for t in tags_list if isinstance(t, str)]
            self.prestige_index = prestige_index
            self.aw = aw_obj or {}
            self.aw_defense_champions = aw_def_champs
            self.aw_attack_champions = aw_atk_champs
            self.aw_tag_map = aw_tag_map

            self.tierlist = tier_list
            self.tier_by_name = tier_by_name
            self.tier_by_slug = tier_by_slug


            self.champions_by_id = champions_by_id
            self.champions_by_name = champions_by_name
            self.champions_by_tag = champions_by_tag
            self.champions_by_ability = champions_by_ability
            self.champions_by_immunity = champions_by_immunity

        except Exception:
            log.exception("Failed to rebuild CacheIndex")
            # Reset to safe defaults
            self.abilities = []
            self.aw = {}
            self.aw_defense_champions = []
            self.aw_attack_champions = []
            self.aw_tag_map = {}
            self.champions = []
            self.tags = []
            self.tierlist = []
            self.tier_by_name = {}
            self.tier_by_slug = {}
            self.immunities = []
            self.champions_by_id = {}
            self.champions_by_name = {}
            self.champions_by_tag = {}
            self.champions_by_ability = {}
            self.champions_by_immunity = {}
            self._tags_lower = []
            self.prestige_index = {}
        finally:
            self._rebuild_lock.release()
            
    async def rebuild_async(self) -> None:
        """
        Async wrapper that runs rebuild in a thread. Call this from async code.
        """
        await asyncio.to_thread(self.rebuild)

    def start_background_build(self) -> None:
        """
        Start a background thread to build the index without blocking the caller.
        Safe to call from sync or async contexts.
        """
        try:
            threading.Thread(target=self.rebuild, daemon=True).start()
        except Exception:
            log.exception("Failed to start background build thread")

    # ---------------------------------------------------------
    # Autocomplete helpers (robust to interaction=None)
    # ---------------------------------------------------------
    def get_prestige_rows_for_slug(self, slug: str) -> List[Dict[str, Any]]:
        """Return list of prestige row entries for a slug (may be empty)."""
        if not slug:
            return []
        return self.prestige_index.get(slug.lower(), [])

    def get_prestige_row(self, slug: str, tier: Optional[int] = None, rank: Optional[int] = None, asc: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Return a single prestige row dict for `slug` that best matches optional filters.
        If tier/rank/asc are provided, prefer exact matches; otherwise return the first row found.
        Returns None if no match.
        """
        if not slug:
            return None
        rows = self.prestige_index.get(slug.lower(), [])
        if not rows:
            return None
        # If all filters provided, try exact match first
        if tier is not None and rank is not None and asc is not None:
            for entry in rows:
                try:
                    if int(entry.get("tier")) == int(tier) and int(entry.get("rank")) == int(rank) and int(entry.get("asc")) == int(asc):
                        return entry.get("row")
                except Exception:
                    continue
        # If partial filters provided, prefer entries matching the provided fields
        if tier is not None or rank is not None or asc is not None:
            for entry in rows:
                try:
                    if tier is not None and int(entry.get("tier")) != int(tier):
                        continue
                    if rank is not None and int(entry.get("rank")) != int(rank):
                        continue
                    if asc is not None and int(entry.get("asc")) != int(asc):
                        continue
                    return entry.get("row")
                except Exception:
                    continue
        # Fallback: return the first available row
        return rows[0].get("row")

    async def tag_autocomplete(self, interaction, current: Optional[str]):
        cur = (current or "").lower()
        if not cur:
            matches = self.tags[:25]
        else:
            matches = [t for t in self.tags if cur in t.lower()][:25]
        # Lazy import to avoid module-level discord dependency
        try:
            import discord as _discord
            Choice = _discord.app_commands.Choice
        except Exception:
            # Fallback simple structure if discord not available in this context
            return [{"name": t, "value": t} for t in matches]
        return [Choice(name=t, value=t) for t in matches]

    async def ability_autocomplete(self, interaction, current: Optional[str]):
        cur = (current or "").lower()
        matches = []
        if not cur:
            matches = self.abilities[:25]
        else:
            for a in self.abilities:
                name = (a.get("name") or "") if isinstance(a, dict) else ""
                if cur in name.lower():
                    matches.append(a)
                    if len(matches) >= 25:
                        break
        try:
            import discord as _discord
            Choice = _discord.app_commands.Choice
        except Exception:
            return [{"name": (a.get("name") or ""), "value": a.get("id")} for a in matches]
        return [Choice(name=(a.get("name") or ""), value=a.get("id")) for a in matches]

    async def immunity_autocomplete(self, interaction, current: Optional[str]):
        cur = (current or "").lower()
        matches = []
        if not cur:
            matches = self.immunities[:25]
        else:
            for i in self.immunities:
                name = (i.get("name") or "") if isinstance(i, dict) else ""
                if cur in name.lower():
                    matches.append(i)
                    if len(matches) >= 25:
                        break
        try:
            import discord as _discord
            Choice = _discord.app_commands.Choice
        except Exception:
            return [{"name": (i.get("name") or ""), "value": i.get("id")} for i in matches]
        return [Choice(name=(i.get("name") or ""), value=i.get("id")) for i in matches]
