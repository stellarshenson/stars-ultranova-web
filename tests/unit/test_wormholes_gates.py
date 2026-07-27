"""
Tests for wormhole transit/drift/discovery and stargate travel.
"""

import pytest

from backend.server.server_data import ServerData, Wormhole
from backend.server.turn_generator import TurnGenerator
from backend.core.data_structures import EmpireData, NovaPoint
from backend.core.game_objects.fleet import Fleet, ShipToken
from backend.core.game_objects.star import Star
from backend.core.waypoints.waypoint import Waypoint, NoTaskObj

from tests.unit.test_phenomena import make_fleet, make_state


class TestWormholes:

    def _wormhole(self):
        return Wormhole(key=1, name="Wormhole Alpha",
                        x1=100, y1=100, x2=500, y2=500, stability=0.8)

    def test_transit_moves_fleet_to_other_end(self):
        fleet = make_fleet(1, 1, 100, 100)
        fleet.waypoints.append(Waypoint(
            position_x=100, position_y=100, warp_factor=0,
            destination="Wormhole Alpha (A)", task=NoTaskObj()))
        state = make_state(fleet)
        state.all_wormholes[1] = self._wormhole()
        gen = TurnGenerator(state)
        gen._check_wormhole_transit(fleet)
        assert fleet.position.x == 500 and fleet.position.y == 500
        assert any(m.message_type == "Wormhole"
                   for m in state.all_messages)

    def test_no_transit_without_wormhole_destination(self):
        fleet = make_fleet(1, 1, 100, 100)
        fleet.waypoints.append(Waypoint(
            position_x=100, position_y=100, warp_factor=0,
            destination="Some Star", task=NoTaskObj()))
        state = make_state(fleet)
        state.all_wormholes[1] = self._wormhole()
        gen = TurnGenerator(state)
        gen._check_wormhole_transit(fleet)
        assert fleet.position.x == 100

    def test_drift_stays_in_bounds(self):
        w = self._wormhole()
        for _ in range(50):
            w.drift(__import__('random').Random(1), 600, 600)
        assert 0 <= w.x1 <= 600 and 0 <= w.y2 <= 600

    def test_discovery_within_scan_range(self):
        fleet = make_fleet(1, 1, 120, 100)
        fleet.tokens[1].scan_range_normal = 60
        state = make_state(fleet)
        state.all_wormholes[1] = self._wormhole()
        gen = TurnGenerator(state)
        gen._update_wormhole_visibility()
        assert 1 in state.all_empires[1].known_wormholes

    def test_no_discovery_out_of_range(self):
        fleet = make_fleet(1, 1, 300, 300)
        fleet.tokens[1].scan_range_normal = 30
        state = make_state(fleet)
        state.all_wormholes[1] = self._wormhole()
        gen = TurnGenerator(state)
        gen._update_wormhole_visibility()
        assert 1 not in state.all_empires[1].known_wormholes

    def test_wormhole_persistence(self):
        state = ServerData()
        state.all_wormholes[1] = self._wormhole()
        restored = ServerData.from_dict(state.to_dict())
        w = restored.all_wormholes[1]
        assert w.name == "Wormhole Alpha" and w.x2 == 500


def _gated_star(state, empire, name, x, y, gate_mass=300, gate_range=600):
    """Create an owned star with a gated starbase."""
    star = Star(name=name, position=NovaPoint(x, y))
    star.owner = empire.id
    state.all_stars[name] = star
    empire.owned_stars[name] = star

    base = Fleet(name=f"{name} Base", position=NovaPoint(x, y))
    base.key = (empire.id << 32) | (900 + len(empire.owned_fleets))
    base.in_orbit_name = name
    base.in_orbit = star
    token = ShipToken(design_key=99, design_name="Starbase", quantity=1,
                      mass=0, armor=500, is_starbase=True)
    token.has_gate = True
    token.gate_mass = gate_mass
    token.gate_range = gate_range
    base.tokens[99] = token
    empire.owned_fleets[base.key] = base
    return star


