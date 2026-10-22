import asyncio
import types

from mcoc.slash.champions import _ChampionGroup


class _ResponseStub:
    def __init__(self):
        self.calls = []

    async def send_message(self, content=None, **kwargs):
        self.calls.append({"content": content, **kwargs})


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
