"""
Seeded e2e: stargate rework and emission nebula glare (user
directives 2026-07-13).

Stargate phase (state surgery per the established harness pattern,
see tests/e2e/test_storms.py): the player homeworld starbase and a
second player-owned star both get stargates on class-B stars (range
factor 1.6). A starting Long Range Scout (small hull) ordered at warp
10 jumps the full distance in one turn with no fuel spent; the same
order on a Battleship-hull fleet is refused outright with a message,
and a fleet loaded with ironium is refused with the no-minerals
message.

Glare phase: a scout parked 60 ly from the enemy starbase detects it
with its 66 ly scanner in clear space, but not from inside a dense
emission nebula, where glare dampens the range to about
66 * (1 - 0.15 * ~0.92) = 56 ly < 60 ly. Emission glow never slows
ships, so the jump/refusal phase is unaffected by the nebula.
"""

import math

SEED = 20260714

RACE = {
    "name": "Gatekeepers",
    "pluralName": "Gatekeepers",
    "prt": "JOAT",
}


def _manager():
    from backend.services.game_manager import get_game_manager
    return get_game_manager()


def _load(harness):
    return _manager()._load_game_state(harness.game_id)


def _save(harness, server_data):
    _manager()._save_game_state(harness.game_id, server_data)


def _clear_phenomena(harness):
    from backend.server.server_data import NebulaField

    server_data = _load(harness)
    server_data.all_storms = {}
    server_data.nebula_field = NebulaField(regions=[])
    _save(harness, server_data)


def _homeworld(server_data, empire_id=1):
    return next(s for s in server_data.all_stars.values()
                if s.owner == empire_id)


def _enemy_starbase(server_data):
    return next(f for f in server_data.all_empires[2].owned_fleets.values()
                if f.is_starbase)


def _add_gate(fleet, gate_mass=300, gate_range=600):
    for token in fleet.tokens.values():
        token.has_gate = True
        token.gate_mass = gate_mass
        token.gate_range = gate_range


def _gate_pair(harness):
    """Gate the homeworld starbase and a second star 85-300 ly away,
    both on class-B stars. Returns (origin_name, dest_name)."""
    from backend.core.data_structures import NovaPoint
    from backend.core.game_objects.fleet import Fleet, ShipToken

    server_data = _load(harness)
    empire = server_data.all_empires[1]
    home = _homeworld(server_data)
    home.spectral_class = "B"

    base = next(f for f in empire.owned_fleets.values() if f.is_starbase)
    _add_gate(base)

    dest = min(
        (s for s in server_data.all_stars.values()
         if s.owner == 0 and 85 < math.hypot(
             s.position.x - home.position.x,
             s.position.y - home.position.y) < 300),
        key=lambda s: math.hypot(s.position.x - home.position.x,
                                 s.position.y - home.position.y))
    dest.owner = 1
    dest.colonists = 10000
    dest.spectral_class = "B"
    empire.owned_stars[dest.name] = dest

    far_base = Fleet(name=f"{dest.name} Base", position=NovaPoint(
        dest.position.x, dest.position.y))
    far_base.key = (1 << 32) | 900
    far_base.owner = 1
    far_base.in_orbit_name = dest.name
    far_base.in_orbit = dest
    token = ShipToken(design_key=990, design_name="Gate Base",
                      quantity=1, mass=0, armor=500, is_starbase=True)
    far_base.tokens[990] = token
    _add_gate(far_base)
    empire.owned_fleets[far_base.key] = far_base

    _save(harness, server_data)
    return home.name, dest.name


def _park_fleet(harness, fleet_key, star_name):
    """Park a player-1 fleet in orbit of a star with clean waypoints."""
    from backend.core.data_structures import NovaPoint

    server_data = _load(harness)
    fleet = server_data.all_empires[1].owned_fleets[fleet_key]
    star = server_data.all_stars[star_name]
    fleet.position = NovaPoint(star.position.x, star.position.y)
    fleet.waypoints = []
    fleet.in_orbit_name = star_name
    fleet.in_orbit = star
    fleet.fuel_available = 5000
    _save(harness, server_data)


def _make_battleship(harness, star_name):
    """Battleship-hull fleet parked at a star, by state surgery."""
    from backend.core.data_structures import NovaPoint
    from backend.core.game_objects.fleet import Fleet, ShipToken

    server_data = _load(harness)
    empire = server_data.all_empires[1]
    star = server_data.all_stars[star_name]
    fleet = Fleet(name="Heavy Squadron #901", position=NovaPoint(
        star.position.x, star.position.y))
    fleet.key = (1 << 32) | 901
    fleet.owner = 1
    fleet.in_orbit_name = star_name
    fleet.in_orbit = star
    fleet.fuel_available = 5000
    fleet.tokens[991] = ShipToken(
        design_key=991, design_name="Heavy", hull_name="Battleship",
        quantity=1, mass=222, armor=2000, fuel_capacity=2800)
    empire.owned_fleets[fleet.key] = fleet
    _save(harness, server_data)
    return fleet.key


def _order_jump(harness, fleet_key, star_name, x, y):
    harness.submit(1, "waypoint", {
        "mode": "Add",
        "fleet_key": fleet_key,
        "index": 0,
        "waypoint": {
            "position_x": x,
            "position_y": y,
            "warp_factor": 10,
            "destination": star_name,
            "task": {"type": "NoTask"},
        },
    })


