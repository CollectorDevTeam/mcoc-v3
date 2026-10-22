from mcoc.common.utilities.hargs import parse_harg_token
from mcoc.common.helpers.roster import parse_roster_entries_from_input, parse_roster_entries_with_errors


class _CacheStub:
    def __init__(self):
        self._map = {
            "colossus": {"id": "colossus", "slug": "colossus", "name": "Colossus"},
            "shangchi": {"id": "shang-chi", "slug": "shang-chi", "name": "Shang-Chi"},
            "futureantman": {"id": "future-ant-man", "slug": "future-ant-man", "name": "Future Ant-Man"},
            "okoye": {"id": "okoye", "slug": "okoye", "name": "Okoye"},
        }

    def get_champion(self, token):
        key = "".join(ch for ch in str(token or "").lower() if ch.isalnum())
        return self._map.get(key)

    def get_all_champions(self):
        return list(self._map.values())


def test_parse_harg_token_compact_prefix_variants():
    p1 = parse_harg_token("7scol")
    assert p1["rarity"] == 7
    assert p1["champion"] == "col"

    p2 = parse_harg_token("7starColossus")
    assert p2["rarity"] == 7
    assert p2["champion"].lower() == "colossus"

    p3 = parse_harg_token("7sr3s40Shang-Chi")
    assert p3["rarity"] == 7
    assert p3["rank"] == 3
    assert p3["sig"] == 40
    assert p3["champion"].lower() == "shang-chi"


def test_parse_roster_entries_multi_compact_stream():
    cache = _CacheStub()
    text = "7sa1r3s60Colossus 7sr3s40Shang-Chi 7sr3s40futureantman"
    entries = parse_roster_entries_from_input(text, cache)
    assert len(entries) == 3
    slugs = [e["champion"] for e in entries]
    assert "colossus" in slugs
    assert "shang-chi" in slugs
    assert "future-ant-man" in slugs


def test_parse_roster_entries_with_errors_reports_unresolved_tokens():
    cache = _CacheStub()
    cache._map["dragonman"] = {"id": "dragon-man", "slug": "dragon-man", "name": "Dragon-Man"}

    entries, failed = parse_roster_entries_with_errors("7sr1a1Dragon-Man 7sr1yabbadabbadoo", cache)

    assert len(entries) == 1
    assert entries[0]["champion"] == "dragon-man"
    assert failed == ["7sr1yabbadabbadoo"]
