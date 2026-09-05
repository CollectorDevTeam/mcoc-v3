# Path: mcoc/common/query_parser.py
# File-Version: 1.0
# File-Id: ab6646d6-125a-49e8-adb5-142eb490bd64
# Purpose: Parse user queries into structured entries and filters for MCOC champions.
# Public-API: parse_query
# Last-Modified: 2026-09-01
# Changelog:
#   1.0 2026-09-01  Initial stabilized API header

from typing import Any, Dict, List, Tuple, Optional


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
    if any(ch in clean for ch in "*★rRsSaA"):
        return False
    if lowered in {"all", "and", "or"}:
        return False
    if lowered in {"skill", "mutant", "tech", "cosmic", "mystic", "science"}:
        return True
    if _cache_has_champion(cache, clean):
        return False
    if any(ch.isdigit() for ch in clean):
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_\-]*", clean))

def parse_query(
    text: Optional[str],
    cache: Any = None,
    *,
    allow_tags: bool = True,
    allow_hargs: bool = True,
    allow_names: bool = True
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Returns (entries, filters)

    entries: list of canonical entry dicts:
      { "champion": slug, "rarity": int, "rank": int, "sig": int, "ascended": int, "raw": str }

    filters: dict for search filters:
      { "tags": [str], "classes": [str], "name": Optional[str], "raw_text": str }
    """

from .hargs import parse_harg_list
from ..helpers.roster import parse_roster_entries_from_input
from .hargs import parse_hargs
from typing import Any, Dict, List, Tuple, Optional
import re

def parse_query(text: Optional[str], cache: Any = None, **opts) -> Tuple[List[Dict[str,Any]], Dict[str,Any]]:
    text = (text or "").strip()
    entries: List[Dict[str,Any]] = []
    filters: Dict[str,Any] = {"tags": [], "classes": [], "name": None, "raw_text": text}

    # 1. quick tag extraction
    try:
        parsed_filters = parse_hargs(text) if text else {}
        filters["tags"] = list(parsed_filters.get("tags", []))
        filters["classes"] = list(parsed_filters.get("classes", []))
        filters["rarities"] = list(parsed_filters.get("rarities", []))
        filters["tiers"] = list(parsed_filters.get("rarities", []))
        filters["ranks"] = list(parsed_filters.get("ranks", []))
        filters["sigs"] = list(parsed_filters.get("sigs", []))
        filters["ascended"] = list(parsed_filters.get("ascended", []))
        if parsed_filters.get("champion"):
            filters["name"] = parsed_filters.get("champion")

        # Support direct string filter tokens like "bleed", "incinerate", or "mystic"
        # without requiring the # predicate. If a bare token does not resolve to a champion
        # name in the current cache, it is treated as a general tag/class filter.
        for token in _tokenize_direct_filters(text):
            lower = token.lower()
            if lower.startswith(("#", "!", "@")):
                continue
            if any(ch in token for ch in "*★rRsSaA"):
                continue
            if lower in {"all", "and", "or"}:
                continue
            if lower in {"skill", "mutant", "tech", "cosmic", "mystic", "science"}:
                if lower not in filters["classes"]:
                    filters["classes"].append(lower)
                if filters.get("name") and filters["name"].lower() == lower:
                    filters["name"] = None
                if lower not in filters["tags"]:
                    filters["tags"].append(lower)
                continue
            if _is_direct_filter_token(token, cache=cache):
                if token.lower() not in filters["tags"]:
                    filters["tags"].append(token.lower())
                if filters.get("name") and filters["name"].lower() == token.lower():
                    filters["name"] = None

        # allow class tokens to behave like tag tokens in the phase-1 filters
        for cls_name in filters["classes"]:
            if cls_name not in filters["tags"]:
                filters["tags"].append(cls_name)
    except Exception:
        pass

    # 2. try explicit hargs entries (prefer these if present)
    try:
        if text and (any(ch.isdigit() for ch in text) or "r" in text.lower() or "s" in text.lower() or "a" in text.lower()):
            try:
                entries = parse_roster_entries_from_input(text, cache)
            except Exception:
                entries = []
    except Exception:
        entries = []

    # 3. if no entries and a plain name exists, leave filters["name"] for caller to search
    return entries, filters
