from mcoc.common.helpers.champions import _champion_matches_filters, build_tier_pages, build_filter_flow_state
from mcoc.common.helpers.roster import filter_roster_entries
from mcoc.common.utilities.formatters import format_tierlist_champion_line
from mcoc.common.helpers.types import MCOCAPP_TIERS, champion_from_dict
from mcoc.common.utilities.query_parser import parse_query


def test_parse_query_tracks_immunity_tokens_and_rarity():
    _, filters = parse_query("#bleed 6* #bleed-immunity", cache=None)

    assert filters["tags"] == ["bleed", "bleed-immunity"]
    assert filters["rarities"] == [6]


def test_parse_query_supports_direct_string_filters_without_hash_prefix():
    _, filters = parse_query("bleed incinerate mystic #cosmic 7-star 6*", cache=None)

    assert "bleed" in filters["tags"]
    assert "incinerate" in filters["tags"]
    assert "mystic" in filters["classes"] or "mystic" in filters["tags"]
    assert "cosmic" in filters["classes"]
    assert 7 in filters["rarities"]
    assert 6 in filters["rarities"]


def test_parse_query_does_not_treat_bare_tag_as_champion_name():
    _, filters = parse_query("bleed", cache=None)

    assert filters["name"] is None or filters["name"] == "bleed" and "bleed" in filters["tags"]
    assert "bleed" in filters["tags"]


def test_parse_query_treats_known_ability_name_as_filter_even_if_champion_name_exists():
    class FakeCache:
        def get_champion(self, value):
            if value.lower() in {"shocker", "shock"}:
                return {"id": "shocker", "name": "Shocker", "class": "science"}
            return None

        def get_all_abilities(self):
            return [{"id": "shock", "name": "Shock"}, {"id": "bleed", "name": "Bleed"}]

        def get_all_tags(self):
            return ["shock", "bleed"]

    _, filters = parse_query("shock", cache=FakeCache())

    assert "shock" in filters["tags"]
    assert filters["name"] is None


def test_champion_from_dict_preserves_prestige_value():
    champ = champion_from_dict({"id": "alpha", "name": "Alpha", "class": "skill", "prestige": 12345})

    assert champ is not None
    assert champ.prestige == 12345


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


def test_filter_flow_state_builds_deduplicated_filter_and_stage_two_choices():
    state = build_filter_flow_state({
        "tags": ["bleed", "bleed", "incinerate"],
        "classes": ["mystic", "cosmic"],
        "tiers": ["7", "6"],
        "rarities": [7, 6],
    }, catalog=[
        {"value": "bleed", "label": "Bleed"},
        {"value": "incinerate", "label": "Incinerate"},
        {"value": "mystic", "label": "Mystic"},
        {"value": "cosmic", "label": "Cosmic"},
    ])

    assert "bleed" in state["filters"]
    assert "incinerate" in state["filters"]
    assert "mystic" in state["classes"]
    assert "cosmic" in state["classes"]
    assert "7" in state["tiers"] or 7 in state["tiers"]
    assert "6" in state["tiers"] or 6 in state["tiers"]


def test_parse_query_and_match_support_class_tag_tokens():
    _, filters = parse_query("#bleed #skill", cache=None)

    assert "bleed" in filters["tags"]
    assert "skill" in filters["tags"]
    assert "classes" in filters

    champ = {
        "name": "Alpha",
        "slug": "alpha",
        "class": "skill",
        "tags": ["bleed"],
        "immunities": [],
    }

    assert _champion_matches_filters(champ, {"tags": ["skill"]}) is True
    assert _champion_matches_filters(champ, {"tags": ["bleed", "skill"]}) is True

    roster_entries = [{"champion": "alpha", "rarity": 6, "rank": 1, "sig": 0, "ascended": 0, "tags": ["bleed"], "class": "skill"}]
    assert filter_roster_entries(roster_entries, {"tags": ["skill"]}) == roster_entries


