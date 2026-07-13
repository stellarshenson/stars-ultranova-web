"""
Seeded e2e: repair and refuel (TurnGenerator.cs RegenerateFleet port).

A scout flies into deep space, burns fuel, returns to the homeworld
starbase and is refueled to full (TurnGenerator.cs:316-319). A damaged
fleet parked at the homeworld dock repairs 20 percentage points of
damage per year while a damaged fleet stopped in deep space repairs
only 2 (situation table, TurnGenerator.cs:283-300/323-367).
"""

import backend.services.game_manager as gm_module

# Seed chosen so the roaming galactic storm (a web extension) stays
# clear of the homeworld and the deep-space parking spot - storm
# damage would otherwise mask the repair rates under test
SEED = 20260713


def _fleet_named(harness, prefix, empire_id=1):
    for fleet in harness.my_fleets(empire_id):
        if fleet["name"].startswith(prefix):
            return fleet
    return None


def _space_point(home):
    """A point 40 ly from home, reachable in one turn at warp 8."""
    dx = 40 if home["position_x"] < 200 else -40
    return home["position_x"] + dx, home["position_y"]


def _add_waypoint(harness, fleet, x, y, destination, warp=8):
    harness.submit(1, "waypoint", {
        "mode": "Add",
        "fleet_key": fleet["key"],
        "index": len(fleet.get("waypoints", [])),
        "waypoint": {
            "position_x": x,
            "position_y": y,
            "warp_factor": warp,
            "destination": destination,
            "task": {"type": "NoTask"},
        },
    })


class TestRepairRefuel:

    def test_refuel_at_own_starbase(self, harness):
        """A scout that burned fuel in deep space is refueled to full
        on returning to the homeworld dock."""
        harness.create_game(seed=SEED, size="small", players=2)

        home = harness.my_stars(1)[0]
        scout = _fleet_named(harness, "Long Range Scout")
        assert scout is not None
        assert scout["fuel_available"] == scout["fuel_capacity"]

        # Fly one turn into empty space at warp 8 (burns fuel)
        x, y = _space_point(home)
        _add_waypoint(harness, scout, x, y, f"Space at {x},{y}")
        harness.generate_turn()

        scout = _fleet_named(harness, "Long Range Scout")
        assert scout["in_orbit"] is None
        assert scout["fuel_available"] < scout["fuel_capacity"]

        # Fly back to the homeworld; arrival and refuel happen in the
        # same turn (movement precedes RegenerateFleet in ProcessFleet)
        _add_waypoint(harness, scout, home["position_x"],
                      home["position_y"], home["name"])
        harness.generate_turn()

        scout = _fleet_named(harness, "Long Range Scout")
        assert scout["in_orbit"] == home["name"]
        assert scout["fuel_available"] == scout["fuel_capacity"]

    def test_repair_rate_dock_vs_deep_space(self, harness):
        """A damaged fleet at the homeworld dock repairs 20 points/yr;
        a damaged fleet stopped in deep space repairs 2 points/yr."""
        harness.create_game(seed=SEED, size="small", players=2)

        home = harness.my_stars(1)[0]
        teamster = _fleet_named(harness, "Teamster")
        scout = _fleet_named(harness, "Long Range Scout")
        assert teamster is not None and scout is not None

        # Park the scout in deep space (arrives and stops in one turn)
        x, y = _space_point(home)
        _add_waypoint(harness, scout, x, y, f"Space at {x},{y}")
        harness.generate_turn()

        # The reached waypoint (NoTask, same position) lingers until
        # the next turn's movement pass pops it, so the scout counts
        # as stopped for repair purposes from the next turn on
        scout = _fleet_named(harness, "Long Range Scout")
        assert scout["in_orbit"] is None

        # Inject 50% damage on both fleets through the manager cache
        gm = gm_module._game_manager
        sd = gm._load_game_state(harness.game_id)
        for key in (teamster["key"], scout["key"]):
            fleet = sd.all_empires[1].owned_fleets[key]
            for token in fleet.tokens.values():
                token.damage_percent = 50.0
        gm._save_game_state(harness.game_id, sd)

        # One year: dock 20%/yr vs stopped-in-space 2%/yr. The scout's
        # 20-armor hull hits the C# 1-armor-point minimum instead
        # (TurnGenerator.cs:376 Math.Max(..., 1)): 1 of 20 armor =
        # 5 percentage points per year - still far below the dock rate
        harness.generate_turn()
        teamster = _fleet_named(harness, "Teamster")
        scout = _fleet_named(harness, "Long Range Scout")
        assert teamster["in_orbit"] == home["name"]
        assert teamster["tokens"][0]["damage_percent"] == 30.0
        assert scout["tokens"][0]["damage_percent"] == 45.0

        # Second year proves the rate, not just any repair
        harness.generate_turn()
        teamster = _fleet_named(harness, "Teamster")
        scout = _fleet_named(harness, "Long Range Scout")
        assert teamster["tokens"][0]["damage_percent"] == 10.0
        assert scout["tokens"][0]["damage_percent"] == 40.0
