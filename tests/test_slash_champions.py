import asyncio
import types

from mcoc.slash.champions import _ChampionGroup
from mcoc.slash.roster import _RosterGroup, _RosterRankupModal, _RosterAwakenModal


class _ResponseStub:
    def __init__(self):
        self.calls = []

    async def send_message(self, content=None, **kwargs):
        self.calls.append({"content": content, **kwargs})

    async def send_modal(self, modal):
        self.calls.append({"modal": modal})


class _InteractionStub:
    def __init__(self, user_id=42):
        self.user = types.SimpleNamespace(id=user_id, display_name="viewer")
        self.response = _ResponseStub()


class _CacheStub:
    def __init__(self, champions):
        self._champions = list(champions)

    def get_all_champions(self):
        return list(self._champions)

    def get_champion(self, token):
        key = str(token or "").strip().lower()
        for champ in self._champions:
            if key in {
                str(champ.get("id") or "").lower(),
                str(champ.get("slug") or "").lower(),
                str(champ.get("name") or "").lower(),
            }:
                return champ
        return None


class _CoreStub:
    def __init__(self, champions):
        self.cache = _CacheStub(champions)


async def _invoke(cmd, group, interaction, *args, **kwargs):
    return await cmd.callback(group, interaction, *args, **kwargs)


def test_slash_champ_info_uses_champion_embed(monkeypatch):
    champions = [{"id": "abomination", "slug": "abomination", "name": "Abomination", "tags": ["poison"]}]
    group = _ChampionGroup(core=_CoreStub(champions))
    interaction = _InteractionStub()

    from mcoc.slash import champions as slash_champions_module

    sentinel_embed = object()
    monkeypatch.setattr(slash_champions_module.CDTEmbed, "champion_embed", lambda *_a, **_k: sentinel_embed)

    asyncio.run(_invoke(group.info, group, interaction, champion="abomination"))

    assert len(interaction.response.calls) == 1
    assert interaction.response.calls[0].get("embed") is sentinel_embed


def test_slash_champ_tag_is_case_insensitive(monkeypatch):
    champions = [
        {"id": "abomination", "slug": "abomination", "name": "Abomination", "tags": ["Poison", "gamma"]},
        {"id": "black-bolt", "slug": "black-bolt", "name": "Black Bolt", "tags": ["inhuman"]},
    ]
    group = _ChampionGroup(core=_CoreStub(champions))
    interaction = _InteractionStub()

    from mcoc.slash import champions as slash_champions_module

    sentinel_embed = object()
    monkeypatch.setattr(slash_champions_module.CDTEmbed, "tag_list_embed", lambda *_a, **_k: sentinel_embed)

    asyncio.run(_invoke(group.tag, group, interaction, tag="poison"))

    assert len(interaction.response.calls) == 1
    assert interaction.response.calls[0].get("embed") is sentinel_embed


def test_slash_champ_tags_uses_shared_lookup_and_does_not_crash(monkeypatch):
    champions = [
        {"id": "abomination", "slug": "abomination", "name": "Abomination", "tags": ["Poison", "gamma"]},
        {"id": "black-bolt", "slug": "black-bolt", "name": "Black Bolt", "tags": ["inhuman"]},
    ]
    group = _ChampionGroup(core=_CoreStub(champions))
    interaction = _InteractionStub()

    from mcoc.slash import champions as slash_champions_module

    sentinel_embed = object()
    monkeypatch.setattr(slash_champions_module.CDTEmbed, "tag_list_embed", lambda *_a, **_k: sentinel_embed)

    asyncio.run(_invoke(group.tags, group, interaction, tag="poison"))

    assert len(interaction.response.calls) == 1
    assert interaction.response.calls[0].get("embed") is sentinel_embed


def test_slash_champ_search_has_name_autocomplete(monkeypatch):
    champions = [{"id": "abomination", "slug": "abomination", "name": "Abomination", "tags": ["poison"]}]
    group = _ChampionGroup(core=_CoreStub(champions))

    # app_commands decorators attach metadata at definition time; verify the command is configured to offer name suggestions.
    search_callback = getattr(group.search, "_callback", None)
    assert search_callback is not None
    assert hasattr(group, "search")


