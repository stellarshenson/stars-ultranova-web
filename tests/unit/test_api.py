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

        # Submit a command (applies immediately to the empire's state)
        response = client.post(f"/api/games/{game_id}/empires/1/commands", json={
            "command_type": "research",
            "command_data": {
                "budget": 25,
                "topics": {"levels": {"Energy": 1}}
            }
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "applied"
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


def _wizard_race(**overrides) -> dict:
    """A default-Humanoids race wizard payload (JOAT baseline)."""
    race = {
        "name": "Humanoids",
        "pluralName": "Humanoids",
        "prt": "JOAT",
        "lrts": [],
        "growthRate": 15,
        "colonistsPerResource": 1000,
        "factoryEfficiency": 10,
        "factoryCost": 10,
        "factoryNumberPer10k": 10,
        "mineEfficiency": 10,
        "mineCost": 5,
        "mineNumberPer10k": 10,
        "gravityMin": 15, "gravityMax": 85,
        "temperatureMin": 15, "temperatureMax": 85,
        "radiationMin": 15, "radiationMax": 85,
        "immuneGravity": False,
        "immuneTemperature": False,
        "immuneRadiation": False,
        "researchCosts": {field: "normal" for field in (
            "energy", "weapons", "propulsion", "construction",
            "electronics", "biotechnology")},
        "startAtLevel3": False,
    }
    race.update(overrides)
    return race


def _over_budget_race() -> dict:
    """A grossly over-budget race design (scores -6359)."""
    return _wizard_race(
        name="Overreach",
        prt="IT",
        lrts=["IFE", "TT", "ARM", "ISB", "UR", "MA"],
        growthRate=20,
        colonistsPerResource=500,
        factoryEfficiency=15,
        factoryCost=5,
        factoryNumberPer10k=25,
        mineEfficiency=25,
        mineCost=2,
        mineNumberPer10k=25,
        gravityMin=0, gravityMax=100,
        temperatureMin=0, temperatureMax=100,
        radiationMin=0, radiationMax=100,
        researchCosts={field: "cheap" for field in (
            "energy", "weapons", "propulsion", "construction",
            "electronics", "biotechnology")},
    )


class TestRaceValidation:
    """Tests for /api/races/validate and the create-game budget gate."""

    def test_validate_default_humanoids(self, client):
        """The default wizard race scores the pinned baseline and is
        legal (see tests/unit/test_race_points.py for the C# parity
        notes on the value)."""
        response = client.post("/api/races/validate", json=_wizard_race())
        assert response.status_code == 200
        data = response.json()
        assert data["points"] == 29
        assert data["legal"] is True
        assert data["leftover_points"] == 29
        assert data["breakdown"]["raw_total"] == 29 * 3 + 1

    def test_validate_over_budget(self, client):
        """An over-budget design is reported illegal with the deficit."""
        response = client.post("/api/races/validate",
                               json=_over_budget_race())
        assert response.status_code == 200
        data = response.json()
        assert data["points"] < 0
        assert data["legal"] is False
        assert data["leftover_points"] == 0

    def test_create_game_rejects_over_budget_race(self, client):
        """Over-budget race payloads are rejected with 422 and no
        orphan game row (the web equivalent of the C# RaceDesigner
        Finish_Click gate)."""
        response = client.post("/api/games/", json={
            "name": "Illegal Race Game",
            "seed": 42,
            "race": _over_budget_race(),
        })
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert "advantage point budget" in detail
        assert "points" in detail

        # No game row was created
        games = client.get("/api/games/").json()
        assert games == []

    def test_create_game_with_legal_race_plays_a_turn(self, client):
        """A legal custom race creates a game, lands on empire 1, and
        survives a full turn generation."""
        race = _wizard_race(name="Testers", pluralName="Testers")
        response = client.post("/api/games/", json={
            "name": "Legal Race Game",
            "seed": 42,
            "race": race,
        })
        assert response.status_code == 200
        game_id = response.json()["id"]

        empires = client.get(f"/api/games/{game_id}/empires").json()
        empire1 = next(e for e in empires if e["id"] == 1)
        assert empire1["race_name"] == "Testers"

        # The real leftover budget (29, from the ported calculator)
        # flows into the race used by the game state
        state = client.get(
            f"/api/games/{game_id}/empires/1/state").json()
        assert state["empire"]["race"]["leftover_points"] == 29

        # The accepted race plays a full turn without error
        response = client.post(f"/api/games/{game_id}/turn/generate")
        assert response.status_code == 200
        assert response.json()["turn"] == 2101


class TestFleetToFleetTransfer:
    """Tests for POST /fleets/{key}/transfer (fleet-to-fleet cargo).

    The C# reference applies this transfer client-side only
    (FleetDetail.cs:766-786); the web port is server-authoritative
    and rejects invalid orders instead of clamping.
    """

    def _setup(self, client):
        """Create a seeded game; return (game_id, fleet lookup)."""
        response = client.post("/api/games/", json={
            "name": "Xfer Game", "player_count": 2,
            "universe_size": "small", "seed": 777,
        })
        game_id = response.json()["id"]
        summaries = client.get(
            f"/api/games/{game_id}/fleets/",
            params={"empire_id": 1}).json()

        def by_name(prefix):
            key = next(f["key"] for f in summaries
                       if f["name"].startswith(prefix))
            return client.get(f"/api/games/{game_id}/fleets/{key}").json()

        return game_id, by_name

    def _post(self, client, game_id, fleet_key, target_key, **delta):
        return client.post(
            f"/api/games/{game_id}/fleets/{fleet_key}/transfer",
            json={"empire_id": 1, "target_fleet_key": target_key,
                  **delta})

    def test_transfer_colonists_both_directions(self, client):
        """Positive deltas pull from the target fleet; negative push
        back. The Santa Maria launches with 25 kT of colonists."""
        game_id, by_name = self._setup(client)
        teamster = by_name("Teamster")
        santa = by_name("Santa Maria")
        assert santa["cargo"]["colonists"] == 2500

        response = self._post(client, game_id, teamster["key"],
                              santa["key"], colonists=500)
        assert response.status_code == 200
        body = response.json()
        assert body["fleet"]["cargo"]["colonists"] == 500
        assert body["other_fleet"]["cargo"]["colonists"] == 2000

        # Reverse direction: negative pushes back to the Santa Maria
        response = self._post(client, game_id, teamster["key"],
                              santa["key"], colonists=-200)
        assert response.status_code == 200
        body = response.json()
        assert body["fleet"]["cargo"]["colonists"] == 300
        assert body["other_fleet"]["cargo"]["colonists"] == 2200

    def test_transfer_minerals_and_fuel(self, client):
        """Minerals loaded off the homeworld move between fleets;
        fuel moves once the receiver has burned some."""
        game_id, by_name = self._setup(client)
        teamster = by_name("Teamster")
        santa = by_name("Santa Maria")

        # Load 30 ironium onto the Teamster from the homeworld and
        # make room on the Santa Maria (it launches full of colonists)
        response = client.post(
            f"/api/games/{game_id}/fleets/{teamster['key']}/cargo",
            json={"empire_id": 1, "ironium": 30})
        assert response.status_code == 200
        response = self._post(client, game_id, teamster["key"],
                              santa["key"], colonists=1000)
        assert response.status_code == 200

        # Move 10 ironium Teamster -> Santa Maria
        response = self._post(client, game_id, santa["key"],
                              teamster["key"], ironium=10)
        assert response.status_code == 200
        body = response.json()
        assert body["fleet"]["cargo"]["ironium"] == 10
        assert body["other_fleet"]["cargo"]["ironium"] == 20

        # Burn a hole in the Santa Maria's tank, then refill from
        # the Teamster
        from backend.services.game_manager import get_game_manager
        manager = get_game_manager()
        server_data = manager._load_game_state(game_id)
        santa_fleet = server_data.all_empires[1].owned_fleets[
            santa["key"]]
        santa_fleet.fuel_available -= 50
        manager._save_game_state(game_id, server_data)

        response = self._post(client, game_id, santa["key"],
                              teamster["key"], fuel=50)
        assert response.status_code == 200
        body = response.json()
        assert body["fleet"]["fuel_available"] == \
            body["fleet"]["fuel_capacity"]
        assert body["other_fleet"]["fuel_available"] == \
            body["other_fleet"]["fuel_capacity"] - 50

    def test_transfer_validation_errors(self, client):
        """Invalid orders are rejected with 400 and a reason."""
        game_id, by_name = self._setup(client)
        teamster = by_name("Teamster")
        santa = by_name("Santa Maria")
        starbase = by_name("Starbase")

        # Same fleet
        response = self._post(client, game_id, teamster["key"],
                              teamster["key"], ironium=1)
        assert response.status_code == 400
        assert "same fleet" in response.json()["detail"]

        # Starbase counterparty
        response = self._post(client, game_id, teamster["key"],
                              starbase["key"], ironium=1)
        assert response.status_code == 400
        assert "Starbases" in response.json()["detail"]

        # Giver lacks stock (Santa Maria carries no minerals)
        response = self._post(client, game_id, teamster["key"],
                              santa["key"], ironium=10)
        assert response.status_code == 400
        assert response.json()["detail"] == "Not enough ironium"

        # Receiver fuel capacity exceeded (both launch with full tanks)
        response = self._post(client, game_id, teamster["key"],
                              santa["key"], fuel=10)
        assert response.status_code == 400
        assert response.json()["detail"] == "Fuel capacity exceeded"

        # Receiver cargo capacity exceeded: fill the Teamster to 60 of
        # its 70 kT, then try to pull 20 kT of colonists on top
        response = client.post(
            f"/api/games/{game_id}/fleets/{teamster['key']}/cargo",
            json={"empire_id": 1, "ironium": 60})
        assert response.status_code == 200
        response = self._post(client, game_id, teamster["key"],
                              santa["key"], colonists=2000)
        assert response.status_code == 400
        assert response.json()["detail"] == "Cargo capacity exceeded"

        # Foreign fleet is not addressable
        foreign = client.get(
            f"/api/games/{game_id}/fleets/",
            params={"empire_id": 2}).json()
        response = self._post(client, game_id, teamster["key"],
                              foreign[0]["key"], ironium=1)
        assert response.status_code == 400
        assert "not owned" in response.json()["detail"]

    def test_transfer_requires_same_location(self, client):
        """Fleets apart in space cannot transfer."""
        game_id, by_name = self._setup(client)
        teamster = by_name("Teamster")
        santa = by_name("Santa Maria")

        from backend.services.game_manager import get_game_manager
        manager = get_game_manager()
        server_data = manager._load_game_state(game_id)
        fleet = server_data.all_empires[1].owned_fleets[teamster["key"]]
        fleet.position.x += 50
        manager._save_game_state(game_id, server_data)

        response = self._post(client, game_id, teamster["key"],
                              santa["key"], colonists=100)
        assert response.status_code == 400
        assert "same location" in response.json()["detail"]


class TestClientParityState:
    """Player-state plumbing for the client waypoint leg editor
    (wave 5 client parity): full waypoint task dicts, per-warp fuel
    consumption, and Edit/Insert command semantics."""

    def _setup(self, client):
        response = client.post("/api/games/", json={
            "name": "Parity", "seed": 4242, "universe_size": "small",
            "player_count": 2})
        game_id = response.json()["id"]
        state = client.get(f"/api/games/{game_id}/empires/1/state").json()
        return game_id, state

    def _fleet(self, client, game_id, key):
        state = client.get(f"/api/games/{game_id}/empires/1/state").json()
        return next(f for f in state["fleets"] if f["key"] == key)

    def _submit_waypoint(self, client, game_id, data):
        response = client.post(
            f"/api/games/{game_id}/empires/1/commands",
            json={"command_type": "waypoint", "command_data": data})
        assert response.status_code == 200
        assert response.json()["status"] == "applied"

    def test_waypoint_task_dict_roundtrip(self, client):
        """Waypoints in the player state expose the full task dict so
        a warp-only Edit can resend the task intact (C# preserves the
        Task object on speed edits, FleetDetail.cs:110)."""
        game_id, state = self._setup(client)
        fleet = state["fleets"][0]

        self._submit_waypoint(client, game_id, {
            "mode": "Add", "fleet_key": fleet["key"],
            "index": len(fleet["waypoints"]),
            "waypoint": {
                "position_x": fleet["position_x"] + 20,
                "position_y": fleet["position_y"],
                "warp_factor": 5, "destination": "Deep Space",
                "task": {"type": "Cargo", "mode": "UNLOAD",
                         "amount": {"ironium": 30},
                         "target_name": "Deep Space"},
            }})

        fleet = self._fleet(client, game_id, fleet["key"])
        wp = fleet["waypoints"][-1]
        assert wp["task_type"] == "CargoTaskObj"
        assert wp["task"]["type"] == "CargoTask"
        assert wp["task"]["mode"] == "UNLOAD"
        assert wp["task"]["amount"]["ironium"] == 30
        assert wp["task"]["target_name"] == "Deep Space"

    def test_fuel_consumption_by_warp(self, client):
        """Every fleet exposes fuel_consumption_by_warp: 11 entries,
        zero at warp 0, non-decreasing, equal to the authoritative
        Fleet.fuel_consumption (Fleet.cs:817-839 port)."""
        game_id, state = self._setup(client)
        fleet_dict = next(f for f in state["fleets"] if f["tokens"])

        by_warp = fleet_dict["fuel_consumption_by_warp"]
        assert len(by_warp) == 11
        assert by_warp[0] == 0
        assert all(by_warp[w] <= by_warp[w + 1] for w in range(10))

        from backend.services.game_manager import get_game_manager
        server_data = get_game_manager()._load_game_state(game_id)
        empire = server_data.all_empires[1]
        fleet = empire.owned_fleets[fleet_dict["key"]]
        for w in range(11):
            assert by_warp[w] == round(
                fleet.fuel_consumption(w, empire.race), 2)

    def test_edit_and_insert_preserve_order(self, client):
        """Edit replaces index N in place (pop+insert,
        WaypointCommand.cs:156-158); Insert at a middle index shifts
        the tail (web extension mode)."""
        game_id, state = self._setup(client)
        fleet = state["fleets"][0]
        base = len(fleet["waypoints"])

        for i, name in enumerate(["A", "B", "C"]):
            self._submit_waypoint(client, game_id, {
                "mode": "Add", "fleet_key": fleet["key"],
                "index": base + i,
                "waypoint": {
                    "position_x": fleet["position_x"] + 10 * (i + 1),
                    "position_y": fleet["position_y"],
                    "warp_factor": 6, "destination": name,
                    "task": {"type": "NoTask"},
                }})

        # Edit the middle leg: warp only, neighbors untouched
        self._submit_waypoint(client, game_id, {
            "mode": "Edit", "fleet_key": fleet["key"], "index": base + 1,
            "waypoint": {
                "position_x": fleet["position_x"] + 20,
                "position_y": fleet["position_y"],
                "warp_factor": 9, "destination": "B",
                "task": {"type": "NoTask"},
            }})
        fleet_now = self._fleet(client, game_id, fleet["key"])
        names = [w["destination"] for w in fleet_now["waypoints"][base:]]
        assert names == ["A", "B", "C"]
        assert fleet_now["waypoints"][base + 1]["warp_factor"] == 9

        # Insert between A and B shifts the tail
        self._submit_waypoint(client, game_id, {
            "mode": "Insert", "fleet_key": fleet["key"], "index": base + 1,
            "waypoint": {
                "position_x": fleet["position_x"] + 15,
                "position_y": fleet["position_y"],
                "warp_factor": 4, "destination": "A2",
                "task": {"type": "NoTask"},
            }})
        fleet_now = self._fleet(client, game_id, fleet["key"])
        names = [w["destination"] for w in fleet_now["waypoints"][base:]]
        assert names == ["A", "A2", "B", "C"]
