from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class MCOCHubTag(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None


class Tag(MCOCHubTag):
    pass


class TagList(BaseModel):
    tags: List[MCOCHubTag] = Field(default_factory=list)
