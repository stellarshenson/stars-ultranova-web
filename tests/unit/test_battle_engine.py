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
    # Electronics aggregates (percent scale, as on ShipDesign)
    jamming: float = 0.0
    battle_computer_accuracy: float = 0.0
    capacitor: float = 0.0
    beam_deflector: float = 0.0

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

    def test_tactic_strings_match_csharp_dialog(self):
        # Exact strings from BattlePlans.Designer.cs:168-174
        from backend.server.battle.battle_plan import TACTICS
        assert TACTICS == [
            "Disengage",
            "Disengage if Challenged",
            "Maximise Damage",
            "Maximise Damage Ratio",
            "Maximise Net Damage",
            "Minimise Damage to Self",
        ]

    def test_attack_strings_match_csharp_dialog(self):
        # Exact strings from BattlePlans.Designer.cs:147-150
        from backend.server.battle.battle_plan import ATTACK_OPTIONS
        assert ATTACK_OPTIONS == [
            "Enemies", "Enemies and Neutrals", "Everyone"]

    def test_plan_cap_and_labels(self):
        from backend.server.battle.battle_plan import (
            MAX_BATTLE_PLANS, VICTIMS_LABELS)
        assert MAX_BATTLE_PLANS == 14  # canonical Stars! cap
        assert len(VICTIMS_LABELS) == 7
        assert VICTIMS_LABELS[Victims.CAPITAL_SHIP] == "Capital Ship"

    def test_full_custom_plan_round_trip(self):
        plan = BattlePlan(
            name="Sniper",
            primary_target=int(Victims.CAPITAL_SHIP),
            secondary_target=int(Victims.STARBASE),
            tertiary_target=int(Victims.BOMBER),
            quaternary_target=int(Victims.ESCORT),
            quinary_target=int(Victims.SUPPORT_SHIP),
            tactic="Disengage if Challenged",
            attack="Enemies and Neutrals",
            target_id=3,
        )
        restored = BattlePlan.from_dict(plan.to_dict())
        assert restored == plan


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

    def test_missile_accuracy_computer_cuts_miss_chance(self):
        """Base 0.75 + computer 20: 1 - 0.25 * 0.8 = 0.80."""
        details = WeaponDetails()
        source = MockDesign(battle_computer_accuracy=20.0)
        target = MockDesign()
        assert details.missile_accuracy(source, target, 0.75) == \
            pytest.approx(0.80)

    def test_missile_accuracy_jammer_cuts_hit_chance(self):
        """Base 0.75 vs jammer 20: 0.75 * 0.8 = 0.60."""
        details = WeaponDetails()
        source = MockDesign()
        target = MockDesign(jamming=20.0)
        assert details.missile_accuracy(source, target, 0.75) == \
            pytest.approx(0.60)

    def test_missile_accuracy_computer_vs_jammer_matchup(self):
        """Matchup matrix: computers modify the miss chance BEFORE
        jammers cut the hit chance (canonical order-independent
        multiplicative form)."""
        details = WeaponDetails()
        cases = [
            # (computer_pct, jamming_pct, expected for base 0.75)
            (0.0, 0.0, 0.75),
            (20.0, 0.0, 0.80),
            (0.0, 20.0, 0.60),
            (20.0, 20.0, 0.64),
            (50.0, 50.0, 0.4375),   # (1 - 0.25*0.5) * 0.5
            (36.0, 28.0, 0.6048),   # 2x BC vs Jammer 20+10 aggregates
        ]
        for computer, jamming, expected in cases:
            source = MockDesign(battle_computer_accuracy=computer)
            target = MockDesign(jamming=jamming)
            assert details.missile_accuracy(source, target, 0.75) == \
                pytest.approx(expected), (computer, jamming)

    def test_missile_accuracy_none_designs(self):
        """None designs leave the base accuracy unchanged."""
        details = WeaponDetails()
        assert details.missile_accuracy(None, None, 0.75) == \
            pytest.approx(0.75)

    def test_beam_power_modifier(self):
        """Capacitor 21 vs deflector 19: 1.21 * 0.81 = 0.9801."""
        details = WeaponDetails()
        source = MockDesign(capacitor=21.0)
        target = MockDesign(beam_deflector=19.0)
        assert details.beam_power_modifier(source, target) == \
            pytest.approx(0.9801)
        assert details.beam_power_modifier(None, None) == 1.0
        assert details.beam_power_modifier(
            MockDesign(capacitor=250.0), MockDesign()) == \
            pytest.approx(3.5)


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
            empire.empire_reports[1 - i] = {"relation": "Enemy"}

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