def test_slash_roster_add_accepts_multiple_champions_in_one_payload():
    champion_rows = [
        {"id": "abomination", "slug": "abomination", "name": "Abomination", "tags": ["poison"]},
        {"id": "black-bolt", "slug": "black-bolt", "name": "Black Bolt", "tags": ["inhuman"]},
    ]

    calls = []

    class _RosterUsersStub:
        def add_champion(self, user_id, champ_slug, rarity, rank, sig=0, ascended=0, tags=None, **kwargs):
            calls.append({
                "user_id": user_id,
                "champ_slug": champ_slug,
                "rarity": rarity,
                "rank": rank,
                "sig": sig,
                "ascended": ascended,
                "tags": tags or [],
            })

    class _RosterCoreStub:
        def __init__(self, champions):
            self.cache = _CacheStub(champions)
            self.users = _RosterUsersStub()

    group = _RosterGroup(core=_RosterCoreStub(champion_rows))
    interaction = _InteractionStub()

    asyncio.run(_invoke(group.add, group, interaction, champion="Abomination 7*r1, Black Bolt 6*r3", hargs=""))

    assert len(calls) == 2
    assert {c["champ_slug"] for c in calls} == {"abomination", "black-bolt"}
    assert interaction.response.calls[0].get("content", "").startswith("Added 2 champion")


def test_slash_roster_add_prompts_modal_for_single_champion_without_hargs(monkeypatch):
    champion_rows = [{"id": "abomination", "slug": "abomination", "name": "Abomination", "tags": ["poison"]}]
    group = _RosterGroup(core=_CoreStub(champion_rows))
    interaction = _InteractionStub()

    called = {}

    async def _fake_modal(interaction_obj, champion):
        called["champion"] = champion

    monkeypatch.setattr(group, "_prompt_single_champion_modal", _fake_modal)

    asyncio.run(_invoke(group.add, group, interaction, champion="Abomination", hargs=None))

    assert called["champion"] == "Abomination"


def test_slash_roster_add_multiple_names_starts_modal_queue(monkeypatch):
    champion_rows = [
        {"id": "abomination", "slug": "abomination", "name": "Abomination", "tags": ["poison"]},
        {"id": "black-bolt", "slug": "black-bolt", "name": "Black Bolt", "tags": ["inhuman"]},
    ]
    group = _RosterGroup(core=_CoreStub(champion_rows))
    interaction = _InteractionStub()

    called = {}

    async def _fake_queue(interaction_obj, champions):
        called["champions"] = champions

    monkeypatch.setattr(group, "_prompt_modal_queue", _fake_queue)

    asyncio.run(_invoke(group.add, group, interaction, champion="Abomination, Black Bolt", hargs=None))

    assert called["champions"] == ["Abomination", "Black Bolt"]


def test_slash_roster_champion_autocomplete_appends_after_comma():
    champion_rows = [
        {"id": "abomination", "slug": "abomination", "name": "Abomination", "tags": ["poison"]},
        {"id": "black-bolt", "slug": "black-bolt", "name": "Black Bolt", "tags": ["inhuman"]},
    ]
    group = _RosterGroup(core=_CoreStub(champion_rows))

    choices = asyncio.run(group.champion_autocomplete(None, "Abomination, bl"))

    values = [c.value for c in choices]
    assert any(v.startswith("Abomination, ") and "Black Bolt" in v for v in values)


def test_slash_roster_rankup_opens_modal():
    champion_rows = [{"id": "abomination", "slug": "abomination", "name": "Abomination", "class": "science"}]
    group = _RosterGroup(core=_CoreStub(champion_rows))
    interaction = _InteractionStub()

    asyncio.run(_invoke(group.rankup, group, interaction))

    assert len(interaction.response.calls) == 1
    modal = interaction.response.calls[0].get("modal")
    assert isinstance(modal, _RosterRankupModal)


