from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class MCOCHubImmunity(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    conditional: Optional[bool] = None


class Immunity(MCOCHubImmunity):
    pass


class ImmunityList(BaseModel):
    immunities: List[MCOCHubImmunity] = Field(default_factory=list)
