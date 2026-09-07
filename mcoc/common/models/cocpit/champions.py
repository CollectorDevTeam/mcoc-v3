# Path: mcoc/common/models/champion_autocomplete.py
# File-Version: 1.0
# File-Id: 3f9b2a6e-8c4b-4f2a-9d2b-1a2b3c4d5e6f
# Purpose: Pydantic models for champion-autocomplete JSON used by autocomplete endpoints
# Public-API: ChampionAutocompleteEntry, ChampionAutocompleteList
# Internal: None
# Uses: typing, pydantic
# Used-By: common/api/autocomplete_loader.py, common/helpers/champion_index.py
# Last-Modified: 2026-09-07

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ChampionAutocompleteEntry(BaseModel):
    """
    Represents a single champion entry from champion-autocomplete.json
    """
    model_config = ConfigDict(populate_by_name=True, extra="allow", str_strip_whitespace=True)

    id: str
    name: str
    aliases: List[str] = Field(default_factory=list)
    img: Optional[str] = None
    class_name: Optional[str] = Field(None, alias="className")
    available_rarities: List[int] = Field(default_factory=list, alias="availableRarities")
    ascension_max_by_rarity: Dict[str, int] = Field(default_factory=dict, alias="ascensionMaxByRarity")


class ChampionAutocompleteList(BaseModel):
    """
    Top-level container when loading the autocomplete JSON as a single object.
    Use parse_obj or parse_raw on the JSON array to get List[ChampionAutocompleteEntry].
    """
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    champions: List[ChampionAutocompleteEntry]

    @classmethod
    def from_list(cls, data: List[dict]) -> "ChampionAutocompleteList":
        return cls(champions=[ChampionAutocompleteEntry.model_validate(item) for item in data])
