from mcoc.common.helpers.champions import _champion_matches_filters, build_tier_pages, build_filter_flow_state, build_filter_picker_sections, _filter_picker_page_values, build_cocpit_ability_lines, build_cocpit_synergy_intersection_lines
from mcoc.common.helpers.roster import filter_roster_entries, _build_selection_option_label, parse_cocpit_roster_csv, import_roster_entries
from mcoc.common.utilities.formatters import format_tierlist_champion_line, format_champion_line
from mcoc.common.helpers.types import MCOCAPP_TIERS, champion_from_dict
from mcoc.common.utilities.query_parser import parse_query
import asyncio


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


def test_champion_from_dict_preserves_inflicts_and_conditional_immunities():
    champ = champion_from_dict({
        "id": "abomination",
        "name": "Abomination",
        "class": "skill",
        "inflicts": ["poison", "bleed"],
        "immunities": [
            {"type": "stun", "conditional": True},
            {"type": "shock", "conditional": False},
        ],
    })

    assert champ is not None
    assert champ.inflicts == ["poison", "bleed"]
    assert champ.immunities[0]["type"] == "stun"
    assert champ.immunities[0]["conditional"] is True
    assert champ.immunities[1]["type"] == "shock"


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


def test_filter_picker_sections_split_primary_categories():
    sections = build_filter_picker_sections([
        {"value": "bleed", "type": "tags"},
        {"value": "shock", "type": "inflicts"},
        {"value": "poison", "type": "immunities"},
        {"value": "mystic", "type": "class"},
        {"value": "incinerate", "type": "abilities"},
        {"value": "7", "type": "tier"},
    ])

    assert "inflicts" in sections
    assert "immune_to" in sections
    assert "classes" in sections
    assert "abilities" in sections
    assert "tiers" in sections
    assert "shock" in sections["inflicts"]
    assert "poison" in sections["immune_to"]
    assert "mystic" in sections["classes"]
    assert "incinerate" in sections["abilities"]
    assert "7" in sections["tiers"]


def test_filter_picker_page_values_cover_all_entries_across_pages():
    values = [f"ability-{index}" for index in range(30)]

    first_page, total_pages = _filter_picker_page_values(values, 0)
    second_page, second_total_pages = _filter_picker_page_values(values, 1)

    assert total_pages == 2
    assert second_total_pages == 2
    assert len(first_page) == 25
    assert len(second_page) == 5
    assert first_page[0] == "ability-0"
    assert second_page[-1] == "ability-29"


def test_format_champion_line_uses_prestige_when_available():
    champ = champion_from_dict({"id": "alpha", "name": "Alpha", "class": "skill", "prestige": 12345})
    line = format_champion_line(champ, {"champion": "alpha", "rarity": 6, "rank": 1, "sig": 0, "ascended": 0})

    assert "[12,345]" in line
    assert "Alpha" in line


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


def test_ability_and_inflict_names_behave_as_filter_tokens():
    champ = {
        "name": "Shocker",
        "slug": "shocker",
        "class": "science",
        "abilities": [{"name": "Shock"}],
        "inflicts": ["Shock"],
        "tags": ["shock"],
    }

    assert _champion_matches_filters(champ, {"tags": ["shock"]}) is True
    assert _champion_matches_filters(champ, {"tags": ["Shock"]}) is True
    assert _champion_matches_filters(champ, {"classes": ["science"], "tags": ["shock"]}) is True


def test_roster_selection_label_uses_champion_name_not_slug():
    class FakeCache:
        def get_champion(self, value):
            return {"name": "Doctor Doom", "slug": "doctordoom"}

    entry = {"champion": "doctordoom", "raw": "doctordoom", "rarity": 6, "rank": 5, "sig": 60, "ascended": 1}
    label = _build_selection_option_label(entry, cache=FakeCache())

    assert label == "Doctor Doom (6★ r5 s60 a1)"


def test_cache_health_check_flags_invalid_payloads_and_cleanup_can_repair(tmp_path):
    from mcoc.common.api.cache import CacheManager

    mgr = CacheManager.__new__(CacheManager)
    mgr.cache_dir = tmp_path
    mgr.metadata = {"versions": {}, "last_sync": None}
    mgr.index = type("IndexStub", (), {"rebuild": lambda self: None})()

    (tmp_path / "champions.json").write_text('{"bad": "shape"}', encoding="utf-8")
    (tmp_path / "tags.json").write_text('[]', encoding="utf-8")

    health = mgr.health_check()
    assert health["ok"] is False
    assert any("champions" in issue.lower() for issue in health["issues"])

    result = mgr.cleanup_stale_cache()
    assert result["healthy"] is True
    assert result["removed"] >= 1


