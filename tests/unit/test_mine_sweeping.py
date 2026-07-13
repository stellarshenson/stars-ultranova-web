"""
Tests for mine sweeping and SD minefield detonation.

Both mechanics are absent from the C# reference (no .cs file mentions
sweeping; detonation exists only as the SD trait text in
PrimaryTraits.cs:58) - the web port follows canonical Stars! rules:
sweep rate = sum of beam power x range^2 (gatling as range 16),
detonation damages every fleet inside a standard field yearly.
"""

import pytest

from backend.server.server_data import ServerData, Minefield
from backend.server.turn_generator import TurnGenerator
from backend.core.components.ship_design import ShipDesign, Weapon
from backend.core.data_structures import EmpireData, NovaPoint
from backend.core.game_objects.fleet import Fleet, ShipToken
from backend.core.waypoints.waypoint import Waypoint
from backend.core.globals import NOBODY


def make_design(key: int, weapons, name: str = "Armed") -> ShipDesign:
    """Hand-built design with a static weapons list (no blueprint)."""
    design = ShipDesign()
    design.key = key
    design.name = name
    design.weapons = list(weapons)
    # A blueprint-less design must not be wiped by update()
    design._needs_update = False
    return design


def make_fleet(key: int, owner: int, x: float, y: float,
               quantity: int = 1, armor: int = 100,
               design_key: int = 1, is_starbase: bool = False) -> Fleet:
    """Build a minimal real fleet with one token."""
    fleet = Fleet(name=f"Fleet #{key}", position=NovaPoint(x, y))
    fleet._key = (owner << 32) | key
    fleet.owner_int = owner
    fleet.owner = owner
    fleet.tokens[design_key] = ShipToken(
        design_key=design_key, design_name="Testship", quantity=quantity,
        mass=10, armor=armor, fuel_capacity=500, is_starbase=is_starbase,
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


class TestMineSweeping:
    """Canonical sweep rates: beam power x range^2, gatling as 16."""

    def _setup(self, weapons, quantity=1, fleet_pos=(100, 100),
               field_owner=2, mines=1000):
        fleet = make_fleet(1, 1, *fleet_pos, quantity=quantity)
        state = make_state(fleet)
        state.all_empires[1].designs[1] = make_design(1, weapons)
        state.all_minefields[1] = Minefield(
            key=1, owner=field_owner, position_x=100, position_y=100,
            number_of_mines=mines, mine_type=0)
        return fleet, state, TurnGenerator(state)

    def test_beam_sweeps_power_times_range_squared(self):
        fleet, state, gen = self._setup(
            [Weapon(power=10, range=2, group="standardBeam")], quantity=3)
        gen._sweep_minefields()
        # 10 x 2^2 x 3 ships = 120 mines swept
        assert state.all_minefields[1].number_of_mines == 880

    def test_gatling_sweeps_as_range_16(self):
        fleet, state, gen = self._setup(
            [Weapon(power=31, range=2, group="gatlingGun")], mines=10000)
        gen._sweep_minefields()
        # Gatling sweeps as range 16: 31 x 256 = 7936 regardless of range
        assert state.all_minefields[1].number_of_mines == 10000 - 7936

    def test_no_sweep_outside_field(self):
        # Field radius sqrt(1000) ~ 31.6; fleet 141 ly away
        fleet, state, gen = self._setup(
            [Weapon(power=10, range=2, group="standardBeam")],
            fleet_pos=(200, 200))
        gen._sweep_minefields()
        assert state.all_minefields[1].number_of_mines == 1000

    def test_no_sweep_own_field(self):
        fleet, state, gen = self._setup(
            [Weapon(power=10, range=2, group="standardBeam")],
            field_owner=1)
        gen._sweep_minefields()
        assert state.all_minefields[1].number_of_mines == 1000
        assert not any(m.message_type == "Minefield Swept"
                       for m in state.all_messages)

    def test_torpedo_does_not_sweep(self):
        fleet, state, gen = self._setup(
            [Weapon(power=50, range=5, group="torpedo")])
        gen._sweep_minefields()
        assert state.all_minefields[1].number_of_mines == 1000
        assert not any(m.message_type == "Minefield Swept"
                       for m in state.all_messages)

    def test_field_removed_when_swept_below_threshold(self):
        fleet, state, gen = self._setup(
            [Weapon(power=10, range=2, group="standardBeam")],
            quantity=3, mines=100)
        gen._sweep_minefields()
        # 120 capacity sweeps all 100 mines; <= 10 removes the field
        assert 1 not in state.all_minefields
        swept = [m for m in state.all_messages
                 if m.message_type == "Minefield Swept"]
        assert any(m.audience == 1 for m in swept)  # sweeping fleet owner
        assert any(m.audience == 2 for m in swept)  # field owner

    def test_starbase_sweeps(self):
        fleet = make_fleet(1, 1, 100, 100, is_starbase=True)
        state = make_state(fleet)
        state.all_empires[1].designs[1] = make_design(
            1, [Weapon(power=25, range=4, group="standardBeam")])
        state.all_minefields[1] = Minefield(
            key=1, owner=2, position_x=100, position_y=100,
            number_of_mines=1000, mine_type=0)
        TurnGenerator(state)._sweep_minefields()
        # 25 x 16 = 400 swept by the orbiting starbase
        assert state.all_minefields[1].number_of_mines == 600


class TestDetonation:
    """SD detonation: yearly damage to every fleet inside the field."""

    def _setup(self, mine_type=0, mines=400):
        # Field at (100,100), radius sqrt(400) = 20
        owner_fleet = make_fleet(1, 1, 95, 100, quantity=1, armor=2000)
        enemy_fleet = make_fleet(2, 2, 105, 100, quantity=2, armor=100)
        outside_fleet = make_fleet(3, 2, 200, 200, quantity=1, armor=100)
        state = make_state(owner_fleet, enemy_fleet, outside_fleet)
        state.all_minefields[1] = Minefield(
            key=1, owner=1, position_x=100, position_y=100,
            number_of_mines=mines, mine_type=mine_type, detonate=True)
        gen = TurnGenerator(state)
        return owner_fleet, enemy_fleet, outside_fleet, state, gen

    def test_detonation_damages_every_fleet_inside(self):
        owner_fleet, enemy_fleet, outside_fleet, state, gen = self._setup()
        gen._detonate_minefields()

        # Enemy: max(500, 100 x 2) = 500 over 2 ships = 250 each;
        # 250% of the token's 100 armor kills both ships
        assert 1 not in enemy_fleet.tokens
        # Owner's own fleet damaged too (friend and foe alike):
        # 500 / 2000 armor = 25%
        assert owner_fleet.tokens[1].damage_percent == pytest.approx(25)
        assert owner_fleet.tokens[1].quantity == 1
        # Fleet outside the radius untouched
        assert outside_fleet.tokens[1].damage_percent == 0
        # 10 mines expended per fleet damaged
        assert state.all_minefields[1].number_of_mines == 380

        det = [m for m in state.all_messages
               if m.message_type == "Minefield Detonation"]
        assert any(m.audience == 2 for m in det)  # victim
        assert any(m.audience == 1 for m in det)  # field owner

    def test_detonation_only_standard_fields(self):
        for mine_type in (1, 2):
            _, enemy_fleet, _, state, gen = self._setup(mine_type=mine_type)
            gen._detonate_minefields()
            assert enemy_fleet.tokens[1].quantity == 2
            assert state.all_minefields[1].number_of_mines == 400
            assert not any(m.message_type == "Minefield Detonation"
                           for m in state.all_messages)

    def test_detonation_does_not_stop_fleets(self):
        _, enemy_fleet, _, state, gen = self._setup()
        enemy_fleet.tokens[1].armor = 10000  # survives with damage
        enemy_fleet.waypoints.append(Waypoint(
            position_x=300, position_y=100, warp_factor=6,
            destination="Away"))
        gen._detonate_minefields()
        assert enemy_fleet.waypoints[0].warp_factor == 6

    def test_detonation_removes_depleted_field(self):
        # Radius sqrt(25) = 5 exactly covers the fleets 5 ly out
        _, _, _, state, gen = self._setup(mines=25)
        gen._detonate_minefields()
        # 25 - 10 x 2 fleets = 5 <= 10: field removed
        assert 1 not in state.all_minefields


class TestStrikeRegression:
    """The _apply_mine_damage refactor left strikes bit-identical."""

    def test_strike_damage_unchanged(self):
        fleet = make_fleet(1, 1, 200, 100, quantity=5, armor=100)
        fleet.waypoints.append(Waypoint(
            position_x=200, position_y=100, warp_factor=9,
            destination="Target"))
        state = make_state(fleet)
        minefield = Minefield(
            key=1, owner=2, position_x=100, position_y=100,
            number_of_mines=2500, mine_type=0)
        state.all_minefields[1] = minefield
        gen = TurnGenerator(state)

        gen._strike_minefield(fleet, minefield, gen.MINE_STATS[0])

        # min fleet damage 500 over 5 ships = 100 each = 100% of the
        # token's armor: exactly one ship destroyed, damage reset
        assert fleet.tokens[1].quantity == 4
        assert fleet.tokens[1].damage_percent == pytest.approx(0)
        assert fleet.waypoints[0].warp_factor == 0
        assert minefield.number_of_mines == 2490
        assert any(m.message_type == "Minefield Hit"
                   for m in state.all_messages)


class TestDetonateCommandValidation:
    """submit_command gates the detonation toggle on the SD trait."""

    def test_non_sd_race_rejected_then_sd_applied(self, tmp_path):
        from backend.services.game_manager import GameManager

        manager = GameManager(str(tmp_path / "test.db"))
        game = manager.create_game("t", 2, "tiny", seed=99)
        game_id = game["id"]
        server_data = manager._load_game_state(game_id)
        server_data.all_minefields[7] = Minefield(
            key=7, owner=1, position_x=50, position_y=50,
            number_of_mines=100, mine_type=0)

        # Default player 1 race is JOAT - not Space Demolition
        result = manager.submit_command(
            game_id, 1, "detonate_minefield", {"key": 7, "detonate": True})
        assert "Space Demolition" in result["error"]
        assert server_data.all_minefields[7].detonate is False

        server_data.all_empires[1].race.primary_trait = "SD"
        result = manager.submit_command(
            game_id, 1, "detonate_minefield", {"key": 7, "detonate": True})
        assert result["status"] == "applied"
        assert server_data.all_minefields[7].detonate is True


class TestDetonateSerialization:

    def test_detonate_flag_serializes(self):
        state = ServerData()
        state.all_minefields[1] = Minefield(
            key=1, owner=1, position_x=10, position_y=20,
            number_of_mines=500, mine_type=0, detonate=True)
        restored = ServerData.from_dict(state.to_dict())
        assert restored.all_minefields[1].detonate is True
        assert restored.all_minefields[1].number_of_mines == 500
