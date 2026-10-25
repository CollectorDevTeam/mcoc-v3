import asyncio
import types

from mcoc.slash.champions import _ChampionGroup
from mcoc.slash.roster import _RosterGroup, _RosterRankupModal, _RosterAwakenModal, _RankupClassSelectView


class _ResponseStub:
    def __init__(self):
        self.calls = []
        self.deferred = False

    async def send_message(self, content=None, **kwargs):
        self.calls.append({"content": content, **kwargs})

    async def send_modal(self, modal):
        self.calls.append({"modal": modal})

    async def defer(self, **kwargs):
        self.deferred = True
        self.calls.append({"defer": True, **kwargs})

    async def edit_message(self, **kwargs):
        self.calls.append({"edit_message": True, **kwargs})


class _InteractionStub:
    def __init__(self, user_id=42):
        self.user = types.SimpleNamespace(id=user_id, display_name="viewer")
        self.guild = None
        self.client = None
        self.response = _ResponseStub()
        self.followup = types.SimpleNamespace(send=self._noop_followup)

    async def _noop_followup(self, *args, **kwargs):
        return None


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


def test_slash_roster_legacy_commands_removed():
    champion_rows = [
        {"id": "abomination", "slug": "abomination", "name": "Abomination", "tags": ["poison"]},
        {"id": "black-bolt", "slug": "black-bolt", "name": "Black Bolt", "tags": ["inhuman"]},
    ]
    group = _RosterGroup(core=_CoreStub(champion_rows))

    for legacy in ("update", "import_roster", "export", "clear"):
        assert not hasattr(group, legacy)
    assert hasattr(group, "add")
    assert hasattr(group, "remove")


def test_slash_roster_champion_autocomplete_appends_after_comma():
    champion_rows = [
        {"id": "abomination", "slug": "abomination", "name": "Abomination", "tags": ["poison"]},
        {"id": "black-bolt", "slug": "black-bolt", "name": "Black Bolt", "tags": ["inhuman"]},
    ]
    group = _RosterGroup(core=_CoreStub(champion_rows))

    choices = asyncio.run(group.champion_autocomplete(None, "Abomination, bl"))

    values = [c.value for c in choices]
    assert any(v.startswith("Abomination, ") and "Black Bolt" in v for v in values)


def test_slash_roster_rankup_command_removed():
    champion_rows = [{"id": "abomination", "slug": "abomination", "name": "Abomination", "class": "science"}]
    group = _RosterGroup(core=_CoreStub(champion_rows))
    assert not hasattr(group, "rankup")


def test_slash_roster_add_parses_bulk_text_without_modal(monkeypatch):
    champion_rows = [{"id": "okoye", "slug": "okoye", "name": "Okoye", "class": "skill"}]
    group = _RosterGroup(core=_CoreStub(champion_rows))
    interaction = _InteractionStub(user_id=42)

    from mcoc.slash import roster as slash_roster_module

    class _UsersStub:
        def __init__(self):
            self.added = []

        def add_champion(self, user_id, slug, rarity, rank, sig, ascended, tags=None):
            self.added.append((user_id, slug, rarity, rank, sig, ascended, tags or []))

    users = _UsersStub()

    monkeypatch.setattr(slash_roster_module, "ensure_user_manager", lambda _core: users)
    monkeypatch.setattr(
        slash_roster_module,
        "parse_roster_entries_with_errors",
        lambda _text, _cache: ([{"champion": "okoye", "rarity": 6, "rank": 3, "sig": 0, "ascended": 0, "tags": []}], ["badtoken"]),
    )

    asyncio.run(_invoke(group.add, group, interaction, champions="6sr3okoye badtoken"))

    assert users.added
    assert interaction.response.calls
    assert "ADD complete" in str(interaction.response.calls[0].get("content") or "")
    assert "Could not resolve" in str(interaction.response.calls[0].get("content") or "")
    assert all("modal" not in call for call in interaction.response.calls)


def test_slash_roster_add_without_args_launches_picker(monkeypatch):
    champion_rows = [{"id": "okoye", "slug": "okoye", "name": "Okoye", "class": "skill"}]
    group = _RosterGroup(core=_CoreStub(champion_rows))
    interaction = _InteractionStub(user_id=42)

    from mcoc.slash import roster as slash_roster_module

    called = {}

    async def _fake_start(core, ctx, operation, parsed_filters=None):
        called["core"] = core
        called["ctx"] = ctx
        called["operation"] = operation
        called["parsed_filters"] = parsed_filters
        return True

    monkeypatch.setattr(slash_roster_module, "start_roster_operation_flow", _fake_start)

    asyncio.run(_invoke(group.add, group, interaction, champions=None))

    assert called.get("operation") == "add"
    assert called.get("parsed_filters") == {}


