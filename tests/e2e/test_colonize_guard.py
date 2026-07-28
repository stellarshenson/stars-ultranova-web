"""
Seeded e2e: colonize aborts on an occupied planet (DEF-12 regression).

Before the fix a COLONIZE task on a foreign-owned planet was silently
converted into a full invasion (run100 Kapteyn's Star), and a colonize
on an already-populated own planet overwrote its population. The C#
reference (ColoniseTask.cs IsValid, lines 88-92) aborts with
"attempted to colonise ... but it is already occupied." for ANY
occupant, keeping colonists aboard and the fleet intact.
"""

SEED = 20260713


def _colony_ship(harness, empire_id=1):
    for fleet in harness.my_fleets(empire_id):
        if fleet["can_colonize"] and not fleet["is_starbase"]:
            return fleet
    return None


class TestColonizeOccupiedGuard:

    def test_colonize_own_homeworld_aborts(self, harness):
        """Colonize ordered at the (occupied) homeworld the colony
        ship is orbiting: aborts with the canonical message, colonists
        stay aboard, population is not overwritten, no invasion."""
        harness.create_game(seed=SEED, size="small", players=2)

        home = harness.my_stars(1)[0]
        ship = _colony_ship(harness)
        assert ship is not None
        colonists_aboard = ship["cargo"]["colonists"]
        assert colonists_aboard > 0

        harness.submit(1, "waypoint", {
            "mode": "Add", "fleet_key": ship["key"], "index": 0,
            "waypoint": {
                "position_x": home["position_x"],
                "position_y": home["position_y"],
                "warp_factor": 6, "destination": home["name"],
                "task": {"type": "Colonise"},
            },
        })
        harness.generate_turn()

        # Homeworld population untouched (grew, never reset to the
        # ship's cargo), still ours
        after = harness.star_by_name(home["name"], 1)
        assert after["owner"] == home["owner"]
        assert after["colonists"] >= home["colonists"]

        # The ship survives with its colonists still aboard
        ship_after = _colony_ship(harness)
        assert ship_after is not None
        assert ship_after["cargo"]["colonists"] == colonists_aboard

        messages = harness.state(1)["messages"]
        assert any("already occupied" in m["text"] for m in messages)
        assert not any(m.get("message_type") == "Invasion"
                       for m in messages)
