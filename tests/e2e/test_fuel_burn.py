"""
Seeded e2e: canonical per-engine fuel burn (DEF-7 regression).

Reproduces the run100 playtest commander's empirical method: fly a
25 kT Long Range Scout (Quick Jump 5) straight one-year legs at warp
5, 6 and 8 and measure the fuel burned per turn. The canonical model
(ShipDesign.cs lines 721-744) burns

    (mass + cargo) * table[warp - 1] / 100 * warp^2 / 200  mg/year

with Quick Jump 5's table (Engine.cs / components.xml, warp 1..10):
0, 25, 100, 100, 100, 180, 500, 800, 900, 1080. The measured burns
must match the table entries exactly and refute the old linear model
(mass * warp^3 / 200 per year) that DEF-7 measured.

Also covers the out-of-fuel drop to the table-derived free warp
(Fleet.cs lines 570-576; Quick Jump 5 is free at warp 1) and the
API fuel_consumption_by_warp surface.
"""

import backend.services.game_manager as gm_module

# Seed chosen so the eastward test legs from the homeworld cross no
# dust nebula (dust would slow the legs and mask the exact per-year
# burns under test)
SEED = 20260713

# Quick Jump 5 per-warp fuel factors (components.xml Warp0..Warp9 =
# warp 1..10; consumed as table[warp - 1] per ShipDesign.cs:732)
QJ5 = [0, 25, 100, 100, 100, 180, 500, 800, 900, 1080]
SCOUT_MASS = 25


def _canonical_burn(mass, warp, years=1.0):
    """int-truncated burn per Fleet.cs:567."""
    rate = mass * QJ5[warp - 1] / 100.0 * warp * warp / 200.0
    return int(rate * years)


def _linear_burn(mass, warp, years=1.0):
    """The old (defective) linear model: mass * warp^3 / 200 per
    year, i.e. mass * warp / 200 per light year."""
    return int(mass * warp ** 3 / 200.0 * years)


def _fleet_named(harness, prefix, empire_id=1):
    for fleet in harness.my_fleets(empire_id):
        if fleet["name"].startswith(prefix):
            return fleet
    return None


def _add_waypoint(harness, fleet, x, y, warp):
    harness.submit(1, "waypoint", {
        "mode": "Add",
        "fleet_key": fleet["key"],
        "index": len(fleet.get("waypoints", [])),
        "waypoint": {
            "position_x": x,
            "position_y": y,
            "warp_factor": warp,
            "destination": f"Space at {x},{y}",
            "task": {"type": "NoTask"},
        },
    })


