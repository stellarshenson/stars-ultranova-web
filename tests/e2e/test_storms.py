"""
Seeded e2e: galactic storm hazards (user directive 2026-07-13).

A single stationary intensity-1.0 blob storm is placed by state
surgery (the established harness pattern, see
tests/e2e/test_cloaking_intel.py) at a searched point 45 ly from the
enemy homeworld and clear of every other star. Three phases:

- detection: a parked scout detects the enemy starbase 45 ly away in
  clear space, but not from the core of the storm, where its 66 ly
  scanner is dampened to 66 * (1 - 0.7) < 45 ly;
- slow edge crossing: a scout entering just inside the blob boundary
  at warp 5 (below STORM_SAFE_WARP) takes only light locally-scaled
  hull damage and never a warp mishap;
- warp mishap: a scout crossing to the storm core at warp 9 suffers a
  mishap within the attempt budget (chance 0.10 * 3 * local), taking
  (20 + 25) * local damage and stopping dead (warp 0) inside the
  storm, with a Storm message.

Every roll rides the per-turn seeded RNG, so the recorded outcome is
reproducible for the fixed seed.
"""

import math
import random

import pytest

from backend.services.galaxy_generator import UNIVERSE_SIZES

SEED = 20260713
MISHAP_ATTEMPTS = 30

RACE = {
    "name": "Stormriders",
    "pluralName": "Stormriders",
    "prt": "JOAT",
}


def _manager():
    from backend.services.game_manager import get_game_manager
    return get_game_manager()


def _load(harness):
    return _manager()._load_game_state(harness.game_id)


def _save(harness, server_data):
    _manager()._save_game_state(harness.game_id, server_data)


def _enemy_starbase(server_data):
    return next(f for f in server_data.all_empires[2].owned_fleets.values()
                if f.is_starbase)


def _find_storm_center(server_data, size="small"):
    """Point 45 ly from the enemy homeworld with the most clearance
    from every other star, in-bounds with room for the warp-9 approach
    run from the -x side. Board bounds come from the generator's
    canonical size table."""
    width, height = UNIVERSE_SIZES[size]
    base = _enemy_starbase(server_data)
    others = [s for s in server_data.all_stars.values()
              if math.hypot(s.position.x - base.position.x,
                            s.position.y - base.position.y) > 1]
    best = None
    for step in range(72):
        angle = math.radians(step * 5)
        cx = base.position.x + math.cos(angle) * 45
        cy = base.position.y + math.sin(angle) * 45
        if not (86 <= cx <= width - 5 and 5 <= cy <= height - 5):
            continue
        clearance = min(math.hypot(cx - s.position.x, cy - s.position.y)
                        for s in others)
        if best is None or clearance > best[0]:
            best = (clearance, cx, cy)
    assert best is not None, "no in-bounds storm placement for this seed"
    return best[1], best[2]


def _place_storm(harness, cx, cy):
    """Replace all storms with one stationary intensity-1.0 blob.
    Base radius 32 keeps the whole blob (at most 32 * 1.35 = 43.2 ly)
    short of the enemy starbase 45 ly away."""
    from backend.server.server_data import GalacticStorm

    server_data = _load(harness)
    storm = GalacticStorm(key=1, x=cx, y=cy, radius=32,
                          velocity_x=0, velocity_y=0, intensity=1.0)
    storm.generate_shape(random.Random(4242))
    server_data.all_storms = {1: storm}
    _save(harness, server_data)
    return storm


def _clear_storms(harness):
    server_data = _load(harness)
    server_data.all_storms = {}
    _save(harness, server_data)


def _reset_fleet(harness, fleet_key, x, y):
    """Park a player 1 fleet at (x, y) undamaged with full tanks."""
    from backend.core.data_structures import NovaPoint

    server_data = _load(harness)
    fleet = server_data.all_empires[1].owned_fleets[fleet_key]
    fleet.position = NovaPoint(x, y)
    fleet.waypoints = []
    fleet.in_orbit_name = None
    fleet.in_orbit = None
    fleet.fuel_available = 100000
    for token in fleet.tokens.values():
        token.damage_percent = 0
    _save(harness, server_data)


def _fleet_ground_truth(harness, fleet_key):
    server_data = _load(harness)
    return server_data, server_data.all_empires[1].owned_fleets[fleet_key]


def _send_to(harness, fleet_key, x, y, warp):
    harness.submit(1, "waypoint", {
        "mode": "Add",
        "fleet_key": fleet_key,
        "index": 0,
        "waypoint": {
            "position_x": x,
            "position_y": y,
            "warp_factor": warp,
            "destination": "storm run",
            "task": {"type": "NoTask"},
        },
    })