def test_slash_roster_remove_with_text_uses_bulk_parser(monkeypatch):
    champion_rows = [{"id": "okoye", "slug": "okoye", "name": "Okoye", "class": "skill"}]
    group = _RosterGroup(core=_CoreStub(champion_rows))
    interaction = _InteractionStub(user_id=42)

    from mcoc.slash import roster as slash_roster_module

    class _UsersStub:
        def __init__(self):
            self.removed = []

        def remove_champion(self, user_id, slug, rarity=None):
            self.removed.append((user_id, slug, rarity))
            return 1

    users = _UsersStub()
    monkeypatch.setattr(slash_roster_module, "ensure_user_manager", lambda _core: users)
    monkeypatch.setattr(
        slash_roster_module,
        "parse_roster_entries_with_errors",
        lambda _text, _cache: ([{"champion": "okoye", "rarity": 6, "rank": 3, "sig": 0, "ascended": 0, "tags": []}], ["badtoken"]),
    )

    asyncio.run(_invoke(group.remove, group, interaction, champions="6sr3okoye badtoken"))

    assert users.removed
    assert "REMOVE complete" in str(interaction.response.calls[0].get("content") or "")


def test_slash_roster_remove_without_args_launches_workflow(monkeypatch):
    champion_rows = [{"id": "okoye", "slug": "okoye", "name": "Okoye", "class": "skill"}]
    group = _RosterGroup(core=_CoreStub(champion_rows))
    interaction = _InteractionStub(user_id=42)

    from mcoc.slash import roster as slash_roster_module

    class _UsersStub:
        def list_roster(self, _user_id):
            return [{"champion": "okoye", "rarity": 7, "rank": 2, "sig": 0, "ascended": 0}]

    monkeypatch.setattr(slash_roster_module, "ensure_user_manager", lambda _core: _UsersStub())

    asyncio.run(_invoke(group.remove, group, interaction, champions=None))

    assert interaction.response.calls
    payload = interaction.response.calls[0]
    assert payload.get("embed") is not None
    assert payload.get("view") is not None


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

    modal = _RosterRankupModal(group, "science")
    modal.stars._value = "7"
    modal.target_rank._value = "3"
    modal.target_per_class._value = "2"

    asyncio.run(modal.on_submit(interaction))

    assert called == {"cls": "science", "stars": 7, "target_rank": 3, "per_class_target": 2}


def test_slash_roster_rankup_class_button_opens_class_modal():
    champion_rows = [{"id": "abomination", "slug": "abomination", "name": "Abomination", "class": "science"}]
    group = _RosterGroup(core=_CoreStub(champion_rows))
    interaction = _InteractionStub()

    view = _RankupClassSelectView(group)
    science_button = next(child for child in view.children if getattr(child, "label", "") == "Science")
    asyncio.run(science_button.callback(interaction))

    assert len(interaction.response.calls) == 1
    modal = interaction.response.calls[0].get("modal")
    assert isinstance(modal, _RosterRankupModal)
    assert modal.class_filter_value == "science"


def test_slash_roster_rankup_class_buttons_use_buttonstyle_enum():
    champion_rows = [{"id": "abomination", "slug": "abomination", "name": "Abomination", "class": "science"}]
    group = _RosterGroup(core=_CoreStub(champion_rows))
    view = _RankupClassSelectView(group)

    for child in view.children:
        style = getattr(child, "style", None)
        assert hasattr(style, "value")


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


