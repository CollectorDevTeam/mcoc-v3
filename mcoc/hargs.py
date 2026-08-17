import re

RARITY_RE = re.compile(r"(?P<rarity>[1-7])\*")
RANK_RE = re.compile(r"r(?P<rank>[1-9])")
SIG_RE = re.compile(r"s(?P<sig>[0-9]{1,3})")
ASC_RE = re.compile(r"a(?P<asc>[0-9])")
TAG_RE = re.compile(r"#(?P<tag>[a-zA-Z0-9_]+)")
NOT_TAG_RE = re.compile(r"!(?P<tag>[a-zA-Z0-9_]+)")

CLASSES = {
    "skill", "mutant", "tech", "cosmic", "mystic", "science", "all"
}

def parse_hargs(text: str):
    parts = text.lower().split()

    result = {
        "champion": None,
        "rarities": [],
        "ranks": [],
        "sigs": [],
        "ascended": [],
        "tags": [],
        "not_tags": [],
        "classes": []
    }

    for part in parts:
        # rarity union
        m = RARITY_RE.search(part)
        if m:
            result["rarities"].append(int(m.group("rarity")))
            # continue (but allow combined forms)
        
        # rank union
        m = RANK_RE.search(part)
        if m:
            result["ranks"].append(int(m.group("rank")))
        
        # ascension
        m = ASC_RE.search(part)
        if m:
            result["ascended"].append(int(m.group("asc")))
        
        # sig union
        m = SIG_RE.search(part)
        if m:
            result["sigs"].append(int(m.group("sig")))
        
        # tag intersection
        m = TAG_RE.search(part)
        if m:
            result["tags"].append(m.group("tag"))
            continue

        # negation
        m = NOT_TAG_RE.search(part)
        if m:
            result["not_tags"].append(m.group("tag"))
            continue

        # class filter
        if part in CLASSES:
            result["classes"].append(part)
            continue

        # champion name fallback
        if not any(x in part for x in ["*", "r", "s", "a", "#", "!"]):
            result["champion"] = part

    return result
