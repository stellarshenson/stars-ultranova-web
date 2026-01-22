"""
Tests for Battle Engine
Phase 5: Battle system tests
"""

import pytest
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from backend.core.data_structures import NovaPoint, Resources, Cargo, TechLevel
from backend.core.game_objects import Fleet, ShipToken
from backend.server.battle import (
    BattleStep,
    BattleStepMovement,
    BattleStepTarget,
    BattleStepWeapons,
    BattleStepDestroy,
    TokenDefence,
    WeaponTarget,
    BattleReport,
    BattlePlan,
    Victims,
    Stack,
    StackToken,
    WeaponDetails,
    TargetPercent,
    SpaceAllocator,
    BattleEngine,
    RonBattleEngine,
)


# =============================================================================
# Mock Classes
# =============================================================================

@dataclass
class MockDesign:
    """Mock ShipDesign for testing."""
    key: int = 1
    name: str = "Test Design"
    mass: int = 100
    battle_speed: float = 1.0
    has_weapons: bool = True
    is_starbase: bool = False
    weapons: List = field(default_factory=list)
    bombs: List = field(default_factory=list)
    power_rating: int = 1000
    summary: Optional[dict] = None

    def update(self):
        pass


@dataclass
class MockWeapon:
    """Mock Weapon for testing."""
    power: int = 10
    range: int = 3
    initiative: int = 100
    accuracy: int = 75
    group: str = "standardBeam"

    @property
    def is_beam(self) -> bool:
        return self.group in ["standardBeam", "shieldSapper", "gatlingGun"]

    @property
    def is_missile(self) -> bool:
        return self.group in ["torpedo", "missile"]


@dataclass
class MockEmpireReport:
    """Mock empire intel report."""
    relation: str = "Enemy"
    designs: Dict = field(default_factory=dict)


@dataclass
class MockEmpire:
    """Mock EmpireData for testing."""
    id: int = 0
    turn_year: int = 2400
    designs: Dict = field(default_factory=dict)
    owned_fleets: Dict = field(default_factory=dict)
    owned_stars: Dict = field(default_factory=dict)
    fleet_reports: Dict = field(default_factory=dict)
    empire_reports: Dict = field(default_factory=dict)
    battle_plans: Dict = field(default_factory=dict)
    battle_reports: List = field(default_factory=list)
    _fleet_counter: int = 0

    def get_next_fleet_key(self) -> int:
        self._fleet_counter += 1
        return self._fleet_counter | (self.id << 32)

    def add_or_update_fleet(self, fleet: Fleet):
        self.owned_fleets[fleet.key] = fleet


@dataclass
class MockServerData:
    """Mock ServerData for testing."""
    all_empires: Dict = field(default_factory=dict)
    all_stars: Dict = field(default_factory=dict)
    all_minefields: Dict = field(default_factory=dict)
    turn_year: int = 2400

    def iterate_all_fleets(self):
        for empire in self.all_empires.values():
            yield from empire.owned_fleets.values()


# =============================================================================
# BattleStep Tests
# =============================================================================

class TestBattleStep:
    """Tests for BattleStep classes."""

    def test_base_step(self):
        step = BattleStep()
        assert step.step_type == "Base"

    def test_movement_step(self):
        step = BattleStepMovement()
        step.stack_key = 123
        step.position = NovaPoint(5, 10)
        assert step.step_type == "Movement"
        assert step.stack_key == 123
        assert step.position.x == 5

    def test_movement_step_serialization(self):
        step = BattleStepMovement()
        step.stack_key = 456
        step.position = NovaPoint(3, 7)
        data = step.to_dict()
        restored = BattleStepMovement.from_dict(data)
        assert restored.stack_key == 456
        assert restored.position.x == 3

    def test_target_step(self):
        step = BattleStepTarget()
        step.stack_key = 1
        step.target_key = 2
        step.percent_to_fire = 75
        assert step.step_type == "Target"
        assert step.percent_to_fire == 75

    def test_weapons_step(self):
        step = BattleStepWeapons()
        step.damage = 50.5
        step.targeting = TokenDefence.ARMOR
        step.weapon_target = WeaponTarget(stack_key=1, target_key=2)
        assert step.step_type == "Weapons"
        assert step.damage == 50.5
        assert step.targeting == TokenDefence.ARMOR

    def test_destroy_step(self):
        step = BattleStepDestroy()
        step.stack_key = 999
        assert step.step_type == "Destroy"
        assert step.stack_key == 999


# =============================================================================
# BattleReport Tests
# =============================================================================

