import asyncio

from mcoc.common.helpers.roster import _resolve_prestige_for_entry
from mcoc.common.api.cache import CacheManager


class _CacheStub:
    def get_prestige_value(self, slug, stars, rank, asc, sig):
        return None

    def get_cocpit_abilities(self, slug):
        if str(slug).lower() != "colossus":
            return None
        return {
            "raw": {
                "baseStats": {
                    "Prestige": 12580,
                }
            }
        }


class _CoreStub:
    def __init__(self):
        self.cache = _CacheStub()
        self.cacheindex = None
        self.api = object()


class _RefreshCacheStub(_CacheStub):
    def __init__(self):
        self._refreshed = False
        self._final_value = 22870

    def get_prestige_value(self, slug, stars, rank, asc, sig):
        if self._refreshed:
            return self._final_value
        return None

    async def check_update_prestige(self, api, force=False, progress=None):
        self._refreshed = True
        return True


def test_resolve_prestige_does_not_use_cocpit_base_stats_for_progressed_entries():
    core = _CoreStub()
    entry = {
        "champion": "colossus",
        "rarity": 7,
        "rank": 3,
        "sig": 60,
        "ascended": 1,
    }
    value = asyncio.run(_resolve_prestige_for_entry(core, entry, {}))
    assert value is None


def test_resolve_prestige_refreshes_missing_cache_value_before_falling_back():
    core = _CoreStub()
    core.cache = _RefreshCacheStub()
    entry = {
        "champion": "shang-chi",
        "rarity": 7,
        "rank": 3,
        "sig": 40,
        "ascended": 0,
    }
    value = asyncio.run(_resolve_prestige_for_entry(core, entry, {}))
    assert value == 22870


def test_cache_manager_get_prestige_value_matches_name_variants_without_punctuation():
    manager = CacheManager.__new__(CacheManager)
    manager.get_prestige_table = lambda tier, rank, asc: {
        "rows": [
            {
                "slug": "shang-chi",
                "name": "Shang Chi",
                "sigs": {"0": 0, "40": 22870},
            }
        ]
    }

    assert manager.get_prestige_value("Shang Chi", 7, 3, 0, 40) == 22870
    assert manager.get_prestige_value("shangchi", 7, 3, 0, 40) == 22870
