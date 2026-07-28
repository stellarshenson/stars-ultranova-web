"""
Tests for race icons: icon field persistence on the Race model and
custom icon upload validation at the API layer (user directive, wave 5:
16 standard SVG emblems keyed 0-15 plus an optional per-player custom
icon as a base64 data URI, PNG/JPEG/SVG up to 128 kB).
"""
import base64
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.core.race.race import Race
from backend.services.game_manager import (
    GameManager, _race_from_wizard, _validate_custom_icon,
    RACE_ICON_MAX_BYTES
)


# 1x1 transparent PNG (70 bytes decoded)
PNG_1X1 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
    "AAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
PNG_DATA_URI = f"data:image/png;base64,{PNG_1X1}"


def oversized_data_uri() -> str:
    """PNG data URI whose decoded payload exceeds the 128 kB limit."""
    payload = base64.b64encode(b"\x00" * (RACE_ICON_MAX_BYTES + 1))
    return f"data:image/png;base64,{payload.decode()}"


@pytest.fixture(autouse=True)
def reset_global_state():
    """Reset global state before each test."""
    import backend.services.game_manager as gm_module

    gm_module._game_manager = None

    yield

    gm_module._game_manager = None


@pytest.fixture
def client():
    """Create test client with isolated database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        import backend.services.game_manager as gm_module
        gm_module._game_manager = GameManager(db_path)

        with TestClient(app) as client:
            yield client
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


class TestIconFieldPersistence:
    """Icon fields on the Race model and wizard mapping."""

    def test_race_defaults(self):
        race = Race()
        assert race.icon == 0
        assert race.custom_icon == ""

    def test_to_dict_from_dict_round_trip(self):
        race = Race(name="Emblems", icon=7, custom_icon=PNG_DATA_URI)
        data = race.to_dict()
        assert data["icon"] == 7
        assert data["custom_icon"] == PNG_DATA_URI
        restored = Race.from_dict(data)
        assert restored.icon == 7
        assert restored.custom_icon == PNG_DATA_URI

    def test_from_dict_defaults_missing_fields(self):
        # Pre-wave-5 saves carry no icon fields
        restored = Race.from_dict({"name": "Old"})
        assert restored.icon == 0
        assert restored.custom_icon == ""

    def test_wizard_maps_icon_index(self):
        race = _race_from_wizard({"name": "Test", "icon": 12})
        assert race.icon == 12
        assert race.custom_icon == ""

    def test_wizard_maps_custom_icon(self):
        race = _race_from_wizard(
            {"name": "Test", "icon": 3, "customIcon": PNG_DATA_URI})
        assert race.icon == 3
        assert race.custom_icon == PNG_DATA_URI

    def test_wizard_defaults_icon_zero(self):
        race = _race_from_wizard({"name": "Test"})
        assert race.icon == 0
        assert race.custom_icon == ""


class TestCustomIconValidation:
    """_validate_custom_icon size and type rules."""

    def test_valid_png_accepted(self):
        assert _validate_custom_icon(PNG_DATA_URI) == PNG_DATA_URI

    def test_valid_jpeg_and_svg_accepted(self):
        payload = base64.b64encode(b"<svg/>").decode()
        for mime in ("image/jpeg", "image/svg+xml"):
            uri = f"data:{mime};base64,{payload}"
            assert _validate_custom_icon(uri) == uri

    def test_non_image_mime_rejected(self):
        payload = base64.b64encode(b"plain").decode()
        with pytest.raises(ValueError, match="PNG, JPEG or SVG"):
            _validate_custom_icon(f"data:text/plain;base64,{payload}")

    def test_gif_rejected(self):
        payload = base64.b64encode(b"GIF89a").decode()
        with pytest.raises(ValueError, match="PNG, JPEG or SVG"):
            _validate_custom_icon(f"data:image/gif;base64,{payload}")

    def test_not_a_data_uri_rejected(self):
        with pytest.raises(ValueError, match="data URI"):
            _validate_custom_icon("http://example.com/icon.png")

    def test_invalid_base64_rejected(self):
        with pytest.raises(ValueError, match="base64"):
            _validate_custom_icon("data:image/png;base64,!!not-base64!!")

    def test_oversized_rejected(self):
        with pytest.raises(ValueError, match="128 kB"):
            _validate_custom_icon(oversized_data_uri())

    def test_exact_limit_accepted(self):
        payload = base64.b64encode(b"\x00" * RACE_ICON_MAX_BYTES).decode()
        uri = f"data:image/png;base64,{payload}"
        assert _validate_custom_icon(uri) == uri


class TestIconUploadApi:
    """Upload validation surfaced as HTTP 422 at the API layer."""

    def test_create_game_rejects_non_image_icon(self, client):
        response = client.post("/api/games/", json={
            "name": "Icon Game",
            "player_count": 2,
            "universe_size": "small",
            "race": {"name": "Test",
                     "customIcon": "data:text/plain;base64,cGxhaW4="},
        })
        assert response.status_code == 422
        assert "PNG, JPEG or SVG" in response.json()["detail"]

    def test_create_game_rejects_oversized_icon(self, client):
        response = client.post("/api/games/", json={
            "name": "Icon Game",
            "player_count": 2,
            "universe_size": "small",
            "race": {"name": "Test", "customIcon": oversized_data_uri()},
        })
        assert response.status_code == 422
        assert "128 kB" in response.json()["detail"]

    def test_validate_race_rejects_bad_icon(self, client):
        response = client.post("/api/races/validate", json={
            "name": "Test",
            "customIcon": "data:application/pdf;base64,cGxhaW4=",
        })
        assert response.status_code == 422

    def test_create_game_accepts_valid_icon(self, client):
        response = client.post("/api/games/", json={
            "name": "Icon Game",
            "player_count": 2,
            "universe_size": "small",
            "seed": 42,
            "race": {"name": "Test", "icon": 5,
                     "customIcon": PNG_DATA_URI},
        })
        assert response.status_code == 200
        game_id = response.json()["id"]

        # Icon fields round-trip into the player state race payload
        state = client.get(f"/api/games/{game_id}/empires/1/state").json()
        assert state["empire"]["race"]["icon"] == 5
        assert state["empire"]["race"]["custom_icon"] == PNG_DATA_URI
