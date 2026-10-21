import asyncio

from mcoc.common.helpers.roster import _resolve_prestige_for_entry


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


def test_resolve_prestige_uses_cocpit_base_stats_fallback():
    core = _CoreStub()
    entry = {
        "champion": "colossus",
        "rarity": 7,
        "rank": 3,
        "sig": 60,
        "ascended": 1,
    }
    value = asyncio.run(_resolve_prestige_for_entry(core, entry, {}))
    assert value == 12580