# =============================================================================
# Battle design learning (BattleEngine.cs:347-368)
# =============================================================================

class TestBattleDesignLearning:
    """Battles reveal FULL enemy designs to every participant."""

    def _make_setup(self, engine_cls):
        from backend.services.ship_specs import SimpleDesign

        server = MockServerData()
        stacks = []
        for i in range(2):
            empire = MockEmpire(id=i)
            design = SimpleDesign(key=(i << 32) | 1, name=f"Warship {i}",
                                  hull_name="Destroyer", armor=100)
            empire.designs[design.key] = design
            server.all_empires[i] = empire

            stack = Stack()
            stack.owner = i
            stack.token = StackToken(design_key=design.key,
                                     design_name=design.name,
                                     quantity=2, armor=200.0)
            stack.token.design = design
            stacks.append(stack)

        engine = engine_cls(server, [])
        return server, engine, stacks

    @pytest.mark.parametrize("engine_cls", [BattleEngine, RonBattleEngine])
    def test_battle_records_full_designs(self, engine_cls):
        server, engine, stacks = self._make_setup(engine_cls)
        engine._update_intel_designs(stacks, {0: 0, 1: 1})

        for i in range(2):
            enemy = 1 - i
            designs = server.all_empires[i].empire_reports[enemy]["designs"]
            record = designs[hex((enemy << 32) | 1)]
            assert record["scope"] == "full"
            assert record["name"] == f"Warship {enemy}"
            assert record["hull_name"] == "Destroyer"
            assert record["owner"] == enemy
            # Full record carries the design payload
            assert record["design"]["name"] == f"Warship {enemy}"

    @pytest.mark.parametrize("engine_cls", [BattleEngine, RonBattleEngine])
    def test_battle_upgrades_hull_record_to_full(self, engine_cls):
        server, engine, stacks = self._make_setup(engine_cls)
        key = hex((1 << 32) | 1)
        server.all_empires[0].empire_reports[1] = {
            "designs": {key: {"key": key, "scope": "hull"}}
        }

        engine._update_intel_designs(stacks, {0: 0, 1: 1})
        record = server.all_empires[0].empire_reports[1]["designs"][key]
        assert record["scope"] == "full"

    @pytest.mark.parametrize("engine_cls", [BattleEngine, RonBattleEngine])
    def test_are_enemies_with_populated_reports(self, engine_cls):
        """Regression for the dict-shaped empire_reports: target
        selection reads relation with a default of Enemy."""
        server, engine, stacks = self._make_setup(engine_cls)
        server.all_empires[0].battle_plans["Default"] = BattlePlan(
            attack="Enemies")
        stacks[0].token.has_weapons = True

        # Populated dict record
        server.all_empires[0].empire_reports[1] = {"relation": "Enemy"}
        assert engine._are_enemies(stacks[0], stacks[1]) is True

        # Unknown empire defaults to Enemy
        server.all_empires[0].empire_reports.clear()
        assert engine._are_enemies(stacks[0], stacks[1]) is True

        # Neutral contact is not attacked under "Enemies"
        # (BattleEngine.cs:487-491)
        server.all_empires[0].empire_reports[1] = {"relation": "Neutral"}
        assert engine._are_enemies(stacks[0], stacks[1]) is False

        # Friendly relation is not attacked
        server.all_empires[0].empire_reports[1] = {"relation": "Friend"}
        assert engine._are_enemies(stacks[0], stacks[1]) is False


