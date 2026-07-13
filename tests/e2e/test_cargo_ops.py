"""
Seeded e2e: cargo operations.

A Teamster freighter runs a two-leg cargo route entirely on waypoint
CargoTask orders (CargoTask.cs:145-228 port): it loads ironium off the
homeworld at waypoint zero, flies to a nearby uninhabited world, and
unloads on arrival - then loads the ore back off the surface as proof
it landed there. A second scenario transfers cargo and fuel between
two co-located fleets over POST /fleets/{key}/transfer (client-side
only in the C# reference, FleetDetail.cs:766-786; server-authoritative
here).
"""

SEED = 20260713
LOAD_KT = 30


def _fleet_named(harness, prefix, empire_id=1):
    for fleet in harness.my_fleets(empire_id):
        if fleet["name"].startswith(prefix):
            return fleet
    return None


def _nearest_foreign_star(harness, home):
    candidates = [
        s for s in harness.state(1)["stars"]
        if s.get("intel") != "owned"
    ]
    assert candidates, "no foreign star near home"
    return min(candidates, key=lambda s: (
        (s["position_x"] - home["position_x"]) ** 2
        + (s["position_y"] - home["position_y"]) ** 2))


def _add_cargo_waypoint(harness, fleet, star, warp, mode, amount):
    """Waypoint order with a Cargo task (CargoTaskObj.from_dict schema)."""
    harness.submit(1, "waypoint", {
        "mode": "Add",
        "fleet_key": fleet["key"],
        "index": len(fleet.get("waypoints", [])),
        "waypoint": {
            "position_x": star["position_x"],
            "position_y": star["position_y"],
            "warp_factor": warp,
            "destination": star["name"],
            "task": {
                "type": "Cargo",
                "mode": mode,
                "amount": amount,
                "target_name": star["name"],
            },
        },
    })


class TestCargoOps:

    def test_waypoint_cargo_route(self, harness):
        """Load at A via a waypoint-zero cargo task, unload at B on
        arrival, then haul the ore back off B's surface as proof."""
        harness.create_game(seed=SEED, size="small", players=2)

        home = harness.my_stars(1)[0]
        teamster = _fleet_named(harness, "Teamster")
        assert teamster is not None
        assert teamster["cargo"]["ironium"] == 0
        home_ironium = home["ironium"]
        assert home_ironium >= LOAD_KT

        # Leg 1: LOAD at the homeworld (waypoint zero, executed by
        # SplitFleetStep during turn generation)
        _add_cargo_waypoint(harness, teamster, home, warp=0,
                            mode="LOAD", amount={"ironium": LOAD_KT})
        result = harness.generate_turn()

        teamster = _fleet_named(harness, "Teamster")
        assert teamster["cargo"]["ironium"] == LOAD_KT
        assert any(
            m["audience"] == 1 and "has loaded cargo from" in m["text"]
            for m in result["messages"])

        # Leg 2: UNLOAD at a nearby uninhabited world on arrival
        # (executed by _update_fleet, TurnGenerator.cs:454-465 port)
        target = _nearest_foreign_star(harness, home)
        _add_cargo_waypoint(harness, teamster, target, warp=4,
                            mode="UNLOAD", amount={"ironium": LOAD_KT})

        unloaded = False
        for _ in range(10):
            result = harness.generate_turn()
            if any(m["audience"] == 1
                   and f"has unloaded its cargo at {target['name']}"
                   in m["text"] for m in result["messages"]):
                unloaded = True
                break
        assert unloaded, "freighter never unloaded at the target"

        teamster = _fleet_named(harness, "Teamster")
        assert teamster["in_orbit"] == target["name"]
        assert teamster["cargo"]["ironium"] == 0

        # Proof the minerals landed on B's surface: load them back
        # with the immediate fleet<->star transfer
        loaded = harness._request(
            "POST",
            f"/api/games/{harness.game_id}/fleets/{teamster['key']}/cargo",
            {"empire_id": 1, "ironium": LOAD_KT},
        )
        assert loaded["status"] == "ok"
        assert loaded["fleet"]["cargo"]["ironium"] == LOAD_KT

    def test_fleet_to_fleet_transfer(self, harness):
        """Immediate cargo transfer between two co-located fleets:
        the Santa Maria hands colonists to the Teamster."""
        harness.create_game(seed=SEED, size="small", players=2)

        teamster = _fleet_named(harness, "Teamster")
        santa = _fleet_named(harness, "Santa Maria")
        assert teamster is not None and santa is not None
        assert santa["cargo"]["colonists"] == 2500

        moved = harness._request(
            "POST",
            f"/api/games/{harness.game_id}/fleets/{teamster['key']}/transfer",
            {"empire_id": 1, "target_fleet_key": santa["key"],
             "colonists": 500},
        )
        assert moved["status"] == "ok"
        assert moved["fleet"]["cargo"]["colonists"] == 500
        assert moved["other_fleet"]["cargo"]["colonists"] == 2000

        # Requesting more than the giver holds is rejected (the
        # harness asserts 200, so post directly for the negative case)
        response = harness.client.post(
            f"/api/games/{harness.game_id}/fleets/{teamster['key']}/transfer",
            json={"empire_id": 1, "target_fleet_key": santa["key"],
                  "colonists": 999900},
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "Not enough colonists"

        # The transfer survives a turn: colonists stay where they went
        harness.generate_turn()
        teamster = _fleet_named(harness, "Teamster")
        santa = _fleet_named(harness, "Santa Maria")
        assert teamster["cargo"]["colonists"] == 500
        assert santa["cargo"]["colonists"] == 2000