class TestBattleReport:
    """Tests for BattleReport class."""

    def test_report_creation(self):
        report = BattleReport()
        report.location = "Alpha Centauri"
        report.year = 2400
        report.space_size = 10
        assert report.key == "2400Alpha Centauri"

    def test_report_losses(self):
        report = BattleReport()
        report.losses[0] = 5
        report.losses[1] = 3
        assert report.losses[0] == 5
        assert report.losses[1] == 3

    def test_report_serialization(self):
        report = BattleReport()
        report.location = "Sol"
        report.year = 2401
        report.steps.append(BattleStepMovement())
        data = report.to_dict()
        assert data["location"] == "Sol"
        assert len(data["steps"]) == 1


# =============================================================================
# BattlePlan Tests
# =============================================================================

class TestBattlePlan:
    """Tests for BattlePlan class."""

    def test_default_plan(self):
        plan = BattlePlan()
        assert plan.name == "Default"
        assert plan.attack == "Enemies"
        assert plan.tactic == "Maximise Damage"

    def test_plan_targets(self):
        plan = BattlePlan()
        assert plan.primary_target == 0  # Starbase
        assert plan.secondary_target == 1  # Bomber

    def test_plan_serialization(self):
        plan = BattlePlan(name="Aggressive", attack="Everyone")
        data = plan.to_dict()
        restored = BattlePlan.from_dict(data)
        assert restored.name == "Aggressive"
        assert restored.attack == "Everyone"


class TestVictims:
    """Tests for Victims enum."""

    def test_victim_values(self):
        assert Victims.STARBASE == 0
        assert Victims.BOMBER == 1
        assert Victims.CAPITAL_SHIP == 2
        assert Victims.ANY_SHIP == 5


# =============================================================================
# Stack Tests
# =============================================================================

class TestStackToken:
    """Tests for StackToken class."""

    def test_from_ship_token(self):
        token = ShipToken()
        token.design_key = 100
        token.design_name = "Destroyer"
        token.quantity = 5
        token.armor = 200
        token.shields = 100

        design = MockDesign(battle_speed=1.5)
        stack_token = StackToken.from_ship_token(token, design)

        assert stack_token.design_key == 100
        assert stack_token.quantity == 5
        assert stack_token.shields == 500.0  # quantity * shields
        assert stack_token.armor == 1000.0  # quantity * armor
        assert stack_token.battle_speed == 1.5


class TestStack:
    """Tests for Stack class."""

    def test_stack_from_fleet(self):
        fleet = Fleet()
        fleet.owner = 1  # Set owner first
        fleet.id = 12345  # Then set ID - key becomes (owner << 32) | id
        fleet.position = NovaPoint(100, 200)
        fleet.battle_plan = "Aggressive"

        token = ShipToken()
        token.design_key = 50
        token.design_name = "Cruiser"
        token.quantity = 3
        token.armor = 100
        token.shields = 50
        token.has_weapons = True

        design = MockDesign(battle_speed=1.25)
        stack = Stack.from_fleet(fleet, 0, token, design)

        assert stack.owner == 1
        assert stack.parent_key == fleet.key  # Parent key is full key including owner
        assert stack.battle_plan == "Aggressive"
        assert stack.position.x == 100
        assert stack.token.quantity == 3

    def test_stack_properties(self):
        stack = Stack()
        stack.token = StackToken()
        stack.token.armor = 500
        stack.token.shields = 200
        stack.token.quantity = 2
        stack.token.has_weapons = True
        stack.token.is_starbase = False
        stack.token.mass = 100

        assert stack.defenses == 700
        assert stack.is_armed == True
        assert stack.is_starbase == False
        assert stack.mass == 200

    def test_stack_is_destroyed(self):
        stack = Stack()
        assert stack.is_destroyed == True  # No token

        stack.token = StackToken()
        stack.token.armor = 0
        assert stack.is_destroyed == True  # No armor

        stack.token.armor = 100
        stack.token.quantity = 0
        assert stack.is_destroyed == True  # No ships

        stack.token.quantity = 1
        assert stack.is_destroyed == False

    def test_stack_copy(self):
        original = Stack()
        original.key = 999
        original.owner = 2
        original.position = NovaPoint(50, 75)
        original.token = StackToken()
        original.token.armor = 100
        original.token.shields = 50

        copy = Stack.copy(original)
        assert copy.key == 999
        assert copy.owner == 2
        assert copy.position.x == 50
        assert copy.token.armor == 100

        # Modify copy shouldn't affect original
        copy.token.armor = 0
        assert original.token.armor == 100


# =============================================================================
# WeaponDetails Tests
# =============================================================================