# =============================================================================
# Attack-who plan option (BattleEngine.cs:468-494 + dialog parity)
# =============================================================================

class TestAreEnemies:
    """Battle plan attack option drives target eligibility."""

    def _make_setup(self, engine_cls):
        server = MockServerData()
        stacks = []
        for i in range(2):
            empire = MockEmpire(id=i)
            server.all_empires[i] = empire

            stack = Stack()
            stack.owner = i
            stack.token = StackToken(design_key=(i << 32) | 1,
                                     quantity=1, armor=100.0)
            stack.token.has_weapons = True
            stacks.append(stack)

        engine = engine_cls(server, [])
        return server, engine, stacks

    @pytest.mark.parametrize("engine_cls", [BattleEngine, RonBattleEngine])
    def test_enemies_and_neutrals(self, engine_cls):
        """Dialog option (BattlePlans.Designer.cs:149) the C# engine
        never consumed - canonical Stars! rule: attacks Enemy and
        Neutral contacts, spares Friends."""
        server, engine, stacks = self._make_setup(engine_cls)
        server.all_empires[0].battle_plans["Default"] = BattlePlan(
            attack="Enemies and Neutrals")

        server.all_empires[0].empire_reports[1] = {"relation": "Enemy"}
        assert engine._are_enemies(stacks[0], stacks[1]) is True

        server.all_empires[0].empire_reports[1] = {"relation": "Neutral"}
        assert engine._are_enemies(stacks[0], stacks[1]) is True

        server.all_empires[0].empire_reports[1] = {"relation": "Friend"}
        assert engine._are_enemies(stacks[0], stacks[1]) is False

    @pytest.mark.parametrize("engine_cls", [BattleEngine, RonBattleEngine])
    def test_enemies_ignores_neutral(self, engine_cls):
        server, engine, stacks = self._make_setup(engine_cls)
        server.all_empires[0].battle_plans["Default"] = BattlePlan(
            attack="Enemies")
        server.all_empires[0].empire_reports[1] = {"relation": "Neutral"}
        assert engine._are_enemies(stacks[0], stacks[1]) is False

    @pytest.mark.parametrize("engine_cls", [BattleEngine, RonBattleEngine])
    def test_target_id_overrides_friendship(self, engine_cls):
        """BattleEngine.cs:484-487: a specific TargetId is attacked
        regardless of relation."""
        server, engine, stacks = self._make_setup(engine_cls)
        server.all_empires[0].battle_plans["Default"] = BattlePlan(
            attack="Enemies", target_id=1)
        server.all_empires[0].empire_reports[1] = {"relation": "Friend"}
        assert engine._are_enemies(stacks[0], stacks[1]) is True


# =============================================================================
# Target-type priority and tactics (Ron engine; canonical Stars! rules)
# =============================================================================

def _make_battle_stack(owner, stack_id, x, y, armor=200.0, shields=0.0,
                       quantity=1, has_weapons=True, battle_speed=1.0,
                       weapon_range=1, battle_plan="Default",
                       is_bomber=False, mass=100):
    """Build a battle-ready Stack with a mock design."""
    design = MockDesign(key=stack_id, battle_speed=battle_speed,
                        has_weapons=has_weapons)
    design.weapons = [MockWeapon(range=weapon_range)] if has_weapons else []

    stack = Stack()
    stack.key = (owner << 32) | stack_id
    stack.owner = owner
    stack.name = f"Stack #{stack_id}"
    stack.battle_plan = battle_plan
    stack.position = NovaPoint(x, y)
    stack.token = StackToken(design_key=stack_id, quantity=quantity,
                             armor=armor, shields=shields, mass=mass)
    stack.token.has_weapons = has_weapons
    stack.token.is_bomber = is_bomber
    stack.token.battle_speed = battle_speed
    stack.token.design = design
    return stack


