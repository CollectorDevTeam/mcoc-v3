# mcoc/common/roster.py
"""
Roster helpers: parsing, matching, prestige resolution, formatting and page construction.

This module provides a single canonical place for:
  - parsing free-form roster/hargs input into canonical entries
  - matching explicit hargs tokens against a user's roster
  - applying filters (rarity, rank, sig, ascended, tags, classes)
  - resolving prestige values using core.cache / cacheindex
  - formatting lines via format_champion_line
  - chunking lines into pages and building Embed embeds
  - returning either a list of embeds or a ready PagesMenu pager

Prefix handlers should be thin: resolve mention -> call make_roster_pager or get_roster_pages -> start pager.
"""

from typing import Any, Dict, List, Optional, Tuple
import re
import logging
import asyncio

from mcoc.common.componentsV2 import CDTEmbed, CDTPagesMenu

ROSTER_FOOTER = " | CollectorDevTeam"

from mcoc.common.hargs import parse_harg_list, parse_harg_token
from mcoc.common.formatters import format_champion_line

log = logging.getLogger("red.mcoc.roster")

# module-level debounce map
_persist_pending: Dict[int, asyncio.Task] = {}

# -----------------------------
# Utilities: user manager
# -----------------------------
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
# Persistence / prestige helpers
# -----------------------------
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


