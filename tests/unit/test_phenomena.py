"""
Tests for spatial phenomena and minefield strike mechanics:
- Dust nebulae slowing fleets and dampening scanners
- Galactic storms drifting and damaging fleets
- Minefield traversal hits (canonical constants from components.xml)
"""

import pytest

from backend.server.server_data import (
    ServerData, NebulaField, NebulaRegion, GalacticStorm, Minefield
)
from backend.server.turn_generator import TurnGenerator
from backend.core.data_structures import EmpireData, NovaPoint
from backend.core.game_objects.fleet import Fleet, ShipToken
from backend.core.waypoints.waypoint import Waypoint
from backend.core.globals import NOBODY


def make_fleet(key: int, owner: int, x: float, y: float,
               quantity: int = 1, armor: int = 100) -> Fleet:
    """Build a minimal real fleet with one token."""
    fleet = Fleet(name=f"Fleet #{key}", position=NovaPoint(x, y))
    fleet._key = (owner << 32) | key
    fleet.owner_int = owner
    fleet.owner = owner
    fleet.tokens[1] = ShipToken(
        design_key=1, design_name="Testship", quantity=quantity,
        mass=10, armor=armor, fuel_capacity=500,
    )
    fleet.fuel_available = 500
    return fleet


def make_state(*fleets: Fleet) -> ServerData:
    state = ServerData()
    for fleet in fleets:
        empire_id = fleet.owner
        if empire_id not in state.all_empires:
            empire = EmpireData()
            empire.id = empire_id
            state.all_empires[empire_id] = empire
        state.all_empires[empire_id].owned_fleets[fleet.key] = fleet
    return state


class TestNebulaDust:
    """Dust (dark) nebulae slow ships and dampen sensors."""

    def test_dust_grid_only_counts_dark_regions(self):
        field = NebulaField(regions=[
            NebulaRegion(x=100, y=100, radius_x=40, radius_y=40,
                         density=0.8, nebula_type='dark'),
            NebulaRegion(x=300, y=300, radius_x=40, radius_y=40,
                         density=0.8, nebula_type='emission'),
        ])
        assert field.get_dust_density_at(100, 100) > 0.5
        assert field.get_dust_density_at(300, 300) == 0.0
        assert field.get_density_at(300, 300) > 0.5

    def test_fleet_slowed_inside_dust_nebula(self):
        fleet = make_fleet(1, 1, 100, 100)
        fleet.waypoints.append(Waypoint(
            position_x=400, position_y=100, warp_factor=9,
            destination="Far Star"))
        state = make_state(fleet)
        state.nebula_field = NebulaField(regions=[
            NebulaRegion(x=140, y=100, radius_x=60, radius_y=60,
                         density=1.0, nebula_type='dark'),
        ])
        gen = TurnGenerator(state)
        gen._move_fleet(fleet, 1.0, None, [])
        travelled = fleet.position.x - 100
        # Warp 9 clear space covers 81 ly; dust must slow it
        assert travelled < 81
        # But never below the minimum speed factor
        assert travelled >= 81 * 0.6 - 1

    def test_fleet_full_speed_outside_dust(self):
        fleet = make_fleet(1, 1, 100, 100)
        fleet.waypoints.append(Waypoint(
            position_x=400, position_y=100, warp_factor=9,
            destination="Far Star"))
        state = make_state(fleet)
        state.nebula_field = NebulaField(regions=[])
        gen = TurnGenerator(state)
        gen._move_fleet(fleet, 1.0, None, [])
        assert fleet.position.x == pytest.approx(181, abs=0.1)

    def test_scan_range_reduced_in_dust(self):
        from backend.server.turn_steps.scan_step import ScanStep
        from backend.core.game_objects.star import Star

        scanner = make_fleet(1, 1, 100, 100)
        scanner.tokens[1].scan_range_normal = 100
        target = make_fleet(2, 2, 190, 100)
        state = make_state(scanner, target)
        # Dense dust at the scanner's position
        state.nebula_field = NebulaField(regions=[
            NebulaRegion(x=100, y=100, radius_x=50, radius_y=50,
                         density=1.0, nebula_type='dark'),
        ])
        ScanStep().process(state)
        # 90 ly away: seen with 100 ly clear-space range, but dust
        # cuts range roughly in half
        empire1 = state.all_empires[1]
        assert target.key not in empire1.fleet_reports

    def test_scan_range_normal_without_dust(self):
        from backend.server.turn_steps.scan_step import ScanStep

        scanner = make_fleet(1, 1, 100, 100)
        scanner.tokens[1].scan_range_normal = 100
        target = make_fleet(2, 2, 190, 100)
        state = make_state(scanner, target)
        state.nebula_field = NebulaField(regions=[])
        ScanStep().process(state)
        empire1 = state.all_empires[1]
        assert target.key in empire1.fleet_reports