class TestStargates:

    def _setup(self, gate_mass=300, gate_range=600, ship_mass=10,
               distance=200):
        fleet = make_fleet(1, 1, 100, 100)
        fleet.tokens[1].mass = ship_mass
        state = make_state(fleet)
        empire = state.all_empires[1]
        origin = _gated_star(state, empire, "Home", 100, 100,
                             gate_mass, gate_range)
        dest = _gated_star(state, empire, "Colony", 100 + distance, 100,
                           gate_mass, gate_range)
        fleet.in_orbit = origin
        fleet.in_orbit_name = "Home"
        wp = Waypoint(position_x=dest.position.x, position_y=dest.position.y,
                      warp_factor=10, destination="Colony", task=NoTaskObj())
        fleet.waypoints.append(wp)
        gen = TurnGenerator(state)
        gen.rand.seed(7)
        return fleet, wp, state, empire, gen

    def test_safe_gate_jump(self):
        fleet, wp, state, empire, gen = self._setup()
        handled = gen._gate_travel(fleet, wp, empire)
        assert handled
        assert fleet.position.x == 300 and fleet.position.y == 100
        assert fleet.tokens[1].quantity == 1
        assert fleet.tokens[1].damage_percent == 0
        assert any(m.message_type == "Stargate" for m in state.all_messages)

    def test_gate_jump_no_fuel_used(self):
        fleet, wp, state, empire, gen = self._setup()
        fuel_before = fleet.fuel_available
        gen._gate_travel(fleet, wp, empire)
        assert fleet.fuel_available == fuel_before

    def test_over_range_damages_ships(self):
        fleet, wp, state, empire, gen = self._setup(
            gate_range=100, distance=400)
        gen._gate_travel(fleet, wp, empire)
        # Either lost or damaged, never unscathed
        token = fleet.tokens.get(1)
        assert token is None or token.damage_percent >= 50

    def test_no_gate_at_destination_blocks_jump(self):
        fleet, wp, state, empire, gen = self._setup()
        # Strip the destination starbase's gate
        for f in empire.owned_fleets.values():
            if f.name == "Colony Base":
                f.tokens[99].has_gate = False
        handled = gen._gate_travel(fleet, wp, empire)
        assert not handled
        assert fleet.position.x == 100  # did not move
        assert wp.warp_factor == 9  # clamped to normal max


class TestStargateHullLimit:
    """Only small and medium hulls may gate (user directive
    2026-07-13); large and capital hulls are refused outright."""

    def _setup(self, hull_name):
        fleet = make_fleet(1, 1, 100, 100)
        fleet.tokens[1].hull_name = hull_name
        state = make_state(fleet)
        empire = state.all_empires[1]
        origin = _gated_star(state, empire, "Home", 100, 100)
        dest = _gated_star(state, empire, "Colony", 300, 100)
        fleet.in_orbit = origin
        fleet.in_orbit_name = "Home"
        wp = Waypoint(position_x=dest.position.x, position_y=dest.position.y,
                      warp_factor=10, destination="Colony", task=NoTaskObj())
        fleet.waypoints.append(wp)
        gen = TurnGenerator(state)
        gen.rand.seed(7)
        return fleet, wp, state, empire, gen

    @pytest.mark.parametrize("hull", ["Battleship", "Dreadnought",
                                      "Battle Cruiser", "Large Freighter"])
    def test_large_and_capital_hulls_refused_outright(self, hull):
        fleet, wp, state, empire, gen = self._setup(hull)
        handled = gen._gate_travel(fleet, wp, empire)
        assert not handled
        assert fleet.position.x == 100  # did not move
        # Refused, not gambled: no losses, no damage
        assert fleet.tokens[1].quantity == 1
        assert fleet.tokens[1].damage_percent == 0
        assert wp.warp_factor == 9
        assert any(m.message_type == "Invalid Command" and
                   "too large" in m.text for m in state.all_messages)

    @pytest.mark.parametrize("hull", ["Scout", "Frigate", "Destroyer",
                                      "Cruiser", "Medium Freighter"])
    def test_small_and_medium_hulls_gate(self, hull):
        fleet, wp, state, empire, gen = self._setup(hull)
        handled = gen._gate_travel(fleet, wp, empire)
        assert handled
        assert fleet.position.x == 300

    def test_unknown_hull_refused(self):
        fleet, wp, state, empire, gen = self._setup("Mystery Hull")
        handled = gen._gate_travel(fleet, wp, empire)
        assert not handled
        assert fleet.position.x == 100


