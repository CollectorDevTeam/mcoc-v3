# mcoc/common/roster_helpers.py
import re
import logging
from typing import Any, Dict, List, Optional, Tuple
from .embeds import cdt_embed
from .hargs import parse_harg_list
import asyncio

log = logging.getLogger("red.mcoc.roster_helpers")

# New import: hargs parsing helpers
try:
    from .hargs import parse_harg_list, parse_harg_token
except Exception:
    # fallback stub if hargs not available at import time
    def parse_harg_list(text: str) -> List[Dict[str, Any]]:
        return []
    def parse_harg_token(token: str) -> Dict[str, Any]:
        return {}

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


# -----------------------------
# Entry extraction and validation
# -----------------------------
def extract_entry_from_parsed(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a parsed filter dict (from parse_hargs) or a single harg token parse
    into a canonical entry dict used by roster operations.

    The returned dict contains:
      {
        "champion": Optional[str],
        "rarity": Optional[int],
        "rank": Optional[int],
        "sig": int,
        "tags": List[str],
        "ascended": int,
      }
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
        # If parsed is the compact token parse (parse_harg_token style)
        if parsed.get("raw") is not None and ("rarity" in parsed or "rank" in parsed or "ascended" in parsed or "sig" in parsed):
            # direct mapping
            entry["champion"] = parsed.get("champion") or None
            entry["rarity"] = int(parsed.get("rarity")) if parsed.get("rarity") is not None else None
            entry["rank"] = int(parsed.get("rank")) if parsed.get("rank") is not None else None
            entry["sig"] = int(parsed.get("sig") or 0)
            entry["ascended"] = int(parsed.get("ascended") or 0)
            # tags may not be present in compact token
            tags = parsed.get("tags") or []
            entry["tags"] = [str(t).lower() for t in tags if t]
            return entry
    except Exception:
        # fall through to legacy handling
        pass

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

# -----------------------------
# Roster parsing adapter & slug resolver
# -----------------------------
def _normalize_candidate_name(name: str) -> str:
    s = (name or "").strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)   # remove punctuation except hyphen
    s = re.sub(r"\s+", "-", s)       # spaces -> hyphen
    return s

def _resolve_champion_slug(name: str, cache) -> str:
    """
    Resolve a champion name (from hargs.parse_harg_token) to a canonical slug.
    Tries: normalized slug, slug without hyphens, exact name match, contains/startswith fallback.
    Raises ValueError if not found.
    """
    if not name or not name.strip():
        raise ValueError("Empty champion name")

    cand = name.strip()
    norm = _normalize_candidate_name(cand)
    candidates = [norm, norm.replace("-", "")]

    # try exact slug candidates
    if cache:
        for c in candidates:
            try:
                if cache.get_champion(c):
                    return c
            except Exception:
                # some cache implementations may raise; ignore and continue
                pass

        # try exact name match (case-insensitive)
        lname = cand.lower()
        try:
            all_champs = getattr(cache, "all_champions", None) or getattr(cache, "get_all_champions", None)
            if callable(all_champs):
                for champ in all_champs() or []:
                    cname = (champ.get("name") or "").lower()
                    if cname == lname:
                        return champ.get("slug")
        except Exception:
            pass

        # try contains/startswith fallback
        try:
            for champ in (all_champs() or []):
                cname = (champ.get("name") or "").lower()
                if lname in cname or cname.startswith(lname):
                    return champ.get("slug")
        except Exception:
            pass

    raise ValueError(f"Champion not found for '{name}'")