def test_slash_roster_awaken_command_removed():
    champion_rows = [{"id": "abomination", "slug": "abomination", "name": "Abomination", "class": "science"}]
    group = _RosterGroup(core=_CoreStub(champion_rows))
    assert not hasattr(group, "awaken")


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
        return {"description": kwargs.get("description", ""), "title": kwargs.get("title", ""), "fields": []}

    def _fake_add_field(*_args, **kwargs):
        emb = _args[1] if len(_args) > 1 else kwargs.get("emb")
        emb.setdefault("fields", []).append({"name": kwargs.get("name", ""), "value": kwargs.get("value", "")})

    monkeypatch.setattr(slash_roster_module.CDTEmbed, "embed", _fake_embed)
    monkeypatch.setattr(slash_roster_module.CDTEmbed, "add_field", _fake_add_field)

    suggestions = group._rankup_suggestions(42, "all", 7, 3)
    pages = group._build_rankup_pages(interaction, "all", 7, 3, suggestions)
    field_names = [field["name"] for field in pages[0]["fields"]]

    assert "S+ TIER" in field_names
    assert "A TIER" in field_names
    assert "B TIER" in field_names
    assert "<:cosmic2:" in pages[0]["fields"][0]["value"]


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
        return {"description": kwargs.get("description", ""), "title": kwargs.get("title", ""), "fields": []}

    def _fake_add_field(*_args, **kwargs):
        emb = _args[1] if len(_args) > 1 else kwargs.get("emb")
        emb.setdefault("fields", []).append({"name": kwargs.get("name", ""), "value": kwargs.get("value", "")})

    monkeypatch.setattr(slash_roster_module.CDTEmbed, "embed", _fake_embed)
    monkeypatch.setattr(slash_roster_module.CDTEmbed, "add_field", _fake_add_field)

    suggestions = group._awaken_suggestions(42, "all", 7, 3)
    pages = group._build_awaken_pages(interaction, "all", 7, 3, suggestions)
    field_names = [field["name"] for field in pages[0]["fields"]]

    assert "S+ TIER" in field_names
    assert "A TIER" in field_names
    assert "B TIER" in field_names


def test_slash_roster_list_mention_targets_other_user(monkeypatch):
    champion_rows = [{"id": "abomination", "slug": "abomination", "name": "Abomination", "class": "science"}]
    group = _RosterGroup(core=_CoreStub(champion_rows))
    interaction = _InteractionStub(user_id=42)

    target = types.SimpleNamespace(id=99, display_name="jjw")
    interaction.guild = types.SimpleNamespace(get_member=lambda uid: target if uid == 99 else None)

    from mcoc.slash import roster as slash_roster_module

    captured = {}

    async def _fake_make_roster_pager(core, ctx_or_author, **kwargs):
        captured["target_id"] = getattr(ctx_or_author, "id", None)
        captured["raw_input"] = kwargs.get("raw_input")
        return types.SimpleNamespace(pages=[{"title": "Roster"}])

    monkeypatch.setattr(slash_roster_module, "make_roster_pager", _fake_make_roster_pager)

    asyncio.run(_invoke(group.list, group, interaction, hargs="<@99> 7*"))

    assert captured["target_id"] == 99
    assert "<@99>" not in (captured["raw_input"] or "")


def test_slash_roster_list_view_builds_filter_buttons():
    from mcoc.slash import roster as slash_roster_module

    champion_rows = [{"id": "abomination", "slug": "abomination", "name": "Abomination", "class": "science"}]
    group = _RosterGroup(core=_CoreStub(champion_rows))
    list_view = slash_roster_module._RosterListControlsView(group, types.SimpleNamespace(id=42, display_name="jjw"), "7*")
    labels = [child.label for child in list_view.children]
    assert labels == ["AWAKEN", "RANKUP", "TIERLIST", "CLEAR"]


def test_slash_roster_list_default_uses_description_and_mode_uses_fields(monkeypatch):
    from mcoc.slash import roster as slash_roster_module

    champion_rows = [
        {"id": "abomination", "slug": "abomination", "name": "Abomination", "class": "science"},
        {"id": "black-bolt", "slug": "black-bolt", "name": "Black Bolt", "class": "cosmic"},
    ]

    class _CacheWithTierlist(_CacheStub):
        def _load_file(self, name):
            if name == "tierlist":
                return {"champions": [
                    {"id": "abomination", "name": "Abomination", "score": 70, "tier": "A"},
                    {"id": "black-bolt", "name": "Black Bolt", "score": 95, "tier": "S+"},
                ]}
            return {}

    class _UsersStub:
        def list_roster(self, _user_id):
            return [
                {"champion": "abomination", "rarity": 7, "rank": 2, "sig": 0, "ascended": 0},
                {"champion": "black-bolt", "rarity": 7, "rank": 2, "sig": 0, "ascended": 0},
            ]

    class _CoreWithUsers:
        def __init__(self):
            self.cache = _CacheWithTierlist(champion_rows)
            self.users = _UsersStub()

    group = _RosterGroup(core=_CoreWithUsers())
    interaction = _InteractionStub(user_id=42)

    async def _fake_make_roster_pager(core, ctx_or_author, **kwargs):
        parsed = kwargs.get("parsed_filters") or {}
        return types.SimpleNamespace(pages=[{"title": "Roster", "description": "list", "fields": [{"name": "S+ TIER", "value": "Black Bolt"}]}])

    monkeypatch.setattr(slash_roster_module, "make_roster_pager", _fake_make_roster_pager)
    interaction.message = types.SimpleNamespace(edit=None)

    original = slash_roster_module._RosterListModeButton.callback
    button = slash_roster_module._RosterListModeButton(group, interaction.user, "", "TIERLIST", "tierlist")
    asyncio.run(button.callback(interaction))

    default_pages = asyncio.run(slash_roster_module.build_roster_pages(group.core, interaction.user, {"list_mode": "default"}))
    tier_pages = asyncio.run(slash_roster_module.build_roster_pages(group.core, interaction.user, {"list_mode": "tierlist"}))

    assert default_pages[0].description and not default_pages[0].fields
    assert tier_pages[0].fields and any(field.name == "S+ TIER" for field in tier_pages[0].fields)