# -----------------------------
# Parsing helpers
# -----------------------------
def extract_entry_from_parsed(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a parsed token (from parse_harg_token or parse_hargs) into canonical entry:
      { champion: slug-or-name, rarity: int, rank: int, sig: int, ascended: int, tags: List[str], raw: str }
    """
    entry = {
        "champion": None,
        "rarity": None,
        "rank": None,
        "sig": 0,
        "tags": [],
        "ascended": 0,
        "raw": parsed.get("raw") if isinstance(parsed, dict) else None,
    }

    try:
        if parsed.get("raw") is not None and ("rarity" in parsed or "rank" in parsed or "ascended" in parsed or "sig" in parsed):
            entry["champion"] = parsed.get("champion") or None
            entry["rarity"] = int(parsed.get("rarity")) if parsed.get("rarity") is not None else None
            entry["rank"] = int(parsed.get("rank")) if parsed.get("rank") is not None else None
            entry["sig"] = int(parsed.get("sig") or 0)
            entry["ascended"] = int(parsed.get("ascended") or 0)
            tags = parsed.get("tags") or []
            entry["tags"] = [str(t).lower() for t in tags if t]
            return entry
    except Exception:
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
            entry["sig"] = int(parsed.get("sigs")[0])
    except Exception:
        entry["sig"] = 0

    try:
        if parsed.get("ascended"):
            entry["ascended"] = int(parsed.get("ascended")[0])
    except Exception:
        entry["ascended"] = 0

    tags = parsed.get("tags") or []
    entry["tags"] = [str(t).lower() for t in tags if t]

    return entry


def _normalize_candidate_name(name: str) -> str:
    s = (name or "").strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    return s


def _resolve_champion_slug(name: str, cache) -> str:
    """
    Resolve a champion name to a canonical slug using cache heuristics.
    Raises ValueError if not found.
    """
    if not name or not name.strip():
        raise ValueError("Empty champion name")

    cand = name.strip()
    norm = _normalize_candidate_name(cand)
    candidates = [norm, norm.replace("-", "")]

    if cache:
        for c in candidates:
            try:
                if cache.get_champion(c):
                    return c
            except Exception:
                pass

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

        try:
            all_champs = getattr(cache, "all_champions", None) or getattr(cache, "get_all_champions", None)
            for champ in (all_champs() or []):
                cname = (champ.get("name") or "").lower()
                if lname in cname or cname.startswith(lname):
                    return champ.get("slug")
        except Exception:
            pass

    raise ValueError(f"Champion not found for '{name}'")


def parse_roster_entries_from_input(text: str, cache) -> List[Dict[str, Any]]:
    """
    Parse free-form text into canonical roster entries.
    Returns list of dicts: { champion: slug, rarity, rank, sig, ascended, tags, raw }.
    Raises ValueError if nothing valid parsed.
    """
    if not text or not text.strip():
        raise ValueError("No input provided")

    try:
        parsed_tokens = parse_harg_list(text)
    except Exception:
        parsed_tokens = []

    if not parsed_tokens:
        parts = [p.strip() for p in re.split(r"[,\n]+", text) if p.strip()]
        if not parts:
            raise ValueError("No valid entries found")
        parsed_tokens = []
        for p in parts:
            try:
                parsed_tokens.append(parse_harg_token(p))
            except Exception:
                parsed_tokens.append({"raw": p, "champion": p})

    out: List[Dict[str, Any]] = []
    errors: List[str] = []
    for parsed in parsed_tokens:
        try:
            entry = extract_entry_from_parsed(parsed)
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


# -----------------------------
# Matching and filtering helpers
# -----------------------------
def match_explicit_entries_to_roster(roster: List[Dict[str, Any]], explicit_entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Given a user's roster and a list of explicit canonical entries (slug+rarity+rank...),
    return the subset of roster entries that match any explicit entry.
    Matching strategy: slug equality (case-insensitive) and rarity equality (stars/tier).
    """
    out: List[Dict[str, Any]] = []
    try:
        # build quick lookup by (slug, rarity)
        lookup: Dict[Tuple[str, int], List[Dict[str, Any]]] = {}
        for r in roster:
            try:
                slug = str(r.get("champion") or "").lower()
                rarity = int(r.get("rarity") or r.get("stars") or 6)
                lookup.setdefault((slug, rarity), []).append(r)
            except Exception:
                continue

        for ent in explicit_entries:
            try:
                slug = str(ent.get("champion") or "").lower()
                rarity = int(ent.get("rarity") or 6)
                matches = lookup.get((slug, rarity)) or []
                # if rank specified, prefer exact rank match
                if ent.get("rank") is not None:
                    rk = int(ent.get("rank"))
                    rk_matches = [m for m in matches if int(m.get("rank") or 1) == rk]
                    if rk_matches:
                        out.extend(rk_matches)
                        continue
                out.extend(matches)
            except Exception:
                continue
    except Exception:
        log.exception("match_explicit_entries_to_roster failed")
    return out


def filter_roster_entries(entries: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Apply filters to a list of canonical roster entries.
    Supported filters keys: rarities (list), ranks (list), sigs (list), ascended (list), tags (list), classes (list), name (str)
    Returns the filtered list (preserves original order).
    """
    if not filters:
        return entries

    out: List[Dict[str, Any]] = []
    rarities = set(filters.get("rarities") or [])
    ranks = set(filters.get("ranks") or [])
    sigs = set(filters.get("sigs") or [])
    ascended = set(filters.get("ascended") or [])
    tags = [t.lower() for t in (filters.get("tags") or [])]
    classes = [c.lower() for c in (filters.get("classes") or [])]
    name_filter = (filters.get("name") or "").lower() if filters.get("name") else None

    for e in entries:
        try:
            # rarity
            r = int(e.get("rarity") or e.get("stars") or 6)
            if rarities and r not in rarities:
                continue
            # rank
            rk = int(e.get("rank") or 1)
            if ranks and rk not in ranks:
                continue
            # sig
            sg = int(e.get("sig") or 0)
            if sigs and sg not in sigs:
                continue
            # ascended
            asc = int(e.get("ascended") or 0)
            if ascended and asc not in ascended:
                continue
            # tags
            if tags:
                entry_tags = [t.lower() for t in (e.get("tags") or [])]
                ok = True
                for tf in tags:
                    if not any(tf in et for et in entry_tags):
                        ok = False
                        break
                if not ok:
                    continue
            # classes: if provided, entry should include class in its champion metadata (caller may attach)
            if classes:
                champ_class = (e.get("class") or "").lower()
                if champ_class and champ_class not in classes:
                    continue
            # name filter: allow partial match against champion slug/name
            if name_filter:
                cand = (str(e.get("champion") or "") + " " + str(e.get("raw") or "")).lower()
                if name_filter not in cand:
                    continue

            out.append(e)
        except Exception:
            continue

    return out


# -----------------------------
# Page building and embed helpers
# -----------------------------
async def _resolve_prestige_for_entry(core: Any, entry: Dict[str, Any], prestige_map: Dict[str, Any]) -> Optional[int]:
    """
    Resolve prestige for a single entry using prestige_map, core.cacheindex or core.cache.
    Returns integer prestige or None.
    """
    try:
        cache = getattr(core, "cache", None)
        idx = getattr(core, "cacheindex", None) or (getattr(cache, "index", None) if cache else None)
        slug = str(entry.get("champion") or "").strip()
        raw_stars = int(entry.get("rarity") or entry.get("stars") or 6)
        raw_rank = int(entry.get("rank") or 1)
        raw_sig = int(entry.get("sig") or 0)
        raw_asc = int(entry.get("ascended") or 0)

        # normalize via cache if available
        if cache and hasattr(cache, "normalize_hargs_by_tier"):
            try:
                stars, rank, sig, asc = cache.normalize_hargs_by_tier(raw_stars, raw_rank, raw_sig, raw_asc)
            except Exception:
                stars, rank, sig, asc = raw_stars, raw_rank, raw_sig, raw_asc
        else:
            stars, rank, sig, asc = raw_stars, raw_rank, raw_sig, raw_asc

        # fast path: persisted prestige_map
        key = f"{slug}|{stars}"
        if key in (prestige_map or {}) and prestige_map.get(key) is not None:
            try:
                return int(prestige_map.get(key))
            except Exception:
                pass

        # try cacheindex
        if idx and slug:
            try:
                row = idx.get_prestige_row(slug, tier=stars, rank=rank, asc=asc)
                if row:
                    sigs = row.get("sigs") or {}
                    if cache and hasattr(cache, "smooth_sig_value"):
                        return cache.smooth_sig_value(sigs, raw_sig)
                    else:
                        return cache._smooth_sig_value(sigs, raw_sig)
            except Exception:
                pass

        # fallback to cache.get_prestige_value
        if cache and hasattr(cache, "get_prestige_value"):
            try:
                return cache.get_prestige_value(slug, stars, rank, asc, raw_sig)
            except Exception:
                pass

    except Exception:
        log.exception("Failed to resolve prestige for entry %s", entry)
    return None


async def build_roster_pages(core: Any, ctx_or_author: Any, parsed_filters: Optional[Dict[str, Any]] = None, *, lines_per_page: int = 15, char_limit: int = 1800) -> List[Any]:
    """
    Build a list of Embed pages for a user's roster.

    Parameters:
      - core: bot/core object (used to access cache, cacheindex, users)
      - ctx_or_author: Context or author-like object used for branding (author name/avatar)
      - parsed_filters: dict returned by parse_query or a shape containing 'explicit_entries' and other filters
      - lines_per_page: number of lines per embed page
      - char_limit: approximate character limit per embed description

    Returns:
      - List of Embed embed objects (normal path) or list of dict fallbacks on catastrophic failure.
    """
    # normalize ctx_or_author -> author_for_embed, user_id
    author_for_embed = None
    user_id = None
    try:
        if ctx_or_author is None:
            author_for_embed = None
            user_id = None
        elif hasattr(ctx_or_author, "author"):
            author_for_embed = ctx_or_author.author
            user_id = getattr(ctx_or_author.author, "id", None)
        else:
            author_for_embed = ctx_or_author
            user_id = getattr(ctx_or_author, "id", None)
    except Exception:
        author_for_embed = None
        user_id = None

    if user_id is None:
        raise ValueError("build_roster_pages requires ctx_or_author with an .id attribute")

    try:
        users = ensure_user_manager(core)
        _ensure_hook_registered(core)

        # load roster (sync or async)
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
        profile = users.get_profile(user_id) if users and hasattr(users, "get_profile") else {}
        prestige_map = profile.get("prestige_map", {}) if isinstance(profile, dict) else {}

        # Normalize roster entries into canonical shape
        entries_with_meta: List[Dict[str, Any]] = []
        for entry in roster:
            try:
                e = dict(entry)
                e.setdefault("stars", int(e.get("rarity") or e.get("stars") or 0))
                e.setdefault("rarity", int(e.get("rarity") or e.get("stars") or 0))
                e.setdefault("rank", int(e.get("rank") or 1))
                e.setdefault("sig", int(e.get("sig") or 0))
                e.setdefault("ascended", int(e.get("ascended") or 0))
                e.setdefault("tags", e.get("tags") or [])
                entries_with_meta.append(e)
            except Exception:
                continue

        # If explicit entries provided, prefer matching roster entries first
        explicit = parsed.get("explicit_entries") if isinstance(parsed, dict) else None
        filtered_entries: List[Dict[str, Any]] = []
        if explicit:
            try:
                matched = match_explicit_entries_to_roster(entries_with_meta, explicit)
                if matched:
                    filtered_entries = matched
                else:
                    # No roster matches: present explicit entries as standalone display entries
                    for ent in explicit:
                        try:
                            display = {
                                "champion": ent.get("champion"),
                                "rarity": int(ent.get("rarity") or 6),
                                "rank": int(ent.get("rank") or 1),
                                "sig": int(ent.get("sig") or 0),
                                "ascended": int(ent.get("ascended") or 0),
                                "tags": ent.get("tags") or [],
                                "raw": ent.get("raw") or str(ent.get("champion") or ""),
                                "prestige": None,
                            }
                            filtered_entries.append(display)
                        except Exception:
                            continue
            except Exception:
                filtered_entries = []
        else:
            # No explicit entries: apply filters to full roster
            filters = parsed if isinstance(parsed, dict) else {}
            filtered_entries = filter_roster_entries(entries_with_meta, filters)

        # Resolve prestige for filtered entries (best-effort)
        for e in filtered_entries:
            try:
                p = await _resolve_prestige_for_entry(core, e, prestige_map)
                e["prestige"] = int(p) if isinstance(p, (int, float)) else None
            except Exception:
                e["prestige"] = None

        # Sort filtered entries: prestige-aware, then tier/rank/sig
        def _sort_key(e: Dict[str, Any]):
            p = e.get("prestige")
            if isinstance(p, (int, float)):
                return (0, -float(p), -int(e.get("rarity") or e.get("stars") or 0), int(e.get("rank") or 0), -int(e.get("sig") or 0))
            return (1, -int(e.get("rarity") or e.get("stars") or 0), int(e.get("rank") or 0), -int(e.get("sig") or 0))

        try:
            filtered_entries.sort(key=_sort_key)
        except Exception:
            pass

        # Build formatted lines using format_champion_line (centralized formatting)
        lines: List[str] = []
        for entry in filtered_entries:
            try:
                champ_obj = None
                if cache:
                    try:
                        champ_obj = cache.get_champion(entry.get("champion"))
                    except Exception:
                        champ_obj = None
                # attach class if available from champ_obj for filtering/formatting
                if champ_obj and not entry.get("class"):
                    try:
                        entry["class"] = champ_obj.get("class")
                    except Exception:
                        pass
                try:
                    line = format_champion_line(champ_obj, entry, include_prestige=entry.get("prestige"))
                except TypeError:
                    # backward-compatible fallback if formatter doesn't accept include_prestige kw
                    line = format_champion_line(champ_obj, entry)
                lines.append(line)
            except Exception:
                continue

        # If no lines, return a single "no matches" embed
        if not lines:
            try:
                emb = CDTEmbed.embed(author_for_embed, title="Roster", description="No champions match the filters.", footer_text=f"Page 1 of 1{ROSTER_FOOTER}")
                return [emb]
            except Exception:
                return [{"title": "Roster", "description": "No champions match the filters.", "footer": {"text": f"Page 1 of 1{ROSTER_FOOTER}"}}]

        # Chunk lines into pages
        page_texts: List[str] = []
        cur: List[str] = []
        cur_len = 0
        for line in lines:
            if len(cur) >= lines_per_page or (cur_len + len(line) + 1) > char_limit:
                page_texts.append("\n".join(cur))
                cur = []
                cur_len = 0
            cur.append(line)
            cur_len += len(line) + 1
        if cur:
            page_texts.append("\n".join(cur))

        # Build title and convert page_texts into Embed pages
        title_count = len(filtered_entries)
        prestige_vals = [int(x["prestige"]) for x in filtered_entries if isinstance(x.get("prestige"), (int, float))]
        title_prestige = int(round(sum(prestige_vals) / len(prestige_vals))) if prestige_vals else "N/A"
        roster_title = f"Roster ({title_count} champions) [{title_prestige}]"

        embed_pages: List[Any] = []
        try:
            for i, ptext in enumerate(page_texts):
                footer = f"Page {i+1} of {len(page_texts)}{ROSTER_FOOTER}"
                emb = CDTEmbed.embed(author_for_embed, title=roster_title, description=ptext, footer_text=footer)
                try:
                    CDTEmbed.set_footer(author_for_embed, emb, text=footer)
                except Exception:
                    pass
                embed_pages.append(emb)
            return embed_pages
        except Exception:
            # fallback to dict pages
            out = []
            for i, ptext in enumerate(page_texts):
                out.append({"title": roster_title, "description": ptext, "footer": {"text": f"Page {i+1} of {len(page_texts)}{ROSTER_FOOTER}"}})
            return out

    except Exception:
        log.exception("Failed to build roster pages")
        return []


async def get_roster_pages(core: Any, ctx_or_author: Any, parsed_filters: Optional[Dict[str, Any]] = None) -> List[Any]:
    """
    Public wrapper that guarantees embed objects where possible.
    Returns List[Embed] or dict fallbacks.
    """
    pages = await build_roster_pages(core, ctx_or_author, parsed_filters=parsed_filters)
    out: List[Any] = []
    for p in pages:
        if isinstance(p, dict):
            try:
                emb = CDTEmbed.embed(ctx_or_author, title=p.get("title"), description=p.get("description"), footer_text=(p.get("footer") or {}).get("text"))
                out.append(emb)
            except Exception:
                out.append(p)
        else:
            out.append(p)
    return out


# -----------------------------
# Pager convenience
# -----------------------------
async def make_roster_pager(core: Any, ctx_or_author: Any, *, raw_input: Optional[str] = None, target_member: Optional[Any] = None, parsed_filters: Optional[Dict[str, Any]] = None, author_for_controls: Optional[Any] = None) -> Optional[CDTPagesMenu]:
    """
    Convenience wrapper that builds pages and returns a ready PagesMenu with brand buttons merged.

    Parameters:
      - core: bot/core object
      - ctx_or_author: Context or author-like object (used for branding)
      - raw_input: optional raw input string (not used if parsed_filters provided)
      - target_member: optional explicit target member (if different from ctx_or_author)
      - parsed_filters: optional parsed filters (preferred)
      - author_for_controls: who should control the pager (defaults to ctx_or_author.author or ctx_or_author)

    Returns:
      - PagesMenu instance ready to start, or None on failure.
    """
    try:
        # If parsed_filters not provided, attempt to parse raw_input using query parser if available
        parsed = parsed_filters or {}
        if not parsed and raw_input:
            try:
                from ..query_parser import parse_query
                cache = getattr(core, "cache", None)
                entries, filters = parse_query(raw_input, cache=cache)
                parsed = {}
                if entries:
                    parsed["explicit_entries"] = entries
                if isinstance(filters, dict):
                    parsed.update(filters)
            except Exception:
                parsed = {}

        # Determine the target for pages: prefer explicit target_member, else ctx_or_author
        target = target_member or ctx_or_author

        pages = await get_roster_pages(core, target, parsed_filters=parsed)
        if not pages:
            return None

        # Instantiate pager with canonical constructor
        try:
            pager = CDTPagesMenu(pages, author=(author_for_controls or (ctx_or_author.author if hasattr(ctx_or_author, "author") else ctx_or_author)))
        except TypeError:
            try:
                pager = CDTPagesMenu(pages, ctx_or_author)
            except TypeError:
                try:
                    pager = CDTPagesMenu(pages)
                    if hasattr(pager, "author"):
                        try:
                            pager.author = (author_for_controls or (ctx_or_author.author if hasattr(ctx_or_author, "author") else ctx_or_author))
                        except Exception:
                            pass
                except Exception:
                    return None

        # Merge brand buttons into pager view if possible
        try:
            brand_view = CDTEmbed.brand_view()
            if hasattr(pager, "add_item"):
                for item in getattr(brand_view, "children", []):
                    try:
                        pager.add_item(item)
                    except Exception:
                        continue
        except Exception:
            pass

        return pager
    except Exception:
        log.exception("make_roster_pager failed")
        return None


# -----------------------------
# Footer helper
# -----------------------------
def add_page_footers(pages: List[Any], author_for_embed: Any = None) -> List[Any]:
    """
    Ensure each embed page has a footer with page numbering.
    Accepts embed objects or dict fallbacks.
    """
    out: List[Any] = []
    total = len(pages)
    for i, p in enumerate(pages):
        try:
            if isinstance(p, dict):
                emb = CDTEmbed.embed(author_for_embed, title=p.get("title", "Roster"), description=p.get("description", ""))
            else:
                emb = p
            try:
                base = emb.footer.text if getattr(emb, "footer", None) and getattr(emb.footer, "text", None) else ""
                footer_text = f"{base} • Page {i+1} of {total}" if base else f"Page {i+1} of {total}"
                footer_text += f"{ROSTER_FOOTER}"
                CDTEmbed.set_footer(author_for_embed, emb, text=footer_text)
            except Exception:
                try:
                    CDTEmbed.set_footer(author_for_embed, emb, text=f"Page {i+1} of {total}{ROSTER_FOOTER}")
                except Exception:
                    pass
            out.append(emb)
        except Exception:
            out.append(p)
    return out
