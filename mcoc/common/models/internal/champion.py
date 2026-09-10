# Path: mcoc/common/models/internal/champion.py
# File-Version: 1.0
# File-Id: 9f9b2a6e-8c4b-4f2a-9d2b-1a2b3c4d5e6f
# Purpose: Internal canonical champion model used by bot logic and cache
# Public-API: CollectorBotChampion
# Internal: None
# Uses: typing, pydantic
# Used-By: common/helpers/champion_index.py
# Last-Modified: 2026-09-07
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _dedupe_strings(values: Optional[Iterable[Any]]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for value in values or []:
        if value is None:
            continue
        if isinstance(value, dict):
            candidate = value.get("name") or value.get("title") or value.get("id") or value.get("text")
        else:
            candidate = value
        text = str(candidate).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


class CollectorBotChampion(BaseModel):
    """Internal canonical champion model used by bot logic and cache."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: Optional[str] = None
    slug: Optional[str] = None
    name: Optional[str] = None
    title: Optional[str] = None
    class_name: Optional[str] = Field(default=None, alias="class")
    class_: Optional[str] = None
    tier: Optional[str] = None
    rarity: Optional[int] = None
    stars: Optional[int] = None
    rank: Optional[int] = None
    sig: Optional[int] = None
    ascended: Optional[int] = None
    tags: List[str] = Field(default_factory=list)
    aliases: List[str] = Field(default_factory=list)
    image_url: Optional[str] = None
    images: Optional[Dict[str, Any]] = None
    ability_tags: List[str] = Field(default_factory=list)
    abilities: List[Dict[str, Any]] = Field(default_factory=list)
    synergies: List[Dict[str, Any]] = Field(default_factory=list)
    signature: Optional[Dict[str, Any]] = None
    rotation_data: Optional[Dict[str, Any]] = None
    immunities: List[Dict[str, Any]] = Field(default_factory=list)
    raw: Optional[Dict[str, Any]] = None
    raw_sources: Dict[str, Any] = Field(default_factory=dict)
    source_map: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def normalize_aliases(cls, values: Any) -> Any:
        if isinstance(values, dict):
            if "class_name" not in values and "class" in values:
                values["class_name"] = values["class"]
            if "class_" not in values and values.get("class_name") is not None:
                values["class_"] = values["class_name"]
            if "ability_tags" not in values and "abilities" in values:
                values["ability_tags"] = _dedupe_strings(
                    [item.get("name") if isinstance(item, dict) else item for item in (values["abilities"] or [])]
                )
        return values

    @field_validator("class_name", mode="before")
    @classmethod
    def coerce_class_name(cls, value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("tags", mode="before")
    @classmethod
    def coerce_tags(cls, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value]
        return [str(value)]

    @field_validator("ability_tags", mode="before")
    @classmethod
    def coerce_ability_tags(cls, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return _dedupe_strings(value)
        return _dedupe_strings([value])

    @field_validator("immunities", mode="before")
    @classmethod
    def coerce_immunities(cls, value: Any) -> List[Dict[str, Any]]:
        if value is None:
            return []
        if isinstance(value, list):
            normalized: List[Dict[str, Any]] = []
            for item in value:
                if isinstance(item, dict):
                    normalized.append(dict(item))
                else:
                    normalized.append({"name": str(item)})
            return normalized
        if isinstance(value, dict):
            return [dict(value)]
        return [{"name": str(value)}]

    @property
    def normalized_slug(self) -> Optional[str]:
        return self.slug or self.id or (self.name.lower().replace(" ", "-") if self.name else None)

    @property
    def class_lower(self) -> Optional[str]:
        value = self.class_name or self.class_ or ""
        return str(value).lower() or None
# Used-By: None
