# Path: mcoc/common/models/mcoc_app/tierlist.py
# File-Version: 1.0
# File-Id: af9b2a6e-8c4b-4f2a-9d2b-1a2b3c4d5e6f
# Purpose: Pydantic models for mcoc.app tierlist JSON
# Public-API: MCOCAppImmunity, MCOCAppTierlistChampion, MCOCAppTierlistDocument, TierList, Immunity, Champion
# Internal: None
# Uses: typing, pydantic
# Used-By: common/helpers/champion_index.py
# Last-Modified: 2026-09-07
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class MCOCAppImmunity(BaseModel):
    """Normalized representation of an immunity entry from mcoc.app."""

    type: str
    conditional: bool = False
    description: Optional[str] = None

    @classmethod
    def from_value(cls, value: Union[str, Dict[str, Any], "MCOCAppImmunity"]) -> "MCOCAppImmunity":
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            return cls(type=value)
        if isinstance(value, dict):
            return cls.model_validate(value)
        raise TypeError(f"Unsupported immunity value: {value!r}")

class MCOCAppTierlistChampion(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    name: str
    class_name: Optional[str] = Field(default=None, alias="class")
    tier: Optional[str] = None
    score: float = 0.0
    awakened: bool = False
    high_sig: bool = False
    no7star: bool = False
    tags: List[str] = Field(default_factory=list)
    rank: int = 1
    portrait: Optional[str] = None
    immunities: List[MCOCAppImmunity] = Field(default_factory=list)
    inflicts: List[str] = Field(default_factory=list)
    class_rank: int = 0

    @model_validator(mode="before")
    @classmethod
    def normalize_aliases(cls, values: Any) -> Any:
        if isinstance(values, dict):
            # keep both "class" and "class_name" consistent
            if "class_name" not in values and "class" in values:
                values["class_name"] = values["class"]
            if "tier" in values and values["tier"] is not None:
                values["tier"] = str(values["tier"])
        return values

    @field_validator("score", mode="before")
    @classmethod
    def coerce_score(cls, value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @field_validator("tags", mode="before")
    @classmethod
    def coerce_tags(cls, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value]
        return [str(value)]

    @field_validator("portrait", mode="before")
    @classmethod
    def coerce_portrait(cls, value: Any) -> Optional[str]:
        # prefer None for missing portraits
        if value in (None, "", "null"):
            return None
        return str(value)

    @field_validator("immunities", mode="before")
    @classmethod
    def coerce_immunities(cls, value: Any) -> List[MCOCAppImmunity]:
        if value is None:
            return []
        if not isinstance(value, list):
            value = [value]
        normalized: List[MCOCAppImmunity] = []
        for item in value:
            if isinstance(item, MCOCAppImmunity):
                normalized.append(item)
            elif isinstance(item, dict):
                normalized.append(MCOCAppImmunity.model_validate(item))
            else:
                # string form -> wrap into object
                normalized.append(MCOCAppImmunity(type=str(item)))
        return normalized

    @field_validator("inflicts", mode="before")
    @classmethod
    def coerce_inflicts(cls, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(v) for v in value]
        return [str(value)]


class MCOCAppTierlistDocument(BaseModel):
    """Root tierlist document from mcoc.app.

    The live JSON is not just a flat champion list; it includes metadata that is useful
    for display and filtering (tag labels, immunity/debuff maps, tier ordering, and
    class metadata) while also carrying prestige data that we intentionally do not
    normalize into the active cache.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    champions: List[MCOCAppTierlistChampion] = Field(default_factory=list)
    tag_labels: Dict[str, Any] = Field(default_factory=dict)
    immunity_map: Dict[str, Any] = Field(default_factory=dict)
    immunity_types: List[str] = Field(default_factory=list)
    debuff_map: Dict[str, Any] = Field(default_factory=dict)
    debuff_types: List[str] = Field(default_factory=list)
    by_class: Dict[str, Any] = Field(default_factory=dict)
    tier_order: List[str] = Field(default_factory=list)
    tier_colors: Dict[str, str] = Field(default_factory=dict)
    class_colors: Dict[str, str] = Field(default_factory=dict)
    awakening_data: Dict[str, Any] = Field(default_factory=dict)
    sig_stones_data: Dict[str, Any] = Field(default_factory=dict)
    last_updated: Optional[str] = None
    total_champions: int = 0


TierList = MCOCAppTierlistDocument


Immunity = MCOCAppImmunity
Champion = MCOCAppTierlistChampion
# Used-By: None
