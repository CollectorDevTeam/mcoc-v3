# mcoc/cacheindex.py
import logging
import threading
import asyncio
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

        # Reverse lookup tables
        self.champions_by_id: Dict[str, Dict[str, Any]] = {}
        self.champions_by_name: Dict[str, Dict[str, Any]] = {}
        self.champions_by_tag: Dict[str, List[Dict[str, Any]]] = {}
        self.champions_by_ability: Dict[str, List[Dict[str, Any]]] = {}
        self.champions_by_immunity: Dict[str, List[Dict[str, Any]]] = {}

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

            # Atomically swap in new stores
            self.champions = champions_list
            self.abilities = abilities_list
            self.immunities = immunities_list
            self.tags = tags_list
            self._tags_lower = [t.lower() for t in tags_list if isinstance(t, str)]

            self.champions_by_id = champions_by_id
            self.champions_by_name = champions_by_name
            self.champions_by_tag = champions_by_tag
            self.champions_by_ability = champions_by_ability
            self.champions_by_immunity = champions_by_immunity

        except Exception:
            log.exception("Failed to rebuild CacheIndex")
            # Reset to safe defaults
            self.champions = []
            self.tags = []
            self.abilities = []
            self.immunities = []
            self.champions_by_id = {}
            self.champions_by_name = {}
            self.champions_by_tag = {}
            self.champions_by_ability = {}
            self.champions_by_immunity = {}
            self._tags_lower = []
        finally:
            try:
                self._rebuild_lock.release()
            except Exception:
                pass

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
