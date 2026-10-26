def test_alliance_slash_surface_exists():
    import mcoc.slash.alliance as alliance_module

    assert hasattr(alliance_module, "AllianceSlashCog")
    assert hasattr(alliance_module, "_AllianceRootView")


def test_setup_does_not_register_legacy_prefix_ui():
    import mcoc.core as mcoc_core_module

    source = mcoc_core_module.setup.__code__.co_consts
    text = "\n".join(str(item) for item in source if isinstance(item, str))

    assert "MCOCPrefix" not in text
    assert "mcoc.prefix.account" not in text


def test_alliance_root_view_includes_expected_actions():
    import inspect
    import mcoc.slash.alliance as alliance_module

    text = inspect.getsource(alliance_module._AllianceRootView)

    assert "CREATE SIMPLE" in text
    assert "CREATE ADVANCED" in text
    assert "TYPE SIMPLE" in text
    assert "TYPE ADVANCED" in text
    assert "DIAGNOSTICS" in text
    assert "MANAGE TARGET" in text
    assert "DELETE" in text


def test_alliance_cog_registers_root_command():
    import inspect
    import mcoc.slash.alliance as alliance_module

    text = inspect.getsource(alliance_module.AllianceSlashCog.cog_load)
    assert "add_command(self.alliance" in text


def test_alliance_cog_group_alias_points_to_root_command():
    import inspect
    import mcoc.slash.alliance as alliance_module

    text = inspect.getsource(alliance_module.AllianceSlashCog.group.fget)
    assert "return self.alliance" in text
