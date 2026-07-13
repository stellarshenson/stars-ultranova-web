"""
Seeded e2e: cloaking and enemy-design learning (AC-INTEL-2/3).

A JOAT empire scouts the enemy homeworld: once the enemy fleets fall
inside the scout's 66 ly scanner, the observer's intel gains HULL-ONLY
design records (port of ScanStep.cs:170-183) and the fleet reports
carry composition. The same game then researches Electronics 5 and
builds a cloaked scout (Scout hull + Stealth Cloak, 70 cloak units =
35%): parked 55 ly from the enemy scanners - inside the nominal 66 ly
range but outside the cloak-reduced 42.9 ly - it stays invisible while
an uncloaked control scout at the same distance is detected. Cloaking
is a stub in the C# reference (ScanStep.cs:165); the detection math
follows canonical Stars! rules.
"""

import math

SEED = 20260717
MAX_TURNS = 40

RESEARCH_FIELDS = ("Biotechnology", "Electronics", "Energy",
                   "Propulsion", "Weapons", "Construction")

# JOAT starts at tech 3 everywhere (Energy 2 for the Stealth Cloak is
# already covered); cheap electronics speeds the climb to level 5 and
# growthRate 6 buys the advantage-point headroom
RACE = {
    "name": "Phantoms",
    "pluralName": "Phantoms",
    "prt": "JOAT",
    "growthRate": 6,
    "researchCosts": {
        "energy": "normal", "electronics": "cheap", "weapons": "normal",
        "propulsion": "normal", "construction": "normal",
        "biotechnology": "normal",
    },
}


def _focus(harness, field, budget):
    topics = {key: 0 for key in RESEARCH_FIELDS}
    topics[field] = 1
    result = harness.submit(1, "research",
                            {"budget": budget,
                             "topics": {"levels": topics}})
    assert result["status"] in ("applied", "unchanged")


def _play_until(harness, predicate):
    """Generate turns until predicate(state of player 1) or MAX_TURNS."""
    for _ in range(MAX_TURNS):
        harness.generate_turn()
        state = harness.state(1)
        if predicate(state):
            return state
    raise AssertionError("condition not reached within MAX_TURNS")


def _fleets_named(harness, prefix, empire_id=1):
    return [f for f in harness.my_fleets(empire_id)
            if f["name"].startswith(prefix)]


def _point_towards(from_pos, to_pos, distance):
    """Point `distance` ly from from_pos along the line to to_pos."""
    dx = to_pos[0] - from_pos[0]
    dy = to_pos[1] - from_pos[1]
    length = math.hypot(dx, dy)
    return (from_pos[0] + dx / length * distance,
            from_pos[1] + dy / length * distance)


def _send_to(harness, fleet, x, y, warp):
    harness.submit(1, "waypoint", {
        "mode": "Add",
        "fleet_key": fleet["key"],
        "index": len(fleet.get("waypoints", [])),
        "waypoint": {
            "position_x": x,
            "position_y": y,
            "warp_factor": warp,
            "destination": "deep space",
            "task": {"type": "NoTask"},
        },
    })


def _arrived(harness, fleet_key, x, y):
    for fleet in harness.my_fleets(1):
        if fleet["key"] == fleet_key:
            return (abs(fleet["position_x"] - x) < 1.0
                    and abs(fleet["position_y"] - y) < 1.0)
    return False


