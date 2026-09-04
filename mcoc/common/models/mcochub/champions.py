from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .abilities import Ability
from .immunities import Immunity


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
    class_: str = Field(alias="class")
    release_year: Optional[int] = None
    tags: List[str] = Field(default_factory=list)
    abilities: List[Ability] = Field(default_factory=list)
    immunities: List[Immunity] = Field(default_factory=list)
    images: Optional[ImageSet] = None
    image_url: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None


class Champion(MCOCHubChampion):
    pass


class ChampionList(BaseModel):
    champions: List[MCOCHubChampion] = Field(default_factory=list)
