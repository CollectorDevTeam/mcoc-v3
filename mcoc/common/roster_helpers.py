# mcoc/common/roster_helpers.py
import re
import logging
from typing import Any, Dict, List, Optional, Tuple
import asyncio

log = logging.getLogger("red.mcoc.roster_helpers")


def ensure_user_manager(core_or_bot) -> Any:
    """
    Return a UserDataManager instance.
    Prefer an existing manager on the core (core.users or core.user_manager),
    otherwise create a fresh UserDataManager.
    """
    try:
        if core_or_bot is None:
            from .userdata import UserDataManager
            return UserDataManager()
        um = getattr(core_or_bot, "users", None) or getattr(core_or_bot, "user_manager", None)
        if um:
            return um
    except Exception:
        log.exception("Error resolving existing user manager")

    try:
        from .userdata import UserDataManager
        return UserDataManager()
    except Exception:
        log.exception("Failed to create UserDataManager")
        return None


# module-level debounce map
_persist_pending: Dict[int, asyncio.Task] = {}


def schedule_persist_user_prestige(core, user_id: int, delay: float = 1.5) -> None:
    """
    Debounced schedule for persist_user_prestige(core, user_id).
    Multiple calls within `delay` seconds coalesce into one run.
    """
    try:
        existing = _persist_pending.get(user_id)
        if existing and not existing.done():
            existing.cancel()
    except Exception:
        pass

    async def _delayed():
        try:
            await asyncio.sleep(delay)
            await persist_user_prestige(core, user_id)
        except asyncio.CancelledError:
            return
        except Exception:
            log.exception("Debounced persist_user_prestige failed for %s", user_id)
        finally:
            _persist_pending.pop(user_id, None)

    loop = getattr(core.bot, "loop", None) or asyncio.get_event_loop()
    task = loop.create_task(_delayed())
    _persist_pending[user_id] = task


async def persist_user_prestige(core: Any, user_id: int) -> None:
    """
    Compute prestige for each roster entry using core.cache/index and persist
    a small prestige_map into the user's profile: { "slug|stars": prestige }.
    Safe to call after add/update/remove roster operations.
    """
    try:
        users = ensure_user_manager(core)
        if users is None:
            return

        # load roster (sync or async)
        if asyncio.iscoroutinefunction(getattr(users, "list_roster", None)):
            roster = await users.list_roster(user_id)
        else:
            roster = users.list_roster(user_id)

        cache = getattr(core, "cache", None)
        idx = getattr(core, "cacheindex", None) or (getattr(cache, "index", None) if cache else None)

        prestige_map: Dict[str, Optional[int]] = {}

        for e in roster:
            try:
                slug = str(e.get("champion") or "").strip()
                raw_stars = int(e.get("rarity") or e.get("stars") or 6)
                raw_rank = int(e.get("rank") or 1)
                raw_sig = int(e.get("sig") or 0)
                raw_asc = int(e.get("ascended") or 0)

                if cache and hasattr(cache, "normalize_hargs_by_tier"):
                    try:
                        stars, rank, sig, asc = cache.normalize_hargs_by_tier(raw_stars, raw_rank, raw_sig, raw_asc)
                    except Exception:
                        stars, rank, sig, asc = raw_stars, raw_rank, raw_sig, raw_asc
                else:
                    stars, rank, sig, asc = raw_stars, raw_rank, raw_sig, raw_asc

                prestige = None
                if idx and slug:
                    try:
                        row = idx.get_prestige_row(slug, tier=stars, rank=rank, asc=asc)
                        if row:
                            sigs = row.get("sigs") or {}
                            prestige = cache.smooth_sig_value(sigs, sig) if hasattr(cache, "smooth_sig_value") else cache._smooth_sig_value(sigs, sig)
                    except Exception:
                        prestige = None

                if prestige is None and cache and hasattr(cache, "get_prestige_value"):
                    try:
                        prestige = cache.get_prestige_value(slug, stars, rank, asc, sig)
                    except Exception:
                        prestige = None

                key = f"{slug}|{stars}"
                prestige_map[key] = int(prestige) if isinstance(prestige, (int, float)) else None
            except Exception:
                continue

        # persist map into profile['prestige_map']
        try:
            if asyncio.iscoroutinefunction(getattr(users, "set_profile_field_async", None)):
                await users.set_profile_field_async(user_id, "prestige_map", prestige_map)
            else:
                users.set_profile_field(user_id, "prestige_map", prestige_map)
        except Exception:
            log.exception("Failed to persist prestige_map for user %s", user_id)

    except Exception:
        log.exception("persist_user_prestige failed for user %s", user_id)


def _ensure_hook_registered(core):
    """
    Ensure the UserDataManager.post_mutation_hook is set to schedule prestige persistence.
    Call this once when core is available (e.g., in build_roster_pages or when cog attaches).
    """
    users = ensure_user_manager(core)
    if not users:
        return
    if getattr(users, "_prestige_hook_registered", False):
        return

    def _hook(user_id: int):
        try:
            schedule_persist_user_prestige(core, user_id)
        except Exception:
            log.exception("Failed to schedule prestige persist for %s", user_id)

    users.post_mutation_hook = _hook
    users._prestige_hook_registered = True


def extract_entry_from_parsed(parsed: Dict[str, Any]) -> Dict[str, Any]:
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
            entry["ascended"] = int(parsed["ascended"][0])
    except Exception:
        entry["ascended"] = 0

    tags = parsed.get("tags") or []
    entry["tags"] = [str(t).lower() for t in tags if t]

    return entry