def _storm_messages(state, name):
    return [m for m in state["messages"]
            if m.get("type") == "Storm" and name in m.get("text", "")]


class TestStormHazardsE2E:

    def test_storm_mishap_edge_damage_and_scan_dampening(self, harness):
        harness.create_game(seed=SEED, size="small", players=2, race=RACE)

        server_data = _load(harness)
        starbase = _enemy_starbase(server_data)
        base_pos = (starbase.position.x, starbase.position.y)
        cx, cy = _find_storm_center(server_data)

        scouts = [f for f in harness.my_fleets(1)
                  if f["name"].startswith("Long Range Scout")]
        assert len(scouts) >= 2  # JOAT starts with two
        scan_scout, edge_scout = scouts[0]["key"], scouts[1]["key"]

        # -- Phase 1a: detection control, no storm ---------------------
        # A parked scout 45 ly from the enemy starbase sees it with its
        # 66 ly scanner in clear space
        _clear_storms(harness)
        _reset_fleet(harness, scan_scout, cx, cy)
        harness.generate_turn()
        state = harness.state(1)
        assert starbase.key in [f["key"] for f in state["foreign_fleets"]], \
            "control: enemy starbase not detected in clear space"

        # -- Phase 1b: scan range provably reduced inside the storm ----
        # The same scout now sits at the core of an intensity-1.0 storm:
        # scan range drops to 66 * (1 - 0.7) = 19 ly < 45 ly
        storm = _place_storm(harness, cx, cy)
        assert storm.get_intensity_at(cx, cy) == 1.0
        assert storm.get_intensity_at(*base_pos) == 0.0  # target outside
        harness.generate_turn()
        state = harness.state(1)
        assert starbase.key not in [f["key"]
                                    for f in state["foreign_fleets"]], \
            "enemy starbase still detected from inside the storm"

        # Park the scan scout far from the storm so it stops taking
        # damage while the other phases run
        _reset_fleet(harness, scan_scout, 5, 5)

        # -- Phase 2: slow crossing near the edge, light damage --------
        # Enter just inside the blob boundary at warp 5 (below the safe
        # warp): only the small local intensity applies and there is no
        # mishap risk
        boundary = storm.boundary_radius(math.pi)  # bearing core -> -x
        end_x = cx - boundary * 0.94
        _reset_fleet(harness, edge_scout, end_x - 12, cy)
        _send_to(harness, edge_scout, end_x, cy, warp=5)
        harness.generate_turn()

        server_data, fleet = _fleet_ground_truth(harness, edge_scout)
        local = server_data.all_storms[1].get_intensity_at(
            fleet.position.x, fleet.position.y)
        assert 0.0 < local < 0.25, "edge scout did not stop near the edge"
        damage = fleet.tokens[next(iter(fleet.tokens))].damage_percent
        assert damage == pytest.approx(20 * local)
        assert damage < 5.0, "edge crossing should only scratch the hull"
        state = harness.state(1)
        edge_name = fleet.name
        assert _storm_messages(state, edge_name), "no Storm message"
        assert not any("warp mishap" in m["text"]
                       for m in _storm_messages(state, edge_name))

        # -- Phase 3: high-warp crossing suffers a mishap and stops ----
        # Warp 9 to the core: mishap chance 0.10 * (9 - 6) * local per
        # turn on the seeded RNG; the attempt loop is deterministic for
        # the fixed seed
        server_data, fleet = _fleet_ground_truth(harness, scan_scout)
        runner_name = fleet.name
        mishap_state = None
        for _ in range(MISHAP_ATTEMPTS):
            _reset_fleet(harness, scan_scout, cx - 81, cy)
            _send_to(harness, scan_scout, cx, cy, warp=9)
            harness.generate_turn()
            state = harness.state(1)
            if any("warp mishap" in m["text"]
                   for m in _storm_messages(state, runner_name)):
                mishap_state = state
                break
        assert mishap_state is not None, \
            f"no mishap within {MISHAP_ATTEMPTS} warp-9 crossings"

        server_data, fleet = _fleet_ground_truth(harness, scan_scout)
        local = server_data.all_storms[1].get_intensity_at(
            fleet.position.x, fleet.position.y)
        assert local > 0.0, "mishap fleet is not inside the storm"
        # Stopped dead: warp 0, waypoint preserved
        assert fleet.waypoints, "mishap cleared the waypoint"
        assert fleet.waypoints[0].warp_factor == 0
        # Storm damage plus mishap damage, both locally scaled
        damage = fleet.tokens[next(iter(fleet.tokens))].damage_percent
        assert damage == pytest.approx((20 + 25) * local)


