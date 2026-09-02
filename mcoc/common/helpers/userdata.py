# Path: mcoc/common/helpers/userdata.py
# File-Version: 1.0
# File-Id: 825a7571-4e86-4f52-ae3d-8e41e1cfa5c8      # unique file id (generate with `python -c "import uuid; print(uuid.uuid4())"`)
# Purpose: Provide a manager for per-user JSON storage, handling rosters, profiles, and privacy settings.
# Public-API: UserDataManager
# Internal: 
# Last-Modified: 2026-09-01
# Changelog:
#   1.0 2026-09-01  Initial stabilized API header

# Public API (documented)
# - get_user_manager(user_dir: Optional[pathlib.Path] = None) -> UserDataManager
# - UserDataManager.add_champion(...)
# - UserDataManager.remove_champion(...)
# - UserDataManager.update_champion(...)
# - UserDataManager.list_roster(...)
# - UserDataManager.get_profile(...)
# - UserDataManager.set_profile_field(...)
# - UserDataManager.delete_user(...)
# - UserDataManager.set_privacy_mode(...)
# - UserDataManager.allow_guild(...)
# - UserDataManager.revoke_guild(...)
# - UserDataManager.can_view_profile(...)
# - UserDataManager.join_alliance(...)
# - UserDataManager.leave_alliance(...)
# - UserDataManager.get_alliance_for_guild(...)
# - UserDataManager.compute_user_prestige_from_roster(...)
# - UserDataManager.sort_roster_entries(...)

# Internal API (not documented)
# - UserDataManager._load(...)
# - UserDataManager._save(...)
# - UserDataManager._default_user_data(...)
# - UserDataManager._path(...)
# - UserDataManager._read_json_blocking(...)
# - UserDataManager._atomic_write_json_blocking(...)
# - UserDataManager._read_json_async(...)
# - UserDataManager._atomic_write_json_async(...)

import json
import pathlib
import logging
import tempfile
import os
import asyncio
from typing import Any, Dict, List, Optional, Tuple, Callable

log = logging.getLogger("red.mcoc.userdata")

DEFAULT_USER_DIR = pathlib.Path("data") / "users"