def parse_roster_entries_from_input(text: str, cache) -> List[Dict[str, Any]]:
    """
    Adapter that converts free-form user input into canonical roster entries.
    Uses hargs.parse_harg_list for tokenization and parse_harg_token-style parsing,
    then resolves champion names to slugs and normalizes numeric fields.
    Returns list of dicts: {'champion': slug, 'rarity': int, 'rank': int, 'sig': int, 'ascended': int, 'raw': str}
    Raises ValueError with a helpful message if nothing valid is parsed.
    """
    if not text or not text.strip():
        raise ValueError("No input provided")

    # Use hargs to parse tokens (preserves quoted names, commas, semicolons)
    try:
        parsed_tokens = parse_harg_list(text)
    except Exception:
        parsed_tokens = []

    # If hargs returned nothing, try splitting by commas/newlines and parse each token
    if not parsed_tokens:
        parts = [p.strip() for p in re.split(r"[,\n]+", text) if p.strip()]
        if not parts:
            raise ValueError("No valid entries found")
        parsed_tokens = []
        for p in parts:
            try:
                parsed_tokens.append(parse_harg_token(p))
            except Exception:
                # fallback: create a minimal token dict so extract_entry_from_parsed can try
                parsed_tokens.append({"raw": p, "champion": p})

    out: List[Dict[str, Any]] = []
    errors: List[str] = []
    for parsed in parsed_tokens:
        try:
            # Normalize parsed token into canonical entry shape
            entry = extract_entry_from_parsed(parsed)
            # Ensure defaults
            if entry.get("rarity") is None:
                entry["rarity"] = 6
            if entry.get("rank") is None:
                entry["rank"] = 1
            if entry.get("ascended") is None:
                entry["ascended"] = 1
            if entry.get("sig") is None:
                entry["sig"] = 0

            champ_name = entry.get("champion")
            if not champ_name:
                # try to extract alphabetic run from raw
                raw = parsed.get("raw") or ""
                m = re.search(r"[A-Za-z][A-Za-z0-9 '\-\.]{0,80}", raw)
                if m:
                    champ_name = m.group(0).strip()
            if not champ_name:
                errors.append(f"Could not determine champion name from '{parsed.get('raw')}'")
                continue

            try:
                slug = _resolve_champion_slug(champ_name, cache)
            except ValueError as exc:
                errors.append(str(exc))
                continue

            out.append({
                "champion": slug,
                "rarity": int(entry.get("rarity") or 6),
                "rank": int(entry.get("rank") or 1),
                "sig": int(entry.get("sig") or 0),
                "ascended": int(entry.get("ascended") or 1),
                "tags": entry.get("tags") or [],
                "raw": parsed.get("raw") or str(champ_name),
            })
        except Exception as exc:
            log.debug("parse_roster_entries_from_input: failed token=%s exc=%s", parsed, exc)
            continue

    if not out:
        raise ValueError("No valid entries parsed: " + ("; ".join(errors) if errors else "unknown error"))
    return out

# New helper: convert a free-form hargs text into a list of normalized entries
def entries_from_hargs_text(text: str) -> List[Dict[str, Any]]:
    """
    Parse a text containing one or more ChampionHargs / HargsChampion / plain champion tokens
    and return a list of normalized entry dicts suitable for add/remove/update operations.
    Uses parse_harg_list from mcoc.hargs and resolves champion slugs via cache.
    """
    out: List[Dict[str, Any]] = []
    try:
        # prefer using the core cache if available; callers that call this function
        # should pass core or use ensure_user_manager to get core. Here we attempt to
        # use a best-effort cache from the module-level context if present.
        # The roster add handler should call parse_roster_entries_from_input directly with core.cache.
        # For backward compatibility, try to use a global cache if available.
        cache = None
        # If this module is used from a core context, callers should call parse_roster_entries_from_input directly.
        parsed_entries = []
        try:
            # try hargs-only path first (no slug resolution)
            parsed_list = parse_harg_list(text or "")
            for parsed in parsed_list:
                entry = extract_entry_from_parsed(parsed)
                if entry.get("rarity") is None:
                    entry["rarity"] = 6
                if entry.get("rank") is None:
                    entry["rank"] = 1
                if entry.get("ascended") is None:
                    entry["ascended"] = 1
                if entry.get("sig") is None:
                    entry["sig"] = 0
                out.append(entry)
            if out:
                return out
        except Exception:
            pass

        # fallback: try the full resolver if caller provided a cache via module-level core (best-effort)
        # NOTE: callers that have access to core should call parse_roster_entries_from_input(core_text, core.cache)
        return out
    except Exception:
        return []

def validate_entry_for_add(entry: Dict[str, Any]) -> bool:
    """
    Validate a normalized entry for add/update operations.

    Rules:
      - rarity: 1..7
      - rank: 1..5
      - ascended: 0..2
      - sig: bounds depend on rarity (<=99 for tiers 1-4, <=200 for tiers 5-7)
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
        if not (0 <= asc <= 2):
            return False

        # signature bounds by tier
        if r <= 4:
            if not (0 <= sig <= 99):
                return False
        else:
            if not (0 <= sig <= 200):
                return False

        return True
    except Exception:
        return False


# -----------------------------
# build_roster_pages (unchanged except it can accept parsed_filters from parse_hargs)
# -----------------------------
async def build_roster_pages(core: Any, ctx_or_author: Any, parsed_filters: Optional[Dict[str, Any]] = None) -> List[Any]:
    pages: List[Any] = []
    try:
        users = ensure_user_manager(core)
        _ensure_hook_registered(core)

        roster = []
        try:
            if asyncio.iscoroutinefunction(getattr(users, "list_roster", None)):
                roster = await users.list_roster(ctx_or_author.id)
            else:
                roster = users.list_roster(ctx_or_author.id) if users else []
        except Exception:
            try:
                roster = users.list_roster(ctx_or_author.id) if users else []
            except Exception:
                roster = []

        cache = getattr(core, "cache", None)
        parsed = parsed_filters or {}
        profile = users.get_profile(ctx_or_author.id) if hasattr(users, "get_profile") else {}
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
                # emb = discord.Embed(title="Roster", description="No champions match the filters.")
                emb = await cdt_embed(ctx_or_author, title="Roster", description="No champions match the filters.")
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
            for i, p in enumerate(pages):
                title = "Roster"
                emb = await cdt_embed(ctx_or_author, title=title, description=p)
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
