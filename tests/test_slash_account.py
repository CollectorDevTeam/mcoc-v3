import types

import discord

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


def test_slash_account_select_requires_premium_for_roster_switch(monkeypatch):
    group = _AccountGroup(core=object())
    interaction = _InteractionStub()

    from mcoc.slash import account as slash_account_module

    monkeypatch.setattr(
        slash_account_module.Account,
        "get_selectable_rosters",
        lambda *a, **k: (["main", "alt"], "main"),
    )
    monkeypatch.setattr(
        slash_account_module,
        "user_has_collectorverse_premium",
        lambda user: False,
    )

    import asyncio
    asyncio.run(_invoke(group.select, group, interaction, roster="alt"))

    assert len(interaction.response.calls) == 1
    call = interaction.response.calls[0]
    assert "Premium membership is required" in call.get("content")
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


def test_slash_account_edit_page_has_no_privacy_field():
    from mcoc.slash.account import _PROFILE_PAGE_LAYOUTS, _ProfilePageSelectorView

    flattened = [field_name for page in _PROFILE_PAGE_LAYOUTS.values() for _, field_name, _ in page]
    assert "privacy_mode" not in flattened

    view = _ProfilePageSelectorView(core=object(), user_id=42, profile={"mcoc_name": "tester"}, mode="edit")
    assert all(getattr(item, "label", "") != "PRIVACY" for item in view.children)
    assert [getattr(item, "label", "") for item in view.children if isinstance(item, discord.ui.Button)] == ["Info", "Details"]


def test_account_settings_pages_exclude_privacy_from_generic_fields(monkeypatch):
    from mcoc.common.helpers import account as account_helper

    profile = {"mcoc_name": "tester", "privacy_mode": "private"}
    monkeypatch.setattr(account_helper, "get_profile", lambda *a, **k: profile)

    pages = account_helper.build_settings_pages(object(), object(), 42, title_prefix="Tester")
    assert pages
    field_names = []
    for page in pages:
        field_names.extend(getattr(page, "fields", []))
    assert all("privacy_mode" not in getattr(field, "name", "") for field in field_names)


def test_profile_edit_modal_timezone_uses_text_input_not_select():
    from mcoc.slash.account import _ProfileSettingsModal

    modal = _ProfileSettingsModal(core=object(), user_id=42, profile={"timezone": "UTC"}, page=1)
    tz_input = modal.inputs["timezone"]

    assert isinstance(tz_input, discord.ui.TextInput)
    assert tz_input.default == "UTC"


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


def test_slash_account_root_command_opens_account_manager(monkeypatch):
    from mcoc.slash.account import AccountSlashCog

    cog = AccountSlashCog(bot=object())
    interaction = _InteractionStub()

    import asyncio

    asyncio.run(_invoke(cog.account, cog, interaction))

    assert len(interaction.response.calls) == 1
    content = interaction.response.calls[0].get("content")
    assert content.startswith("Manage your CollectorVerse account settings and privacy.")
    assert "runtime:" in content.lower()


def test_account_manager_no_profile_shows_create_only(monkeypatch):
    from mcoc.slash.account import _AccountManagerView

    monkeypatch.setattr(
        "mcoc.slash.account.Account.get_profile",
        lambda *a, **k: {},
    )
    monkeypatch.setattr(
        "mcoc.slash.account.Account.user_has_consented",
        lambda *a, **k: False,
    )

    view = _AccountManagerView(core=object(), user_id=42)
    labels = [item.label for item in view.children]

    assert labels == ["CREATE"]
    assert "CONSENT" not in labels


def test_user_has_profile_rejects_default_placeholder_profile(monkeypatch):
    from mcoc.common.helpers import account as account_helpers

    profile = {
        "mcoc_id": None,
        "mcoc_name": None,
        "consent": False,
        "consent_ts": None,
        "website": None,
        "timezone": None,
        "alliance": None,
        "job": None,
        "created_at": None,
        "updated_at": None,
    }
    monkeypatch.setattr(account_helpers, "get_profile", lambda *a, **k: profile)

    assert account_helpers.user_has_profile(object(), 42) is False


def test_account_manager_after_consent_has_standard_actions(monkeypatch):
    from mcoc.slash.account import _AccountManagerView

    monkeypatch.setattr(
        "mcoc.slash.account.Account.get_profile",
        lambda *a, **k: {"consent": True, "privacy_mode": "private"},
    )
    monkeypatch.setattr(
        "mcoc.slash.account.Account.user_has_consented",
        lambda *a, **k: True,
    )
    monkeypatch.setattr(
        "mcoc.slash.account.Account.user_has_profile",
        lambda *a, **k: True,
    )

    view = _AccountManagerView(core=object(), user_id=42)
    labels = [item.label for item in view.children]

    assert labels == ["VIEW", "EDIT", "PRIVACY"]
    assert "CREATE" not in labels
    assert "CONSENT" not in labels


