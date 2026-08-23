# mcoc/hargs.py
import re
from typing import Dict, Any, List

# Patterns accept both '*' and '★' for rarity and allow ranges like 1-3
RARITY_RE = re.compile(r"(?P<rarity>\d(?:-\d)?)\s*(?:\*|★)")
RANK_RE = re.compile(r"r(?P<rank>\d(?:-\d)?)\b", re.IGNORECASE)
SIG_RE = re.compile(r"s(?P<sig>\d{1,4})\b", re.IGNORECASE)
ASC_RE = re.compile(r"a(?P<asc>\d)\b", re.IGNORECASE)
TAG_RE = re.compile(r"#(?P<tag>[a-zA-Z0-9_]+)")
NOT_TAG_RE = re.compile(r"!(?P<tag>[a-zA-Z0-9_]+)")

CLASSES = {"skill", "mutant", "tech", "cosmic", "mystic", "science", "all"}

# Inline compact hargs regex (matches 6*r4s40A1, 6r4s40A1, 6sr4 etc.)
INLINE_HARGS_RE = re.compile(
    r"(?P<stars>[1-9])[\*\s★]?[sS]?[\*\s]?[rR]?(?P<rank>\d{1,2})(?:[sS](?P<sig>\d{1,4}))?(?:[aA](?P<asc>\d))?"
)

def _expand_range_token(tok: str) -> List[int]:
    """Expand a token like '1-3' into [1,2,3] or single number into [n]."""
    if "-" in tok:
        try:
            a, b = tok.split("-", 1)
            a_i = int(a)
            b_i = int(b)
            if a_i > b_i:
                a_i, b_i = b_i, a_i
            return list(range(a_i, b_i + 1))
        except Exception:
            return []
    try:
        return [int(tok)]
    except Exception:
        return []

def _tokenize_preserving_quotes(text: str) -> List[str]:
    """
    Split text into tokens but preserve quoted phrases as single tokens.
    Also treat commas and semicolons as separators.
    Examples:
      '5* "Spider Man" r3 #attack' -> ['5*', 'Spider Man', 'r3', '#attack']
      'Angela 6*r4s40, Black Bolt 6*r1' -> ['Angela 6*r4s40', 'Black Bolt 6*r1']
    """
    tokens: List[str] = []
    cur = []
    in_quote = False
    quote_char = None
    i = 0
    while i < len(text):
        ch = text[i]
        if in_quote:
            if ch == quote_char:
                tokens.append("".join(cur).strip())
                cur = []
                in_quote = False
                quote_char = None
            else:
                cur.append(ch)
        else:
            if ch in ('"', "'"):
                in_quote = True
                quote_char = ch
            elif ch.isspace():
                if cur:
                    tokens.append("".join(cur).strip())
                    cur = []
            elif ch in (",", ";"):
                if cur:
                    tokens.append("".join(cur).strip())
                    cur = []
            else:
                cur.append(ch)
        i += 1
    if cur:
        tokens.append("".join(cur).strip())
    return tokens

