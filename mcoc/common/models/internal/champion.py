from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CollectorBotChampion(BaseModel):
    """Internal canonical champion model used by bot logic and cache.

    This deliberately normalizes the external MCOCHub payloads into a stable shape
    that downstream business logic can consume without repeated key checking.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: Optional[str] = None
    slug: Optional[str] = None
    name: Optional[str] = None
    title: Optional[str] = None
    class_name: Optional[str] = Field(default=None, alias="class")
    class_: Optional[str] = None
    tier: Optional[str] = None
    rarity: Optional[int] = None
    stars: Optional[int] = None
    rank: Optional[int] = None
    sig: Optional[int] = None
    ascended: Optional[int] = None
    tags: List[str] = Field(default_factory=list)
    aliases: List[str] = Field(default_factory=list)
    image_url: Optional[str] = None
    images: Optional[Dict[str, Any]] = None
    abilities: List[Dict[str, Any]] = Field(default_factory=list)
    immunities: List[Dict[str, Any]] = Field(default_factory=list)
    raw: Optional[Dict[str, Any]] = None

    @field_validator("class_name", mode="before")
    @classmethod
    def coerce_class_name(cls, value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

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
    def coerce_immunities(cls, value: Any) -> List[Dict[str, Any]]:
        if value is None:
            return []
        if isinstance(value, list):
            return [dict(item) if isinstance(item, dict) else {"name": str(item)} for item in value]
        if isinstance(value, dict):
            return [dict(value)]
        return [{"name": str(value)}]

    @property
    def normalized_slug(self) -> Optional[str]:
        return self.slug or self.id or (self.name.lower().replace(" ", "-") if self.name else None)

    @property
    def class_lower(self) -> Optional[str]:
        return (self.class_name or self.class_ or "").lower() or None
