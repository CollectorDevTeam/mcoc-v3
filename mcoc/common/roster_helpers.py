# mcoc/common/roster_helpers.py
import logging
from typing import Any, Dict, List, Optional
import asyncio

log = logging.getLogger("red.mcoc.roster_helpers")


def ensure_user_manager(core_or_bot) -> Any:
    """
    Return a UserDataManager instance.
    Prefer an existing manager on the core (core.users or core.user_manager),
    otherwise create a fresh UserDataManager.
    """
    try:
        # core object (preferred)
        if core_or_bot is None:
            from .userdata import UserDataManager
            return UserDataManager()
        # core may expose a users manager
        um = getattr(core_or_bot, "users", None) or getattr(core_or_bot, "user_manager", None)
        if um:
            return um
    except Exception:
        log.exception("Error resolving existing user manager")

    # fallback: create a new one
    try:
        from .userdata import UserDataManager
        return UserDataManager()
    except Exception:
        log.exception("Failed to create UserDataManager")
        return None


def extract_entry_from_parsed(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert parse_hargs output into a canonical roster entry dict:
      { "rarity": int, "rank": int, "sig": int, "tags": List[str], "ascended": int }
    Values default to sensible defaults (sig 0, ascended 0).
    """
    entry = {
        "rarity": None,
        "rank": None,
        "sig": 0,
        "tags": [],
        "ascended": 0,
    }
    try:
        if parsed.get("rarities"):
            entry["rarity"] = int(parsed["rarities"][0])
    except Exception:
        entry["rarity"] = None
    try:
        if parsed.get("ranks"):
            entry["rank"] = int(parsed["ranks"][0])
    except Exception:
        entry["rank"] = None
    try:
        if parsed.get("sigs"):
            entry["sig"] = int(parsed["sigs"][0])
    except Exception:
        entry["sig"] = 0
    try:
        if parsed.get("ascended"):
            entry["ascended"] = int(parsed["ascended"][0])
    except Exception:
        entry["ascended"] = 0
    # normalize tags to strings
    tags = parsed.get("tags") or []
    entry["tags"] = [str(t).lower() for t in tags if t]
    return entry


async def build_roster_pages(core: Any, user_id: int, parsed_filters: Optional[Dict[str, Any]] = None) -> List[Any]:
    """
    Build a list of embed-like pages for a user's roster entries that match parsed_filters.
    Returns a list of discord.Embed or dict fallback objects.
    This function is async because it may call embed builders that are async.
    """
    pages: List[Any] = []
    try:
        users = ensure_user_manager(core)
        roster = users.list_roster(user_id) if users else []
        cache = getattr(core, "cache", None)
        parsed = parsed_filters or {}

        for entry in roster:
            try:
                # apply simple filters if provided
                if parsed.get("rarities") and entry.get("rarity") not in parsed.get("rarities"):
                    continue
                if parsed.get("ranks") and entry.get("rank") not in parsed.get("ranks"):
                    continue
                if parsed.get("sigs") and entry.get("sig") not in parsed.get("sigs"):
                    continue
                # tags intersection: every requested tag must be present
                skip = False
                for t in parsed.get("tags", []):
                    if t.lower() not in [x.lower() for x in (entry.get("tags") or [])]:
                        skip = True
                        break
                if skip:
                    continue

                # resolve champion object
                champ = None
                if cache:
                    try:
                        champ = cache.get_champion(entry.get("champion"))
                    except Exception:
                        champ = None
                # fallback: try scanning cache
                if not champ and cache:
                    try:
                        for c in cache.get_all_champions():
                            if str(c.get("id") or c.get("slug") or "").lower() == str(entry.get("champion")).lower():
                                champ = c
                                break
                    except Exception:
                        champ = None

                # Build embed using common embed helper (async)
                try:
                    from .embeds import roster_entry_embed
                    if champ:
                        embed = await roster_entry_embed(core if hasattr(core, "bot") else None, champ, entry)
                    else:
                        # fallback minimal dict embed
                        embed = {
                            "title": entry.get("champion"),
                            "description": f"Rarity: {entry.get('rarity')} Rank: {entry.get('rank')}",
                        }
                    pages.append(embed)
                except Exception:
                    # fallback minimal representation
                    pages.append({
                        "title": entry.get("champion"),
                        "description": f"Rarity: {entry.get('rarity')} Rank: {entry.get('rank')}"
                    })
            except Exception:
                continue
    except Exception:
        log.exception("Failed to build roster pages")
    return pages


def validate_entry_for_add(entry: Dict[str, Any]) -> bool:
    """
    Basic validation for adding a roster entry: requires rarity and rank.
    Returns True if valid.
    """
    try:
        if entry.get("rarity") is None or entry.get("rank") is None:
            return False
        # basic numeric sanity
        r = int(entry["rarity"])
        rk = int(entry["rank"])
        if not (1 <= r <= 7):
            return False
        if not (1 <= rk <= 5):
            return False
        return True
    except Exception:
        return False
