# Path: mcoc/common/models/mcochub/immunities.py
# File-Version: 1.1
# File-Id: 6f9b2a6e-8c4b-4f2a-9d2b-1a2b3c4d5e6f
# Purpose: Pydantic models for MCOCHub immunities and champion-level immunity entries
# Public-API: MCOCHubImmunity, ChampionImmunity, ImmunityList
# Internal: None
# Uses: typing, pydantic
# Used-By: mcoc/common/models/mcochub/champions.py, common/api/autocomplete_loader.py
# Last-Modified: 2026-09-10

from __future__ import annotations
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class MCOCHubImmunity(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")
    id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    champion_count: Optional[int] = None


class ChampionImmunity(BaseModel):
    """
    Champion-level immunity entry as seen in champion records.
    Example: {"name":"poison-immunity","type":"partial","note":"..."}
    """
    model_config = ConfigDict(populate_by_name=True, extra="allow")
    id: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None  # 'full' | 'partial' | 'conditional'
    note: Optional[str] = None
    conditional: bool = False

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip().lower()
        if text in {"full", "partial", "conditional"}:
            return text
        return text or None

    @model_validator(mode="before")
    @classmethod
    def map_type_to_conditional(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
        t = str(values.get("type") or "").strip().lower()
        if values.get("conditional") is None:
            if t == "partial":
                values["conditional"] = True
            elif t in {"full", "conditional"}:
                values["conditional"] = False if t == "full" else True
        return values


Immunity = MCOCHubImmunity


class ImmunityList(BaseModel):
    immunities: List[MCOCHubImmunity] = Field(default_factory=list)
