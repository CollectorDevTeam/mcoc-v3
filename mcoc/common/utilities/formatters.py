# Path: mcoc/common/formatters.py
# File-Version: 1.0
# File-Id: 56127cd0-45de-48d5-9a9f-3d8ab2754f64
# Purpose: Provide utility functions for formatting champion and prestige lines in MCOC bot context.
# Public-API: format_champion_line, format_top5_prestige_line
# Last-Modified: 2026-09-01
# Changelog:
#   1.0 2026-09-01  Initial stabilized API header

from typing import Dict, Any, Optional, Mapping, Union, List
from mcoc.common.helpers.types import CLASS_EMOJI, Champion, champion_from_dict, MCOCAPP_PROPERTIES
import re

ChampionLike = Union[Champion, Mapping[str, Any], None]


def _normalize_property_key(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")


def _resolve_tag_shortname(tag: Any) -> Optional[str]:
    key = _normalize_property_key(tag)
    if not key:
        return None
    tag_map = MCOCAPP_PROPERTIES.get("tags", {})
    if key in tag_map:
        return tag_map[key].get("short")
    for alias, meta in tag_map.items():
        if alias == key or key in alias.replace("_", " ") or alias.replace("_", " ") in key:
            return meta.get("short")
    return None


def _resolve_tag_longname(tag: Any) -> Optional[str]:
    key = _normalize_property_key(tag)
    if not key:
        return None
    tag_map = MCOCAPP_PROPERTIES.get("tags", {})
    if key in tag_map:
        return tag_map[key].get("long")
    for alias, meta in tag_map.items():
        if alias == key or key in alias.replace("_", " ") or alias.replace("_", " ") in key:
            return meta.get("long")
    return None


def format_tierlist_property_tokens(champ: ChampionLike, *, long_labels: bool = False) -> List[str]:
    """Return a short or long token list for tierlist display using MCOCAPP_PROPERTIES."""
    champion = _normalize_champ_obj(champ)
    raw = {}
    if isinstance(champ, Mapping):
        raw = dict(champ)
    elif champion is not None and isinstance(getattr(champion, "raw", None), Mapping):
        raw = dict(champion.raw)
    elif champion is not None and isinstance(champ, dict):
        raw = dict(champ)

    items: List[str] = []
    if not raw:
        return items

    for key in ("awakened", "high_sig", "no7star"):
        enabled = bool(raw.get(key, False))
        if enabled:
            meta = MCOCAPP_PROPERTIES.get(key)
            if meta:
                items.append(str((meta.get("long") if long_labels else meta.get("short")) or meta.get("long") or meta.get("short") or key.upper()))

    for tag in raw.get("tags", []) or []:
        if long_labels:
            label = _resolve_tag_longname(tag)
        else:
            label = _resolve_tag_shortname(tag)
        if label:
            items.append(label)
    if not items:
        for tag in raw.get("tags", []) or []:
            tag_text = str(tag).strip()
            if tag_text:
                items.append(tag_text)
    return items


def format_tierlist_champion_line(champ: ChampionLike, *, long_labels: bool = False) -> str:
    """Display a tierlist row, optionally using long property labels for wider pages."""
    champion = _normalize_champ_obj(champ)
    if isinstance(champ, Mapping):
        raw = dict(champ)
    elif champion is not None and isinstance(getattr(champion, "raw", None), Mapping):
        raw = dict(champion.raw)
    else:
        raw = {}

    if not raw and champion is None:
        return "Unknown"

    name = str(raw.get("name") or getattr(champion, "name", None) or getattr(champion, "slug", None) or "Unknown")
    tier = raw.get("tier") if raw else getattr(champion, "tier", None)
    score = raw.get("score") if raw else None
    if score is None and champion is not None:
        score = getattr(champion, "raw", {}).get("score") if isinstance(getattr(champion, "raw", None), Mapping) else None

    score_text = score if score is not None else 0
    property_tokens = format_tierlist_property_tokens(raw if raw else champion, long_labels=long_labels)
    if not property_tokens:
        token_text = "—"
    else:
        token_text = ", ".join(property_tokens)

    if long_labels:
        return f"{name} | {score_text} | {token_text}"

    tier_text = str(tier or "Unranked")
    return f"{name} | score {score_text} | {token_text}"


def format_tierlist_champion_detail(champ: ChampionLike) -> Dict[str, str]:
    """Return long-form property/tag strings used by the champion tierlist embed."""
    champion = _normalize_champ_obj(champ)
    if champion is None:
        return {"properties": "None", "tags": "None"}

    raw = champion.raw if isinstance(champion.raw, Mapping) else {}
    properties: List[str] = []

    for key in ("awakened", "high_sig", "no7star"):
        val = bool(raw.get(key)) if key in raw else False
        if val:
            meta = MCOCAPP_PROPERTIES.get(key)
            if meta:
                properties.append(f"{meta.get('long', key.upper())}")

    tag_text = []
    for tag in raw.get("tags", []) or []:
        meta = MCOCAPP_PROPERTIES.get("tags", {}).get(_normalize_property_key(tag))
        if meta:
            tag_text.append(str(meta.get("long") or tag))
        else:
            tag_text.append(str(tag))

    return {
        "properties": ", ".join(properties) if properties else "None",
        "tags": ", ".join(tag_text) if tag_text else "None",
    }


def _normalize_champ_obj(champ_obj: ChampionLike) -> Optional[Champion]:
    if isinstance(champ_obj, Champion):
        return champ_obj
    try:
        return champion_from_dict(champ_obj or {})
    except Exception:
        return None


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
    prestige = _normalize_prestige(entry.get("prestige"))

    asc_emoji = f"A{asc}" if asc > 0 else ""

    star_glyph = "★"
    star_display = f"{rarity}{star_glyph}"

    sig_text = f"s{sig}" if sig else "s0"

    cls_emoji = CLASS_EMOJI.get(cls, CLASS_EMOJI["all"])

    return f"{cls_emoji} {star_display} {name} r{rank} {sig_text} {asc_emoji} [{prestige}]".strip()


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