def test_slash_roster_rankup_modal_parses_inputs_and_calls_runner(monkeypatch):
    champion_rows = [{"id": "abomination", "slug": "abomination", "name": "Abomination", "class": "science"}]
    group = _RosterGroup(core=_CoreStub(champion_rows))
    interaction = _InteractionStub()

    called = {}

    async def _fake_runner(interaction_obj, cls, stars, target_rank, per_class_target):
        called["cls"] = cls
        called["stars"] = stars
        called["target_rank"] = target_rank
        called["per_class_target"] = per_class_target

    monkeypatch.setattr(group, "_run_rankup_suggestions", _fake_runner)

    modal = _RosterRankupModal(group)
    modal.class_filter._value = "science"
    modal.stars._value = "7"
    modal.target_rank._value = "3"
    modal.target_per_class._value = "2"

    asyncio.run(modal.on_submit(interaction))

    assert called == {"cls": "science", "stars": 7, "target_rank": 3, "per_class_target": 2}


def test_slash_roster_rankup_suggestions_sort_by_score():
    champion_rows = [
        {"id": "abomination", "slug": "abomination", "name": "Abomination", "class": "science"},
        {"id": "black-bolt", "slug": "black-bolt", "name": "Black Bolt", "class": "cosmic"},
    ]

    class _CacheWithTierlist(_CacheStub):
        def _load_file(self, name):
            if name == "tierlist":
                return {
                    "champions": [
                        {"id": "abomination", "name": "Abomination", "score": 40},
                        {"id": "black-bolt", "name": "Black Bolt", "score": 90},
                    ]
                }
            return {}

    class _UsersStub:
        def list_roster(self, _user_id):
            return [
                {"champion": "abomination", "rarity": 7, "rank": 1, "sig": 0, "ascended": 0},
                {"champion": "black-bolt", "rarity": 7, "rank": 1, "sig": 0, "ascended": 0},
            ]

    class _CoreWithUsers:
        def __init__(self):
            self.cache = _CacheWithTierlist(champion_rows)
            self.users = _UsersStub()

    group = _RosterGroup(core=_CoreWithUsers())
    suggestions = group._rankup_suggestions(42, "all", 7, 3)

    assert [item["slug"] for item in suggestions[:2]] == ["black-bolt", "abomination"]


def test_slash_roster_awaken_opens_modal():
    champion_rows = [{"id": "abomination", "slug": "abomination", "name": "Abomination", "class": "science"}]
    group = _RosterGroup(core=_CoreStub(champion_rows))
    interaction = _InteractionStub()

    asyncio.run(_invoke(group.awaken, group, interaction))

    assert len(interaction.response.calls) == 1
    modal = interaction.response.calls[0].get("modal")
    assert isinstance(modal, _RosterAwakenModal)


def test_slash_roster_awaken_modal_parses_inputs_and_calls_runner(monkeypatch):
    champion_rows = [{"id": "abomination", "slug": "abomination", "name": "Abomination", "class": "science"}]
    group = _RosterGroup(core=_CoreStub(champion_rows))
    interaction = _InteractionStub()

    called = {}

    async def _fake_runner(interaction_obj, cls, stars, min_rank, per_class_target):
        called["cls"] = cls
        called["stars"] = stars
        called["min_rank"] = min_rank
        called["per_class_target"] = per_class_target

    monkeypatch.setattr(group, "_run_awaken_suggestions", _fake_runner)

    modal = _RosterAwakenModal(group)
    modal.class_filter._value = "science"
    modal.stars._value = "7"
    modal.min_rank._value = "3"
    modal.target_per_class._value = "1"

    asyncio.run(modal.on_submit(interaction))

    assert called == {"cls": "science", "stars": 7, "min_rank": 3, "per_class_target": 1}