class TestRonTargetPriority:
    """Plan target tiers gate what an armed stack may engage."""

    def _make_server(self):
        server = MockServerData()
        for i in range(2):
            empire = MockEmpire(id=i)
            empire.battle_plans["Default"] = BattlePlan(attack="Everyone")
            server.all_empires[i] = empire
        return server

    def test_primary_tier_beats_attractiveness(self):
        """A bomber matching the primary tier is chosen over a far
        more attractive armed ship on a lower tier."""
        server = self._make_server()
        server.all_empires[0].battle_plans["AntiBomber"] = BattlePlan(
            name="AntiBomber", attack="Everyone",
            primary_target=int(Victims.BOMBER),
            secondary_target=int(Victims.ARMED_SHIP))
        engine = RonBattleEngine(server, [])

        wolf = _make_battle_stack(0, 1, 200, 200,
                                  battle_plan="AntiBomber")
        # Bomber: tanky, hence unattractive (cost/defenses low)
        bomber = _make_battle_stack(1, 2, 800, 200, armor=5000.0,
                                    has_weapons=False, is_bomber=True)
        # Armed ship: fragile, hence highly attractive
        juicy = _make_battle_stack(1, 3, 800, 300, armor=10.0)
        assert (engine._get_attractiveness(juicy)
                > engine._get_attractiveness(bomber))

        assert engine._select_targets([wolf, bomber, juicy]) > 0
        assert wolf.target is bomber
        # Fire allocation consumes target_list from the front: the
        # priority target eats the fire first
        assert wolf.target_list[0] is bomber

    def test_no_tier_match_means_no_engagement(self):
        """A plan whose five tiers match nothing about the lamb does
        not engage it (canonical: target types define what may be
        shot at; the C# engine never consumed the tiers)."""
        server = self._make_server()
        server.all_empires[0].battle_plans["BasesOnly"] = BattlePlan(
            name="BasesOnly", attack="Everyone",
            primary_target=int(Victims.STARBASE),
            secondary_target=int(Victims.STARBASE),
            tertiary_target=int(Victims.STARBASE),
            quaternary_target=int(Victims.STARBASE),
            quinary_target=int(Victims.STARBASE))
        engine = RonBattleEngine(server, [])

        wolf = _make_battle_stack(0, 1, 200, 200,
                                  battle_plan="BasesOnly")
        # Unarmed freighter - matches no STARBASE tier
        freighter = _make_battle_stack(1, 2, 800, 200,
                                       has_weapons=False)

        # The freighter still (unarmed) targets the wolf to flee from,
        # but the wolf engages nothing
        engine._select_targets([wolf, freighter])
        assert wolf.target is None
        assert wolf.target_list == []


class TestUnarmedBattleTrigger:
    """DEF-14: unarmed stacks never trigger battles - C# SelectTargets
    skips unarmed wolves before any target assignment
    (BattleEngine.cs:412-415), so unarmed-vs-unarmed co-location
    yields zero targets and run() aborts before any report."""

    def _make_engine(self):
        server = MockServerData()
        for i in range(2):
            empire = MockEmpire(id=i)
            empire.battle_plans["Default"] = BattlePlan(attack="Everyone")
            server.all_empires[i] = empire
        return RonBattleEngine(server, [])

    def test_unarmed_vs_unarmed_yields_zero_targets(self):
        engine = self._make_engine()
        a = _make_battle_stack(0, 1, 200, 200, has_weapons=False)
        b = _make_battle_stack(1, 2, 800, 200, has_weapons=False)

        assert engine._select_targets([a, b]) == 0
        # Flee targets are still assigned so movement would work if
        # an armed enemy joined mid-battle
        assert a.target is b
        assert b.target is a

    def test_unarmed_plus_armed_still_battles(self):
        engine = self._make_engine()
        wolf = _make_battle_stack(0, 1, 200, 200)
        freighter = _make_battle_stack(1, 2, 800, 200,
                                       has_weapons=False)

        assert engine._select_targets([wolf, freighter]) == 1
        assert wolf.target is freighter
        # The unarmed stack keeps its flee target for movement
        assert freighter.target is wolf
        assert freighter.target_list == [wolf]

    def test_armed_vs_armed_counts_both(self):
        engine = self._make_engine()
        a = _make_battle_stack(0, 1, 200, 200)
        b = _make_battle_stack(1, 2, 800, 200)
        assert engine._select_targets([a, b]) == 2


