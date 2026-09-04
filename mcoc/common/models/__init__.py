"""Typed models for external and internal Collectorbot data."""

from .internal.account import CollectorBotAccount
from .internal.champion import CollectorBotChampion
from .mcochub.abilities import Ability, AbilityList, MCOCHubAbility
from .mcochub.champions import Champion, ChampionList, MCOCHubChampion
from .mcochub.immunities import Immunity, ImmunityList, MCOCHubImmunity
from .mcochub.tags import MCOCHubTag, Tag, TagList
from .mcoc_app.tierlist import (
    Champion as TierlistChampion,
    MCOCAppImmunity,
    MCOCAppTierlistChampion,
    TierList,
)

__all__ = [
    "CollectorBotAccount",
    "CollectorBotChampion",
    "Ability",
    "AbilityList",
    "MCOCHubAbility",
    "Champion",
    "ChampionList",
    "MCOCHubChampion",
    "Immunity",
    "ImmunityList",
    "MCOCHubImmunity",
    "MCOCHubTag",
    "Tag",
    "TagList",
    "TierlistChampion",
    "MCOCAppImmunity",
    "MCOCAppTierlistChampion",
    "TierList",
]
