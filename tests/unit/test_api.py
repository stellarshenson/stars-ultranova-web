"""
Tests for API endpoints.
"""
import pytest
import tempfile
import os
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.game_manager import GameManager, _game_manager
from backend.persistence.database import _database


@pytest.fixture(autouse=True)
def reset_global_state():
    """Reset global state before each test."""
    # Reset global instances
    import backend.services.game_manager as gm_module
    import backend.persistence.database as db_module

    gm_module._game_manager = None
    db_module._database = None

    yield

    # Cleanup after test
    gm_module._game_manager = None
    db_module._database = None


@pytest.fixture
def client():
    """Create test client with isolated database."""
    # Use temp file for database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        # Set up game manager with temp database
        import backend.services.game_manager as gm_module
        gm_module._game_manager = GameManager(db_path)

        with TestClient(app) as client:
            yield client
    finally:
        # Cleanup temp database
        if os.path.exists(db_path):
            os.unlink(db_path)


class TestGameEndpoints:
    """Tests for /api/games endpoints."""

    def test_create_game(self, client):
        """Test creating a new game."""
        response = client.post("/api/games/", json={
            "name": "Test Game",
            "player_count": 2,
            "universe_size": "small"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Game"
        assert data["player_count"] == 2
        assert data["universe_size"] == "small"
        assert data["status"] == "active"
        assert "id" in data
        assert data["turn"] == 2100  # STARTING_YEAR

    def test_list_games_empty(self, client):
        """Test listing games when none exist."""
        response = client.get("/api/games/")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_games_with_game(self, client):
        """Test listing games after creating one."""
        # Create a game first
        client.post("/api/games/", json={"name": "Test Game"})

        response = client.get("/api/games/")
        assert response.status_code == 200
        games = response.json()
        assert len(games) == 1
        assert games[0]["name"] == "Test Game"

    def test_get_game(self, client):
        """Test getting a specific game."""
        # Create a game
        create_response = client.post("/api/games/", json={"name": "Test Game"})
        game_id = create_response.json()["id"]

        # Get the game
        response = client.get(f"/api/games/{game_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Game"
        assert data["id"] == game_id

    def test_get_game_not_found(self, client):
        """Test getting a non-existent game."""
        response = client.get("/api/games/nonexistent-id")
        assert response.status_code == 404

    def test_delete_game(self, client):
        """Test deleting a game."""
        # Create a game
        create_response = client.post("/api/games/", json={"name": "Test Game"})
        game_id = create_response.json()["id"]

        # Delete it
        response = client.delete(f"/api/games/{game_id}")
        assert response.status_code == 200

        # Verify it's gone
        response = client.get(f"/api/games/{game_id}")
        assert response.status_code == 404

    def test_delete_game_not_found(self, client):
        """Test deleting a non-existent game."""
        response = client.delete("/api/games/nonexistent-id")
        assert response.status_code == 404

    def test_generate_turn(self, client):
        """Test generating a turn."""
        # Create a game
        create_response = client.post("/api/games/", json={"name": "Test Game"})
        game_id = create_response.json()["id"]

        # Generate a turn
        response = client.post(f"/api/games/{game_id}/turn/generate")
        assert response.status_code == 200
        data = response.json()
        assert data["turn"] == 2101  # STARTING_YEAR + 1
        assert "messages" in data


class TestStarEndpoints:
    """Tests for /api/games/{game_id}/stars endpoints."""

    def test_list_stars(self, client):
        """Test listing stars in a game."""
        # Create a game
        create_response = client.post("/api/games/", json={
            "name": "Test Game",
            "universe_size": "small"
        })
        game_id = create_response.json()["id"]

        # List stars
        response = client.get(f"/api/games/{game_id}/stars/")
        assert response.status_code == 200
        stars = response.json()
        assert len(stars) > 0
        # Check star structure
        star = stars[0]
        assert "name" in star
        assert "position_x" in star
        assert "position_y" in star

    def test_get_star(self, client):
        """Test getting a specific star."""
        # Create a game
        create_response = client.post("/api/games/", json={"name": "Test Game"})
        game_id = create_response.json()["id"]

        # Get stars list to find a name
        stars_response = client.get(f"/api/games/{game_id}/stars/")
        stars = stars_response.json()
        star_name = stars[0]["name"]

        # Get specific star
        response = client.get(f"/api/games/{game_id}/stars/{star_name}")
        assert response.status_code == 200
        star = response.json()
        assert star["name"] == star_name
        assert "gravity" in star
        assert "temperature" in star
        assert "radiation" in star

    def test_get_star_not_found(self, client):
        """Test getting a non-existent star."""
        # Create a game
        create_response = client.post("/api/games/", json={"name": "Test Game"})
        game_id = create_response.json()["id"]

        response = client.get(f"/api/games/{game_id}/stars/NonexistentStar")
        assert response.status_code == 404


class TestFleetEndpoints:
    """Tests for /api/games/{game_id}/fleets endpoints."""

    def test_list_fleets(self, client):
        """Test listing fleets in a game."""
        # Create a game with 2 players (each gets a starting fleet)
        create_response = client.post("/api/games/", json={
            "name": "Test Game",
            "player_count": 2
        })
        game_id = create_response.json()["id"]

        # List fleets
        response = client.get(f"/api/games/{game_id}/fleets/")
        assert response.status_code == 200
        fleets = response.json()
        assert len(fleets) >= 2  # At least 2 starting fleets


class TestEmpireEndpoints:
    """Tests for /api/games/{game_id}/empires endpoints."""

    def test_list_empires(self, client):
        """Test listing empires in a game."""
        # Create a game with 3 players
        create_response = client.post("/api/games/", json={
            "name": "Test Game",
            "player_count": 3
        })
        game_id = create_response.json()["id"]

        # List empires
        response = client.get(f"/api/games/{game_id}/empires")
        assert response.status_code == 200
        empires = response.json()
        assert len(empires) == 3
        # Check structure
        empire = empires[0]
        assert "id" in empire
        assert "race_name" in empire
        assert "star_count" in empire
        assert "fleet_count" in empire

    def test_get_empire(self, client):
        """Test getting a specific empire."""
        # Create a game
        create_response = client.post("/api/games/", json={"name": "Test Game"})
        game_id = create_response.json()["id"]

        # Get empire 1
        response = client.get(f"/api/games/{game_id}/empires/1")
        assert response.status_code == 200
        empire = response.json()
        assert empire["id"] == 1
        assert "race_name" in empire

    def test_get_empire_not_found(self, client):
        """Test getting a non-existent empire."""
        # Create a game
        create_response = client.post("/api/games/", json={"name": "Test Game"})
        game_id = create_response.json()["id"]

        response = client.get(f"/api/games/{game_id}/empires/999")
        assert response.status_code == 404


class TestCommandEndpoints:
    """Tests for command submission."""

    def test_submit_command(self, client):
        """Test submitting a command."""
        # Create a game
        create_response = client.post("/api/games/", json={"name": "Test Game"})
        game_id = create_response.json()["id"]

        # Submit a command
        response = client.post(f"/api/games/{game_id}/empires/1/commands", json={
            "command_type": "waypoint",
            "command_data": {"fleet_key": 1, "waypoints": []}
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"
        assert "turn_year" in data


class TestGalaxyGenerator:
    """Tests for galaxy generation."""

    def test_galaxy_sizes(self, client):
        """Test different universe sizes."""
        sizes = ["tiny", "small", "medium", "large"]

        for size in sizes:
            response = client.post("/api/games/", json={
                "name": f"Test {size}",
                "universe_size": size
            })
            assert response.status_code == 200
            game_id = response.json()["id"]

            # Check stars were generated
            stars_response = client.get(f"/api/games/{game_id}/stars/")
            stars = stars_response.json()
            assert len(stars) > 0

    def test_seed_reproducibility(self, client):
        """Test that same seed produces same galaxy."""
        # Create two games with same seed
        response1 = client.post("/api/games/", json={
            "name": "Game 1",
            "seed": 12345
        })
        game_id1 = response1.json()["id"]

        # Reset game manager to get fresh state
        import backend.services.game_manager as gm_module
        db_path = gm_module._game_manager.db.db_path
        gm_module._game_manager = GameManager(db_path)

        response2 = client.post("/api/games/", json={
            "name": "Game 2",
            "seed": 12345
        })
        game_id2 = response2.json()["id"]

        # Get stars from both
        stars1 = client.get(f"/api/games/{game_id1}/stars/").json()
        stars2 = client.get(f"/api/games/{game_id2}/stars/").json()

        # Same seed should produce same star names
        names1 = sorted([s["name"] for s in stars1])
        names2 = sorted([s["name"] for s in stars2])
        assert names1 == names2


class TestHealthEndpoint:
    """Tests for health check."""

    def test_health(self, client):
        """Test health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}
