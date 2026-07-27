"""
Seeded e2e scenario: race icons (user directive, wave 5).

A custom race carrying a standard emblem index plus an uploaded custom
icon (base64 data URI) round-trips through game creation into the
player state, survives turn generation, and invalid uploads are
rejected with HTTP 422 without creating a game.
"""
import base64

from backend.services.game_manager import RACE_ICON_MAX_BYTES

# 1x1 transparent PNG
PNG_DATA_URI = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
    "AAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

SEED = 4242


class TestRaceIcons:
    """Race icon persistence through game creation and turns."""

    def test_icon_round_trips_through_game_and_turns(self, harness):
        harness.create_game(SEED, race={
            "name": "Emblem Bearers",
            "pluralName": "Emblem Bearers",
            "icon": 7,
            "customIcon": PNG_DATA_URI,
        })

        race = harness.state(1)["empire"]["race"]
        assert race["icon"] == 7
        assert race["custom_icon"] == PNG_DATA_URI

        # AI empire carries its template emblem index (Rabbitoids -> 1)
        ai_race = harness.state(2)["empire"]["race"]
        assert ai_race["icon"] == 1
        assert ai_race["custom_icon"] == ""

        # Icons survive turn generation and persistence
        for _ in range(3):
            harness.generate_turn()
        race = harness.state(1)["empire"]["race"]
        assert race["icon"] == 7
        assert race["custom_icon"] == PNG_DATA_URI

    def test_invalid_uploads_rejected_without_game(self, harness):
        games_before = harness.client.get("/api/games/").json()

        # Non-image upload
        response = harness.client.post("/api/games/", json={
            "name": "Bad Icon", "player_count": 2,
            "universe_size": "small", "seed": SEED,
            "race": {"name": "Test",
                     "customIcon": "data:text/plain;base64,cGxhaW4="},
        })
        assert response.status_code == 422
        assert "PNG, JPEG or SVG" in response.json()["detail"]

        # Oversized upload (decoded payload over 128 kB)
        payload = base64.b64encode(
            b"\x00" * (RACE_ICON_MAX_BYTES + 1)).decode()
        response = harness.client.post("/api/games/", json={
            "name": "Big Icon", "player_count": 2,
            "universe_size": "small", "seed": SEED,
            "race": {"name": "Test",
                     "customIcon": f"data:image/png;base64,{payload}"},
        })
        assert response.status_code == 422
        assert "128 kB" in response.json()["detail"]

        # Selection unchanged: no game was created
        games_after = harness.client.get("/api/games/").json()
        assert len(games_after) == len(games_before)