def _fleet(harness, fleet_key):
    server_data = _load(harness)
    return server_data.all_empires[1].owned_fleets.get(fleet_key)


class TestStargateReworkE2E:

    def test_small_hull_gates_battleship_and_minerals_refused(
            self, harness):
        harness.create_game(seed=SEED, size="small", players=2, race=RACE)
        _clear_phenomena(harness)
        origin_name, dest_name = _gate_pair(harness)

        server_data = _load(harness)
        dest = server_data.all_stars[dest_name]
        dx, dy = dest.position.x, dest.position.y
        home = server_data.all_stars[origin_name]
        distance = math.hypot(dx - home.position.x, dy - home.position.y)
        assert 85 < distance < 300
        # Class-B stars: 600 ly gates throw 600 * 1.6 = 960 ly - safe
        assert distance < 960

        scouts = [f for f in harness.my_fleets(1)
                  if f["name"].startswith("Long Range Scout")]
        assert len(scouts) >= 2  # JOAT starts with two
        gate_scout, cargo_scout = scouts[0]["key"], scouts[1]["key"]

        # -- Small hull: jumps the full distance in one turn ----------
        _park_fleet(harness, gate_scout, origin_name)
        fuel_before = _fleet(harness, gate_scout).fuel_available
        _order_jump(harness, gate_scout, dest_name, dx, dy)

        # -- Battleship hull: refused outright ------------------------
        battleship = _make_battleship(harness, origin_name)
        _order_jump(harness, battleship, dest_name, dx, dy)

        harness.generate_turn()

        scout = _fleet(harness, gate_scout)
        assert scout.position.x == dx and scout.position.y == dy, \
            "small hull did not gate the full distance in one turn"
        assert scout.fuel_available == fuel_before, "gate jump burned fuel"

        heavy = _fleet(harness, battleship)
        gone = math.hypot(heavy.position.x - dx, heavy.position.y - dy)
        assert gone > 1, "battleship should not have arrived"

        state = harness.state(1)
        refusals = [m for m in state["messages"]
                    if m.get("type") == "Invalid Command"
                    and "too large" in m.get("text", "")]
        assert refusals, "no hull-size refusal message"
        assert any(m.message_type == "Stargate"
                   for m in _load(harness).all_messages
                   ), "no stargate jump message"

        # -- Mineral cargo: refused with the no-minerals message ------
        _park_fleet(harness, cargo_scout, origin_name)
        server_data = _load(harness)
        server_data.all_empires[1].owned_fleets[
            cargo_scout].cargo.ironium = 10
        _save(harness, server_data)
        _order_jump(harness, cargo_scout, dest_name, dx, dy)
        harness.generate_turn()

        loaded = _fleet(harness, cargo_scout)
        at_dest = math.hypot(loaded.position.x - dx, loaded.position.y - dy)
        assert at_dest > 1, "mineral-laden fleet should not have gated"
        state = harness.state(1)
        assert any(m.get("type") == "Invalid Command"
                   and "mineral cargo" in m.get("text", "")
                   for m in state["messages"]), "no mineral refusal message"

    def test_scout_scans_shorter_inside_emission_nebula(self, harness):
        from backend.server.server_data import NebulaField, NebulaRegion

        harness.create_game(seed=SEED, size="small", players=2, race=RACE)
        _clear_phenomena(harness)

        server_data = _load(harness)
        starbase = _enemy_starbase(server_data)
        bx, by = starbase.position.x, starbase.position.y
        # Park 60 ly from the enemy starbase, in-bounds
        angle = 0.0 if bx < 200 else math.pi
        sx = bx + math.cos(angle) * 60
        sy = by

        scout = [f for f in harness.my_fleets(1)
                 if f["name"].startswith("Long Range Scout")][0]["key"]

        # -- Control: detected at 60 ly with the 66 ly scanner --------
        _park_fleet_at(harness, scout, sx, sy)
        harness.generate_turn()
        state = harness.state(1)
        assert starbase.key in [f["key"] for f in state["foreign_fleets"]], \
            "control: enemy starbase not detected in clear space"

        # -- Dense emission glow at the scout: 66 -> ~56 ly < 60 ------
        server_data = _load(harness)
        server_data.nebula_field = NebulaField(regions=[
            NebulaRegion(x=sx, y=sy, radius_x=50, radius_y=50,
                         density=1.0, nebula_type='emission'),
        ])
        glare = server_data.nebula_field.get_emission_density_at(sx, sy)
        assert glare > 0.6, "emission density too low at the scout"
        assert server_data.nebula_field.get_dust_density_at(sx, sy) == 0.0
        _save(harness, server_data)

        harness.generate_turn()
        state = harness.state(1)
        assert starbase.key not in [f["key"]
                                    for f in state["foreign_fleets"]], \
            "enemy starbase still detected from inside the emission glow"


def _park_fleet_at(harness, fleet_key, x, y):
    from backend.core.data_structures import NovaPoint

    server_data = _load(harness)
    fleet = server_data.all_empires[1].owned_fleets[fleet_key]
    fleet.position = NovaPoint(x, y)
    fleet.waypoints = []
    fleet.in_orbit_name = None
    fleet.in_orbit = None
    fleet.fuel_available = 5000
    _save(harness, server_data)