class TestWeaponDetails:
    """Tests for WeaponDetails class."""

    def test_beam_dispersal(self):
        details = WeaponDetails()
        details.weapon = MockWeapon(range=3)

        # At same location
        dispersal = details.beam_dispersal(0)
        assert dispersal == 100.0

        # At max range (3^2 = 9)
        dispersal = details.beam_dispersal(9)
        assert dispersal == 90.0  # 10% reduction at max range

    def test_weapon_sorting(self):
        w1 = WeaponDetails()
        w1.weapon = MockWeapon(initiative=100)
        w2 = WeaponDetails()
        w2.weapon = MockWeapon(initiative=200)
        w3 = WeaponDetails()
        w3.weapon = MockWeapon(initiative=50)

        weapons = [w1, w2, w3]
        weapons.sort()

        assert weapons[0].weapon.initiative == 50
        assert weapons[1].weapon.initiative == 100
        assert weapons[2].weapon.initiative == 200


# =============================================================================
# SpaceAllocator Tests
# =============================================================================

class TestSpaceAllocator:
    """Tests for SpaceAllocator class."""

    def test_grid_calculation(self):
        # 4 items -> 2x2 grid
        alloc = SpaceAllocator(4)
        assert alloc.grid_axis_count == 2

        # 5 items -> 3x3 grid (rounds up)
        alloc = SpaceAllocator(5)
        assert alloc.grid_axis_count == 3

        # 9 items -> 3x3 grid
        alloc = SpaceAllocator(9)
        assert alloc.grid_axis_count == 3

    def test_space_allocation(self):
        alloc = SpaceAllocator(4)
        alloc.allocate_space(100)

        assert alloc.grid_size == 100
        assert len(alloc.available_boxes) == 4

    def test_get_box(self):
        alloc = SpaceAllocator(2)
        alloc.allocate_space(100)

        box1 = alloc.get_box(0, 2)
        box2 = alloc.get_box(1, 2)

        # Boxes should be at different positions
        assert (box1.x, box1.y) != (box2.x, box2.y)


# =============================================================================
# Movement Table Tests
# =============================================================================

class TestMovementTable:
    """Tests for movement table values."""

    def test_movement_table_import(self):
        from backend.server.battle.battle_engine import MOVEMENT_TABLE

        # Table should be 9x8
        assert len(MOVEMENT_TABLE) == 9
        assert all(len(row) == 8 for row in MOVEMENT_TABLE)

    def test_speed_0_5_movement(self):
        from backend.server.battle.battle_engine import MOVEMENT_TABLE

        # Speed 0.5 row: alternating 0,1 pattern
        row = MOVEMENT_TABLE[0]
        assert row == [0, 1, 0, 1, 0, 1, 0, 1]

    def test_speed_2_5_movement(self):
        from backend.server.battle.battle_engine import MOVEMENT_TABLE

        # Speed 2.5+ row: mostly 2s and 3s
        row = MOVEMENT_TABLE[8]
        assert row == [2, 3, 2, 3, 2, 3, 2, 3]


# =============================================================================
# BattleEngine Tests
# =============================================================================

class TestBattleEngine:
    """Tests for BattleEngine class."""

    def test_engine_creation(self):
        server = MockServerData()
        reports = []
        engine = BattleEngine(server, reports)

        assert engine.server_state == server
        assert engine.battles == reports
        assert engine.MAX_BATTLE_ROUNDS == 16

    def test_no_battles_empty_state(self):
        server = MockServerData()
        reports = []
        engine = BattleEngine(server, reports)

        engine.run()
        assert len(reports) == 0

    def test_no_battles_single_fleet(self):
        server = MockServerData()
        empire = MockEmpire(id=0)
        fleet = Fleet()
        fleet.key = 1
        fleet.owner = 0
        fleet.position = NovaPoint(100, 100)
        empire.owned_fleets[fleet.key] = fleet
        server.all_empires[0] = empire

        reports = []
        engine = BattleEngine(server, reports)
        engine.run()

        # No battle with only one fleet
        assert len(reports) == 0

    def test_colocated_detection(self):
        server = MockServerData()

        empire1 = MockEmpire(id=0)
        fleet1 = Fleet()
        fleet1.key = 1
        fleet1.owner = 0
        fleet1.name = "Fleet 1"
        fleet1.position = NovaPoint(100, 100)
        empire1.owned_fleets[fleet1.key] = fleet1
        server.all_empires[0] = empire1

        empire2 = MockEmpire(id=1)
        fleet2 = Fleet()
        fleet2.key = 2
        fleet2.owner = 1
        fleet2.name = "Fleet 2"
        fleet2.position = NovaPoint(100, 100)  # Same position
        empire2.owned_fleets[fleet2.key] = fleet2
        server.all_empires[1] = empire2

        reports = []
        engine = BattleEngine(server, reports)
        colocated = engine._determine_colocated_fleets()

        assert len(colocated) == 1
        assert len(colocated[0]) == 2

    def test_battle_move_to(self):
        server = MockServerData()
        engine = BattleEngine(server, [])

        from_pos = NovaPoint(0, 0)
        to_pos = NovaPoint(5, 5)
        new_pos = engine._battle_move_to(from_pos, to_pos)

        # Should move one step toward target
        assert new_pos.x == 1
        assert new_pos.y == 1

    def test_attractiveness_calculation(self):
        server = MockServerData()
        engine = BattleEngine(server, [])

        stack = Stack()
        stack.token = StackToken()
        stack.token.mass = 100
        stack.token.armor = 50
        stack.token.shields = 50
        stack.token.quantity = 1

        attractiveness = engine._get_attractiveness(stack)

        # cost / defenses = (mass + energy) / (armor + shields)
        # With default cost estimation: mass/3 for each mineral, mass for energy
        # cost = 100 + 100 = 200 (mass + energy)
        # defenses = 100
        # attractiveness = 200 / 100 = 2.0
        assert attractiveness > 0