def test_filters_are_normalized_by_category_for_multi_select_filters():
    champ = {
        "name": "Alpha",
        "slug": "alpha",
        "class": "skill",
        "tier": "S+",
        "tags": ["bleed"],
        "abilities": [{"name": "incinerate"}],
        "immunities": [{"name": "bleed-immunity"}],
        "inflicts": ["incinerate"],
    }

    assert _champion_matches_filters(champ, {"classes": ["skill"], "tiers": ["S+"]}) is True
    assert _champion_matches_filters(champ, {"tags": ["bleed", "incinerate"]}) is True
    assert _champion_matches_filters(champ, {"abilities": ["incinerate"], "immunities": ["bleed-immunity"]}) is True
    assert _champion_matches_filters(champ, {"classes": ["skill"], "tags": ["science"]}) is False


def test_tierlist_pages_group_by_defined_tier_order_and_color():
    champions = [
        {"name": "Black Bolt", "tier": "S+", "score": 97, "class": "Cosmic", "tags": ["control"], "awakened": True, "high_sig": True, "no7star": False, "immunities": [], "inflicts": [], "portrait": "", "rank": 1, "class_rank": 1},
        {"name": "White Bolt", "tier": "S+", "score": 94, "class": "Cosmic", "tags": ["control"], "awakened": False, "high_sig": True, "no7star": True, "immunities": [], "inflicts": [], "portrait": "", "rank": 2, "class_rank": 1},
        {"name": "Alpha", "tier": "A", "score": 88, "class": "Skill", "tags": ["defense"], "awakened": False, "high_sig": False, "no7star": False, "immunities": [], "inflicts": [], "portrait": "", "rank": 1, "class_rank": 2},
    ]

    pages = build_tier_pages(champions, filters={"name": "bolt"})

    assert len(pages) == 1
    assert pages[0]["color"] == MCOCAPP_TIERS["S+"]["color"]
    assert [group["tier"] for group in pages[0]["groups"]] == ["S+"]
    assert [champ["name"] for champ in pages[0]["groups"][0]["items"]] == ["Black Bolt", "White Bolt"]


def test_tierlist_line_uses_short_property_tokens_and_tags():
    champ = {
        "name": "Black Bolt",
        "tier": "S+",
        "score": 97,
        "class": "Cosmic",
        "tags": ["defense", "control"],
        "awakened": True,
        "high_sig": True,
        "no7star": False,
        "immunities": [{"type": "bleed", "conditional": False}],
        "inflicts": ["Incinerate"],
    }

    token_line = format_tierlist_champion_line(champ)
    assert "Black Bolt" in token_line
    assert "97" in token_line
    assert "A" in token_line and "HS" in token_line
    assert "BG-DEF" in token_line or "control" in token_line


def test_tierlist_pages_normalize_live_mco_app_tier_strings_and_sort_order():
    champions = [
        {"name": "Abomination", "tier": "F", "score": 20, "class": "Skill", "tags": [], "awakened": False, "high_sig": False, "no7star": False},
        {"name": "Abomination Immortal", "tier": "C Tier", "score": 58, "class": "Skill", "tags": [], "awakened": False, "high_sig": False, "no7star": False},
        {"name": "Black Bolt", "tier": "D", "score": 30, "class": "Cosmic", "tags": [], "awakened": False, "high_sig": False, "no7star": False},
        {"name": "Alpha", "tier": "S+", "score": 80, "class": "Mutant", "tags": [], "awakened": False, "high_sig": False, "no7star": False},
    ]

    pages = build_tier_pages(champions)
    groups = pages[0]["groups"]
    assert [group["tier"] for group in groups] == ["S+", "C", "D", "F"]
    assert "Unranked" not in [group["tier"] for group in groups]
    assert groups[0]["items"][0]["name"] == "Alpha"
    assert groups[1]["items"][0]["name"] == "Abomination Immortal"
    assert groups[3]["items"][0]["name"] == "Abomination"
