import pathlib

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


def test_cache_manager_wipe_cache_removes_all_json_files(tmp_path):
    manager = CacheManager.__new__(CacheManager)
    manager.cache_dir = tmp_path
    manager.metadata = {"last_sync": "now", "versions": {"champions": "1"}}
    manager.metadata_file = tmp_path / "metadata.json"

    (tmp_path / "champions.json").write_text('{"champions": []}', encoding="utf-8")
    (tmp_path / "tags.json").write_text('{"tags": []}', encoding="utf-8")
    (tmp_path / "metadata.json").write_text('{"last_sync": "now"}', encoding="utf-8")

    removed = manager.wipe_cache()

    assert removed["removed"] == 3
    assert not (tmp_path / "champions.json").exists()
    assert not (tmp_path / "tags.json").exists()
    assert not (tmp_path / "metadata.json").exists()
    assert manager.metadata == {"versions": {}, "last_sync": None}