def _run_scenario(harness):
    harness.create_game(seed=SEED, size="small", players=2,
                        race=RACE, accelerated_start=True)
    p1_home = harness.my_stars(1)[0]
    p2_home = harness.my_stars(2)[0]
    p2_pos = (p2_home["position_x"], p2_home["position_y"])
    p1_pos = (p1_home["position_x"], p1_home["position_y"])

    _focus(harness, "Electronics", budget=100)

    # -- Scenario A: design learning on detection (AC-INTEL-3) --------
    # Park the scout 60 ly from the enemy homeworld: inside its own
    # 66 ly scanner (mutual detection) but never co-located (no battle,
    # so the learned records stay hull-only)
    scouts = _fleets_named(harness, "Long Range Scout")
    assert len(scouts) >= 2  # JOAT starts with two
    watch_point = _point_towards(p2_pos, p1_pos, 60)
    _send_to(harness, scouts[0], watch_point[0], watch_point[1], warp=5)

    state = _play_until(
        harness,
        lambda s: any(f["owner"] == 2 for f in s["foreign_fleets"]))

    # Learned records are hull-only: hull name yes, component data no
    assert state["enemy_designs"], "no designs learned on detection"
    for record in state["enemy_designs"]:
        assert record["scope"] == "hull"
        assert record["owner"] == 2
        assert record["hull_name"]
        assert "design" not in record

    # Fleet reports reveal composition (FleetIntel.cs:206-217)
    seen = [f for f in state["foreign_fleets"] if f["owner"] == 2]
    assert any(f["composition"] for f in seen)
    for entry in seen[0]["composition"]:
        assert entry["design_name"]
        assert entry["quantity"] >= 1

    # -- Scenario B: a cloaked scout slips past (AC-INTEL-2) ----------
    _play_until(
        harness,
        lambda s: s["research"]["levels"]["Electronics"] >= 5)
    # Park research so the homeworld's resources go to production
    _focus(harness, "Electronics", budget=0)

    harness.submit(1, "design", {"mode": "Add", "design": {
        "name": "Shadow Scout",
        "hull": "Scout",
        "slots": [
            {"cell_number": 11, "component": "Quick Jump 5", "count": 1},
            {"cell_number": 12, "component": "Stealth Cloak", "count": 1},
        ],
    }})
    design = next(d for d in harness.state(1)["designs"]
                  if d["name"] == "Shadow Scout")
    harness.submit(1, "production", {
        "mode": "Add", "star_key": p1_home["name"], "index": 0,
        "production_order": {"production_type": "SHIP", "quantity": 1,
                             "name": "Shadow Scout",
                             "design_key": design["key"]},
    })
    _play_until(
        harness,
        lambda s: any(f["name"].startswith("Shadow Scout")
                      for f in s["fleets"]))

    # Park the cloaked scout and an uncloaked control at 62 ly from
    # the enemy scanners. Enemy coverage: 66 ly fleet scanners plus a
    # Viewer 50 homeworld scanner that its own research may upgrade to
    # Viewer 90 during the run. 62 ly is inside the nominal 66 ly
    # fleet-scanner range (control detected) but outside every
    # 35%-cloak-reduced range: 66 -> 42.9, 90 -> 58.5
    park_point = _point_towards(p2_pos, p1_pos, 62)
    cloaked = _fleets_named(harness, "Shadow Scout")[0]
    control = _fleets_named(harness, "Long Range Scout")[1]
    _send_to(harness, cloaked, park_point[0], park_point[1], warp=5)
    _send_to(harness, control, park_point[0], park_point[1], warp=5)

    _play_until(
        harness,
        lambda s: (_arrived(harness, cloaked["key"], *park_point)
                   and _arrived(harness, control["key"], *park_point)))

    p2_state = harness.state(2)
    # Guard: the geometry above tolerates at most a Viewer 90 upgrade
    assert next(s for s in p2_state["stars"]
                if s["name"] == p2_home["name"])["scan_range"] <= 90
    foreign_keys = [f["key"] for f in p2_state["foreign_fleets"]]
    assert control["key"] in foreign_keys, \
        "uncloaked control scout not detected"
    assert cloaked["key"] not in foreign_keys, \
        "cloaked scout was detected despite 35% cloak"

    # The enemy learned our hull designs from what it detected
    assert any(r["scope"] == "hull" and r["owner"] == 1
               for r in p2_state["enemy_designs"])


class TestCloakingIntel:

    def test_cloak_hides_and_detection_teaches_designs(self, harness):
        _run_scenario(harness)

    def test_scenario_is_deterministic(self, harness):
        """Same seed + same commands -> identical state digest."""
        digests = []
        for _ in range(2):
            _run_scenario(harness)
            digests.append(harness.state_digest(1))
        assert digests[0] == digests[1]