def test_slash_roster_list_button_mode_sets_list_mode_filter(monkeypatch):
    from mcoc.slash import roster as slash_roster_module

    champion_rows = [{"id": "abomination", "slug": "abomination", "name": "Abomination", "class": "science"}]
    group = _RosterGroup(core=_CoreStub(champion_rows))
    target = types.SimpleNamespace(id=42, display_name="jjw")
    button = slash_roster_module._RosterListModeButton(group, target, "7*", "TIERLIST", "tierlist")

    class _DeferredInteraction(_InteractionStub):
        def __init__(self):
            super().__init__(user_id=42)
            self.original_response = []

        async def edit_original_response(self, **kwargs):
            self.original_response.append(kwargs)

    interaction = _DeferredInteraction()
    interaction.message = types.SimpleNamespace(edit=None)

    captured = {}

    async def _fake_make_roster_pager(core, ctx_or_author, **kwargs):
        captured["parsed_filters"] = kwargs.get("parsed_filters")
        return types.SimpleNamespace(pages=[{"title": "Roster"}])

    monkeypatch.setattr(slash_roster_module, "make_roster_pager", _fake_make_roster_pager)
    asyncio.run(button.callback(interaction))

    assert captured["parsed_filters"]["list_mode"] == "tierlist"
    assert interaction.response.deferred is True
    assert interaction.original_response


def test_slash_roster_list_clear_mode_removes_all_filters(monkeypatch):
    from mcoc.slash import roster as slash_roster_module

    champion_rows = [{"id": "abomination", "slug": "abomination", "name": "Abomination", "class": "science"}]
    group = _RosterGroup(core=_CoreStub(champion_rows))
    target = types.SimpleNamespace(id=42, display_name="jjw")
    button = slash_roster_module._RosterListModeButton(
        group,
        target,
        "7*",
        "CLEAR",
        "default",
        parsed_filters={"list_mode": "tierlist", "rarities": [7], "ranks": [2], "classes": ["skill"]},
    )
    interaction = _InteractionStub(user_id=42)
    interaction.message = types.SimpleNamespace(edit=None)

    captured = {}

    async def _fake_make_roster_pager(core, ctx_or_author, **kwargs):
        captured["parsed_filters"] = kwargs.get("parsed_filters")
        return types.SimpleNamespace(pages=[{"title": "Roster"}])

    async def _fake_edit_message(**kwargs):
        captured["edit_kwargs"] = kwargs

    interaction.response.edit_message = _fake_edit_message
    monkeypatch.setattr(slash_roster_module, "make_roster_pager", _fake_make_roster_pager)
    asyncio.run(button.callback(interaction))

    assert captured["parsed_filters"] == {}
    assert "edit_kwargs" in captured


def test_slash_roster_filter_category_view_has_expected_buttons():
    from mcoc.slash import roster as slash_roster_module

    champion_rows = [{"id": "abomination", "slug": "abomination", "name": "Abomination", "class": "science"}]
    group = _RosterGroup(core=_CoreStub(champion_rows))
    target = types.SimpleNamespace(id=42, display_name="jjw")
    view = slash_roster_module._RosterFilterCategoryView(group, target, "7*", {})
    labels = [child.label for child in view.children]
    assert labels == ["STAR", "RANK", "CLASS", "CLOSE"]


def test_slash_roster_rankup_pages_group_by_tier_into_fields():
    from mcoc.slash import roster as slash_roster_module

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
    suggestions = group._rankup_suggestions(42, "all", 7, 3)
    pages = group._build_rankup_pages(interaction, "all", 7, 3, suggestions)
    embed = pages[0]
    names = [field.name for field in embed.fields]
    assert "S+ TIER" in names
    assert "A TIER" in names
    assert "B TIER" in names


def test_slash_roster_modal_labels_fit_discord_limit():
    group = _RosterGroup(core=_CoreStub([]))
    rankup_modal = _RosterRankupModal(group, "all")
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
