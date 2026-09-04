from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CollectorBotAccount(BaseModel):
    """Internal model for the per-user account/profile payload stored by Collectorbot."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    user_id: Optional[int] = None
    mcoc_name: Optional[str] = None
    mcoc_id: Optional[str] = None
    display_name: Optional[str] = None
    website: Optional[str] = None
    invite: Optional[str] = None
    timezone: Optional[str] = None
    alliance: Optional[str] = None
    job: Optional[str] = None
    age: Optional[str] = None
    gender: Optional[str] = None
    about: Optional[str] = None
    mastery: Optional[str] = None
    started: Optional[str] = None
    roster_public: bool = False
    privacy_mode: Optional[str] = None
    linked: bool = False
    prestige_map: Dict[str, int] = Field(default_factory=dict)
    top5: List[str] = Field(default_factory=list)
    consent: bool = False
    consent_ts: Optional[str] = None
    consent_version: Optional[str] = None
    consent_source: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @field_validator("prestige_map", mode="before")
    @classmethod
    def normalize_prestige_map(cls, value: Any) -> Dict[str, int]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            return {}
        result: Dict[str, int] = {}
        for key, item in value.items():
            try:
                result[str(key)] = int(item)
            except Exception:
                result[str(key)] = 0
        return result

    @field_validator("top5", mode="before")
    @classmethod
    def normalize_top5(cls, value: Any) -> List[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            return [str(value)]
        return [str(item) for item in value]
