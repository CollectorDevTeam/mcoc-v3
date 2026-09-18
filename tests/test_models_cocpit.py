from pathlib import Path

from mcoc.common.models.cocpit.champion import ChampionData


def test_cocpit_champion_data_generates_group_and_entry_ids():
    payload = {
        "attackMoves": {"id": "arcade"},
        "coreAbilities": {
            "Always Active": [
                {"text": "Arcade starts each fight with a bonus."},
                {"text": "Arcade gains a passive effect."},
            ]
        },
        "sigAbilities": {"Passive": [{"text": "Arcade gets powered up."}]},
    }

    model = ChampionData.model_validate(payload)
    assert model.coreAbilities is not None
    assert "Always Active" in model.coreAbilities
    assert all(entry.id for entries in model.coreAbilities.values() for entry in entries)

    sample = Path("data/cocpit.arcade.json").read_text(encoding="utf-8")
    assert "coreAbilities" in sample
    assert "sigAbilities" in sample
