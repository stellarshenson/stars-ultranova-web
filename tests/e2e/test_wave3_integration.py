"""
Wave-3 cross-feature integration: one seeded game combining the four
wave-3 gap families end to end.

A JOAT empire (default race) plays a single seeded game in which:

- a damaged Stalwart Defender parked at the homeworld starbase dock
  repairs 20 percentage points per year (RegenerateFleet situation
  table, TurnGenerator.cs:283-300);
- a cloaked freighter (Small Freighter + Stealth Cloak, 70 cloak
  units = 35% fleet cloak) runs a waypoint cargo route: LOAD at
  waypoint zero (SplitFleetStep), UNLOAD on arrival at a foreign star
  (_update_fleet, CargoTask.cs:145-228 port);
- the repaired Defender (2 beams, power 16 range 3 -> sweeps 288
  mines/yr) parks inside a hostile minefield and sweeps it away over
  several turns (canonical rate power x range^2, both owners
  messaged, field deleted at <= 10 mines);
- a Long Range Scout crossing a stationary intensity-1.0 storm at
  warp 9 (above STORM_SAFE_WARP 6) suffers a warp mishap: locally
  scaled (20 + 25) x intensity hull damage and stopped dead (warp 0)
  inside the storm.

Phenomena are placed by state surgery (the established harness
pattern, see tests/e2e/test_storms.py and test_cloaking_intel.py);
every roll rides the per-turn seeded RNG, so the recorded outcome is
reproducible for the fixed seed.
"""

import math
import random

import pytest

SEED = 20260713
UNIVERSE = 400            # "small" universe (galaxy_generator SIZES)
BUILD_TURNS = 8
CARGO_TURNS = 12
SWEEP_TURNS = 8
MISHAP_ATTEMPTS = 30
LOAD_KT = 30
MINEFIELD_KEY = 7777
MINEFIELD_MINES = 700     # radius ~26 ly; swept at 288/yr in a few turns


def _manager():
    from backend.services.game_manager import get_game_manager
    return get_game_manager()


def _load(harness):
    return _manager()._load_game_state(harness.game_id)


def _save(harness, server_data):
    _manager()._save_game_state(harness.game_id, server_data)


def _fleet_named(harness, prefix, empire_id=1):
    for fleet in harness.my_fleets(empire_id):
        if fleet["name"].startswith(prefix):
            return fleet
    return None


def _zero_research(harness):
    """All homeworld resources to production, none to labs."""
    levels = {key: 0 for key in harness.state(1)["research"]["levels"]}
    levels["Energy"] = 1
    harness.submit(1, "research", {"budget": 0,
                                   "topics": {"levels": levels}})


def _add_waypoint(harness, fleet_key, x, y, warp, dest, task=None):
    harness.submit(1, "waypoint", {
        "mode": "Add",
        "fleet_key": fleet_key,
        "index": 0,
        "waypoint": {
            "position_x": x,
            "position_y": y,
            "warp_factor": warp,
            "destination": dest,
            "task": task or {"type": "NoTask"},
        },
    })


def _add_cargo_waypoint(harness, fleet, star, warp, mode, amount):
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


def _inject_damage(harness, fleet_key, percent):
    server_data = _load(harness)
    fleet = server_data.all_empires[1].owned_fleets[fleet_key]
    for token in fleet.tokens.values():
        token.damage_percent = percent
    _save(harness, server_data)


def _teleport(harness, fleet_key, x, y, refit=False):
    """Park a player 1 fleet at (x, y); optionally reset damage/fuel."""
    from backend.core.data_structures import NovaPoint

    server_data = _load(harness)
    fleet = server_data.all_empires[1].owned_fleets[fleet_key]
    fleet.position = NovaPoint(x, y)
    fleet.waypoints = []
    fleet.in_orbit_name = None
    fleet.in_orbit = None
    if refit:
        fleet.fuel_available = 100000
        for token in fleet.tokens.values():
            token.damage_percent = 0
    _save(harness, server_data)


def _ground_fleet(harness, fleet_key):
    server_data = _load(harness)
    return server_data, server_data.all_empires[1].owned_fleets[fleet_key]