class TestCanonicalFuelBurn:

    def test_burn_matches_engine_table_not_linear(self, harness):
        """One-year legs at warp 5/6/8 burn exactly the table-derived
        3/8/64 mg - not the linear model's 15/27/64."""
        harness.create_game(seed=SEED, size="small", players=2)

        scout = _fleet_named(harness, "Long Range Scout")
        assert scout is not None
        direction = 1 if scout["position_x"] < 200 else -1

        measured = {}
        for warp in (5, 6, 8):
            scout = _fleet_named(harness, "Long Range Scout")
            fuel_before = scout["fuel_available"]
            # A leg of exactly warp^2 ly = one year of travel
            target_x = scout["position_x"] + direction * warp * warp
            target_y = scout["position_y"]
            _add_waypoint(harness, scout, target_x, target_y, warp)
            harness.generate_turn()

            scout = _fleet_named(harness, "Long Range Scout")
            # The leg must complete in the year (no dust interference)
            # or the exact one-year burn assertion is meaningless
            assert scout["position_x"] == target_x
            assert scout["position_y"] == target_y
            measured[warp] = fuel_before - scout["fuel_available"]

        # Canonical per-engine table burn, int-truncated (Fleet.cs:567)
        assert measured[5] == _canonical_burn(SCOUT_MASS, 5) == 3
        assert measured[6] == _canonical_burn(SCOUT_MASS, 6) == 8
        assert measured[8] == _canonical_burn(SCOUT_MASS, 8) == 64

        # Refute DEF-7's measured linear model where it diverges
        # (at warp 8 the two coincide for Quick Jump 5: 800/20000 =
        # 8/200 per kT-ly)
        assert measured[5] != _linear_burn(SCOUT_MASS, 5) == 15
        assert measured[6] != _linear_burn(SCOUT_MASS, 6) == 27

        # Quadratic-by-warp character: per-ly burn ratio follows the
        # table (800/100 = 8x from warp 5 to 8), not the linear 1.6x
        per_ly_5 = measured[5] / 25.0
        per_ly_8 = measured[8] / 64.0
        assert per_ly_8 / per_ly_5 > 5.0

    def test_out_of_fuel_drops_to_table_free_warp(self, harness):
        """A Teamster (mass 60, fuel 130) ordered on a long warp 8 leg
        runs dry in the first year (burn 153 > 130) and drops to
        Quick Jump 5's free warp 1 - not to warp 0 (Fleet.cs:570-576
        with the table-derived free warp)."""
        harness.create_game(seed=SEED, size="small", players=2)

        teamster = _fleet_named(harness, "Teamster")
        assert teamster is not None
        assert _canonical_burn(60, 8) > teamster["fuel_available"]
        direction = 1 if teamster["position_x"] < 200 else -1
        _add_waypoint(harness, teamster,
                      teamster["position_x"] + direction * 100,
                      teamster["position_y"], 8)
        harness.generate_turn()

        teamster = _fleet_named(harness, "Teamster")
        assert teamster["fuel_available"] == 0
        # The travel waypoint is the last one (the serializer inserts
        # a current-position marker at index 0 while in transit)
        assert teamster["waypoints"], "leg unfinished, waypoint kept"
        assert teamster["waypoints"][-1]["warp_factor"] == 1
        messages = harness.state(1).get("messages", [])
        assert any("run out of fuel" in m["text"] for m in messages)

    def test_fuel_time_caps_travel_distance(self, harness):
        """DEF-13 regression: travel is capped by fuel time
        (Fleet.cs:520-546) - a Teamster with 130 mg on a 100 ly warp 8
        leg (rate 153.6/yr) covers exactly 64 * 130/153.6 = 54.17 ly
        in year 1, not the full 64 ly year the old code moved before
        deducting fuel. Year 2 it crawls at the free warp 1."""
        harness.create_game(seed=SEED, size="small", players=2)

        teamster = _fleet_named(harness, "Teamster")
        assert teamster is not None
        start_x = teamster["position_x"]
        fuel = teamster["fuel_available"]
        direction = 1 if start_x < 200 else -1
        _add_waypoint(harness, teamster, start_x + direction * 100,
                      teamster["position_y"], 8)
        harness.generate_turn()

        teamster = _fleet_named(harness, "Teamster")
        rate = 60 * QJ5[8 - 1] / 100.0 * 8 * 8 / 200.0  # 153.6 mg/yr
        expected = 64 * (fuel / rate)  # 54.17 ly, not 64
        moved = abs(teamster["position_x"] - start_x)
        assert abs(moved - expected) < 0.01
        assert moved < 64
        assert teamster["fuel_available"] == 0

        # Year 2: free warp 1 covers 1 ly on an empty tank
        harness.generate_turn()
        teamster = _fleet_named(harness, "Teamster")
        moved2 = abs(teamster["position_x"] - start_x) - moved
        assert abs(moved2 - 1.0) < 0.01
        assert teamster["fuel_available"] == 0

    def test_api_by_warp_readout_is_table_derived(self, harness):
        """fuel_consumption_by_warp (fleet panel readout) equals the
        canonical table values for the scout fleet."""
        harness.create_game(seed=SEED, size="small", players=2)

        scout = _fleet_named(harness, "Long Range Scout")
        by_warp = scout["fuel_consumption_by_warp"]
        assert len(by_warp) == 11
        for warp in range(11):
            if warp == 0:
                assert by_warp[warp] == 0
            else:
                expected = (SCOUT_MASS * QJ5[warp - 1] / 100.0
                            * warp * warp / 200.0)
                assert by_warp[warp] == round(expected, 2)
