# Path: mcoc/common/models/mcochub/tags.py
# File-Version: 1.0
# File-Id: 8f9b2a6e-8c4b-4f2a-9d2b-1a2b3c4d5e6f
# Purpose: Pydantic models for champion-tag JSON used by autocomplete endpoints
# Public-API: MCOCHubTag, Tag, TagList
# Internal: None
# Uses: typing, pydantic
# Used-By: common/api/autocomplete_loader.py, common/helpers/champion_index.py
# Last-Modified: 2026-09-07
from __future__ import annotations
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MCOCHubTag(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None

    @field_validator("id", "name", "description", mode="before")
    @classmethod
    def normalize_text(cls, value: Any) -> Optional[str]:
        if value is None:
            return None
        return str(value).strip() or None


class Tag(MCOCHubTag):
    pass


class TagList(BaseModel):
    tags: List[MCOCHubTag] = Field(default_factory=list)

    def index_by_id(self) -> Dict[str, MCOCHubTag]:
        return {t.id: t for t in self.tags if t.id}

# Used-By: None