class TestStargateStarFuelledRange:
    """Gate range scales with the host star's spectral class, and no
    gate is unlimited (user directive 2026-07-13)."""

    def _gate_at(self, spectral, gate_range):
        fleet = make_fleet(1, 1, 100, 100)
        state = make_state(fleet)
        empire = state.all_empires[1]
        star = _gated_star(state, empire, "Home", 100, 100,
                           gate_range=gate_range)
        star.spectral_class = spectral
        gen = TurnGenerator(state)
        return gen._star_gate(star)

    @pytest.mark.parametrize("spectral,factor", [
        ("O", 2.0), ("B", 1.6), ("A", 1.3), ("F", 1.1),
        ("G", 1.0), ("K", 0.8), ("M", 0.6),
    ])
    def test_spectral_class_scales_range(self, spectral, factor):
        mass, eff_range = self._gate_at(spectral, 600)
        assert eff_range == pytest.approx(600 * factor)

    def test_any_range_gate_clamps_to_max(self):
        # SafeRange -1 ("any") clamps to GATE_MAX_BASE_RANGE before
        # the star factor - never unlimited
        from backend.core.globals import GATE_MAX_BASE_RANGE
        mass, eff_range = self._gate_at("G", -1)
        assert eff_range == pytest.approx(GATE_MAX_BASE_RANGE)
        mass, eff_range = self._gate_at("O", -1)
        assert eff_range == pytest.approx(GATE_MAX_BASE_RANGE * 2.0)

    def test_small_star_shrinks_jump_to_over_range_gamble(self):
        # 400 ly jump: safe through G-star 600 ly gates, over-range
        # through M-star gates (600 * 0.6 = 360 ly) - the canonical
        # 25% loss / 50% damage gamble applies to the allowed hull
        fleet = make_fleet(1, 1, 100, 100, quantity=8)
        state = make_state(fleet)
        empire = state.all_empires[1]
        origin = _gated_star(state, empire, "Home", 100, 100)
        dest = _gated_star(state, empire, "Colony", 500, 100)
        for star in (origin, dest):
            star.spectral_class = "M"
        fleet.in_orbit = origin
        fleet.in_orbit_name = "Home"
        wp = Waypoint(position_x=500, position_y=100, warp_factor=10,
                      destination="Colony", task=NoTaskObj())
        fleet.waypoints.append(wp)
        gen = TurnGenerator(state)
        gen.rand.seed(7)
        handled = gen._gate_travel(fleet, wp, empire)
        assert handled
        token = fleet.tokens.get(1)
        assert token is None or token.quantity < 8 or \
            token.damage_percent >= 50


class TestStargateCargoRules:
    """Minerals never gate (user directive 2026-07-13); colonists
    gate only for IT races (canonical); fuel always travels."""

    def _setup(self, prt=None):
        fleet = make_fleet(1, 1, 100, 100)
        state = make_state(fleet)
        empire = state.all_empires[1]
        if prt is not None:
            from backend.core.race.race import Race
            empire.race = Race(primary_trait=prt)
        origin = _gated_star(state, empire, "Home", 100, 100)
        dest = _gated_star(state, empire, "Colony", 300, 100)
        fleet.in_orbit = origin
        fleet.in_orbit_name = "Home"
        wp = Waypoint(position_x=dest.position.x, position_y=dest.position.y,
                      warp_factor=10, destination="Colony", task=NoTaskObj())
        fleet.waypoints.append(wp)
        gen = TurnGenerator(state)
        gen.rand.seed(7)
        return fleet, wp, state, empire, gen

    def test_mineral_cargo_refused(self):
        fleet, wp, state, empire, gen = self._setup()
        fleet.cargo.ironium = 10
        handled = gen._gate_travel(fleet, wp, empire)
        assert not handled
        assert fleet.position.x == 100
        assert any(m.message_type == "Invalid Command" and
                   "mineral cargo" in m.text for m in state.all_messages)

    def test_mineral_cargo_refused_even_for_it(self):
        fleet, wp, state, empire, gen = self._setup(prt="IT")
        fleet.cargo.germanium = 5
        handled = gen._gate_travel(fleet, wp, empire)
        assert not handled

    def test_colonists_refused_for_non_it(self):
        fleet, wp, state, empire, gen = self._setup(prt="JOAT")
        fleet.cargo.colonists_in_kilotons = 5
        handled = gen._gate_travel(fleet, wp, empire)
        assert not handled
        assert any("Interstellar Traveler" in m.text
                   for m in state.all_messages)

    def test_colonists_gate_for_it(self):
        fleet, wp, state, empire, gen = self._setup(prt="IT")
        fleet.cargo.colonists_in_kilotons = 5
        handled = gen._gate_travel(fleet, wp, empire)
        assert handled
        assert fleet.position.x == 300

    def test_fuel_gates_freely(self):
        fleet, wp, state, empire, gen = self._setup()
        fuel_before = fleet.fuel_available
        handled = gen._gate_travel(fleet, wp, empire)
        assert handled
        assert fleet.fuel_available == fuel_before
