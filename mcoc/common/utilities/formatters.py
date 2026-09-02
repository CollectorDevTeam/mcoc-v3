# Path: mcoc/common/formatters.py
# File-Version: 1.0
# File-Id: 56127cd0-45de-48d5-9a9f-3d8ab2754f64
# Purpose: Provide utility functions for formatting champion and prestige lines in MCOC bot context.
# Public-API: format_champion_line, format_top5_prestige_line
# Last-Modified: 2026-09-01
# Changelog:
#   1.0 2026-09-01  Initial stabilized API header

from typing import Dict, Any, Optional, Mapping, Union
from mcoc.common.helpers.types import Champion, champion_from_dict
import re

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


def _normalize_prestige(value: Any) -> int:
    """
    Accepts ints or strings like 'P12345' or '12345' and returns an int.
    Non-numeric content is stripped; fallback to 0.
    """
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        try:
            return int(value)
        except Exception:
            return 0
    s = str(value).strip()
    # strip leading non-digits (e.g., 'P12345') and any commas
    m = re.search(r"(\d[\d,]*)", s)
    if not m:
        return 0
    digits = m.group(1).replace(",", "")
    try:
        return int(digits)
    except Exception:
        return 0


def format_champion_line(champ_obj: ChampionLike, entry: Dict[str, Any]) -> str:
    """
    champ_obj: champion metadata from cache (may be None or dict)
    entry: canonical entry dict with keys: champion (slug), rarity, rank, sig, ascended
    Returns: formatted string like:
      "<:skill:...> 7★ Colossus r1 s0 A1"
    """
    champ = _normalize_champ_obj(champ_obj)

    # name resolution: prefer dataclass name, then slug, then entry raw
    name = None
    if champ:
        name = getattr(champ, "name", None) or getattr(champ, "slug", None)
    name = name or entry.get("raw") or entry.get("champion") or "Unknown"

    # class resolution: support multiple possible field names
    cls = ""
    if champ:
        cls = (
            getattr(champ, "class_name", None)
            or getattr(champ, "class_", None)
            or getattr(champ, "class", None)
            or getattr(champ, "cls", None)
            or ""
        )
    cls = (cls or "").lower()

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


def format_top5_prestige_line(champ_obj: Optional[Champion], entry: Dict[str, Any]) -> str:
    """
    champ_obj: champion metadata from cache (may be None or Champion dataclass)
    entry: canonical entry dict with keys: champion (slug), rarity, rank, sig, ascended, prestige
    Returns: formatted string like:
      "<:skill:...> 7★ Colossus r1 s0 [12,345]"
    """
    # normalize champ_obj (Champion dataclass or dict)
    champ = _normalize_champ_obj(champ_obj)

    # name resolution: prefer dataclass name, then slug, then entry raw
    name = None
    if champ:
        name = getattr(champ, "name", None) or getattr(champ, "slug", None)
    name = name or entry.get("raw") or entry.get("champion") or "Unknown"

    # champion class resolution: support multiple possible field names
    cls = ""
    if champ:
        cls = (
            getattr(champ, "class_name", None)
            or getattr(champ, "class_", None)
            or getattr(champ, "class", None)
            or getattr(champ, "cls", None)
            or ""
        )
    cls = (cls or "").lower()

    # stars / rarity
    rarity = _safe_int(entry.get("rarity") or entry.get("stars") or 6)
    sig = _safe_int(entry.get("sig") or 0)
    rank = _safe_int(entry.get("rank") or 1)
    asc = _safe_int(entry.get("ascended") or 0)

    asc_emoji = f"A{asc}" if asc > 0 else ""

    star_glyph = "★"
    star_display = f"{rarity}{star_glyph}"

    sig_text = f"s{sig}" if sig else "s0"

    cls_emoji = CLASS_EMOJI.get(cls, CLASS_EMOJI["all"])

    # sanitize prestige (handles "P12345" and strings)
    prestige_val = _normalize_prestige(entry.get("prestige"))
    prestige_text = f"{prestige_val:,}" if prestige_val > 0 else ""

    base_line = f"{cls_emoji} {star_display} {name} r{rank} {sig_text} {asc_emoji}".strip()
    if prestige_text:
        return f"{base_line} [{prestige_text}]"
    return base_line
