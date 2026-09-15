import asyncio
import pathlib

from mcoc.common.api.api import MCOCHubAPI
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


def test_cache_manager_normalizes_cocpit_champion_stats_and_harvests_by_tier_limits(tmp_path):
    manager = CacheManager.__new__(CacheManager)
    manager.cache_dir = tmp_path
    manager.metadata = {"versions": {}, "last_sync": None}
    manager.metadata_file = tmp_path / "metadata.json"

    payload = {
        "rarity": 7,
        "rank": 4,
        "sig_level": 200,
        "ascension_level": 0,
        "page": 1,
        "page_size": 50,
        "entries": [{
            "champion_id": "venompool",
            "champion_name": "VENOMPOOL",
            "rarity": 7,
            "rank": 4,
            "sig_level": 200,
            "ascension_level": 0,
            "attack": 7515,
            "health": 104889,
            "prestige": 33060,
        }],
        "has_more": False,
        "total_count": 1,
    }

    normalized = manager.normalize_cocpit_champion_stats_payload(payload)
    assert normalized is not None
    assert normalized["entries"][0]["champion_id"] == "venompool"
    assert normalized["totals"]["total_count"] == 1

    class FakeAPI:
        def __init__(self):
            self.calls = []

        async def get_cocpit_champion_stats(self, rarity, rank, sig_level, ascension_level, page=1, page_size=50):
            self.calls.append({
                "rarity": rarity,
                "rank": rank,
                "sig_level": sig_level,
                "ascension_level": ascension_level,
                "page": page,
                "page_size": page_size,
            })
            return {
                "rarity": rarity,
                "rank": rank,
                "sig_level": sig_level,
                "ascension_level": ascension_level,
                "page": page,
                "page_size": page_size,
                "entries": [{
                    "champion_id": f"test-{rarity}-{rank}-{sig_level}-{ascension_level}-{page}",
                    "champion_name": "TEST",
                    "rarity": rarity,
                    "rank": rank,
                    "sig_level": sig_level,
                    "ascension_level": ascension_level,
                    "attack": 1,
                    "health": 2,
                    "prestige": 3,
                }],
                "has_more": False,
                "total_count": 1,
            }

    fake_api = FakeAPI()
    result = asyncio.run(manager.harvest_cocpit_champion_stats(fake_api))

    assert result["count"] >= 1
    assert any(call["rarity"] == 7 and call["rank"] == 1 and call["sig_level"] == 0 and call["ascension_level"] == 0 for call in fake_api.calls)
    assert (tmp_path / "champstats.json").exists()


def test_mcochub_api_extracts_cocpit_release_date_from_head_assets():
        html = '''
        <!DOCTYPE html>
        <html lang="en">
            <head>
                <meta charset="utf-8" />
                <link rel="icon" type="image/png" href="https://cocpit-cdn.nyc3.cdn.digitaloceanspaces.com/2026.09.09/images/favicon-16x16.png" />
                <style>@font-face { font-family: 'Eurostile'; src: url('https://cocpit-cdn.nyc3.cdn.digitaloceanspaces.com/2026.09.09/fonts/eurostile.woff') format('woff'); }</style>
            </head>
        </html>
        '''

        assert MCOCHubAPI.extract_cocpit_release_date(html) == "2026.09.09"
