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
    """Champion entry from the mcoc.app tierlist JSON."""

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
    portrait: str = ""
    immunities: List[Union[str, MCOCAppImmunity]] = Field(default_factory=list)
    inflicts: List[str] = Field(default_factory=list)
    class_rank: int = 0

    @model_validator(mode="before")
    @classmethod
    def normalize_aliases(cls, values: Any) -> Any:
        if isinstance(values, dict):
            if "class_name" not in values and "class_" in values and "class" not in values:
                values["class"] = values["class_"]
            if "class_name" not in values and "class" in values:
                values["class_name"] = values["class"]
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

    @field_validator("immunities", mode="before")
    @classmethod
    def coerce_immunities(cls, value: Any) -> List[Union[str, MCOCAppImmunity]]:
        if value is None:
            return []
        if not isinstance(value, list):
            return [value]
        normalized: List[Union[str, MCOCAppImmunity]] = []
        for item in value:
            if isinstance(item, dict):
                normalized.append(MCOCAppImmunity.model_validate(item))
            else:
                normalized.append(str(item))
        return normalized


class TierList(BaseModel):
    champions: List[MCOCAppTierlistChampion] = Field(default_factory=list)


Immunity = MCOCAppImmunity
Champion = MCOCAppTierlistChampion
