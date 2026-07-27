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
        design_key=1, design_name="Testship", hull_name="Scout",
        quantity=quantity, mass=10, armor=armor, fuel_capacity=500,
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


class TestNebulaGlare:
    """Emission nebula glare dampens sensors (user directive
    2026-07-13): NEBULA_GLARE_SCAN_PENALTY (0.15) scaled by local
    emission density, composed with dust; no effect on speed."""

    def test_emission_grid_only_counts_emission_regions(self):
        field = NebulaField(regions=[
            NebulaRegion(x=100, y=100, radius_x=40, radius_y=40,
                         density=0.8, nebula_type='dark'),
            NebulaRegion(x=300, y=300, radius_x=40, radius_y=40,
                         density=0.8, nebula_type='emission'),
        ])
        assert field.get_emission_density_at(300, 300) > 0.5
        assert field.get_emission_density_at(100, 100) == 0.0

    def test_scan_range_reduced_by_glare(self):
        from backend.server.turn_steps.scan_step import ScanStep

        scanner = make_fleet(1, 1, 100, 100)
        scanner.tokens[1].scan_range_normal = 100
        target = make_fleet(2, 2, 190, 100)
        state = make_state(scanner, target)
        # Dense emission glow at the scanner's position: range drops
        # to at most 100 * (1 - 0.15) = 85 < 90 ly
        state.nebula_field = NebulaField(regions=[
            NebulaRegion(x=100, y=100, radius_x=50, radius_y=50,
                         density=1.0, nebula_type='emission'),
        ])
        ScanStep().process(state)
        assert target.key not in state.all_empires[1].fleet_reports

    def test_glare_composes_with_dust(self):
        from backend.server.turn_steps.scan_step import ScanStep

        # Target 48 ly away: survives the dust penalty alone
        # (dust ~0.92 -> range 53 >= 48) but not dust composed with
        # glare (53 * (1 - 0.15 * 0.92) -> 45 < 48)
        overlapping = [
            NebulaRegion(x=100, y=100, radius_x=50, radius_y=50,
                         density=1.0, nebula_type='dark'),
            NebulaRegion(x=100, y=100, radius_x=50, radius_y=50,
                         density=1.0, nebula_type='emission'),
        ]
        scanner = make_fleet(1, 1, 100, 100)
        scanner.tokens[1].scan_range_normal = 100
        target = make_fleet(2, 2, 148, 100)
        state = make_state(scanner, target)
        state.nebula_field = NebulaField(regions=overlapping[:1])
        ScanStep().process(state)
        assert target.key in state.all_empires[1].fleet_reports

        scanner = make_fleet(1, 1, 100, 100)
        scanner.tokens[1].scan_range_normal = 100
        target = make_fleet(2, 2, 148, 100)
        state = make_state(scanner, target)
        state.nebula_field = NebulaField(regions=overlapping)
        ScanStep().process(state)
        assert target.key not in state.all_empires[1].fleet_reports

    def test_no_speed_effect_in_emission_nebula(self):
        fleet = make_fleet(1, 1, 100, 100)
        fleet.waypoints.append(Waypoint(
            position_x=400, position_y=100, warp_factor=9,
            destination="Far Star"))
        state = make_state(fleet)
        state.nebula_field = NebulaField(regions=[
            NebulaRegion(x=140, y=100, radius_x=60, radius_y=60,
                         density=1.0, nebula_type='emission'),
        ])
        gen = TurnGenerator(state)
        gen._move_fleet(fleet, 1.0, None, [])
        # Warp 9 covers the full 81 ly - glow imposes no drag
        assert fleet.position.x == pytest.approx(181, abs=0.1)


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