class UserDataManager:
    """
    Simple per-user JSON storage for rosters, profiles and privacy settings.

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
        # optional hook called after roster mutations: hook(user_id: int)
        # The hook should be non-blocking and schedule any async work on the bot loop.
        self.post_mutation_hook: Optional[Callable[[int], Any]] = None
        # optional bot loop for scheduling coroutines returned by hooks
        self.bot_loop = None

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
    # Defaults
    # -----------------------------
    def _default_user_data(self, user_id: int) -> Dict[str, Any]:
        return {
            "user_id": str(user_id),
            "roster": [],
            "profile": {
                "mcoc_id": None,
                "mcoc_name": None,
                "consent": False,
                "consent_ts": None,
                "consent_version": None,
                "consent_source": "https://github.com/CollectorDevTeam/mcoc-v3/blob/main/mcoc/privacy_policy.md",
                "website": None,
                "invite": None,
                "timezone": None,
                "alliance": None,
                "job": None,
                "created_at": None,
                "updated_at": None,
            },
            "privacy": {
                "mode": "private",  # private | alliance | guild | public
                "share_with_alliance": False,
                "share_with_guilds": [],  # list of guild ids (ints)
            },
            "alliances": {},  # guild_id (str) : alliance_name
        }

    # -----------------------------
    # Load / Save (sync)
    # -----------------------------
    def _load(self, user_id: int) -> Dict[str, Any]:
        path = self._path(user_id)
        if not path.exists():
            return self._default_user_data(user_id)
        try:
            data = self._read_json_blocking(path)
            # ensure minimal keys exist
            if not isinstance(data, dict):
                return self._default_user_data(user_id)
            data.setdefault("roster", [])
            data.setdefault("profile", self._default_user_data(user_id)["profile"])
            data.setdefault("privacy", self._default_user_data(user_id)["privacy"])
            data.setdefault("alliances", {})
            return data
        except Exception:
            log.exception("Failed to load user data for %s; returning default", user_id)
            return self._default_user_data(user_id)

    def _save(self, user_id: int, data: Dict[str, Any]) -> None:
        path = self._path(user_id)
        try:
            # ensure timestamps for profile
            prof = data.setdefault("profile", {})
            if not prof.get("created_at"):
                prof["created_at"] = __import__("datetime").datetime.utcnow().isoformat()
            prof["updated_at"] = __import__("datetime").datetime.utcnow().isoformat()
            self._atomic_write_json_blocking(path, data)
        except Exception:
            log.exception("Failed to save user data for %s", user_id)

    # -----------------------------
    # Post-mutation hook
    # -----------------------------
    def _call_post_hook(self, user_id: int) -> None:
        try:
            hook = getattr(self, "post_mutation_hook", None)
            if not callable(hook):
                return
            result = hook(user_id)
            # If hook returned a coroutine, schedule it on the running loop
            if asyncio.iscoroutine(result):
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(result)
                except RuntimeError:
                    # no running loop in this thread; try to get bot loop if available
                    try:
                        bot_loop = getattr(self, "bot_loop", None)
                        if bot_loop:
                            asyncio.run_coroutine_threadsafe(result, bot_loop)
                    except Exception:
                        log.exception("Failed to schedule coroutine returned by post_mutation_hook for user %s", user_id)
            else:
                # synchronous hook executed; log debug for visibility
                log.debug("post_mutation_hook executed for user %s", user_id)
        except Exception:
            log.exception("post_mutation_hook failed for user %s", user_id)

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
    # Roster operations (sync)
    # -----------------------------
    def add_champion(self, user_id: int, champ_slug: str, rarity: int, rank: int, sig: int, ascended: int = 0, tags: Optional[List[str]] = None) -> None:
        data = self._load(user_id)
        tags = tags or []

        entry = {
            "champion": str(champ_slug),
            "rarity": int(rarity),
            "rank": int(rank),
            "sig": int(sig),
            "ascended": int(ascended),
            "tags": list(tags),
            "stars": int(rarity),
            "prestige": None,
            "name": None,
        }

        # prevent duplicates (same champion + rarity)
        for c in data.get("roster", []):
            if c.get("champion") == entry["champion"] and c.get("rarity") == entry["rarity"]:
                log.info("Champion %s already exists for user %s. Updating instead.", champ_slug, user_id)
                c.update(entry)
                self._save(user_id, data)
                # call optional post-mutation hook (non-blocking)
                self._call_post_hook(user_id)
                return

        data.setdefault("roster", []).append(entry)
        self._save(user_id, data)

        # call optional post-mutation hook (non-blocking)
        self._call_post_hook(user_id)

    def remove_champion(self, user_id: int, champ_slug: str, rarity: Optional[int] = None) -> int:
        data = self._load(user_id)
        before = len(data.get("roster", []))
        data["roster"] = [
            c for c in data.get("roster", [])
            if not (c.get("champion") == str(champ_slug) and (rarity is None or c.get("rarity") == rarity))
        ]
        self._save(user_id, data)

        # call optional post-mutation hook (non-blocking)
        self._call_post_hook(user_id)

        return before - len(data.get("roster", []))

    def update_champion(self, user_id: int, champ_slug: str, rarity: int, rank: Optional[int] = None, sig: Optional[int] = None, tags: Optional[List[str]] = None, ascended: Optional[int] = None) -> bool:
        data = self._load(user_id)
        for c in data.get("roster", []):
            if c.get("champion") == str(champ_slug) and c.get("rarity") == int(rarity):
                if rank is not None:
                    c["rank"] = int(rank)
                if sig is not None:
                    c["sig"] = int(sig)
                if tags is not None:
                    c["tags"] = list(tags)
                if ascended is not None:
                    c["ascended"] = int(ascended)
                # keep stars/rarity consistent
                c["stars"] = int(c.get("rarity", c.get("stars", rarity)))
                self._save(user_id, data)
                self._call_post_hook(user_id)
                return True
        return False

    def list_roster(self, user_id: int) -> List[Dict[str, Any]]:
        data = self._load(user_id)
        return data.get("roster", [])

    # -----------------------------
    # Profile operations (sync)
    # -----------------------------
    def get_profile(self, user_id: int) -> Dict[str, Any]:
        data = self._load(user_id)
        return data.get("profile", {})

    def set_profile_field(self, user_id: int, field: str, value: Any) -> None:
        data = self._load(user_id)
        profile = data.setdefault("profile", {})
        profile[field] = value
        profile["updated_at"] = __import__("datetime").datetime.utcnow().isoformat()
        if not profile.get("created_at"):
            profile["created_at"] = profile["updated_at"]
        self._save(user_id, data)
        log.info("userdata.set_profile_field: user=%s field=%s value=%r", user_id, field, value)

    def delete_profile(self, user_id: int) -> bool:
        # alias for delete_user
        return self.delete_user(user_id)

    # -----------------------------
    # Privacy operations (sync)
    # -----------------------------
    def set_privacy_mode(self, user_id: int, mode: str) -> None:
        if mode not in ("private", "alliance", "guild", "public"):
            raise ValueError("Invalid privacy mode")
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

    def get_alliance_for_guild(self, user_id: int, guild_id: int) -> Optional[str]:
        data = self._load(user_id)
        return data.get("alliances", {}).get(str(guild_id))

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
    # Prestige and sorting helpers
    # -----------------------------
    @staticmethod
    def compute_user_prestige_from_roster(roster_entries: List[Dict[str, Any]], top_n: int = 5) -> Optional[float]:
        """
        Compute the average prestige of the user's top_n champions.
        Each roster entry should include a numeric 'prestige' field when available.
        Returns None if no prestige values are present.
        """
        vals = [e.get("prestige") for e in roster_entries if isinstance(e.get("prestige"), (int, float))]
        if not vals:
            return None
        vals.sort(reverse=True)
        top = vals[:top_n]
        return sum(top) / len(top)

    @staticmethod
    def sort_roster_entries(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sort roster entries descending by prestige when available.
        Fallback ordering: stars desc, rank asc, sig desc.
        """
        def key(e: Dict[str, Any]) -> Tuple:
            p = e.get("prestige")
            if isinstance(p, (int, float)):
                # primary: prestige (higher first)
                return (0, -float(p), -int(e.get("stars", 0)), int(e.get("rank", 0)), -int(e.get("sig", 0)))
            # fallback group after prestige entries
            return (1, -int(e.get("stars", 0)), int(e.get("rank", 0)), -int(e.get("sig", 0)))
        return sorted(entries, key=key)

    # -----------------------------
    # Privacy check helper
    # -----------------------------
    def can_view_profile(self, viewer_id: int, owner_id: int, guild_id: Optional[int] = None, viewer_alliance: Optional[str] = None) -> bool:
        """
        Determine whether viewer_id can view owner_id's profile given privacy settings.
        - guild_id: the guild where the view is happening (optional)
        - viewer_alliance: alliance name of the viewer in this guild (optional)
        """
        if viewer_id == owner_id:
            return True
        data = self._load(owner_id)
        privacy = data.get("privacy", {}) or {}
        mode = privacy.get("mode", "private")
        if mode == "public":
            return True
        if mode == "private":
            return False
        if mode == "guild":
            if guild_id is None:
                return False
            shares = privacy.get("share_with_guilds", [])
            return guild_id in shares
        if mode == "alliance":
            # owner alliance for this guild
            owner_alliance = self.get_alliance_for_guild(owner_id, guild_id) if guild_id is not None else None
            # if viewer_alliance provided and matches owner's alliance, allow
            if owner_alliance and viewer_alliance and owner_alliance == viewer_alliance:
                return True
            # also allow if owner has share_with_alliance True and viewer_alliance matches any stored alliance
            if privacy.get("share_with_alliance") and viewer_alliance and owner_alliance == viewer_alliance:
                return True
            return False
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

    async def get_profile_async(self, user_id: int) -> Dict[str, Any]:
        return await asyncio.to_thread(self.get_profile, user_id)

    async def set_profile_field_async(self, user_id: int, field: str, value: Any) -> None:
        return await asyncio.to_thread(self.set_profile_field, user_id, field, value)

    async def compute_user_prestige_from_roster_async(self, roster_entries: List[Dict[str, Any]], top_n: int = 5) -> Optional[float]:
        return await asyncio.to_thread(self.compute_user_prestige_from_roster, roster_entries, top_n)

    async def sort_roster_entries_async(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self.sort_roster_entries, entries)


