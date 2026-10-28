from mcoc.common.helpers import account as account_helpers


class _UsersStub:
    def __init__(self, profile, roster=None):
        self.profile = dict(profile)
        self.roster = list(roster or [])

    def get_profile(self, user_id):
        return dict(self.profile)

    def list_roster(self, user_id):
        return list(self.roster)

    def set_profile_field(self, user_id, field, value):
        self.profile[field] = value


class _ParentStub:
    def __init__(self, users):
        self.users = users


def test_get_selectable_rosters_from_profile_rosters_dict():
    users = _UsersStub(
        {
            "active_roster": "main",
            "rosters": {"main": [], "alt": []},
        }
    )
    roster_ids, active = account_helpers.get_selectable_rosters(_ParentStub(users), 1)
    assert roster_ids == ["main", "alt"]
    assert active == "main"


def test_get_selectable_rosters_defaults_single_list_roster():
    users = _UsersStub(
        {
            "mcoc_name": "hero",
        },
        roster=[{"champion": "colossus", "rarity": 6, "rank": 1, "sig": 0}],
    )
    roster_ids, active = account_helpers.get_selectable_rosters(_ParentStub(users), 1)
    assert roster_ids == ["default"]
    assert active == "default"


def test_select_active_roster_case_insensitive_match_updates_profile():
    users = _UsersStub(
        {
            "rosters": {"Main": [], "Alt": []},
        }
    )
    ok, msg = account_helpers.select_active_roster(_ParentStub(users), 1, "main")
    assert ok is True
    assert "Main" in msg
    assert users.profile.get("active_roster") == "Main"