class TestStormShape:
    """Irregular blob perimeter and local intensity field
    (user directive 2026-07-13)."""

    def _blob(self, intensity: float = 1.0, radius: float = 50.0,
              seed: int = 7) -> GalacticStorm:
        import random
        storm = GalacticStorm(key=1, x=300, y=300, radius=radius,
                              velocity_x=0, velocity_y=0,
                              intensity=intensity)
        storm.generate_shape(random.Random(seed))
        return storm

    def test_shape_deterministic_and_bounded(self):
        import random
        from backend.core.globals import (
            STORM_SHAPE_POINTS, STORM_SHAPE_AMPLITUDE)
        a = self._blob(seed=7)
        b = self._blob(seed=7)
        assert a.shape_radii == b.shape_radii
        assert len(a.shape_radii) == STORM_SHAPE_POINTS
        for r in a.shape_radii:
            assert 50.0 * (1 - STORM_SHAPE_AMPLITUDE) <= r
            assert r <= 50.0 * (1 + STORM_SHAPE_AMPLITUDE)
        # The blob is irregular, not a circle
        assert max(a.shape_radii) - min(a.shape_radii) > 1.0

    def test_contains_follows_blob_boundary(self):
        import math
        storm = self._blob()
        # Along each sampled bearing the boundary is exactly the
        # sampled radius: just inside is in, just outside is out
        for i, r in enumerate(storm.shape_radii):
            theta = 2 * math.pi * i / len(storm.shape_radii)
            inside = (storm.x + math.cos(theta) * (r - 0.5),
                      storm.y + math.sin(theta) * (r - 0.5))
            outside = (storm.x + math.cos(theta) * (r + 0.5),
                       storm.y + math.sin(theta) * (r + 0.5))
            assert storm.contains(*inside)
            assert not storm.contains(*outside)

    def test_intensity_ramp_profile(self):
        import math
        storm = self._blob(intensity=0.8)
        # Core carries the full storm intensity
        assert storm.get_intensity_at(300, 300) == pytest.approx(0.8)
        theta = 0.0
        boundary = storm.boundary_radius(theta)
        # Halfway out the smoothstep ramp gives exactly half intensity
        halfway = storm.get_intensity_at(300 + boundary * 0.5, 300)
        assert halfway == pytest.approx(0.4, abs=1e-9)
        # Near the boundary the intensity falls towards zero
        near_edge = storm.get_intensity_at(300 + boundary * 0.97, 300)
        assert 0 < near_edge < 0.01
        # On and beyond the boundary there is no storm effect
        assert storm.get_intensity_at(300 + boundary, 300) == 0.0
        assert storm.get_intensity_at(300 + boundary * 2, 300) == 0.0
        # The ramp decreases monotonically from core to boundary
        samples = [storm.get_intensity_at(300 + boundary * d / 10, 300)
                   for d in range(10)]
        assert samples == sorted(samples, reverse=True)

    def test_serialization_round_trip_with_shape(self):
        storm = self._blob(intensity=0.6)
        restored = GalacticStorm.from_dict(storm.to_dict())
        assert restored.shape_radii == storm.shape_radii
        assert restored.intensity == 0.6
        assert restored.radius == 50.0

    def test_legacy_load_regenerates_shape_deterministically(self):
        # Legacy save: no shape_radii field
        legacy = {'key': 3, 'x': 10, 'y': 20, 'radius': 40.0,
                  'velocity_x': 1, 'velocity_y': 2, 'intensity': 0.7}
        a = GalacticStorm.from_dict(dict(legacy))
        b = GalacticStorm.from_dict(dict(legacy))
        from backend.core.globals import STORM_SHAPE_POINTS
        assert len(a.shape_radii) == STORM_SHAPE_POINTS
        assert a.shape_radii == b.shape_radii
        assert a.x == 10 and a.intensity == 0.7


