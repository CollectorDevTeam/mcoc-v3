# mcoc/common/formatters.py
from typing import Dict, Any, Optional, Mapping, Union
from mcoc.common.types import Champion, champion_from_dict

ChampionLike = Union[Champion, Mapping[str, Any], None]


def _normalize_champ_obj(champ_obj: ChampionLike) -> Optional[Champion]:
    if isinstance(champ_obj, Champion):
        return champ_obj
    try:
        return champion_from_dict(champ_obj or {})
    except Exception:
        return None


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


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def format_champion_line(champ_obj: ChampionLike, entry: Dict[str, Any]) -> str:
    """
    champ_obj: champion metadata from cache (may be None or dict)
    entry: canonical entry dict with keys: champion (slug), rarity, rank, sig, ascended
    Returns: formatted string like:
      "<:skill:...> 7★ Colossus r1 s0 A1"
    """
    champ = _normalize_champ_obj(champ_obj)

    name = champ.name if champ and champ.name else entry.get("champion") or "Unknown"
    cls = (champ.class_name or "").lower() if champ else ""

    # stars / rarity
    rarity = _safe_int(entry.get("rarity") or entry.get("stars"), 6)
    sig = _safe_int(entry.get("sig"), 0)
    rank = _safe_int(entry.get("rank"), 1)
    asc = _safe_int(entry.get("ascended") or entry.get("asc"), 0)

    asc_emoji = f"A{asc}" if asc > 0 else ""

    star_glyph = "★"
    star_display = f"{rarity}{star_glyph}"

    sig_text = f"s{sig}" if sig else "s0"

    cls_emoji = CLASS_EMOJI.get(cls, CLASS_EMOJI["all"])

    return f"{cls_emoji} {star_display} {name} r{rank} {sig_text} {asc_emoji}".strip()


def format_top5_prestige_line(champ_obj: ChampionLike, entry: Dict[str, Any]) -> str:
    """
    champ_obj: champion metadata from cache (may be None or dict)
    entry: canonical entry dict with keys: champion (slug), rarity, rank, sig, ascended, prestige
    Returns: formatted string like:
      "<:skill:...> 7★ Colossus r1 s0 A1 [P123]"
    """
    champ = _normalize_champ_obj(champ_obj)

    name = champ.name if champ and champ.name else entry.get("champion") or "Unknown"
    cls = (champ.class_name or "").lower() if champ else ""

    rarity = _safe_int(entry.get("rarity") or entry.get("stars"), 6)
    sig = _safe_int(entry.get("sig"), 0)
    rank = _safe_int(entry.get("rank"), 1)
    asc = _safe_int(entry.get("ascended") or entry.get("asc"), 0)

    asc_emoji = f"A{asc}" if asc > 0 else ""

    star_glyph = "★"
    star_display = f"{rarity}{star_glyph}"

    sig_text = f"s{sig}" if sig else "s0"

    cls_emoji = CLASS_EMOJI.get(cls, CLASS_EMOJI["all"])
    prestige = _safe_int(entry.get("prestige"), 0)
    prestige_text = f"P{prestige}" if prestige > 0 else ""

    base_line = f"{cls_emoji} {star_display} {name} r{rank} {sig_text} {asc_emoji}".strip()
    if prestige_text:
        return f"{base_line} [{prestige_text}]"
    return base_line
