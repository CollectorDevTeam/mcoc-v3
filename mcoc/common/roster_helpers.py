# mcoc/common/roster_helpers.py
import re
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
      {
        "champion": Optional[str],   # name/slug if present
        "rarity": int or None,
        "rank": int or None,
        "sig": int,
        "tags": List[str],
        "ascended": int,
      }
    Defaults: sig=0, ascended=0. Rarity/rank may be None (validation will catch).
    """
    entry = {
        "champion": None,
        "rarity": None,
        "rank": None,
        "sig": 0,
        "tags": [],
        "ascended": 0,
    }
    try:
        if parsed.get("champion"):
            entry["champion"] = str(parsed["champion"]).strip()
    except Exception:
        entry["champion"] = None

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
            # accept first ascension token as ascended level
            entry["ascended"] = int(parsed["ascended"][0])
    except Exception:
        entry["ascended"] = 0

    # normalize tags to strings lowercased
    tags = parsed.get("tags") or []
    entry["tags"] = [str(t).lower() for t in tags if t]

    return entry


def validate_entry_for_add(entry: Dict[str, Any]) -> bool:
    """
    Basic validation for adding a roster entry:
      - rarity must be 1..7
      - rank must be 1..5
      - sig must be >= 0 and reasonable (0..9999)
      - ascended must be >=0 and small (0..9)
    Returns True if valid, False otherwise.
    """
    try:
        r = entry.get("rarity")
        rk = entry.get("rank")
        sig = entry.get("sig", 0)
        asc = entry.get("ascended", 0)

        if r is None or rk is None:
            return False

        r = int(r); rk = int(rk); sig = int(sig); asc = int(asc)

        if not (1 <= r <= 7):
            return False
        if not (1 <= rk <= 5):
            return False
        if not (0 <= sig <= 9999):
            return False
        if not (0 <= asc <= 9):
            return False

        return True
    except Exception:
        return False


async def build_roster_pages(core: Any, user_id: int, parsed_filters: Optional[Dict[str, Any]] = None) -> List[Any]:
    """
    Build compact list-style pages for a user's roster entries that match parsed_filters.
    Uses the server-specific class emoji IDs provided by the user.
    """
    pages: List[Any] = []
    try:
        users = ensure_user_manager(core)
        roster = []
        try:
            if asyncio.iscoroutinefunction(getattr(users, "list_roster", None)):
                roster = await users.list_roster(user_id)
            else:
                roster = users.list_roster(user_id) if users else []
        except Exception:
            try:
                roster = users.list_roster(user_id) if users else []
            except Exception:
                roster = []

        cache = getattr(core, "cache", None)
        parsed = parsed_filters or {}

        # Use the exact emoji tokens you provided
        class_map = {
            "all": "<:allclasses:748808348996075540>",
            "tech": "<:tech:748808546283683870>",
            "skill": "<:skill:748809095456227389>",
            "mutant": "<:mutant:748808841465954304>",
            "mystic": "<:mystic:748808953701335080>",
            "cosmic": "<:cosmic:748808707328180265>",
            "science": "<:science:748809185398882404>",
        }

        lines: List[str] = []
        for entry in roster:
            try:
                # Filters
                if parsed.get("rarities") and entry.get("rarity") not in parsed.get("rarities"):
                    continue
                if parsed.get("ranks") and entry.get("rank") not in parsed.get("ranks"):
                    continue
                if parsed.get("sigs") and entry.get("sig") not in parsed.get("sigs"):
                    continue

                skip = False
                for t in parsed.get("tags", []):
                    if t.lower() not in [x.lower() for x in (entry.get("tags") or [])]:
                        skip = True
                        break
                if skip:
                    continue

                # Resolve champion object if possible
                champ = None
                if cache:
                    try:
                        champ = cache.get_champion(entry.get("champion"))
                    except Exception:
                        champ = None
                if not champ and cache:
                    try:
                        for c in cache.get_all_champions() or []:
                            if str(c.get("id") or c.get("slug") or "").lower() == str(entry.get("champion")).lower() or str(c.get("name") or "").lower() == str(entry.get("champion")).lower():
                                champ = c
                                break
                    except Exception:
                        champ = None

                # Build display line
                name = (champ.get("name") if champ else entry.get("champion")) or "Unknown"
                cls = (champ.get("class") if champ else "").lower() if champ else ""
                cls_emoji = class_map.get(cls, "<:allclasses:748808348996075540>")
                stars = entry.get("rarity") or entry.get("stars") or 6
                rank = entry.get("rank") or 1
                sig = entry.get("sig") or 0
                asc = entry.get("ascended") or 0

                star_text = f"{stars}★"
                sig_icon = "☆" if sig == 0 else "★"
                asc_text = f" A{asc}" if asc else ""
                sig_text = f" s{sig}" if sig else ""
                line = f"{cls_emoji} {star_text}{sig_icon} **{name}** r{rank}{sig_text}{asc_text}"
                lines.append(line)
            except Exception:
                continue

        if not lines:
            try:
                import discord
                emb = discord.Embed(title="Roster", description="No champions match the filters.")
                pages.append(emb)
            except Exception:
                pages.append({"title": "Roster", "description": "No champions match the filters."})
            return pages

        PAGE_LINE_LIMIT = 15
        PAGE_CHAR_LIMIT = 1800

        cur: List[str] = []
        cur_len = 0
        for line in lines:
            if len(cur) >= PAGE_LINE_LIMIT or (cur_len + len(line) + 1) > PAGE_CHAR_LIMIT:
                pages.append("\n".join(cur))
                cur = []
                cur_len = 0
            cur.append(line)
            cur_len += len(line) + 1
        if cur:
            pages.append("\n".join(cur))

        embed_pages: List[Any] = []
        try:
            import discord
            for i, p in enumerate(pages):
                title = "Roster"
                emb = discord.Embed(title=title, description=p)
                emb.set_footer(text=f"Page {i+1} of {len(pages)}")
                embed_pages.append(emb)
            return embed_pages
        except Exception:
            out = []
            for i, p in enumerate(pages):
                out.append({"title": "Roster", "description": p, "footer": {"text": f"Page {i+1} of {len(pages)}"}})
            return out

    except Exception:
        log.exception("Failed to build roster pages")
        return []
