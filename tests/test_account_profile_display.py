from types import SimpleNamespace

from mcoc.common.helpers.account import build_profile_display


class _UsersStub:
    def __init__(self, profile, roster=None):
        self._profile = profile
        self._roster = roster or []

    def get_profile(self, target_id):
        return self._profile

    def can_view_profile(self, viewer_id, target_id, guild_id=None):
        return True

    def list_roster(self, target_id):
        return list(self._roster)


class _CacheStub:
    def get_prestige_value(self, slug, stars, rank, asc, sig):
        return None

    def get_cocpit_abilities(self, slug):
        values = {
            "colossus": 12580,
            "okoye": 12010,
        }
        v = values.get(str(slug).lower())
        if v is None:
            return None
        return {"raw": {"baseStats": {"Prestige": v}}}

    def get_champion_obj(self, slug):
        return SimpleNamespace(name={"colossus": "Colossus", "okoye": "Okoye"}.get(slug, slug))


class _ParentStub:
    def __init__(self, profile, roster=None):
        self.users = _UsersStub(profile, roster=roster)
        self.cache = _CacheStub()


def test_profile_display_includes_username_id_and_prestige_summary():
    profile = {
        "mcoc_name": "hero_name",
        "mcoc_id": "player-123",
        "link_status": "linked",
        "linked": True,
        "prestige_map": {"colossus|7": 1800, "okoye|7": 1200},
    }
    ctx = SimpleNamespace(author=SimpleNamespace(id=42, display_name="viewer"), guild=None)
    emb, text = build_profile_display(_ParentStub(profile), ctx, 99, viewer_id=42, prefer_embed=True)

    assert text is None
    assert emb is not None
    field_names = [f["name"] for f in emb.to_dict()["fields"]]
    assert "MCOC Username" in field_names
    assert "MCOC ID" in field_names
    assert "Prestige (sum)" in field_names
    assert "Top 5 Champions" in field_names

    values = {f["name"]: f["value"] for f in emb.to_dict()["fields"]}
    assert values["MCOC Username"] == "hero_name"
    assert values["MCOC ID"] == "player-123"
    assert values["Prestige (sum)"] == "3000"
    assert "colossus" in values["Top 5 Champions"].lower()
    assert "okoye" in values["Top 5 Champions"].lower()


def test_profile_display_prefers_active_roster_over_zero_prestige_map():
    profile = {
        "mcoc_name": "hero_name",
        "mcoc_id": "player-123",
        "linked": True,
        "active_roster": "main",
        "prestige_map": {"colossus|6": 0, "okoye|6": 0},
        "rosters": {
            "main": [
                {"champion": "colossus", "rarity": 6, "rank": 1, "sig": 0, "ascended": 0},
                {"champion": "okoye", "rarity": 6, "rank": 1, "sig": 0, "ascended": 0},
            ]
        },
    }
    # list_roster intentionally empty to assert active-roster selection is used.
    parent = _ParentStub(profile, roster=[])
    ctx = SimpleNamespace(author=SimpleNamespace(id=42, display_name="viewer"), guild=None)
    emb, text = build_profile_display(parent, ctx, 99, viewer_id=42, prefer_embed=True)

    assert text is None
    assert emb is not None
    values = {f["name"]: f["value"] for f in emb.to_dict()["fields"]}

    assert values["Prestige (sum)"] == str(12580 + 12010)
    top5 = values["Top 5 Champions"].lower()
    assert "colossus" in top5
    assert "okoye" in top5