class TestStormHazards:
    """Locally-scaled storm damage, warp mishaps and colonist
    attrition (user directive 2026-07-13)."""

    def _storm_state(self, fleet, intensity: float = 1.0):
        state = make_state(fleet)
        state.all_storms[1] = GalacticStorm(
            key=1, x=300, y=300, radius=50,
            velocity_x=0, velocity_y=0, intensity=intensity)
        return state

    def test_damage_scales_with_local_intensity(self):
        from backend.core.globals import STORM_DAMAGE_PER_TURN
        core = make_fleet(1, 1, 300, 300, armor=100)
        # Halfway to the boundary: smoothstep gives local = 0.5
        edge = make_fleet(2, 1, 325, 300, armor=100)
        state = self._storm_state(core)
        state.all_empires[1].owned_fleets[edge.key] = edge
        TurnGenerator(state)._process_storms()
        assert core.tokens[1].damage_percent == \
            pytest.approx(STORM_DAMAGE_PER_TURN)
        assert edge.tokens[1].damage_percent == \
            pytest.approx(STORM_DAMAGE_PER_TURN * 0.5)

    def test_safe_warp_never_mishaps(self):
        for trial in range(50):
            fleet = make_fleet(1, 1, 300, 300, armor=1000)
            fleet.waypoints.append(Waypoint(
                position_x=300, position_y=300, warp_factor=6,
                destination="Core"))
            state = self._storm_state(fleet)
            gen = TurnGenerator(state)
            gen.rand.seed(trial)
            gen._process_storms()
            assert not any("warp mishap" in m.text
                           for m in state.all_messages)

    def test_mishap_odds_match_seeded_rng(self):
        from backend.core.globals import (
            STORM_DAMAGE_PER_TURN, STORM_MISHAP_DAMAGE)
        # Warp 9 at the core of an intensity-1.0 storm:
        # chance = 0.10 * (9 - 6) * 1.0 = 0.30
        hits = 0
        trials = 400
        mishap_damage_seen = None
        for trial in range(trials):
            fleet = make_fleet(1, 1, 300, 300, armor=1000)
            fleet.waypoints.append(Waypoint(
                position_x=300, position_y=300, warp_factor=9,
                destination="Core"))
            state = self._storm_state(fleet)
            gen = TurnGenerator(state)
            gen.rand.seed(trial)
            gen._process_storms()
            if any("warp mishap" in m.text for m in state.all_messages):
                hits += 1
                # Mishap stops the fleet and adds extra damage
                assert fleet.waypoints[0].warp_factor == 0
                mishap_damage_seen = fleet.tokens[1].damage_percent
        assert 0.24 <= hits / trials <= 0.36
        assert mishap_damage_seen == pytest.approx(
            STORM_DAMAGE_PER_TURN + STORM_MISHAP_DAMAGE)

    def test_mishap_chance_capped(self):
        # Warp 20 gives raw chance 0.10 * 14 = 1.4, capped at 0.75
        hits = 0
        trials = 400
        for trial in range(trials):
            fleet = make_fleet(1, 1, 300, 300, armor=1000)
            fleet.waypoints.append(Waypoint(
                position_x=300, position_y=300, warp_factor=20,
                destination="Core"))
            state = self._storm_state(fleet)
            gen = TurnGenerator(state)
            gen.rand.seed(trial)
            gen._process_storms()
            if any("warp mishap" in m.text for m in state.all_messages):
                hits += 1
        assert 0.69 <= hits / trials <= 0.81

    def test_colonist_attrition_scales_with_local_intensity(self):
        from backend.core.globals import COLONISTS_PER_KILOTON
        fleet = make_fleet(1, 1, 300, 300, armor=1000)
        fleet.cargo.colonists_in_kilotons = 100
        state = self._storm_state(fleet)
        TurnGenerator(state)._process_storms()
        # ceil(100 kT * 0.10 * 1.0) = 10 kT lost
        assert fleet.cargo.colonists_in_kilotons == 90
        assert any("colonists" in m.text and m.message_type == "Storm"
                   for m in state.all_messages)
        # Halfway out (local 0.5): ceil(100 * 0.10 * 0.5) = 5 kT
        fleet2 = make_fleet(2, 1, 325, 300, armor=1000)
        fleet2.cargo.colonists_in_kilotons = 100
        state2 = self._storm_state(fleet2)
        TurnGenerator(state2)._process_storms()
        assert fleet2.cargo.colonists_in_kilotons == 95

    def test_no_attrition_without_colonists(self):
        fleet = make_fleet(1, 1, 300, 300, armor=1000)
        state = self._storm_state(fleet)
        TurnGenerator(state)._process_storms()
        assert not any("colonists" in m.text
                       for m in state.all_messages)

    def test_scan_range_reduced_inside_storm(self):
        from backend.server.turn_steps.scan_step import ScanStep

        scanner = make_fleet(1, 1, 100, 100)
        scanner.tokens[1].scan_range_normal = 100
        target = make_fleet(2, 2, 160, 100)
        state = make_state(scanner, target)
        state.nebula_field = NebulaField(regions=[])
        # Without a storm the 60 ly target is seen
        ScanStep().process(state)
        assert target.key in state.all_empires[1].fleet_reports
        # Scanner at the core of an intensity-1.0 storm: range drops
        # to 100 * (1 - 0.7) = 30 ly and the target vanishes
        state.all_storms[1] = GalacticStorm(
            key=1, x=100, y=100, radius=40,
            velocity_x=0, velocity_y=0, intensity=1.0)
        ScanStep().process(state)
        assert target.key not in state.all_empires[1].fleet_reports