class TestTactics:
    """Plan tactics drive battle movement (canonical Stars! rules;
    the C# engine never consumed Tactic - BattleEngine.cs:603 TODO)."""

    def _setup(self, tactic, runner_armed=True, runner_shields=0.0,
               runner_range=1):
        server = MockServerData()
        for i in range(2):
            empire = MockEmpire(id=i)
            empire.battle_plans["Default"] = BattlePlan(attack="Everyone")
            server.all_empires[i] = empire
        server.all_empires[1].battle_plans["Custom"] = BattlePlan(
            name="Custom", tactic=tactic, attack="Everyone")
        engine = RonBattleEngine(server, [])

        wolf = _make_battle_stack(0, 1, 200, 200)
        runner = _make_battle_stack(1, 2, 600, 200,
                                    has_weapons=runner_armed,
                                    shields=runner_shields,
                                    weapon_range=runner_range,
                                    battle_plan="Custom")
        return server, engine, [wolf, runner], wolf, runner

    def test_disengage_flees_and_leaves_after_seven_moves(self):
        server, engine, stacks, wolf, runner = self._setup("Disengage")
        battle = BattleReport()

        # Rounds 5+ (past the random-flip opening): the runner flees
        # its target every round (+x, away from the wolf at 200)
        for i, battle_round in enumerate(range(5, 12)):
            engine._select_targets(stacks)
            x_before = runner.position.x
            engine._move_stacks(stacks, battle_round, battle)
            assert runner.position.x > x_before
            assert runner.flee_rounds == i + 1

        # Canonical: 7 squares of movement to leave the battle
        assert runner.disengaged is True

        # A disengaged stack is neither targeted nor fires
        assert engine._select_targets(stacks) == 0
        assert wolf.target is None
        assert engine._generate_attacks(stacks) == []

    def test_unarmed_disengage_flees_and_leaves(self):
        """The e2e freighter mechanic: an unarmed stack with a
        Disengage plan leaves the board instead of merely keeping out
        of weapon range."""
        server, engine, stacks, wolf, runner = self._setup(
            "Disengage", runner_armed=False)
        battle = BattleReport()

        for battle_round in range(5, 12):
            engine._select_targets(stacks)
            engine._move_stacks(stacks, battle_round, battle)

        assert runner.disengaged is True
        assert engine._select_targets(stacks) == 0

    def test_disengage_if_challenged_closes_then_flees(self):
        server, engine, stacks, wolf, runner = self._setup(
            "Disengage if Challenged")
        battle = BattleReport()

        # Undamaged: behaves as Maximise Damage (closes on the wolf)
        engine._select_targets(stacks)
        engine._move_stacks(stacks, 5, battle)
        assert runner.position.x < 600
        assert runner.flee_rounds == 0

        # First damage flips the tactic to Disengage
        engine._damage_armor(wolf, runner, 10.0, battle)
        assert runner.damage_taken is True

        x_after_damage = runner.position.x
        engine._select_targets(stacks)
        engine._move_stacks(stacks, 6, battle)
        assert runner.position.x > x_after_damage
        assert runner.flee_rounds == 1

    @pytest.mark.parametrize("tactic", ["Maximise Net Damage",
                                        "Maximise Damage Ratio",
                                        "Minimise Damage to Self"])
    def test_stand_off_holds_at_own_weapon_range(self, tactic):
        server, engine, stacks, wolf, runner = self._setup(
            tactic, runner_shields=50.0, runner_range=4)
        battle = BattleReport()

        # Out of range: the stack closes. The wolf moves first in the
        # same pass (200 -> 300), so the runner sees distance 500 > 400
        runner.position = NovaPoint(800, 200)
        engine._select_targets(stacks)
        engine._move_stacks(stacks, 5, battle)
        assert runner.position.x < 800

        # Within own longest weapon range (4 * GRID_SCALE): hold
        wolf.position = NovaPoint(200, 200)
        runner.position = NovaPoint(500, 200)  # distance <= 400
        engine._select_targets(stacks)
        engine._move_stacks(stacks, 6, battle)
        assert (runner.position.x, runner.position.y) == (500, 200)

    def test_minimise_damage_to_self_falls_back_shieldless(self):
        server, engine, stacks, wolf, runner = self._setup(
            "Minimise Damage to Self", runner_shields=0.0,
            runner_range=4)
        battle = BattleReport()

        # In range but shields down: falls back instead of holding
        runner.position = NovaPoint(500, 200)
        engine._select_targets(stacks)
        engine._move_stacks(stacks, 5, battle)
        assert runner.position.x > 500

    def test_maximise_damage_keeps_closing(self):
        """Regression guard: the default tactic still closes."""
        server, engine, stacks, wolf, runner = self._setup(
            "Maximise Damage")
        battle = BattleReport()

        engine._select_targets(stacks)
        engine._move_stacks(stacks, 5, battle)
        assert runner.position.x < 600
        assert runner.flee_rounds == 0
        assert runner.disengaged is False