def test_account_manager_rechecks_live_account_state_before_actions(monkeypatch):
    from mcoc.slash.account import _AccountManagerView

    state = {"has_account": False}

    monkeypatch.setattr(
        "mcoc.slash.account.Account.get_profile",
        lambda *a, **k: {"mcoc_name": "tester"} if state["has_account"] else {},
    )
    monkeypatch.setattr(
        "mcoc.slash.account.Account.user_has_consented",
        lambda *a, **k: False,
    )
    monkeypatch.setattr(
        "mcoc.slash.account.Account.user_has_profile",
        lambda *a, **k: state["has_account"],
    )

    view = _AccountManagerView(core=object(), user_id=42)
    assert [item.label for item in view.children] == ["CREATE"]

    state["has_account"] = True
    view._refresh_state()
    assert view.has_account is True

    calls = []

    class _ResponseStub:
        async def send_message(self, *args, **kwargs):
            calls.append({"message": args[0], "kwargs": kwargs})

    interaction = types.SimpleNamespace(response=_ResponseStub())
    import asyncio
    asyncio.run(view.children[0].callback(interaction))

    assert len(calls) == 1
    assert calls[0]["message"] == "You already have an account configured."
    assert calls[0]["kwargs"]["ephemeral"] is True


def test_runtime_version_label_returns_commit_and_branch(monkeypatch):
    from mcoc.slash import account as slash_account_module

    class _Result:
        def __init__(self, returncode, stdout, stderr=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def _fake_run(cmd, capture_output, text, check):
        if "--short" in cmd:
            return _Result(0, "b645348\n", "")
        if "--abbrev-ref" in cmd:
            return _Result(0, "dev-slash\n", "")
        return _Result(0, "", "")

    monkeypatch.setattr(slash_account_module.subprocess, "run", _fake_run)
    assert slash_account_module._runtime_version_label() == "runtime: b645348 (dev-slash)"


def test_profile_settings_page_selector_has_single_roster_selector(monkeypatch):
    from mcoc.slash.account import _ProfilePageSelectorView

    monkeypatch.setattr(
        "mcoc.slash.account.Account.get_selectable_rosters",
        lambda *a, **k: (["main"], "main"),
    )

    view = _ProfilePageSelectorView(core=object(), user_id=42, profile={}, mode="edit")
    roster_selector = view.children[0]

    assert roster_selector is not None
    assert [option.value for option in roster_selector.options] == ["main"]
    assert roster_selector.options[0].default is True


def test_account_manager_view_action_edits_active_message(monkeypatch):
    from mcoc.slash.account import _AccountManagerView

    monkeypatch.setattr(
        "mcoc.slash.account.Account.get_profile",
        lambda *a, **k: {"mcoc_name": "tester", "privacy_mode": "private"},
    )
    monkeypatch.setattr(
        "mcoc.slash.account.Account.user_has_consented",
        lambda *a, **k: True,
    )
    monkeypatch.setattr(
        "mcoc.slash.account.Account.user_has_profile",
        lambda *a, **k: True,
    )

    view = _AccountManagerView(core=object(), user_id=42)
    calls = []

    class _ResponseStub:
        async def edit_message(self, **kwargs):
            calls.append({"edit_message": True, **kwargs})

        async def send_message(self, *args, **kwargs):
            calls.append({"send_message": True, "args": args, "kwargs": kwargs})

    interaction = types.SimpleNamespace(user=types.SimpleNamespace(id=42), response=_ResponseStub())
    import asyncio
    asyncio.run(view.children[0].callback(interaction))

    assert any("edit_message" in call for call in calls)
    assert not any("send_message" in call for call in calls)


def test_account_manager_modal_errors_show_the_real_reason(monkeypatch):
    from mcoc.slash.account import _ProfilePageSelectorView

    view = _ProfilePageSelectorView(core=object(), user_id=42, profile={"mcoc_name": "tester"}, mode="view")
    calls = []

    class _ResponseStub:
        def __init__(self):
            self.calls = 0

        async def send_modal(self, *args, **kwargs):
            self.calls += 1
            raise RuntimeError("modal blocked")

        async def send_message(self, *args, **kwargs):
            calls.append({"message": args[0], "kwargs": kwargs})

    interaction = types.SimpleNamespace(response=_ResponseStub())
    import asyncio
    asyncio.run(view.children[1].callback(interaction))

    assert len(calls) == 1
    assert "modal blocked" in calls[0]["message"]
    assert calls[0]["kwargs"]["ephemeral"] is True


def test_user_has_profile_counts_created_account_record(monkeypatch):
    from mcoc.common.helpers import account as account_helpers

    monkeypatch.setattr(
        account_helpers,
        "get_profile",
        lambda *a, **k: {"consent": True, "created_at": "2026-10-23T10:26:00Z", "privacy_mode": "private"},
    )

    assert account_helpers.user_has_profile(object(), 42) is True


def test_account_manager_decline_keeps_empty_profile_out_of_manager(monkeypatch):
    from mcoc.slash.account import _AccountManagerView

    monkeypatch.setattr(
        "mcoc.slash.account.Account.get_profile",
        lambda *a, **k: {"consent": False, "consent_ts": "2026-01-01T00:00:00Z"},
    )
    monkeypatch.setattr(
        "mcoc.slash.account.Account.user_has_consented",
        lambda *a, **k: False,
    )
    monkeypatch.setattr(
        "mcoc.slash.account.Account.user_has_profile",
        lambda *a, **k: False,
    )

    view = _AccountManagerView(core=object(), user_id=42)
    labels = [item.label for item in view.children]

    assert labels == ["CREATE"]
    assert "VIEW" not in labels
    assert "EDIT" not in labels
    assert "PRIVACY" not in labels


def test_account_manager_privacy_mode_only_is_not_treated_as_real_account(monkeypatch):
    from mcoc.slash.account import _AccountManagerView

    monkeypatch.setattr(
        "mcoc.slash.account.Account.get_profile",
        lambda *a, **k: {"privacy_mode": "private"},
    )
    monkeypatch.setattr(
        "mcoc.slash.account.Account.user_has_consented",
        lambda *a, **k: False,
    )
    monkeypatch.setattr(
        "mcoc.slash.account.Account.user_has_profile",
        lambda *a, **k: False,
    )

    view = _AccountManagerView(core=object(), user_id=42)
    labels = [item.label for item in view.children]

    assert labels == ["CREATE"]
    assert "VIEW" not in labels
    assert "EDIT" not in labels
    assert "PRIVACY" not in labels


def test_account_privacy_view_updates_current_mode_in_place(monkeypatch):
    from mcoc.slash.account import _AccountPrivacyView

    class _R:
        def __init__(self):
            self.calls = []

        async def edit_message(self, **kwargs):
            self.calls.append(kwargs)

        async def send_message(self, *args, **kwargs):
            self.calls.append({"send": True, "args": args, "kwargs": kwargs})

    interaction = types.SimpleNamespace(response=_R())
    monkeypatch.setattr("mcoc.slash.account.Account.get_profile", lambda *a, **k: {"privacy_mode": "private"})
    monkeypatch.setattr("mcoc.slash.account.Account.set_profile_field", lambda *a, **k: True)

    view = _AccountPrivacyView(core=object(), user_id=42)
    asyncio = __import__("asyncio")
    asyncio.run(view.private_btn.callback(interaction))

    assert view.current_mode == "private"
    assert view.private_btn.style == __import__("discord").ButtonStyle.green
    assert interaction.response.calls[0]["content"].startswith("Current privacy mode: private")


def test_delete_user_profile_removes_underlying_settings_file_when_manager_has_no_delete_method(tmp_path):
    from mcoc.common.helpers import account as account_helpers

    class _Manager:
        def __init__(self, base_dir):
            self.user_dir = base_dir

        def _path(self, user_id):
            return self.user_dir / f"{user_id}.json"

    manager = _Manager(tmp_path)
    target = manager._path(123)
    target.write_text('{"profile":{"mcoc_name":"tester"}}', encoding="utf-8")

    ok, msg = account_helpers.delete_user_profile(manager, 123)

    assert ok is True
    assert target.exists() is False
    assert "deleted" in msg.lower()


def test_slash_public_profile_command_uses_defer_and_followup(monkeypatch):
    from mcoc.slash.account import AccountSlashCog

    cog = AccountSlashCog(bot=object())
    interaction = _InteractionStub()
    sentinel_embed = object()

    from mcoc.slash import account as slash_account_module
    monkeypatch.setattr(slash_account_module.Account, "build_profile_display", lambda *a, **k: (sentinel_embed, None))

    import asyncio
    asyncio.run(_invoke(cog.profile, cog, interaction, user=None))

    assert len(interaction.response.calls) == 1
    assert interaction.response.calls[0].get("defer") is True
    assert len(interaction.followup.calls) == 1
    assert interaction.followup.calls[0].get("embed") is sentinel_embed


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
