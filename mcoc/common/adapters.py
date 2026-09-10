from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional

from mcoc.common.models.cocpit.champion import AbilityEntry, ChampionData
from mcoc.common.models.internal.champion import CollectorBotChampion
from mcoc.common.models.mcochub.champions import MCOCHubChampion
from mcoc.common.models.mcoc_app.tierlist import MCOCAppTierlistChampion


def _slugify(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "item"


def _stable_id(*parts: Any) -> str:
    joined = "|".join(str(part or "") for part in parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:12]


def _to_ability_dict(value: Any, fallback_name: str = "ability") -> Dict[str, Any]:
    if isinstance(value, dict):
        name = value.get("name") or value.get("title") or value.get("id") or fallback_name
        kind = value.get("type")
        if kind is None and value.get("conditional") is not None:
            kind = "partial" if bool(value.get("conditional")) else "full"
        item = {
            "id": value.get("id") or _stable_id(name, kind or "ability"),
            "name": str(name),
            "type": kind,
            "source": value.get("source"),
            "synergy_with": value.get("synergy_with") or value.get("partners") or [],
            "note": value.get("note") or value.get("description") or value.get("text"),
        }
        if value.get("conditional") is not None:
            item["conditional"] = bool(value.get("conditional"))
        return item

    name = str(value)
    return {
        "id": _stable_id(name, "ability"),
        "name": name,
        "type": "full",
        "source": None,
        "synergy_with": [],
        "note": None,
    }


def _to_immunity_dict(value: Any, fallback_name: str = "immunity") -> Dict[str, Any]:
    if isinstance(value, dict):
        name = value.get("name") or value.get("type") or value.get("id") or fallback_name
        kind = value.get("type")
        conditional = value.get("conditional")
        if conditional is None and kind:
            conditional = kind.lower() == "partial"
        item = {
            "id": value.get("id") or _stable_id(name, kind or "immunity"),
            "name": str(name),
            "type": kind,
            "conditional": bool(conditional),
            "note": value.get("note") or value.get("description"),
        }
        return item

    name = str(value)
    return {
        "id": _stable_id(name, "immunity"),
        "name": name,
        "type": "full",
        "conditional": False,
        "note": None,
    }


def _extract_ability_entries(payload: Any) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    if not payload:
        return entries

    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if isinstance(value, dict):
                entries.extend(_extract_ability_entries(value))
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, AbilityEntry):
                        entries.append({
                            "id": item.id or _stable_id(key, item.text or "ability", len(entries)),
                            "name": item.text or key,
                            "type": "full",
                            "source": "cocpit",
                            "note": item.text,
                        })
                    elif isinstance(item, dict):
                        entries.append(_to_ability_dict(item, fallback_name=str(key)))
            elif isinstance(value, AbilityEntry):
                entries.append({
                    "id": value.id or _stable_id(key, value.text or "ability", len(entries)),
                    "name": value.text or key,
                    "type": "full",
                    "source": "cocpit",
                    "note": value.text,
                })
    elif isinstance(payload, list):
        for item in payload:
            if isinstance(item, AbilityEntry):
                entries.append({
                    "id": item.id or _stable_id(item.text or "ability", len(entries)),
                    "name": item.text or "ability",
                    "type": "full",
                    "source": "cocpit",
                    "note": item.text,
                })
            elif isinstance(item, dict):
                entries.append(_to_ability_dict(item))
    return entries