class TestStormProtection:
    """Storm protection model and effect scaling (user directive,
    wave 4): additive per-token sources clamped at 1.0, fleet-min,
    orbit safe harbor, and (1 - protection) scaling of every hazard."""

    def _storm_state(self, fleet, intensity: float = 1.0):
        state = make_state(fleet)
        state.all_storms[1] = GalacticStorm(
            key=1, x=300, y=300, radius=50,
            velocity_x=0, velocity_y=0, intensity=intensity)
        return state

    def _rad_race(self):
        from backend.core.race.race import Race
        race = Race()
        race.radiation_min = 70
        race.radiation_max = 100  # optimum 85 - extreme band
        return race

    def test_each_source_alone(self):
        from backend.core.globals import (
            STORM_SHIELD_PROTECTION, STORM_ARMOR_PROTECTION,
            STORM_RAD_RACE_PROTECTION)
        fleet = make_fleet(1, 1, 300, 300)
        token = fleet.tokens[1]
        assert fleet.storm_protection(None) == 0.0
        token.storm_shield = 0.4
        assert fleet.storm_protection(None) == pytest.approx(0.4)
        token.storm_shield = 0.0
        token.shields = 40
        assert fleet.storm_protection(None) == \
            pytest.approx(STORM_SHIELD_PROTECTION)
        token.shields = 0
        token.has_armor_components = True
        assert fleet.storm_protection(None) == \
            pytest.approx(STORM_ARMOR_PROTECTION)
        token.has_armor_components = False
        assert fleet.storm_protection(self._rad_race()) == \
            pytest.approx(STORM_RAD_RACE_PROTECTION)

    def test_stacking_clamps_at_full_immunity(self):
        # 0.70 + 0.35 + 0.15 + 0.25 = 1.45 -> clamped to 1.0
        fleet = make_fleet(1, 1, 300, 300)
        token = fleet.tokens[1]
        token.storm_shield = 0.7
        token.shields = 40
        token.has_armor_components = True
        assert fleet.storm_protection(self._rad_race()) == 1.0
        # Top-tier storm shield alone is total immunity
        token.shields = 0
        token.has_armor_components = False
        token.storm_shield = 1.0
        assert fleet.storm_protection(None) == 1.0

    def test_fleet_min_weakest_ship(self):
        # A convoy is only as protected as its weakest ship
        fleet = make_fleet(1, 1, 300, 300)
        fleet.tokens[1].storm_shield = 1.0
        fleet.tokens[2] = ShipToken(
            design_key=2, design_name="Naked", quantity=1, armor=100)
        assert fleet.storm_protection(None) == 0.0

    def test_rad_race_qualification(self):
        from backend.core.race.race import Race
        standard = Race()  # radiation 15-85, optimum 50
        assert not standard.is_radiation_hardened
        below_band = Race()
        below_band.radiation_min = 65
        below_band.radiation_max = 100  # optimum 82.5 - not extreme
        assert not below_band.is_radiation_hardened
        assert self._rad_race().is_radiation_hardened  # optimum 85
        immune = Race()
        immune.immune_radiation = True
        assert immune.is_radiation_hardened

    def test_orbit_safe_harbor_skips_all_effects(self):
        from backend.core.game_objects.star import Star

        # A fleet parked at a star inside the storm footprint is
        # sheltered by the planet's magnetosphere: no damage, no
        # attrition, no message
        fleet = make_fleet(1, 1, 300, 300, armor=100)
        fleet.cargo.colonists_in_kilotons = 100
        state = self._storm_state(fleet)
        star = Star(name="Harbor")
        star.position = NovaPoint(300, 300)
        state.all_stars["Harbor"] = star
        TurnGenerator(state)._process_storms()
        assert fleet.tokens[1].damage_percent == 0
        assert fleet.cargo.colonists_in_kilotons == 100
        assert not any(m.message_type == "Storm"
                       for m in state.all_messages)

    def test_damage_scaling_at_protection_levels(self):
        from backend.core.globals import STORM_DAMAGE_PER_TURN
        # protection 0.0 -> full local damage
        naked = make_fleet(1, 1, 300, 300, armor=100)
        state = self._storm_state(naked)
        TurnGenerator(state)._process_storms()
        assert naked.tokens[1].damage_percent == \
            pytest.approx(STORM_DAMAGE_PER_TURN)
        # protection 0.5 (shields 0.35 + armor 0.15) -> half damage
        half = make_fleet(1, 1, 300, 300, armor=100)
        half.tokens[1].shields = 40
        half.tokens[1].has_armor_components = True
        state = self._storm_state(half)
        TurnGenerator(state)._process_storms()
        assert half.tokens[1].damage_percent == \
            pytest.approx(STORM_DAMAGE_PER_TURN * 0.5)
        # protection 1.0 -> fully immune, not even a message
        immune = make_fleet(1, 1, 300, 300, armor=100)
        immune.tokens[1].storm_shield = 1.0
        state = self._storm_state(immune)
        TurnGenerator(state)._process_storms()
        assert immune.tokens[1].damage_percent == 0
        assert not any(m.message_type == "Storm"
                       for m in state.all_messages)

    def test_mishap_never_fires_at_full_protection(self):
        for trial in range(100):
            fleet = make_fleet(1, 1, 300, 300, armor=1000)
            fleet.tokens[1].storm_shield = 1.0
            fleet.waypoints.append(Waypoint(
                position_x=300, position_y=300, warp_factor=9,
                destination="Core"))
            state = self._storm_state(fleet)
            gen = TurnGenerator(state)
            gen.rand.seed(trial)
            gen._process_storms()
            assert not state.all_messages

    def test_mishap_chance_and_damage_scaled_by_protection(self):
        from backend.core.globals import (
            STORM_DAMAGE_PER_TURN, STORM_MISHAP_DAMAGE)
        # Warp 9 at the core with protection 0.5: chance
        # 0.10 * 3 * 1.0 * 0.5 = 0.15; both damage terms halve
        hits = 0
        trials = 400
        mishap_damage_seen = None
        for trial in range(trials):
            fleet = make_fleet(1, 1, 300, 300, armor=1000)
            fleet.tokens[1].shields = 40
            fleet.tokens[1].has_armor_components = True
            fleet.waypoints.append(Waypoint(
                position_x=300, position_y=300, warp_factor=9,
                destination="Core"))
            state = self._storm_state(fleet)
            gen = TurnGenerator(state)
            gen.rand.seed(trial)
            gen._process_storms()
            if any("warp mishap" in m.text for m in state.all_messages):
                hits += 1
                mishap_damage_seen = fleet.tokens[1].damage_percent
        assert 0.10 <= hits / trials <= 0.20
        assert mishap_damage_seen == pytest.approx(
            (STORM_DAMAGE_PER_TURN + STORM_MISHAP_DAMAGE) * 0.5)

    def test_attrition_scaled_by_protection(self):
        # protection 0.5: ceil(100 kT * 0.10 * 1.0 * 0.5) = 5 kT lost
        fleet = make_fleet(1, 1, 300, 300, armor=1000)
        fleet.tokens[1].shields = 40
        fleet.tokens[1].has_armor_components = True
        fleet.cargo.colonists_in_kilotons = 100
        state = self._storm_state(fleet)
        TurnGenerator(state)._process_storms()
        assert fleet.cargo.colonists_in_kilotons == 95
        # protection 1.0: colonists untouched
        immune = make_fleet(1, 1, 300, 300, armor=1000)
        immune.tokens[1].storm_shield = 1.0
        immune.cargo.colonists_in_kilotons = 100
        state = self._storm_state(immune)
        TurnGenerator(state)._process_storms()
        assert immune.cargo.colonists_in_kilotons == 100

    def test_rad_race_protection_applies_in_turn(self):
        from backend.core.globals import (
            STORM_DAMAGE_PER_TURN, STORM_RAD_RACE_PROTECTION)
        fleet = make_fleet(1, 1, 300, 300, armor=100)
        state = self._storm_state(fleet)
        state.all_empires[1].race = self._rad_race()
        TurnGenerator(state)._process_storms()
        assert fleet.tokens[1].damage_percent == pytest.approx(
            STORM_DAMAGE_PER_TURN * (1.0 - STORM_RAD_RACE_PROTECTION))


