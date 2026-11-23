def test_alliance_slash_surface_exists():
    import mcoc.slash.alliance as alliance_module

    assert hasattr(alliance_module, "AllianceSlashCog")
    assert hasattr(alliance_module, "_AllianceGroup")
    assert hasattr(alliance_module, "_AllianceSettingsView")


def test_setup_does_not_register_legacy_prefix_ui():
    import mcoc.core as mcoc_core_module

    source = mcoc_core_module.setup.__code__.co_consts
    text = "\n".join(str(item) for item in source if isinstance(item, str))

    assert "MCOCPrefix" not in text
    assert "mcoc.prefix.account" not in text


def test_alliance_group_has_profile_and_settings():
    import inspect
    import mcoc.slash.alliance as alliance_module

    text = inspect.getsource(alliance_module._AllianceGroup)

    assert 'name="profile"' in text
    assert 'name="settings"' in text


def test_alliance_settings_view_has_required_buttons():
    import inspect
    import mcoc.slash.alliance as alliance_module

    text = inspect.getsource(alliance_module._AllianceSettingsView)

    assert "CREATE" in text
    assert "REPORTS" in text
    assert "MANAGE" in text
    assert "DELETE" in text


def test_alliance_owner_sees_create_when_no_alliance_exists():
    import types
    import mcoc.slash.alliance as alliance_module

    guild = types.SimpleNamespace(id=99, name="Test Guild", owner_id=42)
    author = types.SimpleNamespace(id=42, roles=[], guild_permissions=types.SimpleNamespace(administrator=True))

    caps = alliance_module._caps_for(author, guild, None)
    assert "create" in caps

    view = alliance_module._AllianceSettingsView(object(), caps, guild, author, None)
    labels = [getattr(item, "label", "") for item in view.children if hasattr(item, "label")]
    assert "CREATE" in labels


def test_alliance_profile_is_display_only_without_manage_button():
    import inspect
    import mcoc.slash.alliance as alliance_module

    text = inspect.getsource(alliance_module._AllianceGroup)
    assert "_AllianceProfileActionsView" not in text
    assert "MANAGE TARGET" not in text


def test_alliance_reports_view_exists_and_has_summary_and_bg_select():
    import inspect
    import mcoc.slash.alliance as alliance_module

    text = inspect.getsource(alliance_module._AllianceReportsView)
    assert "DIAGNOSTICS" in text
    assert "ALLIANCE SUMMARY" in text
    assert "_AllianceBattlegroupReportSelect" in text


def test_alliance_manage_workflow_uses_three_pages():
    import inspect
    import mcoc.slash.alliance as alliance_module

    text = inspect.getsource(alliance_module._AllianceSettingsView.manage_btn)
    assert "_AllianceManageInfoModal" in text

    confirm = inspect.getsource(alliance_module._AllianceManageConfirmView)
    assert "Page 3" in confirm
    assert "YES" in confirm
    assert "NO" in confirm


def test_alliance_create_and_manage_buttons_use_resilient_response_helper():
    import inspect
    import mcoc.slash.alliance as alliance_module

    create_text = inspect.getsource(alliance_module._AllianceSettingsView.create_btn)
    manage_text = inspect.getsource(alliance_module._AllianceSettingsView.manage_btn)
    assert "_edit_or_send(interaction" in create_text
    assert "_edit_or_send(interaction" in manage_text
    assert "interaction.response.edit_message" not in create_text
    assert "interaction.response.edit_message" not in manage_text


def test_alliance_cog_registers_group_command():
    import inspect
    import mcoc.slash.alliance as alliance_module

    text = inspect.getsource(alliance_module.AllianceSlashCog.cog_load)
    assert "add_command(self._group" in text
