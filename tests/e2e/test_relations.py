"""
Seeded e2e: player relations (Enemy/Neutral/Friend).

Two empires start as mutual Enemies (GameInitialiser.cs:132-143).
Both declare Neutral and park armed warships (empire 1's Stalwart
Defender, empire 2's Armed Probe) on the same deep-space point: the
co-located encounter passes without battle (plan "Enemies" + Neutral
relation selects no targets, BattleEngine.cs:468-494, zero targets
aborts the battle). After both declare Enemy, the same encounter
fights and ships are lost.

Also covers: relations exposed in player state, RelationCommand
persistence across turn generation and the DB round-trip, and the
error envelope for an invalid relation string.

Empire 2 is AI-driven; its defender is kept under test control with
the parking waypoint stack from test_mine_sweeping (a LayMines no-op
waypoint that never pops plus a trailing dummy).
"""

import math

SEED = 20260713


def _fleet_named(harness, prefix, empire_id):
    for fleet in harness.my_fleets(empire_id):
        if fleet["name"].startswith(prefix):
            return fleet
    return None


def _relation_toward(harness, empire_id, other_id):
    for entry in harness.state(empire_id)["relations"]:
        if entry["id"] == other_id:
            return entry
    return None


def _wp(x, y, warp, task, dest="wp"):
    return {"position_x": x, "position_y": y, "warp_factor": warp,
            "destination": dest, "task": {"type": task}}


def _add_waypoints(harness, empire_id, fleet_key, waypoints):
    for i, waypoint in enumerate(waypoints):
        result = harness.submit(empire_id, "waypoint", {
            "mode": "Add", "fleet_key": fleet_key, "index": i,
            "waypoint": waypoint})
        assert result["status"] == "applied", result


def _at(fleet, x, y):
    return math.hypot(fleet["position_x"] - x,
                      fleet["position_y"] - y) < 0.5


class TestRelations:

    def test_neutral_contact_passes_enemy_fights(self, harness):
        harness.create_game(seed=SEED, size="tiny", players=2)

        # Turn-0 defaults: everyone pre-registered as Enemy
        entry = _relation_toward(harness, 1, 2)
        assert entry is not None
        assert entry["relation"] == "Enemy"
        assert entry["race_name"]
        assert _relation_toward(harness, 2, 1)["relation"] == "Enemy"

        # Invalid relation string is rejected with the error envelope
        result = harness.submit(
            1, "relation", {"target_empire_id": 2, "relation": "Ally"})
        assert "not a valid player relation" in result["error"]

        # Both sides declare Neutral - either side marking Enemy
        # would trigger the fight, so both must stand down
        for empire_id, other_id in ((1, 2), (2, 1)):
            result = harness.submit(empire_id, "relation", {
                "target_empire_id": other_id, "relation": "Neutral"})
            assert result["status"] == "applied"
        assert _relation_toward(harness, 1, 2)["relation"] == "Neutral"
        assert _relation_toward(harness, 2, 1)["relation"] == "Neutral"

        # Both empires' armed warships meet on a deep-space point
        # midway between the homeworlds (off-star: fractional coords)
        home1 = harness.my_stars(1)[0]
        home2 = harness.my_stars(2)[0]
        px = (home1["position_x"] + home2["position_x"]) / 2 + 0.5
        py = (home1["position_y"] + home2["position_y"]) / 2 + 0.5

        defender = _fleet_named(harness, "Stalwart Defender #1", 1)
        probe = _fleet_named(harness, "Armed Probe #1", 2)
        assert defender is not None and probe is not None
        _add_waypoints(harness, 1, defender["key"], [
            _wp(px, py, 4, "NoTask", "Rendezvous"),
        ])
        # AI-held fleet: parking stack keeps DefaultAI hands off
        _add_waypoints(harness, 2, probe["key"], [
            _wp(px, py, 4, "NoTask", "Rendezvous"),
            _wp(px, py, 4, "LayMines", "Rendezvous"),
            _wp(home2["position_x"], home2["position_y"], 4, "NoTask",
                "dummy"),
        ])

        # Fly to the rendezvous; the Neutral encounter never battles
        parked_turns = 0
        for _ in range(15):
            result = harness.generate_turn()
            assert not any(m["type"] == "Battle"
                           for m in result["messages"]), \
                "neutral contact must not battle"
            defender = _fleet_named(harness, "Stalwart Defender #1", 1)
            probe = _fleet_named(harness, "Armed Probe #1", 2)
            assert defender is not None and probe is not None, \
                "warship lost without a battle"
            if _at(defender, px, py) and _at(probe, px, py):
                parked_turns += 1
            if parked_turns >= 2:
                break
        assert parked_turns >= 2, "warships never met at the rendezvous"

        # Neutral relations survived the turns and the DB round-trip
        assert _relation_toward(harness, 1, 2)["relation"] == "Neutral"
        assert _relation_toward(harness, 2, 1)["relation"] == "Neutral"

        # War is declared on both sides: the same encounter now fights
        for empire_id, other_id in ((1, 2), (2, 1)):
            result = harness.submit(empire_id, "relation", {
                "target_empire_id": other_id, "relation": "Enemy"})
            assert result["status"] == "applied"

        result = harness.generate_turn()
        battles = [m for m in result["messages"] if m["type"] == "Battle"]
        assert any(m["audience"] == 1 for m in battles)
        assert any(m["audience"] == 2 for m in battles)
        assert any("deep space" in m["text"] for m in battles)

        # The warships traded beam fire: the outgunned probe (20 armor
        # vs the defender's twin beams) is destroyed
        assert _fleet_named(harness, "Armed Probe #1", 2) is None, \
            "battle resolved without losses"
        assert _fleet_named(harness, "Stalwart Defender #1", 1) is not None

    def test_friend_relation_persists_across_turn(self, harness):
        harness.create_game(seed=SEED, size="tiny", players=2)

        result = harness.submit(
            1, "relation", {"target_empire_id": 2, "relation": "Friend"})
        assert result["status"] == "applied"
        assert _relation_toward(harness, 1, 2)["relation"] == "Friend"
        # The other side keeps its own independent relation
        assert _relation_toward(harness, 2, 1)["relation"] == "Enemy"

        harness.generate_turn()
        assert _relation_toward(harness, 1, 2)["relation"] == "Friend"
        assert _relation_toward(harness, 2, 1)["relation"] == "Enemy"
