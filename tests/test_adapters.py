from mcoc.common.adapters import mcochub_to_internal, cocpit_to_internal, mcoc_app_tierlist_to_internal


def test_source_adapters_return_canonical_champion_records():
    mcochub = {
        "id": "arcade",
        "name": "Arcade",
        "class": "tech",
        "tags": ["control", "tech"],
        "abilities": [{"name": "shock", "type": "full"}, {"name": "bleed", "type": "partial"}],
        "immunities": [{"name": "incinerate-immunity", "type": "full"}, {"name": "poison-immunity", "type": "partial"}],
    }
    tierlist = {
        "champions": [{
            "name": "Arcade",
            "class": "Tech",
            "tier": "S+",
            "tags": ["control"],
            "immunities": [{"type": "poison", "conditional": True}],
            "inflicts": ["shock", "bleed"],
            "portrait": None,
        }],
        "tag_labels": {},
        "immunity_map": {},
        "immunity_types": ["poison"],
        "debuff_map": {},
        "debuff_types": ["shock", "bleed"],
    }
    cocpit = {
        "attackMoves": {"id": "arcade"},
        "coreAbilities": {
            "Always Active": [{"text": "Arcade gains bleed."}, {"text": "Arcade gains shock."}],
        },
        "synergies": [],
    }

    internal_from_mhub = mcochub_to_internal(mcochub)
    internal_from_tier = mcoc_app_tierlist_to_internal(tierlist, tierlist)
    internal_from_cocpit = cocpit_to_internal(cocpit)

    assert internal_from_mhub.id == "arcade"
    assert internal_from_mhub.class_lower == "tech"
    assert internal_from_mhub.abilities[0]["id"]
    assert internal_from_mhub.immunities[0]["id"]
    assert internal_from_mhub.raw_sources["mcochub"] == mcochub

    assert internal_from_tier.name == "Arcade"
    assert internal_from_tier.class_lower == "tech"
    assert internal_from_tier.raw_sources["mcoc_app"]["champions"][0]["name"] == "Arcade"

    assert internal_from_cocpit.id == "arcade"
    assert internal_from_cocpit.raw_sources["cocpit"] == cocpit
    assert internal_from_cocpit.abilities
    assert internal_from_cocpit.immunities
