"""
Seeded e2e: in-transit waypoint warp fidelity (DEF-11 regression).

While a fleet is between waypoints the turn generator inserts a
same-position NoTask placeholder at index 0. Before the fix the
placeholder took the Waypoint dataclass default warp 6 (C#
TurnGenerator.cs:430-436 copies waypointZero.WarpFactor), so every
in-transit fleet serialized phantom warp 6, and warp edits landing on
the placeholder were discarded by the next turn's same-position pop.
Also asserts the out-of-fuel turn emits exactly ONE fuel message (the
web-only "dropped to warp N" duplicate was removed; the canonical
per-turn message is TurnGenerator.cs:270-279).
"""

# Same no-dust seed as test_fuel_burn (eastward legs cross no dust
# nebula, so movement arithmetic is exact)
SEED = 20260713

ORDERED_WARP = 5
EDITED_WARP = 6


def _fleet_named(harness, prefix, empire_id=1):
    for fleet in harness.my_fleets(empire_id):
        if fleet["name"].startswith(prefix):
            return fleet
    return None


def _order_long_leg(harness, fleet, warp, leg=100):
    direction = 1 if fleet["position_x"] < 200 else -1
    harness.submit(1, "waypoint", {
        "mode": "Add",
        "fleet_key": fleet["key"],
        "index": len(fleet.get("waypoints", [])),
        "waypoint": {
            "position_x": fleet["position_x"] + direction * leg,
            "position_y": fleet["position_y"],
            "warp_factor": warp,
            "destination": "Deep Space",
            "task": {"type": "NoTask"},
        },
    })


class TestInTransitWaypoints:

    def test_placeholder_serializes_ordered_warp(self, harness):
        """An in-transit fleet reports the ordered warp, not the
        phantom default 6."""
        harness.create_game(seed=SEED, size="small", players=2)

        scout = _fleet_named(harness, "Long Range Scout")
        assert scout is not None
        _order_long_leg(harness, scout, ORDERED_WARP)
        harness.generate_turn()

        scout = _fleet_named(harness, "Long Range Scout")
        # Placeholder + destination remain
        assert len(scout["waypoints"]) == 2
        placeholder = scout["waypoints"][0]
        assert placeholder["task_type"] == "NoTaskObj"
        assert placeholder["position_x"] == scout["position_x"]
        assert placeholder["warp_factor"] == ORDERED_WARP
        assert scout["warp_factor"] == ORDERED_WARP

    def test_warp_edit_in_transit_survives_the_pop(self, harness):
        """Editing waypoint 0 (the placeholder) mid-transit writes the
        new warp onto the destination waypoint, so the edit survives
        the next turn's same-position pop and drives movement."""
        harness.create_game(seed=SEED, size="small", players=2)

        scout = _fleet_named(harness, "Long Range Scout")
        _order_long_leg(harness, scout, ORDERED_WARP)
        harness.generate_turn()

        scout = _fleet_named(harness, "Long Range Scout")
        placeholder = scout["waypoints"][0]
        # The fleet-panel warp slider edits waypoint 0 in place
        harness.submit(1, "waypoint", {
            "mode": "Edit",
            "fleet_key": scout["key"],
            "index": 0,
            "waypoint": {
                "position_x": placeholder["position_x"],
                "position_y": placeholder["position_y"],
                "warp_factor": EDITED_WARP,
                "destination": placeholder["destination"],
                "task": {"type": "NoTask"},
            },
        })

        position_before = _fleet_named(harness, "Long Range Scout")
        harness.generate_turn()

        scout = _fleet_named(harness, "Long Range Scout")
        # The edit reached the real leg: the fleet moved a full year
        # at the EDITED warp and still reports it
        moved = abs(scout["position_x"] - position_before["position_x"])
        assert abs(moved - EDITED_WARP * EDITED_WARP) < 0.01
        assert scout["warp_factor"] == EDITED_WARP
        assert scout["waypoints"][-1]["warp_factor"] == EDITED_WARP

    def test_out_of_fuel_turn_emits_single_fuel_message(self, harness):
        """Running dry produces exactly one fuel message (the
        canonical per-turn one) - the web-only 'dropped to warp N'
        duplicate is gone; the drop itself is silent
        (Fleet.cs:570-576)."""
        harness.create_game(seed=SEED, size="small", players=2)

        teamster = _fleet_named(harness, "Teamster")
        assert teamster is not None
        _order_long_leg(harness, teamster, 8)
        harness.generate_turn()

        teamster = _fleet_named(harness, "Teamster")
        assert teamster["fuel_available"] == 0
        fuel_messages = [
            m for m in harness.state(1).get("messages", [])
            if "fuel" in m["text"].lower()
            and m["text"].startswith("Teamster")
        ]
        assert len(fuel_messages) == 1
        assert "has run out of fuel" in fuel_messages[0]["text"]
