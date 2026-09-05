# Path: mcoc/common/query_parser.py
# File-Version: 1.0
# File-Id: ab6646d6-125a-49e8-adb5-142eb490bd64
# Purpose: Parse user queries into structured entries and filters for MCOC champions.
# Public-API: parse_query
# Last-Modified: 2026-09-01
# Changelog:
#   1.0 2026-09-01  Initial stabilized API header

import re
from typing import Any, Dict, List, Optional, Tuple

from .hargs import CLASSES, parse_hargs
from ..helpers.roster import parse_roster_entries_from_input


def _cache_has_champion(cache: Any, candidate: str) -> bool:
    token = (candidate or "").strip()
    if not token:
        return False
    try:
        if cache is not None and hasattr(cache, "get_champion"):
            try:
                if cache.get_champion(token):
                    return True
            except Exception:
                pass
    except Exception:
        pass

    needle = "".join(ch for ch in token.lower() if ch.isalnum())
    if not needle:
        return False
    try:
        champions = cache.get_all_champions() if cache is not None and hasattr(cache, "get_all_champions") else []
        for champ in champions or []:
            if not isinstance(champ, dict):
                continue
            for choice in (
                champ.get("id"),
                champ.get("slug"),
                champ.get("name"),
                champ.get("title"),
                champ.get("shortname"),
            ):
                if choice is None:
                    continue
                if "".join(ch for ch in str(choice).lower() if ch.isalnum()) == needle:
                    return True
    except Exception:
        pass
    return False


def _tokenize_direct_filters(text: str) -> List[str]:
    if not text:
        return []
    raw_tokens: List[str] = []
    for token in text.replace(";", " ").replace(",", " ").split():
        clean = token.strip().strip('"\'').strip()
        if clean:
            raw_tokens.append(clean)
    return raw_tokens


def _is_direct_filter_token(token: str, *, cache: Any = None) -> bool:
    clean = (token or "").strip().strip('"\'')
    if not clean:
        return False
    lowered = clean.lower()
    if lowered.startswith(("#", "!", "@")):
        return False
    if lowered in {"all", "and", "or"}:
        return False
    if re.fullmatch(r"(?i)(?:[1-7](?:\*|★)?(?:[-\s]*stars?)?|[rR][1-5](?:-[1-5])?|[sS]\d{1,4}|[aA]\d)", clean):
        return False
    if lowered in set(CLASSES):
        return True

    # Known ability/tag names should remain filter tokens even if a champion with the same
    # name exists (e.g. "shock" vs "Shocker"). The canonical matcher accepts these values.
    try:
        if cache is not None:
            if hasattr(cache, "get_all_abilities"):
                for ability in cache.get_all_abilities() or []:
                    name = (ability.get("name") if isinstance(ability, dict) else str(ability))
                    if name and name.lower() == lowered:
                        return True
            if hasattr(cache, "get_all_tags"):
                for tag in cache.get_all_tags() or []:
                    if isinstance(tag, str) and tag.lower() == lowered:
                        return True
    except Exception:
        pass

    if _cache_has_champion(cache, clean):
        return False
    if any(ch.isdigit() for ch in clean):
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_\-]*", clean))


def _dedupe_preserve_order(values: List[Any]) -> List[Any]:
    seen = set()
    out: List[Any] = []
    for value in values:
        if value is None:
            continue
        key = str(value).lower() if isinstance(value, str) else value
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def parse_query(
    text: Optional[str],
    cache: Any = None,
    *,
    allow_tags: bool = True,
    allow_hargs: bool = True,
    allow_names: bool = True,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Return parsed entries and canonical filters for champion search input."""
    text = (text or "").strip()
    entries: List[Dict[str, Any]] = []
    filters: Dict[str, Any] = {
        "tags": [],
        "classes": [],
        "name": None,
        "raw_text": text,
        "rarities": [],
        "tiers": [],
        "ranks": [],
        "sigs": [],
        "ascended": [],
    }

    if not text:
        return entries, filters

    try:
        parsed_filters = parse_hargs(text)
        filters["tags"] = list(parsed_filters.get("tags", []))
        filters["classes"] = list(parsed_filters.get("classes", []))
        filters["rarities"] = list(parsed_filters.get("rarities", []))
        filters["tiers"] = list(parsed_filters.get("rarities", []))
        filters["ranks"] = list(parsed_filters.get("ranks", []))
        filters["sigs"] = list(parsed_filters.get("sigs", []))
        filters["ascended"] = list(parsed_filters.get("ascended", []))
        if parsed_filters.get("champion"):
            filters["name"] = parsed_filters.get("champion")
    except Exception:
        pass

    for token in _tokenize_direct_filters(text):
        lower = token.lower()
        if lower.startswith(("#", "!", "@")):
            continue
        if re.fullmatch(r"(?i)(?:[1-7](?:\*|★)?(?:[-\s]*stars?)?|[rR][1-5](?:-[1-5])?|[sS]\d{1,4}|[aA]\d)", token):
            continue
        if lower in {"all", "and", "or"}:
            continue
        if lower in set(CLASSES):
            if lower not in filters["classes"]:
                filters["classes"].append(lower)
            if lower not in filters["tags"]:
                filters["tags"].append(lower)
            if filters.get("name") and filters["name"].lower() == lower:
                filters["name"] = None
            continue
        if _is_direct_filter_token(token, cache=cache):
            if lower not in filters["tags"]:
                filters["tags"].append(lower)
            if filters.get("name") and filters["name"].lower() == lower:
                filters["name"] = None

    for key in ("tags", "classes", "rarities", "tiers", "ranks", "sigs", "ascended"):
        if key in filters:
            filters[key] = _dedupe_preserve_order(filters[key])

    if filters.get("name") and filters["name"].lower() in set(CLASSES):
        filters["name"] = None

    try:
        if text and (any(ch.isdigit() for ch in text) or "r" in text.lower() or "s" in text.lower() or "a" in text.lower()):
            entries = parse_roster_entries_from_input(text, cache)
    except Exception:
        entries = []

    return entries, filters