def _clear_space(harness, min_x=90, avoid=(), avoid_by=60):
    """Grid-search the point with the most clearance from every star
    (and every `avoid` point), in-bounds with room for a -x approach
    run (same constraint as tests/e2e/test_storms.py)."""
    server_data = _load(harness)
    stars = list(server_data.all_stars.values())
    best = None
    for gx in range(min_x, UNIVERSE - 10, 10):
        for gy in range(10, UNIVERSE - 10, 10):
            if any(math.hypot(gx - ax, gy - ay) < avoid_by
                   for ax, ay in avoid):
                continue
            clearance = min(math.hypot(gx - s.position.x,
                                       gy - s.position.y) for s in stars)
            if best is None or clearance > best[0]:
                best = (clearance, gx, gy)
    assert best is not None, "no clear space for this seed"
    return best[1], best[2]


def _storm_messages(state, name):
    return [m for m in state["messages"]
            if m.get("type") == "Storm" and name in m.get("text", "")]


class TestWave3Integration:

    def test_cross_feature_seeded_game(self, harness):
        harness.create_game(seed=SEED, size="small", players=2)
        home = harness.my_stars(1)[0]
        _zero_research(harness)

        # No wandering storms: they would pollute the repair-rate and
        # cargo phases (storm placement is phase 4's surgery)
        server_data = _load(harness)
        server_data.all_storms = {}
        _save(harness, server_data)

        # -- Phase 1 setup: cloaked freighter design + build order ----
        # Electronics 5 unlocks the Stealth Cloak (components.xml);
        # granted by state surgery so the route runs early in the game
        server_data = _load(harness)
        server_data.all_empires[1].research_levels.levels["Electronics"] = 5
        _save(harness, server_data)

        result = harness.submit(1, "design", {"mode": "Add", "design": {
            "name": "Shadow Hauler",
            "hull": "Small Freighter",
            "slots": [
                {"cell_number": 10, "component": "Quick Jump 5",
                 "count": 1},
                {"cell_number": 13, "component": "Stealth Cloak",
                 "count": 1},
            ],
        }})
        assert result["status"] == "applied", result
        design = next(d for d in harness.state(1)["designs"]
                      if d["name"] == "Shadow Hauler")
        harness.submit(1, "production", {
            "mode": "Add", "star_key": home["name"], "index": 0,
            "production_order": {"production_type": "SHIP", "quantity": 1,
                                 "name": "Shadow Hauler",
                                 "design_key": design["key"]},
        })

        # -- Phase 1: dock repair at 20 points/yr ----------------------
        # The Stalwart Defender sits in orbit at the homeworld starbase
        # dock: RegenerateFleet repairs 20 percentage points per year
        defender = _fleet_named(harness, "Stalwart Defender")
        assert defender is not None
        assert defender["in_orbit"] == home["name"]
        _inject_damage(harness, defender["key"], 50.0)

        harness.generate_turn()
        defender = _fleet_named(harness, "Stalwart Defender")
        assert defender["tokens"][0]["damage_percent"] == 30.0

        harness.generate_turn()
        defender = _fleet_named(harness, "Stalwart Defender")
        assert defender["tokens"][0]["damage_percent"] == 10.0

        # -- Phase 2: cloaked freighter runs the cargo route -----------
        for _ in range(BUILD_TURNS):
            if _fleet_named(harness, "Shadow Hauler"):
                break
            harness.generate_turn()
        hauler = _fleet_named(harness, "Shadow Hauler")
        assert hauler is not None, "Shadow Hauler never built"

        # The empty hauler is a genuinely cloaked fleet: Stealth Cloak
        # 70 units/kT -> 35% (canonical curve, ScanStep port)
        from backend.server.turn_steps.scan_step import ScanStep
        server_data, fleet = _ground_fleet(harness, hauler["key"])
        cloak = ScanStep()._fleet_cloak_percent(
            fleet, server_data.all_empires[1])
        assert cloak == pytest.approx(35.0)

        target = min(
            (s for s in harness.state(1)["stars"]
             if s.get("intel") != "owned"),
            key=lambda s: ((s["position_x"] - home["position_x"]) ** 2
                           + (s["position_y"] - home["position_y"]) ** 2))

        _add_cargo_waypoint(harness, hauler, home, warp=0,
                            mode="LOAD", amount={"ironium": LOAD_KT})
        result = harness.generate_turn()
        hauler = _fleet_named(harness, "Shadow Hauler")
        assert hauler["cargo"]["ironium"] == LOAD_KT
        assert any(m["audience"] == 1 and "has loaded cargo from"
                   in m["text"] for m in result["messages"])

        # Cargo mass dilutes the cloak but never disables it
        server_data, fleet = _ground_fleet(harness, hauler["key"])
        loaded_cloak = ScanStep()._fleet_cloak_percent(
            fleet, server_data.all_empires[1])
        assert 0.0 < loaded_cloak < 35.0

        _add_cargo_waypoint(harness, hauler, target, warp=4,
                            mode="UNLOAD", amount={"ironium": LOAD_KT})
        unloaded = False
        for _ in range(CARGO_TURNS):
            result = harness.generate_turn()
            if any(m["audience"] == 1
                   and f"has unloaded its cargo at {target['name']}"
                   in m["text"] for m in result["messages"]):
                unloaded = True
                break
        assert unloaded, "cloaked freighter never unloaded at the target"
        hauler = _fleet_named(harness, "Shadow Hauler")
        assert hauler["in_orbit"] == target["name"]
        assert hauler["cargo"]["ironium"] == 0

        # -- Phase 3: the armed fleet sweeps a hostile minefield -------
        # An enemy standard field appears in clear space; the repaired
        # Defender (2 beams, 16 x 3^2 x 2 = 288 mines/yr) parks inside
        from backend.server.server_data import Minefield

        target_pos = (target["position_x"], target["position_y"])
        mine_site = _clear_space(harness, avoid=(target_pos,))
        server_data = _load(harness)
        server_data.all_minefields[MINEFIELD_KEY] = Minefield(
            key=MINEFIELD_KEY, owner=2,
            position_x=mine_site[0], position_y=mine_site[1],
            number_of_mines=MINEFIELD_MINES, mine_type=0)
        _save(harness, server_data)
        _teleport(harness, defender["key"], mine_site[0], mine_site[1])

        mines_seen = [MINEFIELD_MINES]
        saw_sweep_messages = False
        for _ in range(SWEEP_TURNS):
            result = harness.generate_turn()
            sweeps = [m for m in result["messages"]
                      if m["type"] == "Minefield Swept"]
            if any(m["audience"] == 1 and "Stalwart Defender"
                   in m["text"] for m in sweeps) and \
                    any(m["audience"] == 2 for m in sweeps):
                saw_sweep_messages = True
            server_data = _load(harness)
            field = server_data.all_minefields.get(MINEFIELD_KEY)
            if field is None:
                break  # swept away
            assert field.number_of_mines < mines_seen[-1], \
                "minefield did not shrink while the Defender sat inside"
            mines_seen.append(field.number_of_mines)
        else:
            raise AssertionError("minefield was never swept away")
        assert len(mines_seen) >= 3, "expected several sweeping turns"
        assert saw_sweep_messages, "no sweep messages for both owners"

        # -- Phase 4: warp-9 storm crossing suffers a local mishap -----
        # A stationary intensity-1.0 blob storm in clear space; a scout
        # crosses to the core at warp 9 (mishap chance
        # 0.10 x (9 - 6) x local per turn on the seeded RNG)
        from backend.server.server_data import GalacticStorm

        cx, cy = _clear_space(
            harness, avoid=(target_pos, mine_site), avoid_by=70)
        server_data = _load(harness)
        storm = GalacticStorm(key=1, x=cx, y=cy, radius=32,
                              velocity_x=0, velocity_y=0, intensity=1.0)
        storm.generate_shape(random.Random(4242))
        server_data.all_storms = {1: storm}
        _save(harness, server_data)

        scout = _fleet_named(harness, "Long Range Scout")
        assert scout is not None
        server_data, fleet = _ground_fleet(harness, scout["key"])
        scout_name = fleet.name

        mishap_state = None
        for _ in range(MISHAP_ATTEMPTS):
            _teleport(harness, scout["key"], cx - 81, cy, refit=True)
            _add_waypoint(harness, scout["key"], cx, cy, warp=9,
                          dest="storm run")
            harness.generate_turn()
            state = harness.state(1)
            if any("warp mishap" in m["text"]
                   for m in _storm_messages(state, scout_name)):
                mishap_state = state
                break
        assert mishap_state is not None, \
            f"no mishap within {MISHAP_ATTEMPTS} warp-9 crossings"

        server_data, fleet = _ground_fleet(harness, scout["key"])
        local = server_data.all_storms[1].get_intensity_at(
            fleet.position.x, fleet.position.y)
        assert local > 0.0, "mishap fleet is not inside the storm"
        # Stopped dead inside the storm, waypoint preserved at warp 0
        assert fleet.waypoints, "mishap cleared the waypoint"
        assert fleet.waypoints[0].warp_factor == 0
        # Storm damage plus mishap damage, both scaled by the LOCAL
        # intensity at the fleet's stopping position
        damage = fleet.tokens[next(iter(fleet.tokens))].damage_percent
        assert damage == pytest.approx((20 + 25) * local)
