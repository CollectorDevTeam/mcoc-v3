from mcoc.common.api.cache import CacheManager


def test_cache_manager_preserves_tierlist_metadata_and_validates_canonical_dicts():
    manager = CacheManager.__new__(CacheManager)
    payload = {
        "champions": [{"name": "Arcade", "class": "Tech", "tier": "S+", "immunities": [{"type": "poison", "conditional": True}], "inflicts": ["shock"]}],
        "tag_labels": {"tech": "Tech"},
        "immunity_map": {"poison": {"name": "Poison"}},
        "immunity_types": ["poison"],
        "debuff_map": {"shock": {"name": "Shock"}},
        "debuff_types": ["shock"],
    }

    normalized = manager.normalize_tierlist_payload(payload)

    assert normalized is not None
    assert normalized["immunity_map"]["poison"]["name"] == "Poison"
    assert normalized["debuff_map"]["shock"]["name"] == "Shock"
    assert normalized["champions"][0]["name"] == "Arcade"
