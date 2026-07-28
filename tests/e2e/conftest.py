"""
Seeded end-to-end gameplay test harness.

GameHarness drives the real FastAPI app (backend.main:app) through
fastapi.testclient.TestClient with an isolated temporary database, so
tests never touch data/stars_nova.db and never need a live server. Its
methods are thin wrappers over the same player-scoped HTTP API that
scripts/autoplay.py exercises against a running instance.

Every harness session records each API call plus a compact per-turn
state digest to a JSONL transcript under logs/e2e/<test-name>.jsonl
(recordings are evidence, not source; logs/ is gitignored).
"""

import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
TRANSCRIPT_DIR = REPO_ROOT / "logs" / "e2e"


class GameHarness:
    """Scripted gameplay against the in-process app, one game at a time.

    create_game() binds the harness to the newly created game; the
    other methods operate on that game. Create a second game to switch.
    """

    def __init__(self, client: TestClient, transcript_path: Path):
        self.client = client
        self.transcript_path = transcript_path
        self.game_id = None

    # -- recording ---------------------------------------------------

    def _record(self, entry: dict):
        with open(self.transcript_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def _request(self, method: str, path: str, body: dict = None) -> dict:
        response = self.client.request(method, path, json=body)
        self._record({
            "event": "call",
            "method": method,
            "path": path,
            "body": body,
            "status": response.status_code,
        })
        assert response.status_code == 200, (
            f"{method} {path} -> {response.status_code}: "
            f"{response.text[:200]}"
        )
        return response.json()

    # -- API wrappers (mirror scripts/autoplay.py) --------------------

    def create_game(self, seed, size="small", players=2, race=None,
                    **settings) -> dict:
        """Create a game and bind the harness to it."""
        body = {
            "name": settings.pop("name", f"e2e-seed{seed}"),
            "player_count": players,
            "universe_size": size,
            "seed": seed,
            "race": race,
            **settings,
        }
        game = self._request("POST", "/api/games/", body)
        self.game_id = game["id"]
        return game

    def state(self, empire_id: int = 1) -> dict:
        """Player-scoped game state (fog of war applied)."""
        return self._request(
            "GET", f"/api/games/{self.game_id}/empires/{empire_id}/state"
        )

    def submit(self, empire_id: int, command_type: str, data: dict) -> dict:
        """Submit a player command."""
        return self._request(
            "POST", f"/api/games/{self.game_id}/empires/{empire_id}/commands",
            {"command_type": command_type, "command_data": data},
        )

    def generate_turn(self) -> dict:
        """Generate the next turn and record per-empire state digests."""
        result = self._request(
            "POST", f"/api/games/{self.game_id}/turn/generate"
        )
        empires = self._request("GET", f"/api/games/{self.game_id}/empires")
        result["digests"] = {
            e["id"]: self.state_digest(e["id"]) for e in empires
        }
        self._record({
            "event": "turn",
            "game_id": self.game_id,
            "turn": result["turn"],
            "digests": result["digests"],
        })
        return result

    # -- helpers -------------------------------------------------------

    def state_digest(self, empire_id: int = 1) -> str:
        """SHA-256 over the canonical player state, minus the game id
        (which differs between otherwise identical games)."""
        state = self.state(empire_id)
        state.pop("game_id", None)
        canonical = json.dumps(state, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def my_stars(self, empire_id: int = 1) -> list:
        """Stars owned by the empire."""
        return [s for s in self.state(empire_id)["stars"]
                if s.get("intel") == "owned"]

    def my_fleets(self, empire_id: int = 1) -> list:
        """Fleets owned by the empire."""
        return self.state(empire_id)["fleets"]

    def star_by_name(self, name: str, empire_id: int = 1) -> dict:
        """Star entry from the empire's view, or None."""
        for star in self.state(empire_id)["stars"]:
            if star["name"] == name:
                return star
        return None


@pytest.fixture
def harness(request, tmp_path):
    """GameHarness on the real app with an isolated temp database."""
    import backend.services.game_manager as gm_module
    from backend.main import app
    from backend.services.game_manager import GameManager

    # Point the module singleton at a per-test database
    gm_module._game_manager = GameManager(str(tmp_path / "e2e.db"))

    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    transcript = TRANSCRIPT_DIR / f"{request.node.name}.jsonl"
    transcript.write_text("")  # fresh recording per run

    with TestClient(app) as client:
        yield GameHarness(client, transcript)

    gm_module._game_manager = None