def _set_protection(harness, fleet_key, shields=0, armor_comp=False,
                    storm_shield=0.0):
    """State surgery: set a fleet's storm protection sources on every
    token (shields grant 0.35, armor components 0.15, storm shields
    their tier value; fleet protection is the token minimum)."""
    server_data = _load(harness)
    fleet = server_data.all_empires[1].owned_fleets[fleet_key]
    for token in fleet.tokens.values():
        token.shields = shields
        token.has_armor_components = armor_comp
        token.storm_shield = storm_shield
    _save(harness, server_data)


class TestStormProtectionE2E:
    """Storm protection (user directive, wave 4): three fleets cross
    the same storm - the unprotected one takes full locally-scaled
    damage, the shielded+armored one takes half, the Storm Bulwark
    fleet takes zero - while a fourth fleet parked in orbit inside the
    storm footprint is untouched (orbit safe harbor)."""

    def test_protection_tiers_and_orbit_safe_harbor(self, harness):
        harness.create_game(seed=SEED, size="small", players=2, race=RACE)

        # The storm sits centered ON the player's homeworld, so the
        # blob footprint covers the star and its orbit
        server_data = _load(harness)
        home = next(s for s in server_data.all_stars.values()
                    if s.owner == 1)
        cx, cy = home.position.x, home.position.y
        storm = _place_storm(harness, cx, cy)
        assert storm.contains(cx, cy)

        movers = [f for f in harness.my_fleets(1)
                  if not f.get("is_starbase")]
        assert len(movers) >= 4, "need four non-starbase fleets"
        naked, halved, bulwark, orbiter = [f["key"] for f in movers[:4]]

        # Three fleets fly the identical leg into the storm at warp 5
        # (below the safe warp - no mishap randomness); the fourth
        # parks in orbit of the star at the storm's core with
        # colonists aboard
        for key, kwargs in [
                (naked, {}),
                (halved, {"shields": 40, "armor_comp": True}),
                (bulwark, {"storm_shield": 1.0})]:
            _reset_fleet(harness, key, cx - 30, cy)
            _set_protection(harness, key, **kwargs)
            _send_to(harness, key, cx, cy, warp=5)
        _reset_fleet(harness, orbiter, cx, cy)
        _set_protection(harness, orbiter)
        server_data = _load(harness)
        server_data.all_empires[1].owned_fleets[orbiter] \
            .cargo.colonists_in_kilotons = 100
        _save(harness, server_data)

        # The fleet API exposes the fleet-min protection (wave 4)
        by_key = {f["key"]: f for f in harness.my_fleets(1)}
        assert by_key[naked]["storm_protection"] == pytest.approx(0.0)
        assert by_key[halved]["storm_protection"] == pytest.approx(0.5)
        assert by_key[bulwark]["storm_protection"] == pytest.approx(1.0)

        harness.generate_turn()

        # All three movers end at the same spot inside the blob
        server_data = _load(harness)
        fleets = server_data.all_empires[1].owned_fleets
        positions = {(fleets[k].position.x, fleets[k].position.y)
                     for k in (naked, halved, bulwark)}
        assert len(positions) == 1, "movers diverged"
        local = server_data.all_storms[1].get_intensity_at(*positions.pop())
        assert local > 0.0, "movers did not end inside the storm"

        def damage(key):
            fleet = fleets[key]
            return fleet.tokens[next(iter(fleet.tokens))].damage_percent

        # Unprotected takes the full locally-scaled hit, the
        # shielded+armored fleet exactly half, the Bulwark fleet zero
        assert damage(naked) == pytest.approx(20 * local)
        assert damage(halved) == pytest.approx(20 * local * 0.5)
        assert damage(bulwark) == 0.0

        # Orbit safe harbor: parked at the star under the storm core -
        # no damage, no colonist attrition
        assert damage(orbiter) == 0.0
        assert fleets[orbiter].cargo.colonists_in_kilotons == 100

        # Storm messages name the two damaged fleets only
        state = harness.state(1)
        assert _storm_messages(state, fleets[naked].name)
        assert _storm_messages(state, fleets[halved].name)
        assert not _storm_messages(state, fleets[bulwark].name)
        assert not _storm_messages(state, fleets[orbiter].name)
