import types

from mcoc.slash.account import _AccountGroup


class _ResponseStub:
    def __init__(self):
        self.calls = []
        self._done = False

    async def send_message(self, content=None, **kwargs):
        self._done = True
        self.calls.append({"content": content, **kwargs})

    async def defer(self, **kwargs):
        self._done = True
        self.calls.append({"defer": True, **kwargs})

    def is_done(self):
        return self._done


class _FollowupStub:
    def __init__(self):
        self.calls = []

    async def send(self, content=None, **kwargs):
        self.calls.append({"content": content, **kwargs})


class _InteractionStub:
    def __init__(self, user_id=42, display_name="viewer"):
        self.user = types.SimpleNamespace(id=user_id, display_name=display_name)
        self.response = _ResponseStub()
        self.followup = _FollowupStub()


async def _invoke(cmd, group, interaction, *args, **kwargs):
    return await cmd.callback(group, interaction, *args, **kwargs)


def test_slash_account_profile_uses_backend_embed_path(monkeypatch):
    group = _AccountGroup(core=object())
    interaction = _InteractionStub()
    target = types.SimpleNamespace(id=99)
    sentinel_embed = object()

    from mcoc.slash import account as slash_account_module

    monkeypatch.setattr(
        slash_account_module.Account,
        "build_profile_display",
        lambda *a, **k: (sentinel_embed, None),
    )

    import asyncio
    asyncio.run(_invoke(group.profile, group, interaction, user=target))

    assert len(interaction.response.calls) == 1
    assert interaction.response.calls[0].get("defer") is True
    assert len(interaction.followup.calls) == 1
    call = interaction.followup.calls[0]
    assert call.get("embed") is sentinel_embed
    assert call.get("ephemeral") is False


def test_slash_account_select_sets_roster(monkeypatch):
    group = _AccountGroup(core=object())
    interaction = _InteractionStub()

    from mcoc.slash import account as slash_account_module

    monkeypatch.setattr(
        slash_account_module.Account,
        "select_active_roster",
        lambda *a, **k: (True, "Active roster set to `main`."),
    )

    import asyncio
    asyncio.run(_invoke(group.select, group, interaction, roster="main"))

    assert len(interaction.response.calls) == 1
    call = interaction.response.calls[0]
    assert call.get("content") == "Active roster set to `main`."
    assert call.get("ephemeral") is False


def test_slash_account_select_no_rosters(monkeypatch):
    group = _AccountGroup(core=object())
    interaction = _InteractionStub()

    from mcoc.slash import account as slash_account_module

    monkeypatch.setattr(
        slash_account_module.Account,
        "get_selectable_rosters",
        lambda *a, **k: ([], None),
    )

    import asyncio
    asyncio.run(_invoke(group.select, group, interaction, roster=None))

    assert len(interaction.response.calls) == 1
    call = interaction.response.calls[0]
    assert "No rosters are available yet" in call.get("content")
    assert call.get("ephemeral") is True


def test_slash_account_privacy_invalid_mode():
    group = _AccountGroup(core=object())
    interaction = _InteractionStub()

    import asyncio
    asyncio.run(_invoke(group.privacy, group, interaction, mode="team-only"))

    assert len(interaction.response.calls) == 1
    call = interaction.response.calls[0]
    assert "Allowed privacy modes" in call.get("content")
    assert call.get("ephemeral") is True


def test_slash_account_settings_multi_page_uses_pages_menu(monkeypatch):
    group = _AccountGroup(core=object())
    interaction = _InteractionStub()
    target = types.SimpleNamespace(id=99, display_name="Target")

    from mcoc.slash import account as slash_account_module

    sentinel_view = object()

    monkeypatch.setattr(
        slash_account_module.Account,
        "build_settings_pages",
        lambda *a, **k: [object(), object()],
    )
    monkeypatch.setattr(
        slash_account_module,
        "CDTPagesMenu",
        lambda pages, author=None: sentinel_view,
    )

    import asyncio
    asyncio.run(_invoke(group.settings, group, interaction, user=target))

    assert len(interaction.response.calls) == 1
    call = interaction.response.calls[0]
    assert call.get("view") is sentinel_view
    assert call.get("ephemeral") is False


def test_slash_account_settings_empty_pages_returns_ephemeral(monkeypatch):
    group = _AccountGroup(core=object())
    interaction = _InteractionStub()

    from mcoc.slash import account as slash_account_module

    monkeypatch.setattr(
        slash_account_module.Account,
        "build_settings_pages",
        lambda *a, **k: [],
    )

    import asyncio
    asyncio.run(_invoke(group.settings, group, interaction, user=None))

    assert len(interaction.response.calls) == 1
    call = interaction.response.calls[0]
    assert call.get("content") == "No account settings found."
    assert call.get("ephemeral") is True


def test_slash_account_agree_uses_backend_consent(monkeypatch):
    group = _AccountGroup(core=object())
    interaction = _InteractionStub()

    from mcoc.slash import account as slash_account_module

    async def _fake_handle(*a, **k):
        return True, "Consent recorded."

    monkeypatch.setattr(
        slash_account_module.Account,
        "handle_consent_response",
        _fake_handle,
    )

    import asyncio
    asyncio.run(_invoke(group.agree, group, interaction))

    assert len(interaction.response.calls) == 1
    call = interaction.response.calls[0]
    assert call.get("content") == "Consent recorded."
    assert call.get("ephemeral") is True


def test_slash_account_create_uses_backend_enroll_handler(monkeypatch):
    group = _AccountGroup(core=object())
    interaction = _InteractionStub()

    from mcoc.slash import account as slash_account_module

    async def _fake_enroll(*a, **k):
        return False, "policy backend unavailable"

    monkeypatch.setattr(
        slash_account_module.Account,
        "enroll_command_handler",
        _fake_enroll,
    )

    import asyncio
    asyncio.run(_invoke(group.create, group, interaction))

    assert len(interaction.response.calls) == 1
    call = interaction.response.calls[0]
    assert call.get("content") == "Failed to start enrollment: policy backend unavailable"
    assert call.get("ephemeral") is True


def test_account_compute_top5_from_roster_ignores_stale_prestige_cache():
    class _Cache:
        def get_prestige_value(self, slug, stars, rank, ascended, sig):
            return {"abomination": 4200, "black-bolt": 3500}.get(slug, 0)

    profile = {"prestige_map": {"abomination|6": 99999, "black-bolt|6": 99999}}
    roster = [
        {"champion": "abomination", "rarity": 6, "rank": 1, "sig": 0, "ascended": 0},
        {"champion": "black-bolt", "rarity": 6, "rank": 1, "sig": 0, "ascended": 0},
    ]

    from mcoc.common.helpers import account as account_helpers

    lines, total = account_helpers.compute_top5_from_roster(type("Core", (), {"cache": _Cache()})(), roster, profile)

    assert total == 7700
    assert "abomination" in lines[0]
    assert "4200" in lines[0]
    assert "black-bolt" in lines[1]
    assert "3500" in lines[1]


def test_slash_account_set_updates_profile_field(monkeypatch):
    group = _AccountGroup(core=object())
    interaction = _InteractionStub()

    from mcoc.slash import account as slash_account_module

    monkeypatch.setattr(
        slash_account_module.Account,
        "set_profile_field",
        lambda *a, **k: True,
    )

    import asyncio
    asyncio.run(_invoke(group.set, group, interaction, field="about", value="hello world"))

    assert len(interaction.response.calls) == 1
    call = interaction.response.calls[0]
    assert call.get("content") == "Updated about: hello world"
    assert call.get("ephemeral") is True
