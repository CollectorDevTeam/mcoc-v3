def test_contextmenu_slash_surface_exists():
    import mcoc.slash.contextmenu as contextmenu_module

    assert hasattr(contextmenu_module, "ContextMenuSlashCog")


def test_slash_core_loads_contextmenu_cog():
    import inspect
    import mcoc.slash.core as slash_core_module

    text = inspect.getsource(slash_core_module.MCOCSlash._attach_slash_cogs)

    assert "mcoc.slash.contextmenu" in text
    assert "ContextMenuSlashCog" in text


def test_contextmenu_is_consolidated_to_single_command():
    import inspect
    import mcoc.slash.contextmenu as contextmenu_module

    text = inspect.getsource(contextmenu_module.ContextMenuSlashCog.cog_load)

    assert 'ContextMenu(name="CollectorVerse"' in text
    assert 'ContextMenu(name="CollectorVerse Profile"' not in text
    assert 'ContextMenu(name="Roster Add"' not in text


def test_contextmenu_alliance_manage_has_bg_actions():
    import inspect
    import mcoc.slash.contextmenu as contextmenu_module

    text = inspect.getsource(contextmenu_module._AllianceManageMemberView.__init__)

    assert "Set BG1" in text
    assert "Set BG2" in text
    assert "Set BG3" in text
    assert "Set AQBG1" in text
    assert "Set AQBG2" in text
    assert "Set AQBG3" in text
    assert "Set AWBG1" in text
    assert "Set AWBG2" in text
    assert "Set AWBG3" in text
    assert "Set Manager" in text
