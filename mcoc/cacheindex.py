import logging

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

        # Build index
        self.rebuild()

    # ---------------------------------------------------------
    # Rebuild the entire index from cache files
    # ---------------------------------------------------------
    def rebuild(self):
        try:
            champs_raw = self.cache._load_file("champions").get("champions", {})
            # Accept list or dict; normalize to dict keyed by id/name
            if isinstance(champs_raw, list):
                mapped = {}
                for i, item in enumerate(champs_raw):
                    if isinstance(item, dict):
                        key = item.get("id") or item.get("champion_id") or item.get("name", "").lower() or str(i)
                    else:
                        key = str(i)
                    mapped[str(key)] = item
                champs_raw = mapped
            if isinstance(champs_raw, dict):
                self.champions = list(champs_raw.values())
            else:
                self.champions = []

            # Abilities
            abilities_raw = self.cache._load_file("abilities").get("abilities", {})
            if isinstance(abilities_raw, list):
                mapped = {}
                for i, item in enumerate(abilities_raw):
                    key = item.get("id") if isinstance(item, dict) else str(i)
                    mapped[str(key)] = item
                abilities_raw = mapped
            self.abilities = list(abilities_raw.values()) if isinstance(abilities_raw, dict) else []

            # Immunities
            immunities_raw = self.cache._load_file("immunities").get("immunities", {})
            if isinstance(immunities_raw, list):
                mapped = {}
                for i, item in enumerate(immunities_raw):
                    key = item.get("id") if isinstance(item, dict) else str(i)
                    mapped[str(key)] = item
                immunities_raw = mapped
            self.immunities = list(immunities_raw.values()) if isinstance(immunities_raw, dict) else []

            # Tags
            tags_raw = self.cache._load_file("tags").get("tags", {})
            if isinstance(tags_raw, list):
                mapped = {}
                for i, item in enumerate(tags_raw):
                    key = item.get("id") if isinstance(item, dict) else str(i)
                    mapped[str(key)] = item
                tags_raw = mapped
            # For tags we might want a list of names
            if isinstance(tags_raw, dict):
                self.tags = [t.get("name", str(k)) for k, t in tags_raw.items()]
            elif isinstance(tags_raw, list):
                self.tags = tags_raw
            else:
                self.tags = []

            # Rebuild reverse lookup tables defensively
            self.champions_by_id = {}
            self.champions_by_name = {}
            self.champions_by_tag = {}
            self.champions_by_ability = {}
            self.champions_by_immunity = {}

            for champ in self.champions:
                if not isinstance(champ, dict):
                    continue
                cid = champ.get("id")
                name = champ.get("name")
                if cid:
                    self.champions_by_id[str(cid)] = champ
                if name:
                    self.champions_by_name[name.lower()] = champ
                for tag in champ.get("tags", []):
                    self.champions_by_tag.setdefault(tag, []).append(champ)
                for ability in champ.get("abilities", []):
                    aid = ability.get("name") if isinstance(ability, dict) else ability
                    self.champions_by_ability.setdefault(aid, []).append(champ)
                for imm in champ.get("immunities", []):
                    iid = imm.get("name") if isinstance(imm, dict) else imm
                    self.champions_by_immunity.setdefault(iid, []).append(champ)

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


    # ---------------------------------------------------------
    # Autocomplete helpers
    # ---------------------------------------------------------
    async def tag_autocomplete(self, interaction, current: str):
        current = current.lower()
        matches = [
            tag for tag in self.tags
            if current in tag.lower()
        ]
        return [
            interaction.client.app_commands.Choice(name=t, value=t)
            for t in matches[:25]
        ]

    async def ability_autocomplete(self, interaction, current: str):
        current = current.lower()
        matches = [
            a for a in self.abilities
            if current in a["name"].lower()
        ]
        return [
            interaction.client.app_commands.Choice(name=a["name"], value=a["id"])
            for a in matches[:25]
        ]

    async def immunity_autocomplete(self, interaction, current: str):
        current = current.lower()
        matches = [
            i for i in self.immunities
            if current in i["name"].lower()
        ]
        return [
            interaction.client.app_commands.Choice(name=i["name"], value=i["id"])
            for i in matches[:25]
        ]