# -----------------------------
# Module-level shared manager and helpers
# -----------------------------
_GLOBAL_USER_MANAGER: Optional[UserDataManager] = None


def get_user_manager(user_dir: Optional[pathlib.Path] = None) -> UserDataManager:
    """
    Return a shared UserDataManager instance. If one does not exist, create it.
    Optional user_dir overrides the default storage location for the first creation.
    """
    global _GLOBAL_USER_MANAGER
    if _GLOBAL_USER_MANAGER is None:
        _GLOBAL_USER_MANAGER = UserDataManager(user_dir=user_dir)
    return _GLOBAL_USER_MANAGER


def set_post_mutation_hook(hook: Optional[Callable[[int], Any]]) -> None:
    """
    Set the post-mutation hook on the global user manager.
    The hook should accept a single user_id argument and may return a coroutine.
    """
    mgr = get_user_manager()
    mgr.post_mutation_hook = hook


def set_global_bot_loop(loop: Optional[asyncio.AbstractEventLoop]) -> None:
    """
    Optionally set a bot loop on the global manager so hooks can be scheduled
    when called from non-async threads.
    """
    mgr = get_user_manager()
    mgr.bot_loop = loop


def user_exists(user_id: int) -> bool:
    """
    Return True if a user data file exists for the given user_id.
    """
    mgr = get_user_manager()
    return mgr._path(user_id).exists()

# DECLARE PUBLIC API
__all__ = [
    "UserDataManager",
    "get_user_manager",
    "set_post_mutation_hook",
    "set_global_bot_loop",
    "user_exists",
    "export", 
    "import_data",
    "add_champion",
    "remove_champion",
    "update_champion",
    "list_roster",
    "get_profile",
    "set_profile_field",
    "delete_profile",
    "set_privacy_mode",
    "allow_guild",
    "revoke_guild",
    "can_view_profile",
    "join_alliance",
    "leave_alliance",
    "get_alliance_for_guild",
    "compute_user_prestige_from_roster",
    "sort_roster_entries"
]