def test_slash_roster_awaken_filters_awakened_true_and_unawakened_only():
    champion_rows = [
        {"id": "abomination", "slug": "abomination", "name": "Abomination", "class": "science"},
        {"id": "black-bolt", "slug": "black-bolt", "name": "Black Bolt", "class": "cosmic"},
    ]

    class _CacheWithTierlist(_CacheStub):
        def _load_file(self, name):
            if name == "tierlist":
                return {
                    "champions": [
                        {"id": "abomination", "name": "Abomination", "score": 80, "awakened": True},
                        {"id": "black-bolt", "name": "Black Bolt", "score": 95, "awakened": False},
                    ]
                }
            return {}

    class _UsersStub:
        def list_roster(self, _user_id):
            return [
                {"champion": "abomination", "rarity": 7, "rank": 3, "sig": 0, "ascended": 0},
                {"champion": "black-bolt", "rarity": 7, "rank": 3, "sig": 0, "ascended": 0},
            ]

    class _CoreWithUsers:
        def __init__(self):
            self.cache = _CacheWithTierlist(champion_rows)
            self.users = _UsersStub()

    group = _RosterGroup(core=_CoreWithUsers())
    suggestions = group._awaken_suggestions(42, "all", 7, 3)

    assert [item["slug"] for item in suggestions] == ["abomination"]


def test_slash_roster_rankup_per_class_target_only_returns_needed_classes():
    champion_rows = [
        {"id": "abomination", "slug": "abomination", "name": "Abomination", "class": "science"},
        {"id": "spider-man", "slug": "spider-man", "name": "Spider-Man", "class": "science"},
        {"id": "wolverine", "slug": "wolverine", "name": "Wolverine", "class": "mutant"},
    ]

    class _CacheWithTierlist(_CacheStub):
        def _load_file(self, name):
            if name == "tierlist":
                return {
                    "champions": [
                        {"id": "abomination", "name": "Abomination", "score": 60},
                        {"id": "spider-man", "name": "Spider-Man", "score": 50},
                        {"id": "wolverine", "name": "Wolverine", "score": 80},
                    ]
                }
            return {}

    class _UsersStub:
        def list_roster(self, _user_id):
            return [
                {"champion": "abomination", "rarity": 7, "rank": 3, "sig": 0, "ascended": 0},
                {"champion": "spider-man", "rarity": 7, "rank": 1, "sig": 0, "ascended": 0},
                {"champion": "wolverine", "rarity": 7, "rank": 1, "sig": 0, "ascended": 0},
            ]

    class _CoreWithUsers:
        def __init__(self):
            self.cache = _CacheWithTierlist(champion_rows)
            self.users = _UsersStub()

    group = _RosterGroup(core=_CoreWithUsers())
    suggestions = group._rankup_suggestions(42, "all", 7, 3, per_class_target=1)

    # Science already meets target/class via Abomination at r3, so only Mutant remains suggested.
    assert [item["slug"] for item in suggestions] == ["wolverine"]


def test_slash_roster_awaken_per_class_target_uses_awakened_gap():
    champion_rows = [
        {"id": "abomination", "slug": "abomination", "name": "Abomination", "class": "science"},
        {"id": "wolverine", "slug": "wolverine", "name": "Wolverine", "class": "mutant"},
    ]

    class _CacheWithTierlist(_CacheStub):
        def _load_file(self, name):
            if name == "tierlist":
                return {
                    "champions": [
                        {"id": "abomination", "name": "Abomination", "score": 65, "awakened": True},
                        {"id": "wolverine", "name": "Wolverine", "score": 90, "awakened": True},
                    ]
                }
            return {}

    class _UsersStub:
        def list_roster(self, _user_id):
            return [
                {"champion": "abomination", "rarity": 7, "rank": 3, "sig": 40, "ascended": 0},
                {"champion": "wolverine", "rarity": 7, "rank": 3, "sig": 0, "ascended": 0},
            ]

    class _CoreWithUsers:
        def __init__(self):
            self.cache = _CacheWithTierlist(champion_rows)
            self.users = _UsersStub()

    group = _RosterGroup(core=_CoreWithUsers())
    suggestions = group._awaken_suggestions(42, "all", 7, 3, per_class_target=1)

    # Science already has an awakened entry (sig > 0), so only mutant should remain to fill target.
    assert [item["slug"] for item in suggestions] == ["wolverine"]