class TestGalacticStorms:
    """Storms drift and damage fleets caught inside."""

    def test_storm_drifts_and_bounces(self):
        storm = GalacticStorm(key=1, x=595, y=300, radius=30,
                              velocity_x=10, velocity_y=0, intensity=0.5)
        storm.drift(600, 600)
        assert storm.x <= 600
        assert storm.velocity_x == -10  # bounced

    def test_storm_damages_fleet_inside(self):
        fleet = make_fleet(1, 1, 300, 300, quantity=2, armor=100)
        state = make_state(fleet)
        state.all_storms[1] = GalacticStorm(
            key=1, x=300, y=300, radius=50,
            velocity_x=0, velocity_y=0, intensity=1.0)
        gen = TurnGenerator(state)
        gen._process_storms()
        token = fleet.tokens[1]
        assert token.damage_percent > 0
        # Message generated for the owner
        assert any(m.message_type == "Storm" for m in state.all_messages)

    def test_storm_spares_fleet_outside(self):
        fleet = make_fleet(1, 1, 100, 100)
        state = make_state(fleet)
        state.all_storms[1] = GalacticStorm(
            key=1, x=400, y=400, radius=30,
            velocity_x=0, velocity_y=0, intensity=1.0)
        gen = TurnGenerator(state)
        gen._process_storms()
        assert fleet.tokens[1].damage_percent == 0

    def test_storm_destroys_heavily_damaged_ships(self):
        fleet = make_fleet(1, 1, 300, 300, quantity=3, armor=100)
        fleet.tokens[1].damage_percent = 95
        state = make_state(fleet)
        state.all_storms[1] = GalacticStorm(
            key=1, x=300, y=300, radius=50,
            velocity_x=0, velocity_y=0, intensity=1.0)
        gen = TurnGenerator(state)
        gen._process_storms()
        assert fleet.tokens[1].quantity == 2

    def test_storms_persist_through_serialization(self):
        state = ServerData()
        state.all_storms[1] = GalacticStorm(
            key=1, x=10, y=20, radius=35,
            velocity_x=3, velocity_y=-4, intensity=0.7)
        data = state.to_dict()
        restored = ServerData.from_dict(data)
        storm = restored.all_storms[1]
        assert storm.x == 10 and storm.y == 20
        assert storm.velocity_y == -4
        assert storm.intensity == 0.7


class TestMinefieldStrikes:
    """Minefield traversal mechanics per components.xml constants."""

    def _setup(self, warp: int, mine_type: int = 0):
        fleet = make_fleet(1, 1, 0, 100, quantity=5, armor=100)
        fleet.waypoints.append(Waypoint(
            position_x=200, position_y=100, warp_factor=warp,
            destination="Target"))
        state = make_state(fleet)
        state.all_minefields[1] = Minefield(
            key=1, owner=2, position_x=100, position_y=100,
            number_of_mines=2500, mine_type=mine_type)  # radius 50
        gen = TurnGenerator(state)
        gen.rand.seed(42)
        return fleet, state, gen

    def test_safe_speed_never_hits(self):
        fleet, state, gen = self._setup(warp=4)  # standard safe speed
        # Simulate the fleet having crossed the whole field
        fleet.position.x = 200
        gen._check_minefield(fleet, 0, 100)
        assert not any(m.message_type == "Minefield Hit"
                       for m in state.all_messages)

    def test_own_minefield_never_hits(self):
        fleet, state, gen = self._setup(warp=9)
        state.all_minefields[1].owner = 1  # own field
        fleet.position.x = 200
        gen._check_minefield(fleet, 0, 100)
        assert not any(m.message_type == "Minefield Hit"
                       for m in state.all_messages)

    def test_fast_crossing_hits_and_damages(self):
        fleet, state, gen = self._setup(warp=9)
        fleet.position.x = 200
        # Warp 9 through 100 ly of standard mines:
        # p = 0.003 * 5 * 100 = 1.0 - guaranteed hit
        gen._check_minefield(fleet, 0, 100)
        assert any(m.message_type == "Minefield Hit"
                   for m in state.all_messages)
        # Fleet stopped dead
        assert fleet.waypoints[0].warp_factor == 0
        # Damage applied: min fleet damage 500 over 5 ships = 100 each
        # = 100% of armor - all five ships destroyed
        assert 1 not in fleet.tokens or fleet.tokens[1].quantity < 5
        # Field lost detonated mines
        assert state.all_minefields[1].number_of_mines == 2490

    def test_speed_trap_stops_without_damage(self):
        fleet, state, gen = self._setup(warp=9, mine_type=2)
        fleet.position.x = 200
        gen._check_minefield(fleet, 0, 100)
        assert fleet.waypoints[0].warp_factor == 0
        assert fleet.tokens[1].quantity == 5
        assert fleet.tokens[1].damage_percent == 0

    def test_chord_length_geometry(self):
        gen = TurnGenerator(ServerData())
        # Straight through the center of a radius-50 circle
        assert gen._chord_length(0, 100, 200, 100, 100, 100, 50) == \
            pytest.approx(100)
        # Missing the circle entirely
        assert gen._chord_length(0, 0, 200, 0, 100, 100, 50) == 0.0