def test_make_roster_pager_attaches_filter_handler(monkeypatch):
    from mcoc.common.helpers import roster as roster_helpers

    class FakePager:
        def __init__(self, pages, author=None):
            self.pages = pages
            self.author = author
            self.filter_handler = None

    async def fake_get_roster_pages(core, ctx_or_author, parsed_filters=None):
        del core, ctx_or_author, parsed_filters
        return [{"title": "Roster", "description": "Alpha"}]

    monkeypatch.setattr(roster_helpers, "get_roster_pages", fake_get_roster_pages)
    monkeypatch.setattr(roster_helpers, "CDTPagesMenu", FakePager)

    author = type("Author", (), {"id": 1})()
    pager = asyncio.run(roster_helpers.make_roster_pager(object(), author, raw_input="#bleed", parsed_filters={"tags": ["bleed"]}))

    assert pager is not None
    assert pager.pages
    assert callable(pager.filter_handler)


def test_parse_cocpit_roster_csv_returns_canonical_entries():
    csv_text = """ID,Full Name,Class,Rarity,Rank,Sig Level,Ascension Level,Prestige
doctordoom,DOCTOR DOOM,mystic,6,5,40,0,15780
ironman,IRON MAN,tech,7,1,40,0,14820
"""

    class FakeCache:
        def get_champion(self, value):
            lookup = {
                "doctordoom": {"id": "doctordoom", "name": "Doctor Doom", "class": "mystic"},
                "ironman": {"id": "ironman", "name": "Iron Man", "class": "tech"},
            }
            return lookup.get(str(value).lower())

    entries = parse_cocpit_roster_csv(csv_text, FakeCache())

    assert len(entries) == 2
    assert entries[0]["champion"] == "doctordoom"
    assert entries[0]["rarity"] == 6
    assert entries[0]["rank"] == 5
    assert entries[0]["sig"] == 40
    assert entries[0]["prestige"] == 15780
    assert entries[1]["champion"] == "ironman"
    assert entries[1]["class"] == "tech"


def test_import_roster_entries_persists_rows_and_reports_count(monkeypatch):
    class FakeUsers:
        def __init__(self):
            self.calls = []

        def add_champion(self, user_id, champ_slug, rarity, rank, sig, ascended=0, tags=None):
            self.calls.append((user_id, champ_slug, rarity, rank, sig, ascended, tags or []))

    recorded = []

    def fake_schedule(core, user_id):
        recorded.append((core, user_id))

    monkeypatch.setattr("mcoc.common.helpers.roster.schedule_persist_user_prestige", fake_schedule)

    users = FakeUsers()
    core = object()
    result = import_roster_entries(core, 42, [
        {"champion": "doctordoom", "rarity": 6, "rank": 5, "sig": 40, "ascended": 0, "tags": []},
        {"champion": "ironman", "rarity": 7, "rank": 1, "sig": 40, "ascended": 0, "tags": []},
    ], users=users)

    assert result["imported"] == 2
    assert result["errors"] == []
    assert len(users.calls) == 2
    assert recorded == [(core, 42)]


def test_build_cocpit_ability_lines_prefers_grouped_descriptions():
    lines = build_cocpit_ability_lines({
        "sigAbilities": {
            "Passive": [
                {"text": "Personal effects expire more slowly."},
            ]
        },
        "coreAbilities": {
            "Special Attack 1": [
                {"text": "Gain a Fury Buff for 16 seconds."},
            ]
        },
    })

    assert "**Signature: Passive**" in lines
    assert "• Personal effects expire more slowly." in lines
    assert "**Core: Special Attack 1**" in lines
    assert "• Gain a Fury Buff for 16 seconds." in lines


def test_build_cocpit_synergy_intersection_only_returns_active_synergies():
    base = {"id": "thanos_deathless_trophy", "name": "Thanos (Deathless)"}
    team = [
        base,
        {"id": "vision_deathless", "name": "Vision (Deathless)"},
    ]
    lines = build_cocpit_synergy_intersection_lines(
        base,
        team,
        {
            "synergies": [
                {
                    "title": "TWISTED INSIGHT",
                    "description_parts": ["Vision gains a power burn effect."],
                    "partners": [{"champName": "vision_deathless", "champDisplayName": "VISION (DEATHLESS)"}],
                },
                {
                    "title": "IRON HEEL",
                    "description_parts": ["She-Hulk gains immunity to Rupture."],
                    "partners": [{"champName": "shehulk_deathless", "champDisplayName": "SHE-HULK (DEATHLESS)"}],
                },
            ]
        },
        cache=None,
    )

    text = "\n".join(lines)
    assert "TWISTED INSIGHT" in text
    assert "VISION (DEATHLESS)" in text
    assert "IRON HEEL" not in text