# =============================================================================
# Electronics in battle (canonical Stars! rules; the C# consumption
# is a stub - BattleEngine.cs:880-929)
# =============================================================================

class TestElectronicsInBattle:
    """Capacitors/deflectors modify beam damage and computers/jammers
    modify torpedo accuracy inside both battle engines."""

    def _make_stack(self, key, owner, design, quantity=1,
                    armor=10000.0, shields=10000.0):
        stack = Stack()
        stack.key = key
        stack.owner = owner
        stack.token = StackToken()
        stack.token.design = design
        stack.token.quantity = quantity
        stack.token.armor = armor
        stack.token.shields = shields
        return stack

    def _attack(self, attacker_design, target_design, weapon,
                attacker_quantity=1):
        attacker = self._make_stack(1, 0, attacker_design,
                                    quantity=attacker_quantity)
        target = self._make_stack(2, 1, target_design)
        attack = WeaponDetails()
        attack.source_stack = attacker
        attack.target_stack = TargetPercent(target, 100)
        attack.weapon = weapon
        return attack

    @staticmethod
    def _weapon_steps(battle):
        return [s for s in battle.steps
                if isinstance(s, BattleStepWeapons)]

    def test_ron_beam_capacitor_boost(self):
        """Ron beam damage = power * quantity * (1 + capacitor/100);
        the deep-shielded target captures it in one shields step."""
        engine = RonBattleEngine(MockServerData(), [])
        attack = self._attack(MockDesign(capacitor=10.0), MockDesign(),
                              MockWeapon(power=10), attacker_quantity=2)
        battle = BattleReport()
        engine._execute_attack(attack, battle)
        steps = self._weapon_steps(battle)
        assert len(steps) == 1
        assert steps[0].damage == pytest.approx(10 * 2 * 1.1)

    def test_ron_beam_deflector_cut(self):
        """Ron beam damage x 0.9 against a deflector-fitted target."""
        engine = RonBattleEngine(MockServerData(), [])
        attack = self._attack(MockDesign(),
                              MockDesign(beam_deflector=10.0),
                              MockWeapon(power=10), attacker_quantity=2)
        battle = BattleReport()
        engine._execute_attack(attack, battle)
        steps = self._weapon_steps(battle)
        assert len(steps) == 1
        assert steps[0].damage == pytest.approx(10 * 2 * 0.9)

    def test_ron_missile_jammer_reduces_damage(self):
        """Same seeded roll: the jammered target takes strictly less
        torpedo damage (Ron's percent_hit scales with accuracy)."""
        import random

        totals = []
        for jamming in (0.0, 50.0):
            engine = RonBattleEngine(MockServerData(), [])
            engine._random = random.Random(7)
            attack = self._attack(MockDesign(),
                                  MockDesign(jamming=jamming),
                                  MockWeapon(power=100, accuracy=75,
                                             group="torpedo"))
            battle = BattleReport()
            engine._execute_attack(attack, battle)
            totals.append(sum(s.damage for s in
                              self._weapon_steps(battle)))
        assert totals[1] < totals[0]

    def test_standard_missile_jammer_turns_hit_into_miss(self):
        """Seeded rng rolls 49: base accuracy 75 hits (shields 32 +
        armor 32); vs jammer 50 accuracy drops to 37.5 and the same
        roll misses (splash 64/8 = 8 to shields)."""
        import random

        engine = BattleEngine(MockServerData(), [])
        engine._random = random.Random(0)  # first randint(0,100) == 49
        attack = self._attack(MockDesign(), MockDesign(),
                              MockWeapon(power=64, accuracy=75,
                                         group="torpedo"))
        battle = BattleReport()
        engine._execute_attack(attack, battle)
        damages = [s.damage for s in self._weapon_steps(battle)]
        assert damages == [pytest.approx(32.0), pytest.approx(32.0)]

        engine = BattleEngine(MockServerData(), [])
        engine._random = random.Random(0)
        attack = self._attack(MockDesign(), MockDesign(jamming=50.0),
                              MockWeapon(power=64, accuracy=75,
                                         group="torpedo"))
        battle = BattleReport()
        engine._execute_attack(attack, battle)
        damages = [s.damage for s in self._weapon_steps(battle)]
        assert damages == [pytest.approx(8.0)]

    def test_standard_missile_computer_turns_miss_into_hit(self):
        """Mirror case, same roll 49: base accuracy 40 misses; with a
        20% computer accuracy rises to (1 - 0.6 * 0.8) * 100 = 52 and
        the same roll hits."""
        import random

        engine = BattleEngine(MockServerData(), [])
        engine._random = random.Random(0)  # first randint(0,100) == 49
        attack = self._attack(MockDesign(), MockDesign(),
                              MockWeapon(power=64, accuracy=40,
                                         group="torpedo"))
        battle = BattleReport()
        engine._execute_attack(attack, battle)
        damages = [s.damage for s in self._weapon_steps(battle)]
        assert damages == [pytest.approx(8.0)]  # miss splash

        engine = BattleEngine(MockServerData(), [])
        engine._random = random.Random(0)
        attack = self._attack(
            MockDesign(battle_computer_accuracy=20.0), MockDesign(),
            MockWeapon(power=64, accuracy=40, group="torpedo"))
        battle = BattleReport()
        engine._execute_attack(attack, battle)
        damages = [s.damage for s in self._weapon_steps(battle)]
        assert damages == [pytest.approx(32.0), pytest.approx(32.0)]

    def test_standard_beam_power_uses_modifier(self):
        """Standard engine beam power = weapon.power * modifier
        (BattleEngine.cs:880-908 stub returns raw power)."""
        engine = BattleEngine(MockServerData(), [])
        attack = self._attack(MockDesign(capacitor=21.0),
                              MockDesign(beam_deflector=19.0),
                              MockWeapon(power=100))
        assert engine._calculate_weapon_power(attack) == \
            pytest.approx(100 * 0.9801)
        # Missiles are unaffected by capacitors/deflectors
        attack.weapon = MockWeapon(power=100, group="torpedo")
        assert engine._calculate_weapon_power(attack) == 100.0