class TestStormShieldComponents:
    """Storm Shield catalog line and design aggregation (web-only
    extension, user directive - wave 4)."""

    @pytest.fixture(scope="class")
    def loader(self):
        from backend.core.components.component_loader import (
            get_component_loader, load_components
        )
        loader = get_component_loader()
        if not loader.is_loaded:
            load_components("backend/data/components.xml")
        return loader

    def test_catalog_carries_three_tiers(self, loader):
        tiers = [("Storm Deflector", 6, 0.40), ("Storm Barrier", 12, 0.70),
                 ("Storm Bulwark", 18, 1.00)]
        for name, tech, value in tiers:
            comp = loader.get_component(name)
            assert comp is not None, f"{name} missing from catalog"
            assert comp.required_tech.levels.get("Propulsion") == tech
            assert comp.required_tech.levels.get("Energy") == tech
            prop = comp.get_property("Storm Shield")
            assert prop.values["Value"] == pytest.approx(value)
            # No conventional Shield rating - a storm shield never
            # grants the standard-shield protection bonus on top
            assert comp.shield_value == 0

    def test_storm_shields_mount_in_shield_slots(self, loader):
        from backend.services.design_builder import slot_accepts
        comp = loader.get_component("Storm Bulwark")
        assert slot_accepts("Shield", comp.item_type)
        assert slot_accepts("Shield or Armor", comp.item_type)
        assert not slot_accepts("Engine", comp.item_type)

    def _design(self, allocations):
        """Design on a fabricated hull with catalog components
        allocated by name (pattern from test_ship_design.py)."""
        from backend.core.components.component import (
            Component, ComponentProperty
        )
        from backend.core.data_structures.resources import Resources
        from backend.core.game_objects.item import ItemType
        from backend.core.components.ship_design import ShipDesign

        c = Component()
        c.name = "Storm Test Hull"
        c.item_type = ItemType.HULL
        c.mass = 25
        c.cost = Resources(4, 2, 4, 10)
        hull_prop = ComponentProperty()
        hull_prop.property_type = "Hull"
        hull_prop.values = {
            "fuel_capacity": 50,
            "armor_strength": 20,
            "modules": [
                {"cell_number": i + 1, "component_maximum": 4,
                 "component_type": slot_type,
                 "allocated_component": name,
                 "component_count": count}
                for i, (slot_type, name, count) in enumerate(allocations)
            ],
        }
        c.add_property(hull_prop)
        design = ShipDesign(blueprint=c)
        design.name = "Storm Test"
        design.update()
        return design

    def test_best_tier_wins_never_summed(self, loader):
        design = self._design([
            ("Shield", "Storm Deflector", 2),
            ("Shield", "Storm Barrier", 1),
        ])
        # Two Deflectors (0.4) and a Barrier (0.7): best tier wins,
        # nothing sums to immunity
        assert design.storm_shield == pytest.approx(0.7)
        # Bare hull armor does not count as armor components
        assert not design.has_armor_components

    def test_armor_components_flagged(self, loader):
        design = self._design([("Armor", "Tritanium", 1)])
        assert design.has_armor_components
        assert design.storm_shield == 0.0

    def test_token_caches_protection_sources(self, loader):
        from backend.services.ship_specs import make_token
        design = self._design([
            ("Shield", "Storm Bulwark", 1),
            ("Armor", "Tritanium", 1),
        ])
        design.key = 42
        token = make_token(design, quantity=1)
        assert token.storm_shield == pytest.approx(1.0)
        assert token.has_armor_components
        assert token.storm_protection(None) == 1.0
        # Round trip through serialization keeps the sources
        restored = ShipToken.from_dict(token.to_dict())
        assert restored.storm_shield == pytest.approx(1.0)
        assert restored.has_armor_components


class TestStormSpawning:
    """Storms preferentially spawn inside nebulae
    (user directive 2026-07-13)."""

    def test_storms_prefer_nebulae(self):
        from backend.services.galaxy_generator import GalaxyGenerator

        # One nebula covering roughly an eighth of the map: unbiased
        # sampling would land ~13% of storms inside it
        nebula = NebulaField(regions=[
            NebulaRegion(x=100, y=100, radius_x=60, radius_y=60,
                         density=1.0, nebula_type='emission'),
        ], universe_width=600, universe_height=600)
        inside = total = 0
        for seed in range(40):
            gen = GalaxyGenerator(seed=seed)
            for storm in gen._generate_storms(600, 600, nebula):
                total += 1
                if nebula.get_density_at(storm.x, storm.y) > 0.0:
                    inside += 1
        assert inside / total >= 0.5

    def test_generated_storms_carry_shapes(self):
        from backend.services.galaxy_generator import GalaxyGenerator
        from backend.core.globals import STORM_SHAPE_POINTS

        gen = GalaxyGenerator(seed=99)
        storms = gen._generate_storms(600, 600, None)
        assert storms
        for storm in storms:
            assert len(storm.shape_radii) == STORM_SHAPE_POINTS
