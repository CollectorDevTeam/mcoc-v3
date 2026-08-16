import json
import pathlib
import logging

log = logging.getLogger("red.mcoc.userdata")

USER_DIR = pathlib.Path("data/users")
USER_DIR.mkdir(parents=True, exist_ok=True)

class UserDataManager:
    def __init__(self):
        pass

    # -----------------------------
    # Helpers
    # -----------------------------
    def _path(self, user_id: int):
        return USER_DIR / f"{user_id}.json"

    def _load(self, user_id: int):
        path = self._path(user_id)
        if not path.exists():
            return {
                "user_id": str(user_id),
                "roster": [],
                "privacy": {
                    "mode": "private",  # private | alliance | guild | public
                    "share_with_alliance": False,
                    "share_with_guilds": []
                },
                "alliances": {}  # guild_id : alliance_name
            }
        return json.load(open(path, "r"))

    def _save(self, user_id: int, data: dict):
        json.dump(data, open(self._path(user_id), "w"), indent=2)

    # -----------------------------
    # Roster operations
    # -----------------------------
    def add_champion(self, user_id: int, champ_slug: str, rarity: int, rank: int, sig: int, tags=None):
        data = self._load(user_id)
        tags = tags or []

        entry = {
            "champion": champ_slug,
            "rarity": rarity,
            "rank": rank,
            "sig": sig,
            "tags": tags
        }

        # prevent duplicates
        for c in data["roster"]:
            if c["champion"] == champ_slug and c["rarity"] == rarity:
                log.info(f"Champion {champ_slug} already exists for user {user_id}. Updating instead.")
                c.update(entry)
                self._save(user_id, data)
                return

        data["roster"].append(entry)
        self._save(user_id, data)

    def remove_champion(self, user_id: int, champ_slug: str, rarity=None):
        data = self._load(user_id)
        before = len(data["roster"])

        data["roster"] = [
            c for c in data["roster"]
            if not (c["champion"] == champ_slug and (rarity is None or c["rarity"] == rarity))
        ]

        self._save(user_id, data)
        return before - len(data["roster"])

    def update_champion(self, user_id: int, champ_slug: str, rarity: int, rank=None, sig=None, tags=None):
        data = self._load(user_id)
        for c in data["roster"]:
            if c["champion"] == champ_slug and c["rarity"] == rarity:
                if rank is not None:
                    c["rank"] = rank
                if sig is not None:
                    c["sig"] = sig
                if tags is not None:
                    c["tags"] = tags
                self._save(user_id, data)
                return True
        return False

    def list_roster(self, user_id: int):
        data = self._load(user_id)
        return data["roster"]

    # -----------------------------
    # Privacy operations
    # -----------------------------
    def set_privacy_mode(self, user_id: int, mode: str):
        data = self._load(user_id)
        data["privacy"]["mode"] = mode
        self._save(user_id, data)

    def allow_guild(self, user_id: int, guild_id: int):
        data = self._load(user_id)
        if guild_id not in data["privacy"]["share_with_guilds"]:
            data["privacy"]["share_with_guilds"].append(guild_id)
        self._save(user_id, data)

    def revoke_guild(self, user_id: int, guild_id: int):
        data = self._load(user_id)
        data["privacy"]["share_with_guilds"] = [
            g for g in data["privacy"]["share_with_guilds"] if g != guild_id
        ]
        self._save(user_id, data)

    # -----------------------------
    # Alliance membership
    # -----------------------------
    def join_alliance(self, user_id: int, guild_id: int, alliance_name: str):
        data = self._load(user_id)
        data["alliances"][str(guild_id)] = alliance_name
        self._save(user_id, data)

    def leave_alliance(self, user_id: int, guild_id: int):
        data = self._load(user_id)
        if str(guild_id) in data["alliances"]:
            del data["alliances"][str(guild_id)]
        self._save(user_id, data)

    # -----------------------------
    # Export / Import
    # -----------------------------
    def export(self, user_id: int):
        return self._load(user_id)

    def import_data(self, user_id: int, data: dict):
        self._save(user_id, data)

    # -----------------------------
    # Delete user data
    # -----------------------------
    def delete_user(self, user_id: int):
        path = self._path(user_id)
        if path.exists():
            path.unlink()
            return True
        return False
