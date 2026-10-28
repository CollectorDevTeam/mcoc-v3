from pathlib import Path

from mcoc.common.models.mcochub.abilities import MCOCHubAbility
from mcoc.common.models.mcochub.champions import MCOCHubChampion
from mcoc.common.models.mcochub.immunities import ChampionImmunity


def test_mcochub_champion_tags_and_ability_immunity_normalization():
    payload = {
        "id": "arcade",
        "name": "Arcade",
        "class": "tech",
        "tags": ["arcade", "control"],
        "abilities": [
            {"name": "shock", "type": "full"},
            {"name": "poison", "type": "partial", "source": "synergy"},
        ],
        "immunities": [
            {"name": "poison-immunity", "type": "partial"},
            {"name": "incinerate-immunity", "type": "full"},
        ],
    }

    model = MCOCHubChampion.model_validate(payload)
    assert model.tags == ["arcade", "control"]
    assert model.abilities[0].name == "shock"
    assert model.abilities[0].type == "full"
    assert model.immunities[0].conditional is True
    assert model.immunities[1].conditional is False

    sample = json_text("data/cocpit.arcade.json")
    assert "Arcade" in sample


def json_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")