def mcochub_to_internal(raw: Mapping[str, Any]) -> CollectorBotChampion:
    champion = MCOCHubChampion.model_validate(raw)
    abilities = [
        _to_ability_dict(item.model_dump(exclude_none=True), fallback_name=item.name or "ability")
        if hasattr(item, "model_dump")
        else _to_ability_dict(item)
        for item in (champion.abilities or [])
    ]
    immunities = [
        _to_immunity_dict(item.model_dump(exclude_none=True), fallback_name=item.name or "immunity")
        if hasattr(item, "model_dump")
        else _to_immunity_dict(item)
        for item in (champion.immunities or [])
    ]

    record = CollectorBotChampion(
        id=champion.id,
        slug=_slugify(champion.name or champion.id),
        name=champion.name,
        class_name=champion.class_,
        tags=[str(tag) for tag in (champion.tags or [])],
        abilities=abilities,
        immunities=immunities,
        raw=raw,
        raw_sources={"mcochub": raw},
        source_map={"mcochub": champion.id or (champion.name or "")},
    )
    if record.class_ is None:
        record.class_ = record.class_name
    return record


def mcoc_app_tierlist_to_internal(raw: Mapping[str, Any], doc: Optional[Mapping[str, Any]] = None) -> CollectorBotChampion:
    payload = dict(raw or {})
    champions = payload.get("champions") if isinstance(payload, Mapping) and "champions" in payload else []
    if not champions:
        champion_entry = payload
    else:
        champion_entry = champions[0]

    if isinstance(champion_entry, Mapping):
        model = MCOCAppTierlistChampion.model_validate(champion_entry)
    else:
        model = MCOCAppTierlistChampion.model_validate({"name": str(champion_entry)})

    class_name = (
        champion_entry.get("class_name")
        or champion_entry.get("class")
        or getattr(model, "class_name", None)
        or getattr(model, "class_", None)
        or "unknown"
    )

    abilities = [{
        "id": _stable_id(name, "tierlist"),
        "name": str(name),
        "type": "full",
        "source": "mcoc_app_tierlist",
        "note": "mcoc.app tierlist inflict",
    } for name in (model.inflicts or [])]

    immunities = [_to_immunity_dict(item) for item in (model.immunities or [])]

    record = CollectorBotChampion(
        id=_slugify(model.name),
        slug=_slugify(model.name),
        name=model.name,
        class_name=str(class_name),
        tier=model.tier,
        tags=[str(tag) for tag in (model.tags or [])],
        abilities=abilities,
        immunities=immunities,
        raw=payload,
        raw_sources={"mcoc_app": payload},
        source_map={"mcoc_app": model.name},
    )
    if record.class_ is None:
        record.class_ = record.class_name
    return record


def cocpit_to_internal(raw: Mapping[str, Any]) -> CollectorBotChampion:
    data = ChampionData.model_validate(raw)
    flattened_abilities = _extract_ability_entries({
        "coreAbilities": data.coreAbilities,
        "sigAbilities": data.sigAbilities,
    })

    # The Cocpit payload is rich enough to be the canonical descriptive source; we also
    # preserve a few synthetic immunity entries so downstream callers can show filters.
    immunities = []
    for item in flattened_abilities:
        immunities.append({
            "id": _stable_id(item.get("name"), "cocpit-immunity"),
            "name": item.get("name"),
            "type": "full",
            "conditional": False,
            "note": item.get("note"),
        })

    champion_id = None
    if isinstance(raw, Mapping):
        attack_moves = raw.get("attackMoves") or {}
        if isinstance(attack_moves, Mapping):
            champion_id = attack_moves.get("id") or attack_moves.get("name")
    if not champion_id:
        champion_id = _slugify(raw.get("id") if isinstance(raw, Mapping) else "champion")

    record = CollectorBotChampion(
        id=champion_id,
        slug=_slugify(champion_id),
        name=str(champion_id).replace("-", " ").title(),
        class_name="unknown",
        tags=[],
        abilities=flattened_abilities,
        immunities=immunities,
        raw=raw,
        raw_sources={"cocpit": raw},
        source_map={"cocpit": champion_id},
    )
    if record.class_ is None:
        record.class_ = record.class_name
    return record


__all__ = [
    "mcochub_to_internal",
    "mcoc_app_tierlist_to_internal",
    "cocpit_to_internal",
]
