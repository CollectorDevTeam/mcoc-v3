from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class MCOCHubAbility(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None


class Ability(MCOCHubAbility):
    pass


class AbilityList(BaseModel):
    abilities: List[MCOCHubAbility] = Field(default_factory=list)
