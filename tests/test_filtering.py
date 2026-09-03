from mcoc.common.helpers.champions import _champion_matches_filters
from mcoc.common.utilities.query_parser import parse_query


def test_parse_query_tracks_immunity_tokens_and_rarity():
    _, filters = parse_query("#bleed 6* #bleed-immunity", cache=None)

    assert filters["tags"] == ["bleed", "bleed-immunity"]
    assert filters["rarities"] == [6]


def test_champion_match_uses_tags_and_immunities_union():
    champ = {
        "name": "Archangel",
        "slug": "archangel",
        "class": "mutant",
        "tags": ["bleed", "poison"],
        "immunities": [{"name": "bleed-immunity"}],
    }

    assert _champion_matches_filters(champ, {"tags": ["bleed"]}) is True
    assert _champion_matches_filters(champ, {"tags": ["bleed-immunity"]}) is True
    assert _champion_matches_filters(champ, {"tags": ["bleed", "bleed-immunity"]}) is True
    assert _champion_matches_filters(champ, {"tags": ["bleed", "incinerate"]}) is False
