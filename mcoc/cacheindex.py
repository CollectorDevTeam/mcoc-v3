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
        log.info("Rebuilding CacheIndex...")

        # Load raw data
        champs = self.cache._load_file("champions").get("champions", {})
        tags = self.cache._load_file("tags").get("tags", [])
        abilities = self.cache._load_file("abilities").get("abilities", [])
        immunities = self.cache._load_file("immunity").get("immunity", [])

        self.champions = list(champs.values())
        self.tags = tags
        self.abilities = abilities
        self.immunities = immunities

        # Clear reverse lookup tables
        self.champions_by_id.clear()
        self.champions_by_name.clear()
        self.champions_by_tag.clear()
        self.champions_by_ability.clear()
        self.champions_by_immunity.clear()

        # Build champion lookup tables
        for champ in self.champions:
            cid = champ["id"]
            name = champ["name"].lower()

            self.champions_by_id[cid] = champ
            self.champions_by_name[name] = champ

            # Tags
            for tag in champ.get("tags", []):
                self.champions_by_tag.setdefault(tag, []).append(champ)

            # Abilities
            for ability in champ.get("abilities", []):
                self.champions_by_ability.setdefault(ability, []).append(champ)

            # Immunities
            for immunity in champ.get("immunities", []):
                self.champions_by_immunity.setdefault(immunity, []).append(champ)

        log.info("CacheIndex rebuilt successfully.")

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