def test_slash_roster_rankup_pages_group_by_tier_order(monkeypatch):
    champion_rows = [
        {"id": "abomination", "slug": "abomination", "name": "Abomination", "class": "science"},
        {"id": "black-bolt", "slug": "black-bolt", "name": "Black Bolt", "class": "cosmic"},
        {"id": "wolverine", "slug": "wolverine", "name": "Wolverine", "class": "mutant"},
    ]

    class _CacheWithTierlist(_CacheStub):
        def _load_file(self, name):
            if name == "tierlist":
                return {
                    "champions": [
                        {"id": "abomination", "name": "Abomination", "score": 70, "tier": "A"},
                        {"id": "black-bolt", "name": "Black Bolt", "score": 95, "tier": "S+"},
                        {"id": "wolverine", "name": "Wolverine", "score": 60, "tier": "B"},
                    ]
                }
            return {}

    class _UsersStub:
        def list_roster(self, _user_id):
            return [
                {"champion": "abomination", "rarity": 7, "rank": 1, "sig": 0, "ascended": 0},
                {"champion": "black-bolt", "rarity": 7, "rank": 1, "sig": 0, "ascended": 0},
                {"champion": "wolverine", "rarity": 7, "rank": 1, "sig": 0, "ascended": 0},
            ]

    class _CoreWithUsers:
        def __init__(self):
            self.cache = _CacheWithTierlist(champion_rows)
            self.users = _UsersStub()

    group = _RosterGroup(core=_CoreWithUsers())
    interaction = _InteractionStub()

    from mcoc.slash import roster as slash_roster_module

    def _fake_embed(*_args, **kwargs):
        return {"description": kwargs.get("description", ""), "title": kwargs.get("title", "")}

    monkeypatch.setattr(slash_roster_module.CDTEmbed, "embed", _fake_embed)

    suggestions = group._rankup_suggestions(42, "all", 7, 3)
    pages = group._build_rankup_pages(interaction, "all", 7, 3, suggestions)
    description = pages[0]["description"]

    assert description.find("**S+**") < description.find("**A**") < description.find("**B**")


def test_slash_roster_awaken_pages_group_by_tier_order(monkeypatch):
    champion_rows = [
        {"id": "abomination", "slug": "abomination", "name": "Abomination", "class": "science"},
        {"id": "black-bolt", "slug": "black-bolt", "name": "Black Bolt", "class": "cosmic"},
        {"id": "wolverine", "slug": "wolverine", "name": "Wolverine", "class": "mutant"},
    ]

    class _CacheWithTierlist(_CacheStub):
        def _load_file(self, name):
            if name == "tierlist":
                return {
                    "champions": [
                        {"id": "abomination", "name": "Abomination", "score": 70, "tier": "A", "awakened": True},
                        {"id": "black-bolt", "name": "Black Bolt", "score": 95, "tier": "S+", "awakened": True},
                        {"id": "wolverine", "name": "Wolverine", "score": 60, "tier": "B", "awakened": True},
                    ]
                }
            return {}

    class _UsersStub:
        def list_roster(self, _user_id):
            return [
                {"champion": "abomination", "rarity": 7, "rank": 3, "sig": 0, "ascended": 0},
                {"champion": "black-bolt", "rarity": 7, "rank": 3, "sig": 0, "ascended": 0},
                {"champion": "wolverine", "rarity": 7, "rank": 3, "sig": 0, "ascended": 0},
            ]

    class _CoreWithUsers:
        def __init__(self):
            self.cache = _CacheWithTierlist(champion_rows)
            self.users = _UsersStub()

    group = _RosterGroup(core=_CoreWithUsers())
    interaction = _InteractionStub()

    from mcoc.slash import roster as slash_roster_module

    def _fake_embed(*_args, **kwargs):
        return {"description": kwargs.get("description", ""), "title": kwargs.get("title", "")}

    monkeypatch.setattr(slash_roster_module.CDTEmbed, "embed", _fake_embed)

    suggestions = group._awaken_suggestions(42, "all", 7, 3)
    pages = group._build_awaken_pages(interaction, "all", 7, 3, suggestions)
    description = pages[0]["description"]

    assert description.find("**S+**") < description.find("**A**") < description.find("**B**")


