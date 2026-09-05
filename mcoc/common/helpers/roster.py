# Path: mcoc/common/helpers/roster.py
# File-Version: 1.0
# File-Id: 8d5385a6-91c5-42a1-ad2f-fb87099afdc5
# Purpose: Provide helpers for managing and displaying user rosters, including parsing, matching, prestige resolution, and page construction.
# Public-API: ensure_user_manager, _ensure_hook_registered, persist_user_prestige
# Last-Modified: 2026-09-01
# Changelog:
#   1.0 2026-09-01  Initial stabilized API header
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

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
import re
import logging
import asyncio

from mcoc.common.components.componentsV2 import CDTEmbed, CDTPagesMenu

if TYPE_CHECKING:
    from discord import Interaction
    from discord.ui import View, Button
else:
    Interaction = Any
    View = Any
    Button = Any

try:
    import discord
except Exception:  # pragma: no cover - optional runtime dependency
    discord = None

if discord is not None:
    try:
        from discord import Interaction as _DiscordInteraction
        from discord.ui import View as _DiscordView, Button as _DiscordButton
        Interaction = _DiscordInteraction
        View = _DiscordView
        Button = _DiscordButton
    except Exception:  # pragma: no cover - optional runtime dependency
        pass

ROSTER_FOOTER = " | CollectorDevTeam"

from mcoc.common.utilities.hargs import parse_harg_list, parse_harg_token
from mcoc.common.utilities.formatters import format_champion_line

# new imports for userdata/types interop
from mcoc.common.helpers import userdata as userdata_module
from mcoc.common.helpers.types import (
    CLASS_EMOJI,
    Champion,
    champion_from_dict,
    get_champion_tier_limits,
    normalize_champion_progression,
    UserAccount,
    useraccount_from_userdata,
)

log = logging.getLogger("red.mcoc.roster")


@dataclass(frozen=True)
class RosterOperationSpec:
    name: str
    title: str
    empty_message: str
    summary: str
    fields: Tuple[str, ...]


ROSTER_OPERATION_SPECS: Dict[str, RosterOperationSpec] = {
    "add": RosterOperationSpec(
        name="add",
        title="Roster Add",
        empty_message="All available champions for that slice are already in your roster.",
        summary="Eligible champions you do not currently own at the selected tier.",
        fields=("rank", "sig", "ascended"),
    ),
    "update": RosterOperationSpec(
        name="update",
        title="Roster Update",
        empty_message="No roster entries are available to update.",
        summary="Owned roster entries that can be adjusted with the shared tier limits.",
        fields=("rank", "sig", "ascended"),
    ),
    "rankup": RosterOperationSpec(
        name="rankup",
        title="Roster Rank Up",
        empty_message="No roster entries are eligible for a rank up.",
        summary="Owned roster entries that are below the maximum rank for their tier.",
        fields=("rank",),
    ),
    "dupe": RosterOperationSpec(
        name="dupe",
        title="Roster Dupe",
        empty_message="No roster entries are eligible for a sig increase.",
        summary="Owned roster entries that are below the maximum signature level for their tier.",
        fields=("sig",),
    ),
    "ascend": RosterOperationSpec(
        name="ascend",
        title="Roster Ascend",
        empty_message="No roster entries are eligible for ascension.",
        summary="Owned roster entries that are below the maximum ascension level for their tier.",
        fields=("ascended",),
    ),
}

ROSTER_OPERATION_CLASSES = ["cosmic", "tech", "mutant", "skill", "science", "mystic"]
ROSTER_FLOW_TIMEOUT = 600.0
ROSTER_SELECTION_LIMIT = 75

# module-level debounce map
_persist_pending: Dict[int, asyncio.Task] = {}