def validate_entry_for_add(entry: Dict[str, Any]) -> bool:
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
    pages: List[Any] = []
    try:
        users = ensure_user_manager(core)
        _ensure_hook_registered(core)

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
        profile = users.get_profile(user_id) if hasattr(users, "get_profile") else {}
        prestige_map = profile.get("prestige_map", {}) if isinstance(profile, dict) else {}

        class_map = {
            "all": "<:allclasses:748808348996075540>",
            "tech": "<:tech:748808546283683870>",
            "skill": "<:skill:748809095456227389>",
            "mutant": "<:mutant:748808841465954304>",
            "mystic": "<:mystic:748808953701335080>",
            "cosmic": "<:cosmic:748808707328180265>",
            "science": "<:science:748809185398882404>",
        }

        # Build entries with metadata, resolve prestige, sort by prestige desc, then render lines
        entries_with_meta: List[Dict[str, Any]] = []
        for entry in roster:
            try:
                e = dict(entry)
                e.setdefault("stars", int(e.get("rarity") or e.get("stars") or 0))
                e.setdefault("rank", int(e.get("rank") or 1))
                e.setdefault("sig", int(e.get("sig") or 0))
                e.setdefault("ascended", int(e.get("ascended") or 0))
                e.setdefault("tags", e.get("tags") or [])
                entries_with_meta.append(e)
            except Exception:
                continue

        def _resolve_prestige(e: Dict[str, Any]) -> Optional[int]:
            try:
                slug_for_lookup = str(e.get("champion") or "").strip()
                champ_obj = None
                if cache:
                    try:
                        champ_obj = cache.get_champion(slug_for_lookup)
                    except Exception:
                        champ_obj = None
                if champ_obj:
                    slug_for_lookup = (champ_obj.get("slug") or champ_obj.get("name") or slug_for_lookup).strip()

                raw_stars = int(e.get("stars") or e.get("rarity") or 6)
                raw_rank = int(e.get("rank") or 1)
                raw_sig = int(e.get("sig") or 0)
                raw_asc = int(e.get("ascended") or 0)
                if cache and hasattr(cache, "normalize_hargs_by_tier"):
                    try:
                        stars, rank, sig, asc = cache.normalize_hargs_by_tier(raw_stars, raw_rank, raw_sig, raw_asc)
                    except Exception:
                        stars, rank, sig, asc = raw_stars, raw_rank, raw_sig, raw_asc
                else:
                    stars, rank, sig, asc = raw_stars, raw_rank, raw_sig, raw_asc

                # Fast-path: check persisted prestige_map first
                key = f"{slug_for_lookup}|{stars}"
                if key in prestige_map and prestige_map.get(key) is not None:
                    return int(prestige_map.get(key))

                idx = getattr(core, "cacheindex", None) or getattr(cache, "index", None)
                if idx and slug_for_lookup:
                    try:
                        row = idx.get_prestige_row(slug_for_lookup, tier=stars, rank=rank, asc=asc)
                        if row:
                            sigs = row.get("sigs") or {}
                            if hasattr(cache, "smooth_sig_value"):
                                return cache.smooth_sig_value(sigs, sig)
                            else:
                                return cache._smooth_sig_value(sigs, sig)
                    except Exception:
                        pass

                if cache and hasattr(cache, "get_prestige_value"):
                    try:
                        return cache.get_prestige_value(slug_for_lookup, stars, rank, asc, sig)
                    except Exception:
                        return None
            except Exception:
                return None
            return None

        for e in entries_with_meta:
            try:
                p = _resolve_prestige(e)
                e["prestige"] = int(p) if isinstance(p, (int, float)) else None
            except Exception:
                e["prestige"] = None

        def _sort_key(e: Dict[str, Any]):
            p = e.get("prestige")
            if isinstance(p, (int, float)):
                return (0, -float(p), -int(e.get("stars", 0)), int(e.get("rank", 0)), -int(e.get("sig", 0)))
            return (1, -int(e.get("stars", 0)), int(e.get("rank", 0)), -int(e.get("sig", 0)))

        entries_with_meta.sort(key=_sort_key)

        lines: List[str] = []
        for entry in entries_with_meta:
            try:
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

                name = (champ.get("name") if champ else entry.get("champion")) or "Unknown"
                cls = (champ.get("class") if champ else "") or ""
                cls_emoji = class_map.get(cls.lower(), "<:allclasses:748808348996075540>")

                raw_stars = int(entry.get("rarity") or entry.get("stars") or 6)
                raw_rank = int(entry.get("rank") or 1)
                raw_sig = int(entry.get("sig") or 0)
                raw_asc = int(entry.get("ascended") or 0)
                if cache and hasattr(cache, "normalize_hargs_by_tier"):
                    try:
                        stars, rank, sig, asc = cache.normalize_hargs_by_tier(raw_stars, raw_rank, raw_sig, raw_asc)
                    except Exception:
                        stars, rank, sig, asc = raw_stars, raw_rank, raw_sig, raw_asc
                else:
                    stars, rank, sig, asc = raw_stars, raw_rank, raw_sig, raw_asc

                sig_icon = "★" if sig > 0 else "☆"
                star_display = f"{stars}{sig_icon}"
                sig_text = f" s{sig}"
                asc_text = f" A{asc}" if asc else ""

                prestige_val = entry.get("prestige")
                prestige_text = f" [{prestige_val}]" if isinstance(prestige_val, (int, float)) else ""

                line = f"{cls_emoji} {star_display} **{name}** r{rank}{sig_text}{asc_text}{prestige_text}"
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
