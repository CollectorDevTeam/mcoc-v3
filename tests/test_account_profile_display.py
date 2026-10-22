from types import SimpleNamespace

from mcoc.common.helpers.account import build_profile_display


class _UsersStub:
    def __init__(self, profile):
        self._profile = profile

    def get_profile(self, target_id):
        return self._profile

    def can_view_profile(self, viewer_id, target_id, guild_id=None):
        return True

    def list_roster(self, target_id):
        return []


class _CacheStub:
    def get_champion_obj(self, slug):
        return SimpleNamespace(name={"colossus": "Colossus", "okoye": "Okoye"}.get(slug, slug))


class _ParentStub:
    def __init__(self, profile):
        self.users = _UsersStub(profile)
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
