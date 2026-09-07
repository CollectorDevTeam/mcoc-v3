from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class AbilityEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str
    icon_filename: Optional[str] = Field(default=None, alias="iconFilename")
    text: Optional[str] = None


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


class AttackMoves(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: Optional[str] = None
    baseDamage: Optional[List[str]] = None
    attacks: Optional[Dict[str, List[AttackDamageEntry]]] = None


class ChampionData(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    availableRanks: Optional[List[int]] = None
    maxSigLevel: Optional[int] = None

    # baseStats contains keys with spaces; keep as a dict to preserve keys
    baseStats: Optional[Dict[str, float]] = None

    sigAbilityDisplayName: Optional[str] = None
    sigAbilities: Optional[Dict[str, List[AbilityEntry]]] = None
    coreAbilities: Optional[Dict[str, List[AbilityEntry]]] = None

    rotationData: Optional[Dict[str, Any]] = None
    synergies: Optional[List[Synergy]] = None
    duelTargets: Optional[List[Any]] = None

    attackMoves: Optional[AttackMoves] = None
