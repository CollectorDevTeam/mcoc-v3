# mcoc/userdata.py
import json
import pathlib
import logging
import tempfile
import os
import asyncio
from typing import Any, Dict, List, Optional

log = logging.getLogger("red.mcoc.userdata")

DEFAULT_USER_DIR = pathlib.Path("data") / "users"


class UserDataManager:
    """
    Simple per-user JSON storage for rosters and privacy settings.

    - Directory creation is done when the manager is instantiated (import-neutral).
    - Provides both sync and async file helpers. Public API remains synchronous
      for compatibility; async variants are available for callers that prefer them.
    """

    def __init__(self, user_dir: Optional[pathlib.Path] = None):
        self.user_dir = (user_dir or DEFAULT_USER_DIR)
        try:
            self.user_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            log.exception("Failed to ensure user data directory exists: %s", self.user_dir)

    # -----------------------------
    # Internal helpers
    # -----------------------------
    def _path(self, user_id: int) -> pathlib.Path:
        return self.user_dir / f"{user_id}.json"

    def _read_json_blocking(self, path: pathlib.Path) -> Any:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _atomic_write_json_blocking(self, path: pathlib.Path, data: Any) -> None:
        fd, tmp = tempfile.mkstemp(dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            pathlib.Path(tmp).replace(path)
        except Exception:
            log.exception("Failed atomic write to %s", path)
            try:
                pathlib.Path(tmp).unlink()
            except Exception:
                pass

    async def _read_json_async(self, path: pathlib.Path) -> Any:
        return await asyncio.to_thread(self._read_json_blocking, path)

    async def _atomic_write_json_async(self, path: pathlib.Path, data: Any) -> None:
        await asyncio.to_thread(self._atomic_write_json_blocking, path, data)

    # -----------------------------
    # Load / Save (sync)
    # -----------------------------
    def _load(self, user_id: int) -> Dict[str, Any]:
        path = self._path(user_id)
        if not path.exists():
            return self._default_user_data(user_id)
        try:
            return self._read_json_blocking(path)
        except Exception:
            log.exception("Failed to load user data for %s; returning default", user_id)
            return self._default_user_data(user_id)

    def _save(self, user_id: int, data: Dict[str, Any]) -> None:
        path = self._path(user_id)
        try:
            self._atomic_write_json_blocking(path, data)
        except Exception:
            log.exception("Failed to save user data for %s", user_id)

    # -----------------------------
    # Load / Save (async)
    # -----------------------------
    async def _load_async(self, user_id: int) -> Dict[str, Any]:
        path = self._path(user_id)
        if not path.exists():
            return self._default_user_data(user_id)
        try:
            return await self._read_json_async(path)
        except Exception:
            log.exception("Failed to load user data async for %s; returning default", user_id)
            return self._default_user_data(user_id)

    async def _save_async(self, user_id: int, data: Dict[str, Any]) -> None:
        path = self._path(user_id)
        try:
            await self._atomic_write_json_async(path, data)
        except Exception:
            log.exception("Failed to save user data async for %s", user_id)

    # -----------------------------
    # Defaults
    # -----------------------------
    def _default_user_data(self, user_id: int) -> Dict[str, Any]:
        return {
            "user_id": str(user_id),
            "roster": [],
            "privacy": {
                "mode": "private",  # private | alliance | guild | public
                "share_with_alliance": False,
                "share_with_guilds": [],
            },
            "alliances": {},  # guild_id : alliance_name
        }

    # -----------------------------
    # Roster operations (sync)
    # -----------------------------
    def add_champion(self, user_id: int, champ_slug: str, rarity: int, rank: int, sig: int, tags: Optional[List[str]] = None) -> None:
        data = self._load(user_id)
        tags = tags or []

        entry = {
            "champion": str(champ_slug),
            "rarity": int(rarity),
            "rank": int(rank),
            "sig": int(sig),
            "tags": list(tags),
        }

        # prevent duplicates (same champion + rarity)
        for c in data.get("roster", []):
            if c.get("champion") == entry["champion"] and c.get("rarity") == entry["rarity"]:
                log.info("Champion %s already exists for user %s. Updating instead.", champ_slug, user_id)
                c.update(entry)
                self._save(user_id, data)
                return

        data.setdefault("roster", []).append(entry)
        self._save(user_id, data)

    def remove_champion(self, user_id: int, champ_slug: str, rarity: Optional[int] = None) -> int:
        data = self._load(user_id)
        before = len(data.get("roster", []))
        data["roster"] = [
            c for c in data.get("roster", [])
            if not (c.get("champion") == str(champ_slug) and (rarity is None or c.get("rarity") == rarity))
        ]
        self._save(user_id, data)
        return before - len(data.get("roster", []))

    def update_champion(self, user_id: int, champ_slug: str, rarity: int, rank: Optional[int] = None, sig: Optional[int] = None, tags: Optional[List[str]] = None) -> bool:
        data = self._load(user_id)
        for c in data.get("roster", []):
            if c.get("champion") == str(champ_slug) and c.get("rarity") == int(rarity):
                if rank is not None:
                    c["rank"] = int(rank)
                if sig is not None:
                    c["sig"] = int(sig)
                if tags is not None:
                    c["tags"] = list(tags)
                self._save(user_id, data)
                return True
        return False

    def list_roster(self, user_id: int) -> List[Dict[str, Any]]:
        data = self._load(user_id)
        return data.get("roster", [])

    # -----------------------------
    # Privacy operations (sync)
    # -----------------------------
    def set_privacy_mode(self, user_id: int, mode: str) -> None:
        data = self._load(user_id)
        data.setdefault("privacy", {})["mode"] = str(mode)
        self._save(user_id, data)

    def allow_guild(self, user_id: int, guild_id: int) -> None:
        data = self._load(user_id)
        shares = data.setdefault("privacy", {}).setdefault("share_with_guilds", [])
        if guild_id not in shares:
            shares.append(guild_id)
        self._save(user_id, data)

    def revoke_guild(self, user_id: int, guild_id: int) -> None:
        data = self._load(user_id)
        shares = data.setdefault("privacy", {}).setdefault("share_with_guilds", [])
        data["privacy"]["share_with_guilds"] = [g for g in shares if g != guild_id]
        self._save(user_id, data)

    # -----------------------------
    # Alliance membership (sync)
    # -----------------------------
    def join_alliance(self, user_id: int, guild_id: int, alliance_name: str) -> None:
        data = self._load(user_id)
        data.setdefault("alliances", {})[str(guild_id)] = str(alliance_name)
        self._save(user_id, data)

    def leave_alliance(self, user_id: int, guild_id: int) -> None:
        data = self._load(user_id)
        if str(guild_id) in data.get("alliances", {}):
            del data["alliances"][str(guild_id)]
        self._save(user_id, data)

    # -----------------------------
    # Export / Import (sync)
    # -----------------------------
    def export(self, user_id: int) -> Dict[str, Any]:
        return self._load(user_id)

    def import_data(self, user_id: int, data: Dict[str, Any]) -> None:
        # Basic validation: ensure dict-like
        if not isinstance(data, dict):
            raise ValueError("import_data expects a dict")
        self._save(user_id, data)

    # -----------------------------
    # Delete user data (sync)
    # -----------------------------
    def delete_user(self, user_id: int) -> bool:
        path = self._path(user_id)
        try:
            if path.exists():
                path.unlink()
                return True
        except Exception:
            log.exception("Failed to delete user data for %s", user_id)
        return False

    # -----------------------------
    # Async convenience wrappers
    # -----------------------------
    async def add_champion_async(self, *args, **kwargs) -> None:
        return await asyncio.to_thread(self.add_champion, *args, **kwargs)

    async def remove_champion_async(self, *args, **kwargs) -> int:
        return await asyncio.to_thread(self.remove_champion, *args, **kwargs)

    async def update_champion_async(self, *args, **kwargs) -> bool:
        return await asyncio.to_thread(self.update_champion, *args, **kwargs)

    async def list_roster_async(self, user_id: int) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self.list_roster, user_id)

    async def export_async(self, user_id: int) -> Dict[str, Any]:
        return await asyncio.to_thread(self.export, user_id)

    async def import_data_async(self, user_id: int, data: Dict[str, Any]) -> None:
        return await asyncio.to_thread(self.import_data, user_id, data)

    async def delete_user_async(self, user_id: int) -> bool:
        return await asyncio.to_thread(self.delete_user, user_id)