def parse_hargs(text: str) -> Dict[str, Any]:
    """
    Parse a human argument string into structured filters.

    Returns dict with keys:
      champion Optional[str]
      rarities List[int]
      ranks List[int]
      sigs List[int]
      ascended List[int]
      tags List[str]
      not_tags List[str]
      classes List[str]

    Supports:
      - Quoted multiword champion names
      - Tokenized flags: 6*, r4, s40, a1, #tag, !tag
      - Inline concatenated forms: 6*r4s40A1, 6r4Angela, Angela6r4s40A1
      - Ranges: 3-5*
    """
    if not text:
        return {
            "champion": None,
            "rarities": [],
            "ranks": [],
            "sigs": [],
            "ascended": [],
            "tags": [],
            "not_tags": [],
            "classes": [],
        }

    parts = _tokenize_preserving_quotes(text.strip())

    result = {
        "champion": None,
        "rarities": [],
        "ranks": [],
        "sigs": [],
        "ascended": [],
        "tags": [],
        "not_tags": [],
        "classes": [],
    }

    for part in parts:
        p = part.strip()
        if not p:
            continue

        lowered = p.lower()

        # Tag negation and tag (exact match)
        m = NOT_TAG_RE.fullmatch(p) or NOT_TAG_RE.search(p)
        if m:
            result["not_tags"].append(m.group("tag").lower())
            continue

        m = TAG_RE.fullmatch(p) or TAG_RE.search(p)
        if m:
            result["tags"].append(m.group("tag").lower())
            continue

        # Class filter (exact token match)
        if lowered in CLASSES:
            result["classes"].append(lowered)
            continue

        # Rarity like '5*' or '3-5*' or '5★'
        m = RARITY_RE.search(p)
        if m:
            tok = m.group("rarity")
            for n in _expand_range_token(tok):
                if 1 <= n <= 7:
                    result["rarities"].append(n)
            # continue parsing other possible flags in same token

        # Rank like 'r3' or 'r1-3'
        m = RANK_RE.search(p)
        if m:
            tok = m.group("rank")
            for n in _expand_range_token(tok):
                if 1 <= n <= 9:
                    result["ranks"].append(n)

        # Ascension like 'a1' (token form)
        m = ASC_RE.search(p)
        if m:
            try:
                n = int(m.group("asc"))
                result["ascended"].append(n)
            except Exception:
                pass

        # Signature like 's50' (token form)
        m = SIG_RE.search(p)
        if m:
            try:
                n = int(m.group("sig"))
                result["sigs"].append(n)
            except Exception:
                pass

        # If token is quoted or contains spaces and not matched above, treat as champion name
        if ((" " in p) or (p.startswith('"') or p.startswith("'"))):
            if result["champion"] is None:
                result["champion"] = p.strip('"').strip("'")
            continue

        # Fallback champion name detection: token without special characters
        if not any(ch in p for ch in "*★rs#a!"):
            if result["champion"] is None:
                result["champion"] = p
            continue

    # If still no champion found, attempt inline compact extraction from original text
    if result["champion"] is None:
        m = INLINE_HARGS_RE.search(text)
        if m:
            start, end = m.span()
            name_part = (text[:start] + text[end:]).strip()
            name_part = name_part.strip().strip('"').strip("'")
            name_part = re.sub(r"^[\s\-\_\,]+|[\s\-\_\,]+$", "", name_part)
            if name_part:
                result["champion"] = name_part

            # populate parsed values from inline match if not already present
            try:
                if m.group("stars") and not result["rarities"]:
                    result["rarities"].append(int(m.group("stars")))
                if m.group("rank") and not result["ranks"]:
                    result["ranks"].append(int(m.group("rank")))
                if m.group("sig") and not result["sigs"]:
                    result["sigs"].append(int(m.group("sig")))
                if m.group("asc") and not result["ascended"]:
                    result["ascended"].append(int(m.group("asc")))
            except Exception:
                pass

    # Normalize and deduplicate lists while preserving order
    def _uniq(seq: List[Any]) -> List[Any]:
        seen = set()
        out = []
        for x in seq:
            if x is None:
                continue
            if isinstance(x, str):
                key = x.lower()
            else:
                key = x
            if key in seen:
                continue
            seen.add(key)
            out.append(x)
        return out

    result["rarities"] = _uniq(result["rarities"])
    result["ranks"] = _uniq(result["ranks"])
    result["sigs"] = _uniq(result["sigs"])
    result["ascended"] = _uniq(result["ascended"])
    result["tags"] = _uniq([t.lower() for t in result["tags"]])
    result["not_tags"] = _uniq([t.lower() for t in result["not_tags"]])
    result["classes"] = _uniq([c.lower() for c in result["classes"]])

    # Champion name normalization: strip quotes if present
    if isinstance(result["champion"], str):
        result["champion"] = result["champion"].strip().strip('"').strip("'")

    return result