# -----------------------------
# Utilities: user manager
# -----------------------------
def ensure_user_manager(core_or_bot) -> Any:
    """
    Return a UserDataManager instance.
    Prefer an existing manager on the core (core.users or core.user_manager),
    otherwise create/return the shared module-level UserDataManager.
    """
    try:
        if core_or_bot is None:
            return userdata_module.get_user_manager()
        um = getattr(core_or_bot, "users", None) or getattr(core_or_bot, "user_manager", None)
        if um:
            return um
    except Exception:
        log.debug("ensure_user_manager: parent lookup failed", exc_info=True)

    try:
        return userdata_module.get_user_manager()
    except Exception:
        log.exception("Failed to create/get UserDataManager")
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
def validate_entry_for_add(entry: Dict[str, Any]) -> bool:
    """Return True when an entry contains the minimum fields needed to add a roster record."""
    if not isinstance(entry, dict):
        return False
    rarity = entry.get("rarity")
    rank = entry.get("rank")
    if rarity is None or rank is None:
        return False
    try:
        return int(rarity) > 0 and int(rank) > 0
    except Exception:
        return False


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
                champion = cache.get_champion(c)
                if isinstance(champion, dict):
                    return str(champion.get("id") or champion.get("slug") or c).strip().lower()
            except Exception:
                pass

        lname = cand.lower()
        try:
            all_champs = getattr(cache, "all_champions", None) or getattr(cache, "get_all_champions", None)
            if callable(all_champs):
                for champ in all_champs() or []:
                    cname = (champ.get("name") or "").lower()
                    if cname == lname:
                        return str(champ.get("id") or champ.get("slug") or lname).strip().lower()
        except Exception:
            pass

        try:
            all_champs = getattr(cache, "all_champions", None) or getattr(cache, "get_all_champions", None)
            for champ in (all_champs() or []):
                cname = (champ.get("name") or "").lower()
                if lname in cname or cname.startswith(lname):
                    return str(champ.get("id") or champ.get("slug") or lname).strip().lower()
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
                entry["ascended"] = 0
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

            rarity, rank, sig, ascended = normalize_champion_progression(
                entry.get("rarity") or 6,
                entry.get("rank") or 1,
                entry.get("sig") or 0,
                entry.get("ascended") if entry.get("ascended") is not None else 0,
            )

            out.append({
                "champion": slug,
                "rarity": rarity,
                "rank": rank,
                "sig": sig,
                "ascended": ascended,
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

    def _normalize_token(value: Any) -> str:
        return "".join(ch for ch in str(value or "").lower() if ch.isalnum())

    def _field_tokens(raw: Any) -> List[str]:
        flattened: List[str] = []
        if raw is None:
            return flattened
        if isinstance(raw, dict):
            for key in ("name", "id", "slug", "type", "class", "class_name", "tier", "title", "value"):
                if key in raw:
                    flattened.extend(_field_tokens(raw[key]))
            return flattened
        if isinstance(raw, (list, tuple, set)):
            for item in raw:
                flattened.extend(_field_tokens(item))
            return flattened
        token = _normalize_token(raw)
        if token:
            flattened.append(token)
        return flattened

    out: List[Dict[str, Any]] = []
    rarities = set(filters.get("rarities") or [])
    ranks = set(filters.get("ranks") or [])
    sigs = set(filters.get("sigs") or [])
    ascended = set(filters.get("ascended") or [])
    tags = [str(t).lower() for t in (filters.get("tags") or [])]
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
            # tags / immunities: every requested token must be present in roster metadata
            if tags:
                entry_tokens: List[str] = []
                for field in ("class", "class_name", "tier", "tags", "abilities", "immunities", "inflicts"):
                    entry_tokens.extend(_field_tokens(e.get(field)))
                entry_tokens = [t for t in entry_tokens if t]
                for tf in tags:
                    tf_norm = _normalize_token(tf)
                    if not tf_norm:
                        continue
                    ok = any(tf_norm == et or tf_norm in et or et in tf_norm for et in entry_tokens)
                    if not ok:
                        break
                else:
                    pass
                if not all(any(_normalize_token(tf) == et or _normalize_token(tf) in et or et in _normalize_token(tf) for et in entry_tokens) for tf in tags):
                    continue
            # classes: if provided, entry should include class in its champion metadata (caller may attach)
            if classes:
                champ_class = (e.get("class") or "").lower()
                if not champ_class:
                    # class tokens can be supplied as tag-style filters (#skill) and should still match
                    class_candidates = [str(t).lower() for t in (e.get("tags") or [])]
                    if not any(cls in class_candidates for cls in classes):
                        continue
                elif champ_class not in classes:
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


def get_roster_entry_limits(entry: Dict[str, Any]) -> Any:
    """Return tier limits for a roster entry using its rarity/stars field."""
    return get_champion_tier_limits(entry.get("rarity") or entry.get("stars") or 7)


def _resolve_author_and_user_id(ctx_or_author: Any) -> Tuple[Any, Optional[int]]:
    author_for_embed = None
    user_id = None
    try:
        if ctx_or_author is None:
            return None, None
        if hasattr(ctx_or_author, "author"):
            author_for_embed = ctx_or_author.author
            user_id = getattr(ctx_or_author.author, "id", None)
        else:
            author_for_embed = ctx_or_author
            user_id = getattr(ctx_or_author, "id", None)
    except Exception:
        return None, None
    return author_for_embed, user_id


def _canonicalize_roster_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    rarity, rank, sig, ascended = normalize_champion_progression(
        entry.get("rarity") or entry.get("stars") or 7,
        entry.get("rank") or 1,
        entry.get("sig") or 0,
        entry.get("ascended") or 0,
    )
    canonical = dict(entry)
    canonical["rarity"] = rarity
    canonical["stars"] = rarity
    canonical["rank"] = rank
    canonical["sig"] = sig
    canonical["ascended"] = ascended
    canonical.setdefault("tags", canonical.get("tags") or [])
    return canonical


def _matches_class_filter(entry: Dict[str, Any], classes: List[str]) -> bool:
    if not classes:
        return True
    champ_class = str(entry.get("class") or "").lower()
    return champ_class in classes if champ_class else False


def _matches_roster_filters(entry: Dict[str, Any], filters: Optional[Dict[str, Any]]) -> bool:
    if not filters:
        return True
    return bool(filter_roster_entries([entry], filters))


def _operation_entry_is_eligible(entry: Dict[str, Any], operation: str) -> bool:
    limits = get_roster_entry_limits(entry)
    if operation == "update":
        return True
    if operation == "rankup":
        return int(entry.get("rank") or 0) < limits.max_rank
    if operation == "dupe":
        return int(entry.get("sig") or 0) < limits.max_sig
    if operation == "ascend":
        return int(entry.get("ascended") or 0) < limits.max_ascended
    return False


def _format_operation_line(cache: Any, entry: Dict[str, Any], operation: str) -> str:
    champ_obj = None
    slug = entry.get("champion")
    if cache and slug:
        try:
            raw_champ = cache.get_champion(slug)
            if isinstance(raw_champ, dict):
                champ_obj = champion_from_dict(raw_champ)
            elif isinstance(raw_champ, Champion):
                champ_obj = raw_champ
        except Exception:
            champ_obj = None

    if champ_obj and not entry.get("class"):
        try:
            entry["class"] = champ_obj.class_name
        except Exception:
            pass

    try:
        base = format_champion_line(champ_obj, entry, include_prestige=entry.get("prestige"))
    except TypeError:
        base = format_champion_line(champ_obj, entry)

    if operation == "add":
        return base
    if operation == "update":
        return base
    limits = get_roster_entry_limits(entry)
    if operation == "rankup":
        return f"{base} | next rank {min(int(entry.get('rank') or 1) + 1, limits.max_rank)}/{limits.max_rank}"
    if operation == "dupe":
        return f"{base} | sig {int(entry.get('sig') or 0)}/{limits.max_sig}"
    if operation == "ascend":
        return f"{base} | asc {int(entry.get('ascended') or 0)}/{limits.max_ascended}"
    return base


def _build_operation_overview_pages(ctx_or_author: Any, operation: str, tier_counts: Dict[int, int]) -> List[Any]:
    spec = ROSTER_OPERATION_SPECS[operation]
    lines = [spec.summary, "", "Eligible counts by tier:"]
    for tier in sorted(tier_counts):
        lines.append(f"{tier}★: {tier_counts[tier]}")
    desc = "\n".join(lines)
    try:
        return [CDTEmbed.embed(ctx_or_author, title=spec.title, description=desc, footer_text=f"Page 1 of 1{ROSTER_FOOTER}")]
    except Exception:
        return [{"title": spec.title, "description": desc, "footer": {"text": f"Page 1 of 1{ROSTER_FOOTER}"}}]


def _build_operation_pages(ctx_or_author: Any, operation: str, lines: List[str], count: int) -> List[Any]:
    spec = ROSTER_OPERATION_SPECS[operation]
    if not lines:
        try:
            return [CDTEmbed.embed(ctx_or_author, title=spec.title, description=spec.empty_message, footer_text=f"Page 1 of 1{ROSTER_FOOTER}")]
        except Exception:
            return [{"title": spec.title, "description": spec.empty_message, "footer": {"text": f"Page 1 of 1{ROSTER_FOOTER}"}}]

    page_texts: List[str] = []
    current: List[str] = []
    current_len = 0
    for line in lines:
        if len(current) >= 15 or (current_len + len(line) + 1) > 1800:
            page_texts.append("\n".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += len(line) + 1
    if current:
        page_texts.append("\n".join(current))

    title = f"{spec.title} ({count} eligible)"
    pages: List[Any] = []
    for index, text in enumerate(page_texts, start=1):
        footer = f"Page {index} of {len(page_texts)}{ROSTER_FOOTER}"
        try:
            pages.append(CDTEmbed.embed(ctx_or_author, title=title, description=text, footer_text=footer))
        except Exception:
            pages.append({"title": title, "description": text, "footer": {"text": footer}})
    return pages


def _build_operation_pages_from_entries(ctx_or_author: Any, cache: Any, operation: str, entries: List[Dict[str, Any]]) -> List[Any]:
    lines = [_format_operation_line(cache, dict(entry), operation) for entry in entries]
    return _build_operation_pages(ctx_or_author, operation, lines, len(entries))


def _operation_adjustable_fields(operation: str) -> Tuple[str, ...]:
    spec = ROSTER_OPERATION_SPECS.get(operation)
    return spec.fields if spec else ()


def _normalize_operation_entry(entry: Dict[str, Any], operation: str) -> Dict[str, Any]:
    normalized = _canonicalize_roster_entry(entry)
    if operation == "rankup":
        normalized["sig"] = int(entry.get("sig") or normalized.get("sig") or 0)
        normalized["ascended"] = int(entry.get("ascended") or normalized.get("ascended") or 0)
    elif operation == "dupe":
        normalized["rank"] = int(entry.get("rank") or normalized.get("rank") or 1)
        normalized["ascended"] = int(entry.get("ascended") or normalized.get("ascended") or 0)
    elif operation == "ascend":
        normalized["rank"] = int(entry.get("rank") or normalized.get("rank") or 1)
        normalized["sig"] = int(entry.get("sig") or normalized.get("sig") or 0)
    return normalized


def _set_operation_field(entry: Dict[str, Any], operation: str, field: str, delta: int) -> Dict[str, Any]:
    updated = dict(entry)
    if field not in _operation_adjustable_fields(operation):
        return updated
    updated[field] = int(updated.get(field) or 0) + int(delta)
    return _normalize_operation_entry(updated, operation)


def _build_operation_config_embed(ctx_or_author: Any, cache: Any, operation: str, entries: List[Dict[str, Any]], index: int) -> Any:
    spec = ROSTER_OPERATION_SPECS[operation]
    entry = dict(entries[index])
    lines = [_format_operation_line(cache, entry, operation), ""]
    limits = get_roster_entry_limits(entry)
    lines.append(f"Rank: {int(entry.get('rank') or 1)}/{limits.max_rank}")
    lines.append(f"Sig: {int(entry.get('sig') or 0)}/{limits.max_sig}")
    lines.append(f"Ascension: {int(entry.get('ascended') or 0)}/{limits.max_ascended}")
    fields = ", ".join(_operation_adjustable_fields(operation)) or "none"
    lines.append("")
    lines.append(f"Adjustable fields: {fields}")
    lines.append("Use the buttons below to move between selected champions and adjust allowed values.")
    return CDTEmbed.embed(
        ctx_or_author,
        title=f"{spec.title} Config ({index + 1}/{len(entries)})",
        description="\n".join(lines),
        footer_text=f"Workflow {ROSTER_FOOTER}",
    )


def _build_operation_apply_summary(ctx_or_author: Any, cache: Any, operation: str, entries: List[Dict[str, Any]], applied: int) -> Any:
    preview_entries = entries[:10]
    lines = [_format_operation_line(cache, dict(entry), operation) for entry in preview_entries]
    if len(entries) > len(preview_entries):
        lines.append(f"... and {len(entries) - len(preview_entries)} more")
    description = f"Saved {applied} roster change(s).\n\n" + "\n".join(lines)
    return CDTEmbed.embed(ctx_or_author, title=f"{ROSTER_OPERATION_SPECS[operation].title} Saved", description=description, footer_text=f"Saved {ROSTER_FOOTER}")


def _build_operation_confirm_embed(ctx_or_author: Any, cache: Any, operation: str, entries: List[Dict[str, Any]]) -> Any:
    preview_entries = entries[:10]
    lines = [f"Selected champions: {len(entries)}", "", "Review these changes before applying:"]
    lines.extend(_format_operation_line(cache, dict(entry), operation) for entry in preview_entries)
    if len(entries) > len(preview_entries):
        lines.append(f"... and {len(entries) - len(preview_entries)} more")
    return CDTEmbed.embed(
        ctx_or_author,
        title=f"{ROSTER_OPERATION_SPECS[operation].title} Confirm",
        description="\n".join(lines),
        footer_text=f"Confirm {ROSTER_FOOTER}",
    )


def apply_roster_operation_entries(core: Any, user_id: int, operation: str, entries: List[Dict[str, Any]]) -> int:
    users = ensure_user_manager(core)
    if not users:
        return 0
    applied = 0
    for entry in entries:
        try:
            normalized = _normalize_operation_entry(entry, operation)
            champ_slug = str(normalized.get("champion") or "")
            rarity = int(normalized.get("rarity") or normalized.get("stars") or 0)
            if not champ_slug or not rarity:
                continue
            if operation == "add":
                users.add_champion(
                    user_id,
                    champ_slug,
                    rarity,
                    int(normalized.get("rank") or 1),
                    int(normalized.get("sig") or 0),
                    int(normalized.get("ascended") or 0),
                    tags=normalized.get("tags") or [],
                )
                applied += 1
            elif operation == "update":
                if users.update_champion(
                    user_id,
                    champ_slug,
                    rarity,
                    rank=int(normalized.get("rank") or 1),
                    sig=int(normalized.get("sig") or 0),
                    ascended=int(normalized.get("ascended") or 0),
                    tags=normalized.get("tags") or [],
                ):
                    applied += 1
            elif operation == "rankup":
                if users.update_champion(user_id, champ_slug, rarity, rank=int(normalized.get("rank") or 1)):
                    applied += 1
            elif operation == "dupe":
                if users.update_champion(user_id, champ_slug, rarity, sig=int(normalized.get("sig") or 0)):
                    applied += 1
            elif operation == "ascend":
                if users.update_champion(user_id, champ_slug, rarity, ascended=int(normalized.get("ascended") or 0)):
                    applied += 1
        except Exception:
            log.exception("Failed applying roster %s entry %s", operation, entry)
    if applied:
        try:
            schedule_persist_user_prestige(core, user_id)
        except Exception:
            pass
    return applied


async def collect_roster_operation_entries(
    core: Any,
    ctx_or_author: Any,
    operation: str,
    *,
    parsed_filters: Optional[Dict[str, Any]] = None,
    tier: Optional[int] = None,
    class_filter: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], Dict[int, int]]:
    spec = ROSTER_OPERATION_SPECS.get(operation)
    if spec is None:
        raise ValueError(f"Unsupported roster operation: {operation}")

    _, user_id = _resolve_author_and_user_id(ctx_or_author)
    if user_id is None:
        raise ValueError("collect_roster_operation_entries requires a user-like object or context")

    cache = getattr(core, "cache", None)
    filters = dict(parsed_filters or {})
    class_filters = [class_filter.lower()] if class_filter else [c.lower() for c in (filters.get("classes") or [])]
    requested_tiers = [int(t) for t in (filters.get("rarities") or []) if str(t).isdigit()]
    selected_tier = int(tier) if tier is not None else (requested_tiers[0] if len(requested_tiers) == 1 else None)

    roster_entries = await _load_canonical_roster_entries(core, user_id)
    owned_lookup = {(str(e.get("champion") or "").lower(), int(e.get("rarity") or e.get("stars") or 0)) for e in roster_entries}
    tier_counts: Dict[int, int] = {}

    if operation == "add":
        champions = cache.get_all_champions() if cache and hasattr(cache, "get_all_champions") else []
        candidates: List[Dict[str, Any]] = []
        tiers_to_scan = [selected_tier] if selected_tier is not None else [1, 2, 3, 4, 5, 6, 7]
        for raw_champ in champions or []:
            if not isinstance(raw_champ, dict):
                continue
            slug = str(raw_champ.get("id") or raw_champ.get("slug") or "").strip().lower()
            if not slug:
                continue
            champ_class = str(raw_champ.get("class") or raw_champ.get("class_name") or "").lower()
            for rarity_value in tiers_to_scan:
                if (slug, rarity_value) in owned_lookup:
                    continue
                rarity_norm, rank, sig, ascended = normalize_champion_progression(rarity_value, 1, 0, 0)
                candidate = {
                    "champion": slug,
                    "rarity": rarity_norm,
                    "stars": rarity_norm,
                    "rank": rank,
                    "sig": sig,
                    "ascended": ascended,
                    "raw": raw_champ.get("name") or slug,
                    "class": champ_class,
                    "tags": raw_champ.get("tags") or [],
                }
                if not _matches_class_filter(candidate, class_filters):
                    continue
                if not _matches_roster_filters(candidate, {k: v for k, v in filters.items() if k != "explicit_entries"}):
                    continue
                tier_counts[rarity_norm] = tier_counts.get(rarity_norm, 0) + 1
                candidates.append(candidate)
        candidates.sort(key=lambda e: (-int(e.get("rarity") or 0), str(e.get("raw") or e.get("champion") or "").lower()))
        return candidates, tier_counts

    eligible_entries: List[Dict[str, Any]] = []
    for entry in roster_entries:
        try:
            if selected_tier is not None and int(entry.get("rarity") or 0) != selected_tier:
                continue
            if class_filters and not entry.get("class") and cache:
                raw_champ = cache.get_champion(entry.get("champion"))
                if isinstance(raw_champ, dict):
                    entry["class"] = raw_champ.get("class") or raw_champ.get("class_name")
                    entry["tags"] = entry.get("tags") or raw_champ.get("tags") or []
            if not _matches_class_filter(entry, class_filters):
                continue
            if not _matches_roster_filters(entry, {k: v for k, v in filters.items() if k != "explicit_entries"}):
                continue
            if not _operation_entry_is_eligible(entry, operation):
                continue
            tier_counts[int(entry.get("rarity") or entry.get("stars") or 0)] = tier_counts.get(int(entry.get("rarity") or entry.get("stars") or 0), 0) + 1
            eligible_entries.append(entry)
        except Exception:
            continue

    eligible_entries.sort(key=lambda e: (-int(e.get("rarity") or 0), str(e.get("raw") or e.get("champion") or "").lower()))
    return eligible_entries, tier_counts


def _build_operation_selection_embed(
    ctx_or_author: Any,
    operation: str,
    *,
    tier: Optional[int] = None,
    class_filter: Optional[str] = None,
    stage: str = "tier",
    selected_count: int = 0,
) -> Any:
    spec = ROSTER_OPERATION_SPECS[operation]
    description_lines = [spec.summary, ""]
    if stage == "tier":
        description_lines.append("Step 1 of 5: choose a star tier.")
    elif stage == "class":
        description_lines.append(f"Step 2 of 5: choose a class for {tier}★.")
    elif stage == "select":
        description_lines.append(f"Step 3 of 5: choose one or more champions for {tier}★ {class_filter.title() if class_filter else 'All Classes'}.")
    elif stage == "config":
        description_lines.append("Step 4 of 5: configure the selected champions.")
    else:
        description_lines.append("Step 5 of 5: confirm and apply the selected changes.")
    if tier is not None:
        description_lines.append(f"Selected tier: {tier}★")
    if class_filter:
        description_lines.append(f"Selected class: {class_filter.title()}")
    if stage == "select":
        description_lines.append(f"Selected champions: {selected_count}/{ROSTER_SELECTION_LIMIT}")
        description_lines.append(f"Selection cap: {ROSTER_SELECTION_LIMIT} champions held between pages.")
    description_lines.append("")
    description_lines.append("This guided flow narrows the result set and keeps your selections until you explicitly continue.")
    description = "\n".join(description_lines)
    return CDTEmbed.embed(ctx_or_author, title=spec.title, description=description, footer_text=f"Workflow {ROSTER_FOOTER}")


def _build_selection_option_label(entry: Dict[str, Any]) -> str:
    name = str(entry.get("raw") or entry.get("champion") or "Unknown")
    rarity = int(entry.get("rarity") or entry.get("stars") or 0)
    rank = int(entry.get("rank") or 1)
    sig = int(entry.get("sig") or 0)
    asc = int(entry.get("ascended") or 0)
    suffix = f"{rarity}★ r{rank} s{sig}"
    if asc:
        suffix += f" a{asc}"
    label = f"{name} ({suffix})"
    return label[:100]


def _champion_page_window(entries: List[Dict[str, Any]], page_index: int, page_size: int) -> Tuple[int, int]:
    if not entries:
        return 0, 0
    start = max(0, page_index * page_size)
    end = min(len(entries), start + page_size)
    return start, end


def _champion_page_label(entries: List[Dict[str, Any]], page_index: int, page_size: int) -> str:
    start, end = _champion_page_window(entries, page_index, page_size)
    if end <= start:
        return "Champions"
    return f"Page {start + 1}-{end}"


def _entry_selection_key(entry: Dict[str, Any]) -> str:
    return f"{entry.get('champion')}|{int(entry.get('rarity') or entry.get('stars') or 0)}"


def _config_button_specs(field: str) -> List[Tuple[str, int]]:
    if field == "sig":
        return [("SIG -20", -20), ("SIG -1", -1), ("SIG +1", 1), ("SIG +20", 20)]
    label = field.upper()
    return [(f"{label} -", -1), (f"{label} +", 1)]


if discord is not None:
    class _RosterFlowView(View):
        def __init__(self, core: Any, author: Any, operation: str, *, parsed_filters: Optional[Dict[str, Any]] = None, tier: Optional[int] = None):
            super().__init__(timeout=ROSTER_FLOW_TIMEOUT)
            self.core = core
            self.author = author
            self.operation = operation
            self.parsed_filters = dict(parsed_filters or {})
            self.tier = tier
            self.message = None

        async def interaction_check(self, interaction: Any) -> bool:
            if getattr(interaction.user, "id", None) == getattr(self.author, "id", None):
                return True
            try:
                await interaction.response.send_message("This roster workflow belongs to the invoking user.", ephemeral=True)
            except Exception:
                pass
            return False

        async def on_timeout(self):
            try:
                for item in self.children:
                    item.disabled = True
                if self.message:
                    await self.message.edit(view=self)
            except Exception:
                pass

        async def _attach_message(self, interaction: Any) -> None:
            try:
                self.message = await interaction.original_response()
            except Exception:
                self.message = None

        async def _open_class_selection(self, interaction: Any, tier: int) -> None:
            view = RosterClassSelectionView(self.core, self.author, self.operation, parsed_filters=self.parsed_filters, tier=tier)
            embed = _build_operation_selection_embed(self.author, self.operation, tier=tier, stage="class")
            await interaction.response.edit_message(embed=embed, view=view)
            await view._attach_message(interaction)

        async def _open_multi_select(self, interaction: Any, *, tier: Optional[int], class_filter: Optional[str]) -> None:
            entries, _ = await collect_roster_operation_entries(
                self.core,
                self.author,
                self.operation,
                parsed_filters=self.parsed_filters,
                tier=tier,
                class_filter=class_filter,
            )
            view = RosterChampionSelectView(
                self.core,
                self.author,
                self.operation,
                entries,
                parsed_filters=self.parsed_filters,
                tier=tier,
                class_filter=class_filter,
            )
            embed = _build_operation_selection_embed(self.author, self.operation, tier=tier, class_filter=class_filter, stage="select", selected_count=0)
            try:
                embed.description = f"{embed.description}\n\nSelect champions on any page, then use Continue To Config when ready."
            except Exception:
                pass
            await interaction.response.edit_message(embed=embed, view=view)
            await view._attach_message(interaction)

        async def _open_results(self, interaction: Any, *, tier: Optional[int], class_filter: Optional[str]) -> None:
            pages = await build_roster_operation_pages(
                self.core,
                self.author,
                self.operation,
                parsed_filters=self.parsed_filters,
                tier=tier,
                class_filter=class_filter,
            )
            pager = CDTPagesMenu(pages, author=self.author)
            await interaction.response.edit_message(embed=await pager._render_page(), view=pager)
            try:
                pager.message = await interaction.original_response()
            except Exception:
                pager.message = None

        async def _open_selected_results(self, interaction: Any, entries: List[Dict[str, Any]]) -> None:
            pages = _build_operation_pages_from_entries(self.author, getattr(self.core, "cache", None), self.operation, entries)
            pager = CDTPagesMenu(pages, author=self.author)
            await interaction.response.edit_message(embed=await pager._render_page(), view=pager)
            try:
                pager.message = await interaction.original_response()
            except Exception:
                pager.message = None

        async def _open_config(self, interaction: Any, entries: List[Dict[str, Any]]) -> None:
            view = RosterConfigView(self.core, self.author, self.operation, entries, parsed_filters=self.parsed_filters, tier=self.tier)
            embed = _build_operation_selection_embed(self.author, self.operation, tier=self.tier, stage="config")
            config_embed = _build_operation_config_embed(self.author, getattr(self.core, "cache", None), self.operation, view.entries, view.index)
            try:
                embed.description = config_embed.description
                embed.title = config_embed.title
            except Exception:
                embed = config_embed
            await interaction.response.edit_message(embed=embed, view=view)
            await view._attach_message(interaction)


    class RosterTierSelectionView(_RosterFlowView):
        def __init__(self, core: Any, author: Any, operation: str, *, parsed_filters: Optional[Dict[str, Any]] = None):
            super().__init__(core, author, operation, parsed_filters=parsed_filters)
            for tier in range(7, 0, -1):
                self.add_item(_RosterTierButton(tier))
            self.add_item(_RosterTierResultsButton())


    class _RosterTierButton(Button):
        def __init__(self, tier: int):
            super().__init__(label=f"{tier}★", style=discord.ButtonStyle.primary, row=0 if tier >= 4 else 1)
            self.tier = tier

        async def callback(self, interaction: Any):
            view = self.view
            if not isinstance(view, _RosterFlowView):
                return
            await view._open_class_selection(interaction, self.tier)


    class _RosterTierResultsButton(Button):
        def __init__(self):
            super().__init__(label="Show Overview", style=discord.ButtonStyle.secondary, row=2)

        async def callback(self, interaction: Any):
            view = self.view
            if not isinstance(view, _RosterFlowView):
                return
            await view._open_results(interaction, tier=None, class_filter=None)


    class RosterClassSelectionView(_RosterFlowView):
        def __init__(self, core: Any, author: Any, operation: str, *, parsed_filters: Optional[Dict[str, Any]] = None, tier: Optional[int] = None):
            super().__init__(core, author, operation, parsed_filters=parsed_filters, tier=tier)
            for index, class_name in enumerate(ROSTER_OPERATION_CLASSES):
                self.add_item(_RosterClassButton(class_name, row=0 if index < 3 else 1))
            self.add_item(_RosterClassResultsButton(label="All Classes", class_filter=None, row=2))
            self.add_item(_RosterBackToTierButton())


    class _RosterClassButton(Button):
        def __init__(self, class_name: str, *, row: int):
            super().__init__(
                label=class_name.title(),
                emoji=CLASS_EMOJI.get(class_name),
                style=discord.ButtonStyle.primary,
                row=row,
            )
            self.class_name = class_name

        async def callback(self, interaction: Any):
            view = self.view
            if not isinstance(view, _RosterFlowView):
                return
            await view._open_multi_select(interaction, tier=view.tier, class_filter=self.class_name)


    class _RosterClassResultsButton(Button):
        def __init__(self, *, label: str, class_filter: Optional[str], row: int):
            super().__init__(label=label, emoji=CLASS_EMOJI.get("all"), style=discord.ButtonStyle.secondary, row=row)
            self.class_filter = class_filter

        async def callback(self, interaction: Any):
            view = self.view
            if not isinstance(view, _RosterFlowView):
                return
            await view._open_multi_select(interaction, tier=view.tier, class_filter=self.class_filter)


    class _RosterBackToTierButton(Button):
        def __init__(self):
            super().__init__(label="Back To Star", style=discord.ButtonStyle.secondary, row=2)

        async def callback(self, interaction: Any):
            view = self.view
            if not isinstance(view, _RosterFlowView):
                return
            new_view = RosterTierSelectionView(view.core, view.author, view.operation, parsed_filters=view.parsed_filters)
            embed = _build_operation_selection_embed(view.author, view.operation, stage="tier")
            await interaction.response.edit_message(embed=embed, view=new_view)
            await new_view._attach_message(interaction)


    class RosterChampionSelectView(_RosterFlowView):
        def __init__(
            self,
            core: Any,
            author: Any,
            operation: str,
            entries: List[Dict[str, Any]],
            *,
            parsed_filters: Optional[Dict[str, Any]] = None,
            tier: Optional[int] = None,
            class_filter: Optional[str] = None,
            page_index: int = 0,
            selected_keys: Optional[set] = None,
        ):
            super().__init__(core, author, operation, parsed_filters=parsed_filters, tier=tier)
            self.entries = list(entries)
            self.class_filter = class_filter
            self.page_index = page_index
            self.page_size = 25
            self.selected_keys = set(selected_keys or set())
            start = self.page_index * self.page_size
            end = start + self.page_size
            current_entries = self.entries[start:end]
            if current_entries:
                self.add_item(_RosterChampionSelect(current_entries, selected_keys=self.selected_keys))
            if self.page_index > 0:
                self.add_item(_RosterSelectPageButton(label=_champion_page_label(self.entries, self.page_index - 1, self.page_size), delta=-1, row=3))
            if end < len(self.entries):
                self.add_item(_RosterSelectPageButton(label=_champion_page_label(self.entries, self.page_index + 1, self.page_size), delta=1, row=3))
            self.add_item(_RosterShowAllSelectedButton(row=3))
            self.add_item(_RosterContinueToConfigButton(selected_count=len(self.selected_keys), row=3))
            self.add_item(_RosterSelectBackButton(row=3))

        def selected_entries(self) -> List[Dict[str, Any]]:
            selected = []
            for entry in self.entries:
                if _entry_selection_key(entry) in self.selected_keys:
                    selected.append(entry)
            return selected

        def build_embed(self) -> Any:
            embed = _build_operation_selection_embed(
                self.author,
                self.operation,
                tier=self.tier,
                class_filter=self.class_filter,
                stage="select",
                selected_count=len(self.selected_keys),
            )
            try:
                embed.description = f"{embed.description}\n\nSelect champions on this page. Use page buttons to keep browsing, or Continue To Config to move to step 4."
            except Exception:
                pass
            return embed


    class _RosterChampionSelect(discord.ui.Select):
        def __init__(self, entries: List[Dict[str, Any]], *, selected_keys: Optional[set] = None):
            selected_keys = selected_keys or set()
            options = []
            for entry in entries:
                value = _entry_selection_key(entry)
                options.append(
                    discord.SelectOption(
                        label=_build_selection_option_label(entry),
                        value=value,
                        default=value in selected_keys,
                    )
                )
            super().__init__(placeholder="Choose champions", min_values=0, max_values=len(options), options=options, row=0)

        async def callback(self, interaction: Any):
            view = self.view
            if not isinstance(view, RosterChampionSelectView):
                return
            start, end = _champion_page_window(view.entries, view.page_index, view.page_size)
            page_entries = view.entries[start:end]
            page_keys = {_entry_selection_key(entry) for entry in page_entries}
            chosen = set(self.values)
            selected_keys = (view.selected_keys - page_keys) | chosen
            if len(selected_keys) > ROSTER_SELECTION_LIMIT:
                try:
                    await interaction.response.send_message(
                        f"You can hold up to {ROSTER_SELECTION_LIMIT} selected champions between pages. Deselect some champions before adding more.",
                        ephemeral=True,
                    )
                except Exception:
                    pass
                return
            new_view = RosterChampionSelectView(
                view.core,
                view.author,
                view.operation,
                view.entries,
                parsed_filters=view.parsed_filters,
                tier=view.tier,
                class_filter=view.class_filter,
                page_index=view.page_index,
                selected_keys=selected_keys,
            )
            await interaction.response.edit_message(embed=new_view.build_embed(), view=new_view)
            await new_view._attach_message(interaction)


    class _RosterSelectPageButton(Button):
        def __init__(self, *, label: str, delta: int, row: int):
            super().__init__(label=label, style=discord.ButtonStyle.secondary, row=row)
            self.delta = delta

        async def callback(self, interaction: Any):
            view = self.view
            if not isinstance(view, RosterChampionSelectView):
                return
            new_index = max(0, view.page_index + self.delta)
            new_view = RosterChampionSelectView(
                view.core,
                view.author,
                view.operation,
                view.entries,
                parsed_filters=view.parsed_filters,
                tier=view.tier,
                class_filter=view.class_filter,
                page_index=new_index,
                selected_keys=view.selected_keys,
            )
            await interaction.response.edit_message(embed=new_view.build_embed(), view=new_view)
            await new_view._attach_message(interaction)


    class _RosterShowAllSelectedButton(Button):
        def __init__(self, *, row: int):
            super().__init__(label="Show All", style=discord.ButtonStyle.secondary, row=row)

        async def callback(self, interaction: Any):
            view = self.view
            if not isinstance(view, RosterChampionSelectView):
                return
            await view._open_results(interaction, tier=view.tier, class_filter=view.class_filter)


    class _RosterContinueToConfigButton(Button):
        def __init__(self, *, selected_count: int, row: int):
            super().__init__(label=f"Continue To Config ({selected_count}/{ROSTER_SELECTION_LIMIT})", style=discord.ButtonStyle.success, row=row)

        async def callback(self, interaction: Any):
            view = self.view
            if not isinstance(view, RosterChampionSelectView):
                return
            selected = view.selected_entries()
            if not selected:
                try:
                    await interaction.response.send_message("Select at least one champion before continuing.", ephemeral=True)
                except Exception:
                    pass
                return
            await view._open_config(interaction, selected)


    class _RosterSelectBackButton(Button):
        def __init__(self, *, row: int):
            super().__init__(label="Back To Class", style=discord.ButtonStyle.secondary, row=row)

        async def callback(self, interaction: Any):
            view = self.view
            if not isinstance(view, RosterChampionSelectView):
                return
            new_view = RosterClassSelectionView(
                view.core,
                view.author,
                view.operation,
                parsed_filters=view.parsed_filters,
                tier=view.tier,
            )
            embed = _build_operation_selection_embed(view.author, view.operation, tier=view.tier, stage="class")
            await interaction.response.edit_message(embed=embed, view=new_view)
            await new_view._attach_message(interaction)


    class RosterConfigView(_RosterFlowView):
        def __init__(self, core: Any, author: Any, operation: str, entries: List[Dict[str, Any]], *, parsed_filters: Optional[Dict[str, Any]] = None, tier: Optional[int] = None):
            super().__init__(core, author, operation, parsed_filters=parsed_filters, tier=tier)
            self.entries = [_normalize_operation_entry(entry, operation) for entry in entries]
            self.index = 0
            self.add_item(_RosterConfigNavButton(label="Prev", delta=-1, row=0))
            self.add_item(_RosterConfigNavButton(label="Next", delta=1, row=0))
            for row_index, field in enumerate(_operation_adjustable_fields(operation), start=1):
                for label, delta in _config_button_specs(field):
                    self.add_item(_RosterConfigAdjustButton(field=field, delta=delta, row=row_index, label=label))
            self.add_item(_RosterConfigPreviewButton(row=4))
            self.add_item(_RosterConfigConfirmButton(row=4))


    class _RosterConfigNavButton(Button):
        def __init__(self, *, label: str, delta: int, row: int):
            super().__init__(label=label, style=discord.ButtonStyle.secondary, row=row)
            self.delta = delta

        async def callback(self, interaction: Any):
            view = self.view
            if not isinstance(view, RosterConfigView):
                return
            view.index = max(0, min(len(view.entries) - 1, view.index + self.delta))
            embed = _build_operation_config_embed(view.author, getattr(view.core, "cache", None), view.operation, view.entries, view.index)
            await interaction.response.edit_message(embed=embed, view=view)


    class _RosterConfigAdjustButton(Button):
        def __init__(self, *, field: str, delta: int, row: int, label: str):
            super().__init__(label=label, style=discord.ButtonStyle.primary, row=row)
            self.field = field
            self.delta = delta

        async def callback(self, interaction: Any):
            view = self.view
            if not isinstance(view, RosterConfigView):
                return
            current = dict(view.entries[view.index])
            view.entries[view.index] = _set_operation_field(current, view.operation, self.field, self.delta)
            embed = _build_operation_config_embed(view.author, getattr(view.core, "cache", None), view.operation, view.entries, view.index)
            await interaction.response.edit_message(embed=embed, view=view)


    class _RosterConfigPreviewButton(Button):
        def __init__(self, *, row: int):
            super().__init__(label="Preview", style=discord.ButtonStyle.secondary, row=row)

        async def callback(self, interaction: Any):
            view = self.view
            if not isinstance(view, RosterConfigView):
                return
            await view._open_selected_results(interaction, view.entries)


    class _RosterConfigConfirmButton(Button):
        def __init__(self, *, row: int):
            super().__init__(label="Review And Confirm", style=discord.ButtonStyle.success, row=row)

        async def callback(self, interaction: Any):
            view = self.view
            if not isinstance(view, RosterConfigView):
                return
            confirm_view = RosterConfirmView(
                view.core,
                view.author,
                view.operation,
                view.entries,
                parsed_filters=view.parsed_filters,
                tier=view.tier,
            )
            embed = _build_operation_confirm_embed(view.author, getattr(view.core, "cache", None), view.operation, view.entries)
            await interaction.response.edit_message(embed=embed, view=confirm_view)
            await confirm_view._attach_message(interaction)


    class RosterConfirmView(_RosterFlowView):
        def __init__(self, core: Any, author: Any, operation: str, entries: List[Dict[str, Any]], *, parsed_filters: Optional[Dict[str, Any]] = None, tier: Optional[int] = None):
            super().__init__(core, author, operation, parsed_filters=parsed_filters, tier=tier)
            self.entries = [_normalize_operation_entry(entry, operation) for entry in entries]
            self.add_item(_RosterConfirmBackButton(row=0))
            self.add_item(_RosterConfirmApplyButton(row=0))


    class _RosterConfirmBackButton(Button):
        def __init__(self, *, row: int):
            super().__init__(label="Back To Config", style=discord.ButtonStyle.secondary, row=row)

        async def callback(self, interaction: Any):
            view = self.view
            if not isinstance(view, RosterConfirmView):
                return
            config_view = RosterConfigView(
                view.core,
                view.author,
                view.operation,
                view.entries,
                parsed_filters=view.parsed_filters,
                tier=view.tier,
            )
            config_view.entries = [_normalize_operation_entry(entry, view.operation) for entry in view.entries]
            embed = _build_operation_config_embed(view.author, getattr(view.core, "cache", None), view.operation, config_view.entries, config_view.index)
            await interaction.response.edit_message(embed=embed, view=config_view)
            await config_view._attach_message(interaction)


    class _RosterConfirmApplyButton(Button):
        def __init__(self, *, row: int):
            super().__init__(label="Confirm Apply", style=discord.ButtonStyle.success, row=row)

        async def callback(self, interaction: Any):
            view = self.view
            if not isinstance(view, RosterConfirmView):
                return
            applied = apply_roster_operation_entries(view.core, getattr(view.author, "id", None), view.operation, view.entries)
            embed = _build_operation_apply_summary(view.author, getattr(view.core, "cache", None), view.operation, view.entries, applied)
            for item in view.children:
                item.disabled = True
                if isinstance(item, _RosterConfirmApplyButton):
                    item.label = "Saved"
            await interaction.response.edit_message(embed=embed, view=view)
else:
    RosterTierSelectionView = None


async def _load_canonical_roster_entries(core: Any, user_id: int) -> List[Dict[str, Any]]:
    users = ensure_user_manager(core)
    if not users:
        return []
    try:
        if asyncio.iscoroutinefunction(getattr(users, "list_roster", None)):
            roster = await users.list_roster(user_id)
        else:
            roster = users.list_roster(user_id)
    except Exception:
        roster = []
    out: List[Dict[str, Any]] = []
    for entry in roster or []:
        try:
            out.append(_canonicalize_roster_entry(entry))
        except Exception:
            continue
    return out


async def build_roster_operation_pages(
    core: Any,
    ctx_or_author: Any,
    operation: str,
    *,
    parsed_filters: Optional[Dict[str, Any]] = None,
    tier: Optional[int] = None,
    class_filter: Optional[str] = None,
) -> List[Any]:
    author_for_embed, user_id = _resolve_author_and_user_id(ctx_or_author)
    if user_id is None:
        raise ValueError("build_roster_operation_pages requires a user-like object or context")

    cache = getattr(core, "cache", None)
    filters = dict(parsed_filters or {})
    class_filters = [class_filter.lower()] if class_filter else [c.lower() for c in (filters.get("classes") or [])]
    requested_tiers = [int(t) for t in (filters.get("rarities") or []) if str(t).isdigit()]
    selected_tier = int(tier) if tier is not None else (requested_tiers[0] if len(requested_tiers) == 1 else None)
    entries, tier_counts = await collect_roster_operation_entries(
        core,
        ctx_or_author,
        operation,
        parsed_filters=parsed_filters,
        tier=tier,
        class_filter=class_filter,
    )

    if operation == "add" and selected_tier is None and not class_filters and not filters.get("name") and not filters.get("tags"):
        return _build_operation_overview_pages(author_for_embed, operation, tier_counts)

    return _build_operation_pages_from_entries(author_for_embed, cache, operation, entries)


async def get_roster_add_pages(core: Any, ctx_or_author: Any, *, parsed_filters: Optional[Dict[str, Any]] = None, tier: Optional[int] = None, class_filter: Optional[str] = None) -> List[Any]:
    return await build_roster_operation_pages(core, ctx_or_author, "add", parsed_filters=parsed_filters, tier=tier, class_filter=class_filter)


async def get_roster_update_pages(core: Any, ctx_or_author: Any, *, parsed_filters: Optional[Dict[str, Any]] = None, tier: Optional[int] = None, class_filter: Optional[str] = None) -> List[Any]:
    return await build_roster_operation_pages(core, ctx_or_author, "update", parsed_filters=parsed_filters, tier=tier, class_filter=class_filter)


async def get_roster_rankup_pages(core: Any, ctx_or_author: Any, *, parsed_filters: Optional[Dict[str, Any]] = None, tier: Optional[int] = None, class_filter: Optional[str] = None) -> List[Any]:
    return await build_roster_operation_pages(core, ctx_or_author, "rankup", parsed_filters=parsed_filters, tier=tier, class_filter=class_filter)


async def get_roster_dupe_pages(core: Any, ctx_or_author: Any, *, parsed_filters: Optional[Dict[str, Any]] = None, tier: Optional[int] = None, class_filter: Optional[str] = None) -> List[Any]:
    return await build_roster_operation_pages(core, ctx_or_author, "dupe", parsed_filters=parsed_filters, tier=tier, class_filter=class_filter)


async def get_roster_ascend_pages(core: Any, ctx_or_author: Any, *, parsed_filters: Optional[Dict[str, Any]] = None, tier: Optional[int] = None, class_filter: Optional[str] = None) -> List[Any]:
    return await build_roster_operation_pages(core, ctx_or_author, "ascend", parsed_filters=parsed_filters, tier=tier, class_filter=class_filter)


async def start_roster_operation_flow(core: Any, ctx: Any, operation: str, *, parsed_filters: Optional[Dict[str, Any]] = None) -> bool:
    """Start the guided roster workflow when Discord UI views are available."""
    if discord is None or RosterTierSelectionView is None:
        return False
    author = getattr(ctx, "author", None)
    if author is None:
        return False
    view = RosterTierSelectionView(core, author, operation, parsed_filters=parsed_filters)
    embed = _build_operation_selection_embed(author, operation, stage="tier")
    await ctx.send(embed=embed, view=view)
    return True


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

        # load profile (may be dict or module-level UserData shape)
        profile_raw = {}
        try:
            if users and hasattr(users, "get_profile"):
                profile_raw = users.get_profile(user_id) or {}
        except Exception:
            profile_raw = {}

        # If profile_raw looks like a full userdata dict, extract profile subkey
        if isinstance(profile_raw, dict) and "profile" in profile_raw and isinstance(profile_raw.get("profile"), dict):
            profile = profile_raw.get("profile", {})
        else:
            profile = profile_raw if isinstance(profile_raw, dict) else {}

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
                        raw_champ = cache.get_champion(entry.get("champion"))
                        # cache.get_champion may return dict or dataclass; normalize to Champion dataclass
                        if isinstance(raw_champ, dict):
                            champ_obj = champion_from_dict(raw_champ)
                        elif isinstance(raw_champ, Champion):
                            champ_obj = raw_champ
                        else:
                            # if cache exposes get_champion_obj, prefer that
                            try:
                                cobj = cache.get_champion_obj(entry.get("champion"))
                                if cobj:
                                    # cobj may be dataclass-like or dict-like
                                    if isinstance(cobj, dict):
                                        champ_obj = champion_from_dict(cobj)
                                    else:
                                        champ_obj = cobj
                            except Exception:
                                champ_obj = None
                    except Exception:
                        champ_obj = None
                # attach class if available from champ_obj for filtering/formatting
                if champ_obj and not entry.get("class"):
                    try:
                        entry["class"] = getattr(champ_obj, "class_name", None) or getattr(champ_obj, "class", None) or entry.get("class")
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