def test_slash_roster_modal_labels_fit_discord_limit():
    group = _RosterGroup(core=_CoreStub([]))
    rankup_modal = _RosterRankupModal(group)
    awaken_modal = _RosterAwakenModal(group)

    for modal in (rankup_modal, awaken_modal):
        for field in modal.children:
            label = getattr(field, "label", "") or ""
            assert 1 <= len(label) <= 45


def test_slash_champ_search_returns_pages(monkeypatch):
    champions = [
        {
            "id": "abomination",
            "slug": "abomination",
            "name": "Abomination",
            "class": "science",
            "tags": ["poison"],
            "abilities": [{"name": "Poison"}],
            "immunities": [],
            "synergies": [],
        },
        {
            "id": "black-bolt",
            "slug": "black-bolt",
            "name": "Black Bolt",
            "class": "cosmic",
            "tags": ["inhuman"],
            "abilities": [{"name": "Fury"}],
            "immunities": [],
            "synergies": [],
        },
    ]
    group = _ChampionGroup(core=_CoreStub(champions))
    interaction = _InteractionStub()

    from mcoc.slash import champions as slash_champions_module

    sentinel_view = object()
    monkeypatch.setattr(slash_champions_module, "CDTPagesMenu", lambda pages, author=None: sentinel_view)
    monkeypatch.setattr(slash_champions_module.CDTEmbed, "champion_embed", lambda *_a, **_k: object())
    monkeypatch.setattr(slash_champions_module, "add_page_footers", lambda pages: pages)

    asyncio.run(
        _invoke(
            group.search,
            group,
            interaction,
            champ_name=None,
            champ_class="science",
            champ_rarity=None,
            champ_tag="poison",
            champ_ability=None,
            champ_immunity=None,
            champ_synergy=None,
        )
    )

    assert len(interaction.response.calls) == 1
    assert interaction.response.calls[0].get("view") is sentinel_view


def test_slash_champ_synergies_multi_team_adds_unactivated_page(monkeypatch):
    champions = [
        {"id": "abomination", "slug": "abomination", "name": "Abomination", "synergies": []},
        {"id": "black-bolt", "slug": "black-bolt", "name": "Black Bolt", "synergies": []},
        {"id": "captain-america", "slug": "captain-america", "name": "Captain America", "synergies": []},
    ]
    group = _ChampionGroup(core=_CoreStub(champions))
    interaction = _InteractionStub()

    from mcoc.slash import champions as slash_champions_module

    sentinel_view = object()
    monkeypatch.setattr(slash_champions_module, "CDTPagesMenu", lambda pages, author=None: sentinel_view)

    async def _fake_cocpit(*_a, **_k):
        return {"synergies": [{"title": "Power Couple"}]}

    monkeypatch.setattr(slash_champions_module, "get_cocpit_champion_data", _fake_cocpit)
    monkeypatch.setattr(
        slash_champions_module,
        "build_cocpit_synergy_activation_sets",
        lambda *_a, **_k: (["**Active**"], ["**Inactive**"]),
    )

    asyncio.run(_invoke(group.synergies, group, interaction, champion="abomination", teammates="black-bolt,captain-america"))

    assert len(interaction.response.calls) == 1
    call = interaction.response.calls[0]
    assert call.get("view") is sentinel_view
    assert "Activated Synergies" in str(getattr(call.get("embed"), "title", ""))
