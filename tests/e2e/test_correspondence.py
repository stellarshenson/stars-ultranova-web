"""
Correspondence play end-to-end scenarios (acc-crit "Correspondence
Play"): turn-package export, orders-file round-trip, full-game
handoff, race passwords, turn locking with 2+ human empires,
determinism (correspondence replays to the live digest) and the
stale-orders rejection edge.

Uses the seeded GameHarness; games are addressed by explicit id so a
single harness can drive the live game, the remote player's copy and
the host's copy side by side.
"""

import hashlib
import json

SEED = 314159


def _digest(harness, game_id, empire_id):
    """State digest for an explicit game id (see GameHarness.state_digest)."""
    state = harness._request(
        "GET", f"/api/games/{game_id}/empires/{empire_id}/state")
    state.pop("game_id", None)
    canonical = json.dumps(state, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _digests(harness, game_id):
    empires = harness._request("GET", f"/api/games/{game_id}/empires")
    return {e["id"]: _digest(harness, game_id, e["id"]) for e in empires}


def _play_orders(harness, game_id):
    """The scripted turn: a research command plus a direct fleet op."""
    state = harness._request(
        "GET", f"/api/games/{game_id}/empires/1/state")
    levels = {key: 0 for key in state["research"]["levels"]}
    levels["Weapons"] = 1
    harness._request(
        "POST", f"/api/games/{game_id}/empires/1/commands",
        {"command_type": "research",
         "command_data": {"budget": 30, "topics": {"levels": levels}}})
    fleet_key = state["fleets"][0]["key"]
    harness._request(
        "POST", f"/api/games/{game_id}/fleets/{fleet_key}/rename",
        {"empire_id": 1, "name": "Correspondence Flagship"})


class TestTurnPackage:
    """Per-empire fog turn package (IntelWriter.cs analog)."""

    def test_envelope_and_fog_integrity(self, harness):
        game = harness.create_game(SEED)
        package = harness._request(
            "GET",
            f"/api/games/{game['id']}/empires/1/turn-package")

        assert package["format"] == "stars-ultranova-turn-package"
        assert package["version"] == 1
        assert package["game_id"] == game["id"]
        assert package["empire_id"] == 1
        assert package["turn_year"] == package["state"]["turn_year"]

        # Fog integrity by construction: the body is exactly the
        # player-scoped state - nothing global, no other empire's
        # unfogged data
        assert package["state"] == harness.state(1)
        assert "all_empires" not in package["state"]
        assert all(f["owner"] == 1
                   for f in package["state"]["fleets"])


class TestOrdersRoundTrip:
    """Orders file export/import replays exactly as if entered live."""

    def test_correspondence_matches_live_digest(self, harness):
        # Live reference game: orders entered directly, then generate
        live = harness.create_game(SEED, name="live")
        live_id = live["id"]
        _play_orders(harness, live_id)
        harness._request("POST", f"/api/games/{live_id}/turn/generate")
        live_digests = _digests(harness, live_id)

        # Correspondence game: the host keeps a copy (full-game
        # export/import) while the remote player plays on their own
        # copy and sends back only the orders file
        remote = harness.create_game(SEED, name="remote")
        remote_id = remote["id"]
        game_file = harness._request(
            "GET", f"/api/games/{remote_id}/export")
        assert game_file["format"] == "stars-ultranova-game"
        assert "host/carrier only" in game_file["note"]
        host = harness._request("POST", "/api/games/import", game_file)
        host_id = host["id"]
        assert host_id != remote_id

        _play_orders(harness, remote_id)
        orders = harness._request(
            "GET", f"/api/games/{remote_id}/empires/1/orders-file")
        assert orders["format"] == "stars-ultranova-orders"
        assert orders["turn_year"] == remote["turn"]
        assert len(orders["orders"]) == 2

        result = harness._request(
            "POST", f"/api/games/{host_id}/import/orders", orders)
        assert result["orders_applied"] == 2

        # Import locked the empire's turn (OrderReader.cs:171-173)
        subs = harness._request(
            "GET", f"/api/games/{host_id}/submissions")
        me = next(s for s in subs if s["empire_id"] == 1)
        assert me["turn_submitted"] is True
        assert me["last_turn_submitted"] == orders["turn_year"]

        harness._request("POST", f"/api/games/{host_id}/turn/generate")
        assert _digests(harness, host_id) == live_digests


class TestFullGameHandoff:
    """Full-game file export/import (hot-seat by correspondence)."""

    def test_export_import_preserves_state_and_determinism(self, harness):
        game = harness.create_game(SEED)
        game_id = game["id"]
        harness._request("POST", f"/api/games/{game_id}/turn/generate")
        harness._request("POST", f"/api/games/{game_id}/turn/generate")

        game_file = harness._request("GET",
                                     f"/api/games/{game_id}/export")
        imported = harness._request("POST", "/api/games/import",
                                    game_file)
        assert imported["turn"] == game_file["turn_year"]
        assert _digests(harness, imported["id"]) \
            == _digests(harness, game_id)

        # Determinism survives the handoff: one more turn on both
        # copies produces identical states
        harness._request(
            "POST", f"/api/games/{game_id}/turn/generate")
        harness._request(
            "POST", f"/api/games/{imported['id']}/turn/generate")
        assert _digests(harness, imported["id"]) \
            == _digests(harness, game_id)

    def test_malformed_game_file_rejected(self, harness):
        response = harness.client.post(
            "/api/games/import", json={"format": "something-else"})
        assert response.status_code == 422


class TestRacePassword:
    """Race password gates the empire view and its orders."""

    def test_password_gate(self, harness):
        game = harness.create_game(SEED, race={
            "name": "Guarded", "password": "hunter2"})
        game_id = game["id"]
        state_path = f"/api/games/{game_id}/empires/1/state"

        assert harness.client.get(state_path).status_code == 401
        assert harness.client.get(
            state_path,
            headers={"X-Empire-Password": "wrong"}).status_code == 401
        assert harness.client.get(
            state_path,
            headers={"X-Empire-Password": "hunter2"}).status_code == 200

        # Command submission is gated the same way
        body = {"command_type": "research",
                "command_data": {"budget": 25}}
        assert harness.client.post(
            f"/api/games/{game_id}/empires/1/commands",
            json=body).status_code == 401
        ok = harness.client.post(
            f"/api/games/{game_id}/empires/1/commands", json=body,
            headers={"X-Empire-Password": "hunter2"})
        assert ok.status_code == 200
        assert ok.json()["status"] == "applied"

        # Empire 2 has no password - open access as before
        assert harness.client.get(
            f"/api/games/{game_id}/empires/2/state").status_code == 200


class TestTurnLocking:
    """Turn-submitted flags gate year advance (NovaConsole.cs:450)."""

    def test_two_humans_gate_generation(self, harness):
        game = harness.create_game(SEED, human_players=2)
        game_id = game["id"]

        # Nobody has submitted: generation is refused
        refused = harness.client.post(
            f"/api/games/{game_id}/turn/generate")
        assert refused.status_code == 409
        assert "Waiting for orders" in refused.json()["detail"]

        harness._request(
            "POST", f"/api/games/{game_id}/empires/1/submit-orders")
        still = harness.client.post(
            f"/api/games/{game_id}/turn/generate")
        assert still.status_code == 409

        # Empire 1 is locked: further orders are rejected
        locked = harness.client.post(
            f"/api/games/{game_id}/empires/1/commands",
            json={"command_type": "research",
                  "command_data": {"budget": 40}})
        assert locked.status_code == 200
        assert "already submitted" in locked.json()["error"]

        harness._request(
            "POST", f"/api/games/{game_id}/empires/2/submit-orders")
        result = harness._request(
            "POST", f"/api/games/{game_id}/turn/generate")
        assert result["turn"] == game["turn"] + 1

        # Flags reset for the new year
        subs = harness._request(
            "GET", f"/api/games/{game_id}/submissions")
        assert all(not s["turn_submitted"] for s in subs)
        assert all(s["last_turn_submitted"] == game["turn"]
                   for s in subs)

    def test_single_human_stays_ungated(self, harness):
        # Backward compatibility: solo games keep one-button turn
        # generation (the C# console's force-generate affordance)
        game = harness.create_game(SEED)
        result = harness._request(
            "POST", f"/api/games/{game['id']}/turn/generate")
        assert result["turn"] == game["turn"] + 1


class TestSubmissionsStatus:
    """Console player-list analog (NovaConsole.cs SetPlayerList)."""

    def test_status_rows(self, harness):
        game = harness.create_game(SEED)
        subs = harness._request(
            "GET", f"/api/games/{game['id']}/submissions")
        human = next(s for s in subs if s["empire_id"] == 1)
        ai = next(s for s in subs if s["empire_id"] == 2)
        assert human["ai_program"] == "Human"
        assert ai["ai_program"] == "Default AI"
        # last_turn_submitted 0 = "No Orders" ever submitted
        assert all(s["last_turn_submitted"] == 0 for s in subs)

        # AI empires submit automatically during generation
        harness._request(
            "POST", f"/api/games/{game['id']}/turn/generate")
        subs = harness._request(
            "GET", f"/api/games/{game['id']}/submissions")
        ai = next(s for s in subs if s["empire_id"] == 2)
        assert ai["last_turn_submitted"] == game["turn"]


class TestStaleOrders:
    """Edge: stale orders rejected cleanly (OrderReader.cs:96-102)."""

    def test_stale_year_rejected_nothing_corrupted(self, harness):
        game = harness.create_game(SEED)
        game_id = game["id"]

        _play_orders(harness, game_id)
        stale_orders = harness._request(
            "GET", f"/api/games/{game_id}/empires/1/orders-file")

        # The year advances, making the file stale
        harness._request("POST", f"/api/games/{game_id}/turn/generate")
        before = _digests(harness, game_id)

        response = harness.client.post(
            f"/api/games/{game_id}/import/orders", json=stale_orders)
        assert response.status_code == 409
        detail = response.json()["detail"]
        assert f"year {stale_orders['turn_year']}" in detail
        assert "rejected" in detail

        # Nothing was applied or corrupted
        assert _digests(harness, game_id) == before
