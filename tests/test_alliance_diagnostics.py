from mcoc.common.helpers import alliance as Alliance


def test_alliance_type_normalization():
    assert Alliance.normalize_alliance_type("simple") == "simple"
    assert Alliance.normalize_alliance_type("advanced") == "advanced"
    assert Alliance.normalize_alliance_type("complex") == "advanced"


def test_expected_battlegroup_keys_by_type():
    assert Alliance.expected_battlegroup_keys("simple") == ["bg1", "bg2", "bg3"]
    assert Alliance.expected_battlegroup_keys("advanced") == [
        "aqbg1",
        "aqbg2",
        "aqbg3",
        "awbg1",
        "awbg2",
        "awbg3",
    ]
