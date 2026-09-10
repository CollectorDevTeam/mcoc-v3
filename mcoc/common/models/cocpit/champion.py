# Path: mcoc/common/models/cocpit/champion.py
# File-Version: 1.0
# File-Id: 4f9b2a6e-8c4b-4f2a-9d2b-1a2b3c4d5e6f
# Purpose: Pydantic models for champion JSON used by autocomplete endpoints
# Public-API: ChampionData
# Internal: None
# Uses: typing, pydantic
# Used-By: common/api/autocomplete_loader.py, common/helpers/champion_index.py
# Last-Modified: 2026-09-07
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


def slugify(text: str) -> str:
    value = str(text or "").strip().lower()
    value = re.sub(r"[^\w\s-]", "", value)
    value = re.sub(r"[\s_-]+", "-", value)
    return value.strip("-")


class AbilityEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")
    id: Optional[str] = None
    icon_filename: Optional[str] = Field(default=None, alias="iconFilename")
    text: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_icon_keys(cls, values: Any) -> Any:
        if isinstance(values, dict):
            if "icon_filename" in values and "iconFilename" not in values:
                values["iconFilename"] = values.pop("icon_filename")
        return values



class SynergyPartner(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    champName: Optional[str] = None
    champPortraitName: Optional[str] = None
    champDisplayName: Optional[str] = None
    rarities: Optional[str] = None


class Synergy(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    title: Optional[str] = None
    icon_filename: Optional[str] = None
    description_parts: Optional[List[str]] = None
    partners: Optional[List[SynergyPartner]] = None


class AttackDamageEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")
    damageTypes: Optional[List[str]] = None
    damage: Optional[float] = None

    @model_validator(mode="before")
    def coerce_damage(cls, values):
        if isinstance(values, dict) and "damage" in values:
            try:
                values["damage"] = float(values["damage"])
            except Exception:
                pass
        return values

class AttackMoves(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: Optional[str] = None
    baseDamage: Optional[List[str]] = None
    attacks: Optional[Dict[str, List[AttackDamageEntry]]] = None


class ChampionData(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    availableRanks: Optional[List[int]] = None
    maxSigLevel: Optional[int] = None

    baseStats: Optional[Dict[str, float]] = None
    sigAbilityDisplayName: Optional[str] = None
    sigAbilities: Optional[Dict[str, List[AbilityEntry]]] = None
    coreAbilities: Optional[Dict[str, List[AbilityEntry]]] = None

    rotationData: Optional[Dict[str, Any]] = None
    synergies: Optional[List[Synergy]] = None
    duelTargets: Optional[List[Any]] = None

    attackMoves: Optional[AttackMoves] = None

    @model_validator(mode="after")
    def ensure_core_and_entry_ids(self) -> "ChampionData":
        champ_id = None
        if isinstance(self.attackMoves, AttackMoves):
            champ_id = self.attackMoves.id
        if not champ_id and self.sigAbilityDisplayName:
            champ_id = slugify(self.sigAbilityDisplayName)[:30]
        if not champ_id:
            champ_id = "champion"

        core = self.coreAbilities or {}
        normalized_core: Dict[str, List[AbilityEntry]] = {}
        for title, entries in core.items():
            group_key = f"{slugify(champ_id)}_{slugify(title)}"
            normalized_entries: List[AbilityEntry] = []
            for i, entry in enumerate(entries or []):
                if not isinstance(entry, AbilityEntry):
                    continue
                if not entry.id:
                    entry.id = f"{group_key}_{i}"
                normalized_entries.append(entry)
            normalized_core[group_key] = normalized_entries
        if normalized_core:
            self.coreAbilities = normalized_core

        if self.sigAbilities:
            for group_name, entries in list(self.sigAbilities.items()):
                normalized_entries: List[AbilityEntry] = []
                for i, entry in enumerate(entries or []):
                    if not isinstance(entry, AbilityEntry):
                        continue
                    if not entry.id:
                        entry.id = f"{slugify(champ_id)}_{slugify(group_name)}_{i}"
                    normalized_entries.append(entry)
                self.sigAbilities[group_name] = normalized_entries
        return self
