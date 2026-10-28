# Path: mcoc/common/models/mcochub/champions.py
# File-Version: 1.0
# File-Id: 5f9b2a6e-8c4b-4f2a-9d2b-1a2b3c4d5e6f
# Purpose: Pydantic models for champion-autocomplete JSON used by autocomplete endpoints
# Public-API: MCOCHubChampion, Champion, ChampionList, ImageSet
# Internal: 
# Uses: typing, pydantic
# Used-By: common/api/autocomplete_loader.py, common/helpers/champion_index.py
# Last-Modified: 2026-09-07
from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .abilities import ChampionAbility
from .immunities import ChampionImmunity


class ImageSet(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")
    portrait: Optional[str] = None
    full: Optional[str] = None
    icon: Optional[str] = None
    other: Optional[Dict[str, Any]] = None


class MCOCHubChampion(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")
    id: Optional[str] = None
    name: Optional[str] = None
    class_: Optional[str] = Field(None, alias="class")
    release_year: Optional[int] = None
    tags: List[str] = Field(default_factory=list)
    abilities: List[ChampionAbility] = Field(default_factory=list)
    immunities: List[ChampionImmunity] = Field(default_factory=list)
    images: Optional[ImageSet] = None
    image_url: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None

    @field_validator("tags", mode="before")
    @classmethod
    def ensure_tags_are_strings(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        if isinstance(v, list):
            normalized: List[str] = []
            for item in v:
                if isinstance(item, str):
                    normalized.append(item)
                elif isinstance(item, dict) and "id" in item:
                    normalized.append(str(item["id"]))
                else:
                    normalized.append(str(item))
            return normalized
        return [str(v)]

    def resolve_tags(self, tag_lookup: Optional[Dict[str, Any]] = None) -> List[Any]:
        if not self.tags:
            return []
        if tag_lookup is None:
            return [tag_id for tag_id in self.tags if tag_id]
        return [tag_lookup.get(tag_id) for tag_id in self.tags if tag_id in tag_lookup]


class Champion(MCOCHubChampion):
    pass


class ChampionList(BaseModel):
    champions: List[MCOCHubChampion] = Field(default_factory=list)
