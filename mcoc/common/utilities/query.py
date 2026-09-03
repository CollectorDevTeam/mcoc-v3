# Path: mcoc/common/query.py
# File-Version: 1.0
# File-Id: f7971b51-2a3f-4a85-8d2d-a69a0e5a5599
# Purpose: Provide utility functions for querying and matching MCOC champions.
# Public-API: match_champion
# Last-Modified: 2026-09-01
# Changelog:
#   1.0 2026-09-01  Initial stabilized API header
import logging

log = logging.getLogger("red.mcoc.query")

__all__ = ["match_champion"]

def match_champion(champ: dict, h: dict) -> bool:
    """
    Robust champion matcher.
    - champ: champion dict from cache (keys may be missing or different types).
    - h: parsed human args from parse_hargs (normalized lists/values).
    """
    # Helper normalizers
    def _get_int(val, default=None):
        try:
            return int(val)
        except Exception:
            return default

    def _in_list_ci(item, lst):
        if item is None:
            return False
        s = str(item).lower()
        return any(s == str(x).lower() for x in lst)

    # Safely extract champion fields with fallbacks
    rarity = _get_int(champ.get("rarity"))
    rank = _get_int(champ.get("rank"))
    sig = _get_int(champ.get("sig"))
    cls = (champ.get("class") or "").lower()
    tags = [t.lower() for t in (champ.get("tags") or []) if isinstance(t, str)]
    slug = (champ.get("slug") or "").lower()
    name = (champ.get("name") or "").lower()

    # Rarity union (if any rarities specified, champ must match one)
    if h.get("rarities"):
        # allow string/int in h["rarities"]
        wanted = {int(x) for x in h["rarities"] if isinstance(x, (int, str)) and str(x).isdigit()}
        if rarity is None or rarity not in wanted:
            return False

    # Rank union
    if h.get("ranks"):
        wanted = {int(x) for x in h["ranks"] if isinstance(x, (int, str)) and str(x).isdigit()}
        if rank is None or rank not in wanted:
            return False

    # Signature union
    if h.get("sigs"):
        wanted = {int(x) for x in h["sigs"] if isinstance(x, (int, str)) and str(x).isdigit()}
        if sig is None or sig not in wanted:
            return False

    # Class filter (support 'all' as wildcard)
    if h.get("classes"):
        classes = [c.lower() for c in h["classes"] if isinstance(c, str)]
        if "all" not in classes:
            if not cls or cls not in classes:
                return False

    # Tag and immunity intersection: every requested tag must be present on champ
    # Accept both hyphenated and compact versions (e.g. bleed-immunity vs bleedimmunity)
    def _norm(value):
        return "".join(ch for ch in str(value or "").lower() if ch.isalnum())

    immunity_names = []
    for item in (champ.get("immunities") or []):
        if isinstance(item, dict):
            for key in ("name", "id", "slug"):
                val = item.get(key)
                if val:
                    immunity_names.append(str(val))
        else:
            immunity_names.append(str(item))

    all_tokens = tags + [str(t).lower() for t in immunity_names if isinstance(t, str)]
    for tag in (h.get("tags") or []):
        if not isinstance(tag, str):
            continue
        tf = _norm(tag)
        if not tf:
            continue
        if not any(tf == _norm(candidate) or tf in _norm(candidate) or _norm(candidate) in tf for candidate in all_tokens):
            return False

    # Negation: none of the not_tags may be present
    for tag in (h.get("not_tags") or []):
        if not isinstance(tag, str):
            continue
        tf = _norm(tag)
        if any(tf == _norm(candidate) or tf in _norm(candidate) or _norm(candidate) in tf for candidate in all_tokens):
            return False

    # Champion name/slug matching: accept slug or name (case-insensitive)
    champ_query = h.get("champion")
    if champ_query:
        q = str(champ_query).lower()
        # exact slug or name match preferred
        if q != slug and q != name:
            # allow partial name match as fallback
            if q not in name and q not in slug:
                return False

    return True
