import logging
import threading
import asyncio

log = logging.getLogger("red.mcoc.cacheindex")


class CacheIndex:
    """
    Fast in-memory index built from CacheManager files.
    Provides instant lookup for champions, tags, abilities, immunities.
    """

    def __init__(self, cache_manager):
        self.cache = cache_manager

        # Primary stores
        self.champions = []              # list of champion dicts
        self.tags = []                   # list[str]
        self.abilities = []              # list[dict]
        self.immunities = []             # list[dict]

        # Reverse lookup tables
        self.champions_by_id = {}
        self.champions_by_name = {}
        self.champions_by_tag = {}
        self.champions_by_ability = {}
        self.champions_by_immunity = {}

        # Protect rebuilds from concurrent execution
        self._rebuild_lock = threading.Lock()

        # Build index (synchronous; caller may offload to a thread)
        try:
            self.rebuild()
        except Exception:
            # If rebuild fails at init, keep object usable
            log.exception("Initial CacheIndex.rebuild() failed during __init__")

    # ---------------------------------------------------------
    # Rebuild the entire index from cache files
    # ---------------------------------------------------------
    def rebuild(self):
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
            # Localize frequently used helpers for speed
            load_file = self.cache._load_file
            champions_raw = load_file("champions").get("champions", {})

            # Normalize champions to dict keyed by id/name
            if isinstance(champions_raw, list):
                mapped = {}
                for i, item in enumerate(champions_raw):
                    if isinstance(item, dict):
                        key = item.get("id") or item.get("champion_id") or (item.get("name") or "").lower() or str(i)
                    else:
                        key = str(i)
                    mapped[str(key)] = item
                champions_raw = mapped

            if isinstance(champions_raw, dict):
                champions_list = list(champions_raw.values())
            else:
                champions_list = []

            # Abilities
            abilities_raw = load_file("abilities").get("abilities", {})
            if isinstance(abilities_raw, list):
                abilities_raw = {str(i): item for i, item in enumerate(abilities_raw)}
            abilities_list = list(abilities_raw.values()) if isinstance(abilities_raw, dict) else []

            # Immunities
            immunities_raw = load_file("immunities").get("immunities", {})
            if isinstance(immunities_raw, list):
                immunities_raw = {str(i): item for i, item in enumerate(immunities_raw)}
            immunities_list = list(immunities_raw.values()) if isinstance(immunities_raw, dict) else []

            # Tags
            tags_raw = load_file("tags").get("tags", {})
            if isinstance(tags_raw, list):
                tags_list = tags_raw
            elif isinstance(tags_raw, dict):
                # prefer explicit name field if present
                tags_list = [t.get("name", str(k)) for k, t in tags_raw.items()]
            else:
                tags_list = []

            # Assign primary stores
            self.champions = champions_list
            self.abilities = abilities_list
            self.immunities = immunities_list
            self.tags = tags_list
            self._tags_lower = [t.lower() for t in tags_list if isinstance(t, str)]

            # Rebuild reverse lookup tables efficiently
            champions_by_id = {}
            champions_by_name = {}
            champions_by_tag = {}
            champions_by_ability = {}
            champions_by_immunity = {}

            for champ in champions_list:
                if not isinstance(champ, dict):
                    continue
                cid = champ.get("id")
                name = champ.get("name")
                if cid is not None:
                    champions_by_id[str(cid)] = champ
                if name:
                    champions_by_name[name.lower()] = champ

                # tags
                for tag in champ.get("tags", []):
                    if not isinstance(tag, str):
                        continue
                    k = tag.lower()
                    champions_by_tag.setdefault(k, []).append(champ)

                # abilities: ability entries may be dicts or simple ids/names
                for ability in champ.get("abilities", []):
                    if isinstance(ability, dict):
                        aid = ability.get("name") or ability.get("id")
                    else:
                        aid = ability
                    if aid is None:
                        continue
                    ak = str(aid).lower()
                    champions_by_ability.setdefault(ak, []).append(champ)

                # immunities
                for imm in champ.get("immunities", []):
                    if isinstance(imm, dict):
                        iid = imm.get("name") or imm.get("id")
                    else:
                        iid = imm
                    if iid is None:
                        continue
                    ik = str(iid).lower()
                    champions_by_immunity.setdefault(ik, []).append(champ)


            # Atomically swap in new maps
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
        finally:
            try:
                self._rebuild_lock.release()
            except Exception:
                pass

    async def rebuild_async(self):
        """
        Async wrapper that runs rebuild in a thread. Call this from async code.
        """
        await asyncio.to_thread(self.rebuild)

    # ---------------------------------------------------------
    # Autocomplete helpers
    # ---------------------------------------------------------
    async def tag_autocomplete(self, interaction, current: str):
        cur = (current or "").lower()
        matches = [t for t in self.tags if cur in t.lower()]
        return [interaction.client.app_commands.Choice(name=t, value=t) for t in matches[:25]]

    async def ability_autocomplete(self, interaction, current: str):
        cur = (current or "").lower()
        matches = [a for a in self.abilities if cur in (a.get("name") or "").lower()]
        return [interaction.client.app_commands.Choice(name=a.get("name"), value=a.get("id")) for a in matches[:25]]

    async def immunity_autocomplete(self, interaction, current: str):
        cur = (current or "").lower()
        matches = [i for i in self.immunities if cur in (i.get("name") or "").lower()]
        return [interaction.client.app_commands.Choice(name=i.get("name"), value=i.get("id")) for i in matches[:25]]

