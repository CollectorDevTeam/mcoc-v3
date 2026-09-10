# Path: mcoc/common/models/mcochub/abilities.py
# File-Version: 1.0
# File-Id: 7f9b2a6e-8c4b-4f2a-9d2b-1a2b3c4d5e6f
# Purpose: Pydantic models for champion-ability JSON used by autocomplete endpoints
# Public-API: MCOCHubAbility, Ability, AbilityList
# Internal: None
# Uses: typing, pydantic
# Used-By: common/api/autocomplete_loader.py, common/helpers/champion_index.py
# Last-Modified: 2026-09-07
from __future__ import annotations
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class MCOCHubAbility(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")
    id: Optional[str] = None
    name: Optional[str] = None
    champion_count: Optional[int] = None

    @field_validator("id", "name", mode="before")
    @classmethod
    def normalize_text(cls, value: Any) -> Optional[str]:
        if value is None:
            return None
        return str(value).strip() or None


class ChampionAbility(BaseModel):
    """
    Champion-level ability entry as seen in champion records.
    Examples: {"name":"bleed","type":"full"} or
              {"name":"fury","type":"partial","source":"synergy","synergy_with":[...],"note":"..."}
    """
    model_config = ConfigDict(populate_by_name=True, extra="allow")
    id: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None  # 'full' | 'partial' | other
    source: Optional[str] = None
    synergy_with: Optional[List[str]] = None
    note: Optional[str] = None

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip().lower()
        if text in {"full", "partial", "conditional"}:
            return text
        return text or None

    @property
    def is_partial(self) -> bool:
        return (self.type or "").lower() == "partial"


Ability = MCOCHubAbility


class AbilityList(BaseModel):
    abilities: List[MCOCHubAbility] = Field(default_factory=list)