# =============================================================================
# RonBattleEngine Tests
# =============================================================================

class TestRonBattleEngine:
    """Tests for RonBattleEngine class."""

    def test_engine_creation(self):
        server = MockServerData()
        reports = []
        engine = RonBattleEngine(server, reports)

        assert engine.GRID_SIZE == 1000
        assert engine.GRID_SCALE == 100
        assert engine.MAX_BATTLE_ROUNDS == 60

    def test_battle_speed_vector(self):
        server = MockServerData()
        engine = RonBattleEngine(server, [])

        direction = NovaPoint(3, 4)  # Length = 5
        speed = 10.0
        result = engine._battle_speed_vector(direction, speed)

        # Should normalize and scale
        # 3/5 * 10 = 6, 4/5 * 10 = 8
        assert result.x == 6
        assert result.y == 8

    def test_priority_matching_starbase(self):
        server = MockServerData()
        empire = MockEmpire(id=0)
        empire.battle_plans["Default"] = BattlePlan()
        server.all_empires[0] = empire

        engine = RonBattleEngine(server, [])

        target = Stack()
        target.token = StackToken()
        target.token.is_starbase = True

        matches = engine._target_matches_priority(Victims.STARBASE, target)
        assert matches == True

    def test_priority_matching_armed(self):
        server = MockServerData()
        engine = RonBattleEngine(server, [])

        target = Stack()
        target.token = StackToken()
        target.token.has_weapons = True
        target.token.is_starbase = False

        matches = engine._target_matches_priority(Victims.ARMED_SHIP, target)
        assert matches == True


# =============================================================================
# Integration Tests
# =============================================================================

class TestBattleIntegration:
    """Integration tests for battle system."""

    def test_full_battle_setup(self):
        """Test setting up a complete battle scenario."""
        server = MockServerData()

        # Create two empires with armed fleets
        for i in range(2):
            empire = MockEmpire(id=i)
            empire.battle_plans["Default"] = BattlePlan(attack="Everyone")
            empire.empire_reports[1 - i] = MockEmpireReport()

            fleet = Fleet()
            fleet.key = empire.get_next_fleet_key()
            fleet.owner = i
            fleet.name = f"Battle Fleet {i}"
            fleet.position = NovaPoint(100, 100)

            token = ShipToken()
            token.design_key = 1
            token.design_name = "Warship"
            token.quantity = 5
            token.armor = 100
            token.shields = 50
            token.has_weapons = True
            fleet.tokens[token.design_key] = token

            empire.owned_fleets[fleet.key] = fleet
            server.all_empires[i] = empire

        reports: List[BattleReport] = []
        engine = BattleEngine(server, reports)

        # Verify fleets are detected
        colocated = engine._determine_colocated_fleets()
        assert len(colocated) == 1

        # Verify multiple races
        engagements = engine._eliminate_single_races(colocated)
        assert len(engagements) == 1

    def test_stack_generation(self):
        """Test generating stacks from fleets."""
        server = MockServerData()
        empire = MockEmpire(id=0)

        # Create design
        design = MockDesign(key=100, name="Cruiser", battle_speed=1.5)
        design.weapons = [MockWeapon()]
        empire.designs[100] = design

        # Create fleet with token
        fleet = Fleet()
        fleet.key = 1
        fleet.owner = 0
        fleet.position = NovaPoint(50, 50)
        fleet.battle_plan = "Default"

        token = ShipToken()
        token.design_key = 100
        token.design_name = "Cruiser"
        token.quantity = 3
        token.armor = 200
        token.shields = 100
        token.has_weapons = True
        fleet.tokens[token.design_key] = token

        empire.owned_fleets[fleet.key] = fleet
        server.all_empires[0] = empire

        engine = BattleEngine(server, [])
        stacks = engine._build_fleet_stacks(fleet)

        assert len(stacks) == 1
        assert stacks[0].token.quantity == 3
        assert stacks[0].token.battle_speed == 1.5
