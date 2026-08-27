# mcoc/hargs.py
import re
from typing import Dict, Any, List, Optional, Tuple

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

# New, more flexible component regexes for single-token Hargs parsing
# Note: SIG_RE2 looks for 's' followed by digits (signature). We intentionally
# match signature first to avoid confusing a bare 's' star marker with signature.
SIG_RE2 = re.compile(r"s(?P<sig>\d{1,3})", re.IGNORECASE)
ASC_RE2 = re.compile(r"a(?P<asc>\d)", re.IGNORECASE)
RANK_RE2 = re.compile(r"r(?P<rank>[1-5])", re.IGNORECASE)
# Rarity digit 1-7; may be followed by '*' or '★' or a bare 's' (star marker).
RARITY_DIGIT_RE = re.compile(r"(?P<rarity>[1-7])(?=(?:\*|★|\s|[rR]|[aA]|$))")

# Defaults for harg parsing (as requested)
DEFAULT_RARITY = 7
DEFAULT_RANK = 1
DEFAULT_ASCENDED = 0
DEFAULT_SIG = 0


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


# -----------------------------
# New helpers for Hargs lists
# -----------------------------
def _strip_nonname_edges(s: str) -> str:
    """Trim separators and stray punctuation from ends of a candidate name."""
    return re.sub(r"^[\s\-\_\,\:\;]+|[\s\-\_\,\:\;]+$", "", s).strip()


def _extract_name_by_removing_components(token: str, components: List[Tuple[int, int]]) -> str:
    """
    Given a token and a list of (start, end) spans that correspond to matched
    harg components, remove those spans and return the remaining string as the name.
    """
    if not components:
        return token.strip()
    pieces = []
    last = 0
    for (s, e) in sorted(components):
        if last < s:
            pieces.append(token[last:s])
        last = e
    if last < len(token):
        pieces.append(token[last:])
    name = "".join(pieces).strip()
    return _strip_nonname_edges(name)


def parse_harg_token(token: str) -> Dict[str, Any]:
    """
    Parse a single compact Hargs token into a structured entry.

    Accepts both ChampionHargs (name then hargs) and HargsChampion (hargs then name),
    and many concatenated forms. Returns a dict:
      {
        "champion": Optional[str],
        "rarity": int,
        "rank": int,
        "ascended": int,
        "sig": int,
        "raw": original_token
      }

    Defaults: rarity=6, rank=1, ascended=1, sig=0
    """
    t = token.strip()
    if not t:
        return {
            "champion": None,
            "rarity": DEFAULT_RARITY,
            "rank": DEFAULT_RANK,
            "ascended": DEFAULT_ASCENDED,
            "sig": DEFAULT_SIG,
            "raw": token,
        }

    # Work on a copy for destructive matching
    working = t
    components_spans: List[Tuple[int, int]] = []

    # 1) Signature: 's' followed by digits (prefer this first)
    sig = None
    for m in SIG_RE2.finditer(working):
        try:
            sig = int(m.group("sig"))
            components_spans.append(m.span())
            break
        except Exception:
            continue

    # 2) Ascension: 'A' followed by digit
    asc = None
    for m in ASC_RE2.finditer(working):
        try:
            asc = int(m.group("asc"))
            components_spans.append(m.span())
            break
        except Exception:
            continue

    # 3) Rank: 'r' followed by 1-5
    rank = None
    for m in RANK_RE2.finditer(working):
        try:
            rank = int(m.group("rank"))
            components_spans.append(m.span())
            break
        except Exception:
            continue

    # 4) Rarity digit 1-7 (take first occurrence not part of a name)
    rarity = None
    # Prefer explicit markers first: digit followed by '*' or '★'
    m = re.search(r"(?P<rarity>[1-7])(?:\*|★)", working)
    if m:
        try:
            rarity = int(m.group("rarity"))
            components_spans.append(m.span())
        except Exception:
            rarity = None
    else:
        # fallback: accept a bare digit only if it's clearly a rarity (not embedded in a name)
        for m in RARITY_DIGIT_RE.finditer(working):
            try:
                # ensure the digit isn't part of an alphanumeric run (e.g., "X7" inside a name)
                s, e = m.span()
                left = working[s-1] if s-1 >= 0 else ""
                right = working[e] if e < len(working) else ""
                if (left.isalpha() and left.islower()) and (right.isalpha() and right.islower()):
                    # looks like part of a name, skip
                    continue
                rarity = int(m.group("rarity"))
                components_spans.append(m.span())
                break
            except Exception:
                continue

    # Build champion name by removing matched spans
    name_candidate = _extract_name_by_removing_components(working, components_spans)
    # If name_candidate is empty or looks like pure punctuation, try alternative heuristics:
    if not name_candidate or all(ch in "0123456789rRsSaA*★_ -.,;:" for ch in name_candidate):
        # Try to find an alphabetic run inside the token
        mname = re.search(r"[A-Za-z][A-Za-z0-9 '\-\.]{0,80}", working)
        if mname:
            name_candidate = mname.group(0).strip()

    if not name_candidate:
        # try to find an alphabetic run anywhere (handles concatenated tokens)
        mname = re.search(r"[A-Za-z][A-Za-z0-9 '\-\.]{0,80}", working)
        if mname:
            name_candidate = mname.group(0).strip()


    # Normalize values with defaults and bounds
    final_rarity = rarity if (isinstance(rarity, int) and 1 <= rarity <= 7) else DEFAULT_RARITY
    final_rank = rank if (isinstance(rank, int) and 1 <= rank <= 5) else DEFAULT_RANK
    final_asc = asc if (isinstance(asc, int) and 0 <= asc <= 2) else DEFAULT_ASCENDED
    final_sig = sig if (isinstance(sig, int) and sig >= 0) else DEFAULT_SIG

    # Additional validation for sig ranges by tier could be applied by roster helpers.
    return {
        "champion": name_candidate if name_candidate else None,
        "rarity": final_rarity,
        "rank": final_rank,
        "ascended": final_asc,
        "sig": final_sig,
        "raw": token,
    }


def parse_harg_list(text: str) -> List[Dict[str, Any]]:
    """
    Parse a text containing one or more ChampionHargs / HargsChampion / plain champion tokens.

    Splits on commas/semicolons and preserves quoted names. Returns a list of parsed
    entries (each as returned by parse_harg_token).

    Examples accepted:
      - "blackbolt6sr1, blackbolt7A1r2"
      - "6r1s0blackbolt; 6A2r2blackbolt"
      - '6r1 "Black Bolt", 7A1r2 "Spider Man"'
      - "blackbolt6s, blackbolt"  (defaults applied)
    """
    if not text:
        return []

    parts = _tokenize_preserving_quotes(text.strip())
    out: List[Dict[str, Any]] = []
    for part in parts:
        if not part:
            continue
        parsed = parse_harg_token(part)
        out.append(parsed)
    return out


# -----------------------------
# Existing parse_hargs (filters)
# -----------------------------
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
