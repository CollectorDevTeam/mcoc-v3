# mcoc/common/query_parser.py
from typing import Any, Dict, List, Tuple, Optional

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
from .helpers.roster import parse_roster_entries_from_input
from .hargs import parse_hargs
from typing import Any, Dict, List, Tuple, Optional

def parse_query(text: Optional[str], cache: Any = None, **opts) -> Tuple[List[Dict[str,Any]], Dict[str,Any]]:
    text = (text or "").strip()
    entries: List[Dict[str,Any]] = []
    filters: Dict[str,Any] = {"tags": [], "classes": [], "name": None, "raw_text": text}

    # 1. quick tag extraction
    try:
        parsed_filters = parse_hargs(text) if text else {}
        filters["tags"] = parsed_filters.get("tags", [])
        filters["classes"] = parsed_filters.get("classes", [])
        if parsed_filters.get("champion"):
            filters["name"] = parsed_filters.get("champion")
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
