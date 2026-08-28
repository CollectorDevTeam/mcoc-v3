# mcoc/common/formatters.py
from typing import Dict, Any, Optional

CLASS_EMOJI = {
    "all": "<:allclasses:748808348996075540>",
    "tech": "<:tech:748808546283683870>",
    "skill": "<:skill:748809095456227389>",
    "mutant": "<:mutant:748808841465954304>",
    "mystic": "<:mystic:748808953701335080>",
    "cosmic": "<:cosmic:748808707328180265>",
    "science": "<:science:748809185398882404>",
    "ascended": "<:ascend:1137124043506585691>"
}

def format_champion_line(champ_obj: Optional[Dict[str, Any]], entry: Dict[str, Any]) -> str:
    """
    champ_obj: champion metadata from cache (may be None)
    entry: canonical entry dict with keys: champion (slug), rarity, rank, sig, ascended
    Returns: formatted string like:
      "<:skill:...> 7A1 7★ Colossus r1 s0"
    """
    # resolve display pieces
    name = None
    cls = ""
    if champ_obj:
        name = champ_obj.get("name") or champ_obj.get("slug")
        cls = (champ_obj.get("class") or "").lower()
    name = name or entry.get("champion") or "Unknown"

    # stars / rarity
    rarity = int(entry.get("rarity") or entry.get("stars") or 6)
    sig = int(entry.get("sig") or 0)
    rank = int(entry.get("rank") or 1)
    asc = int(entry.get("ascended") or 0)

    if asc > 0:
        asc_emoji = CLASS_EMOJI.get("ascended", "")
    else:
        asc_emoji = ""

    # star display: use a star glyph and show rarity number before it
    star_glyph = "★"
    star_display = f"{rarity}{star_glyph}"

    # signature icon optional: keep s<sig> always
    sig_text = f"s{sig}" if sig else "s0"

    # class emoji
    cls_emoji = CLASS_EMOJI.get(cls, CLASS_EMOJI["all"])

    # final line
    # return f"{cls_emoji} {star_display} {name} r{rank} {sig_text} {asc_emoji}"
    return f"{cls_emoji} {star_display} {name} r{rank} {sig_text} A{asc}"

def format_champion_prestige_line(champ_obj: Optional[Dict[str, Any]], entry: Dict[str, Any]) -> str:
    """
    champ_obj: champion metadata from cache (may be None)
    entry: canonical entry dict with keys: champion (slug), rarity, rank, sig, ascended, prestige
    Returns: formatted string like:
      "<:skill:...> 7A1 7★ Colossus r1 s0 P3"
    """
     name = None
    cls = ""
    if champ_obj:
        name = champ_obj.get("name") or champ_obj.get("slug")
        cls = (champ_obj.get("class") or "").lower()
    name = name or entry.get("champion") or "Unknown"

    # stars / rarity
    rarity = int(entry.get("rarity") or entry.get("stars") or 6)
    sig = int(entry.get("sig") or 0)
    rank = int(entry.get("rank") or 1)
    asc = int(entry.get("ascended") or 0)

    if asc > 0:
        asc_emoji = CLASS_EMOJI.get("ascended", "")
    else:
        asc_emoji = ""

    # star display: use a star glyph and show rarity number before it
    star_glyph = "★"
    star_display = f"{rarity}{star_glyph}"

    # signature icon optional: keep s<sig> always
    sig_text = f"s{sig}" if sig else "s0"

    # class emoji
    cls_emoji = CLASS_EMOJI.get(cls, CLASS_EMOJI["all"])
    prestige = int(entry.get("prestige") or 0)
    if prestige > 0:
        prestige_text = f"P{prestige}"
    else:
        prestige_text = ""
    base_line = f"{cls_emoji} {star_display} {name} r{rank} {sig_text} {asc_emoji}"
    return f"{base_line} [{prestige_text}]".strip()