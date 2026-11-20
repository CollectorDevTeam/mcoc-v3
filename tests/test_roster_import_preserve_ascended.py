from mcoc.common.helpers.roster import import_roster_entries


class _UsersStub:
    def __init__(self):
        self.calls = []

    def list_roster(self, _user_id):
        return [
            {"champion": "colossus", "rarity": 7, "rank": 2, "sig": 0, "ascended": 1},
            {"champion": "doctor-doom", "rarity": 6, "rank": 5, "sig": 80, "ascended": 0},
        ]

    def add_champion(self, user_id, champ_slug, rarity, rank, sig, ascended=0, tags=None):
        self.calls.append(
            {
                "user_id": user_id,
                "champion": champ_slug,
                "rarity": rarity,
                "rank": rank,
                "sig": sig,
                "ascended": ascended,
                "tags": tags or [],
            }
        )


def test_import_roster_entries_preserves_existing_ascended_when_enabled():
    users = _UsersStub()
    result = import_roster_entries(
        object(),
        42,
        [
            {"champion": "colossus", "rarity": 7, "rank": 4, "sig": 0, "ascended": 0, "tags": []},
            {"champion": "doctor-doom", "rarity": 6, "rank": 5, "sig": 80, "ascended": 0, "tags": []},
        ],
        users=users,
        preserve_existing_ascended=True,
    )

    assert result["imported"] == 2
    assert result["errors"] == []
    assert users.calls[0]["champion"] == "colossus"
    assert users.calls[0]["ascended"] == 1
    assert users.calls[1]["champion"] == "doctor-doom"
    assert users.calls[1]["ascended"] == 0


def test_import_roster_entries_does_not_preserve_when_disabled():
    users = _UsersStub()
    result = import_roster_entries(
        object(),
        42,
        [
            {"champion": "colossus", "rarity": 7, "rank": 4, "sig": 0, "ascended": 0, "tags": []},
        ],
        users=users,
        preserve_existing_ascended=False,
    )

    assert result["imported"] == 1
    assert result["errors"] == []
    assert users.calls[0]["champion"] == "colossus"
    assert users.calls[0]["ascended"] == 0
