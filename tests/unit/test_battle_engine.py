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
    BattleStepWithdraw,
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
        # Exact strings from BattlePlans.Designer.cs:168-174, plus
        # the web-only Salvo then Close (the engagement-range
        # decision, docs/research-engagement-range.md section 3)
        from backend.server.battle.battle_plan import TACTICS
        assert TACTICS == [
            "Disengage",
            "Disengage if Challenged",
            "Maximise Damage",
            "Maximise Damage Ratio",
            "Maximise Net Damage",
            "Minimise Damage to Self",
            "Salvo then Close",
        ]

    def test_attack_strings_match_csharp_dialog(self):
        # Exact strings from BattlePlans.Designer.cs:147-150
        from backend.server.battle.battle_plan import ATTACK_OPTIONS
        assert ATTACK_OPTIONS == [
            "Enemies", "Enemies and Neutrals", "Everyone"]

    def test_plan_cap_and_labels(self):
        from backend.server.battle.battle_plan import (
            MAX_BATTLE_PLANS, VICTIMS_LABELS, ADMIRALTY_PLANS)
        # Canonical Stars! cap of 14 player plans plus the six
        # admiralty standard plans seeded into every empire, which
        # must not eat the commander's own allowance
        assert MAX_BATTLE_PLANS == 14 + len(ADMIRALTY_PLANS)
        # Seven trunk tiers plus the web-only Logistics and Boarding
        # Ship tiers
        assert len(VICTIMS_LABELS) == 9
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
    stack.token.initial_armor = armor
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
        # Twice the runner's mass: the wolf always moves first (the
        # 15% mass juggle cannot swap a 2:1 gap), so every distance
        # the runner reads below is deterministic
        wolf.token.mass = 200

        # Out of range: the stack closes. The wolf moves first in the
        # same pass (200 -> 300), so the runner sees distance 500 > 400
        runner.position = NovaPoint(800, 200)
        engine._select_targets(stacks)
        engine._move_stacks(stacks, 5, battle)
        assert runner.position.x < 800

        # Inside the hold band [0.9 * 400, 400] of its own longest
        # weapon range (4 * GRID_SCALE): hold. The wolf moves 200 ->
        # 300 first, so the runner reads distance 380
        wolf.position = NovaPoint(200, 200)
        runner.position = NovaPoint(680, 200)
        engine._select_targets(stacks)
        engine._move_stacks(stacks, 6, battle)
        assert (runner.position.x, runner.position.y) == (680, 200)

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


class TestEngagementRange:
    """The engagement-range decision
    (docs/research-engagement-range.md, panel-refined shape): the
    stand-off tactics keep their band BOTH ways on the existing tactic
    field, Maximise Net Damage holds where all weapons bear, and the
    web-only Salvo then Close commits to the run-in once its target
    breaks."""

    def _setup(self, tactic, runner_x=680, wolf_x=200, runner_range=4):
        server = MockServerData()
        for i in range(2):
            empire = MockEmpire(id=i)
            empire.battle_plans["Default"] = BattlePlan(attack="Everyone")
            server.all_empires[i] = empire
        server.all_empires[1].battle_plans["Custom"] = BattlePlan(
            name="Custom", tactic=tactic, attack="Everyone")
        engine = RonBattleEngine(server, [])

        # Twice the runner's mass: the wolf always moves first (the
        # 15% mass juggle cannot swap a 2:1 gap), so every distance
        # the runner reads is deterministic. Wolf speed 1.0 closes
        # GRID_SCALE = 100 units per round
        wolf = _make_battle_stack(0, 1, wolf_x, 200, mass=200)
        runner = _make_battle_stack(1, 2, runner_x, 200,
                                    shields=50.0,
                                    weapon_range=runner_range,
                                    battle_plan="Custom")
        return engine, [wolf, runner], wolf, runner

    def _round(self, engine, stacks, battle_round, battle):
        engine._select_targets(stacks)
        engine._move_stacks(stacks, battle_round, battle)

    # -- 1: two-way range maintenance (give-ground restoration) ------

    @pytest.mark.parametrize("tactic", ["Maximise Net Damage",
                                        "Maximise Damage Ratio",
                                        "Minimise Damage to Self"])
    def test_gives_ground_when_the_target_presses_inside(self, tactic):
        """Canon maintains the band both ways
        (docs/research-battle-doctrine.md:39): a stand-off stack whose
        target closes inside its band steps AWAY along the closing
        vector instead of watching it walk into contact."""
        engine, stacks, wolf, runner = self._setup(tactic, runner_x=450)
        battle = BattleReport()

        # Wolf 200 -> 300; the runner reads distance 150, well inside
        # 0.9 * 400, and gives ground a full step (+100)
        self._round(engine, stacks, 5, battle)
        assert (runner.position.x, runner.position.y) == (550, 200)

        # Giving ground is NOT disengaging: no flee moves accumulate
        # and no withdrawal is ever reported
        # (docs/research-engagement-range.md:44)
        assert runner.flee_rounds == 0
        assert runner.disengaged is False
        assert not [s for s in battle.steps
                    if isinstance(s, BattleStepWithdraw)]

    def test_closes_when_beyond_the_hold_range(self):
        engine, stacks, wolf, runner = self._setup(
            "Maximise Damage Ratio", runner_x=800)
        battle = BattleReport()

        # Wolf 200 -> 300; distance 500 > 400: the runner closes
        self._round(engine, stacks, 5, battle)
        assert (runner.position.x, runner.position.y) == (700, 200)

    def test_give_ground_stops_at_the_board_wall(self):
        """The wall is what keeps kiting beatable: uncapped retreat
        measured +0.04 for the pursuer against +0.72 wall-clamped
        (docs/research-engagement-range.md:345-352)."""
        engine, stacks, wolf, runner = self._setup(
            "Maximise Damage Ratio", wolf_x=700, runner_x=980)
        battle = BattleReport()

        # Wolf 700 -> 800; distance 180 < 360: the give-ground step
        # (980 + 100) is clamped at the 1000-unit board edge
        self._round(engine, stacks, 5, battle)
        assert (runner.position.x, runner.position.y) == (1000, 200)

        # Pressed against the wall, the stack stands instead of
        # leaving the board
        self._round(engine, stacks, 6, battle)
        assert (runner.position.x, runner.position.y) == (1000, 200)
        assert runner.flee_rounds == 0

    def test_approach_lands_on_the_band_not_past_it(self):
        """A closing stand-off step is capped ON the band: uncapped, a
        full battle-speed step (100 units) leapfrogs the 30-unit
        deadband entirely and two stand-off stacks bounce in and out
        of each other's range forever, firing almost never (measured
        as a 250-a-side mirror freezing at 9 volleys in 60 rounds)."""
        engine, stacks, wolf, runner = self._setup(
            "Maximise Damage Ratio", runner_x=650)
        wolf.token.is_starbase = True  # an immobile threat
        battle = BattleReport()

        # Distance 450 > 400: the step is capped at distance - 0.9R =
        # 90, landing exactly on the band floor instead of at 550
        self._round(engine, stacks, 5, battle)
        assert (runner.position.x, runner.position.y) == (560, 200)

        # In band: the stack stands, and keeps standing
        self._round(engine, stacks, 6, battle)
        assert (runner.position.x, runner.position.y) == (560, 200)

    def test_give_ground_backs_off_to_the_band_edge_only(self):
        """A give-ground step is capped at R - distance: back to
        maximum range - "try to stay at maximum range",
        docs/research-battle-doctrine.md:39 - and no further, so the
        stack keeps firing while it keeps its distance."""
        engine, stacks, wolf, runner = self._setup(
            "Maximise Damage Ratio", runner_x=520)
        wolf.token.is_starbase = True
        battle = BattleReport()

        # Distance 320 < 360: the give-ground step is capped at 80,
        # landing on the band's outer edge instead of at 620
        self._round(engine, stacks, 5, battle)
        assert (runner.position.x, runner.position.y) == (600, 200)
        self._round(engine, stacks, 6, battle)
        assert (runner.position.x, runner.position.y) == (600, 200)

    # -- 2: the min/max hold-range split -----------------------------

    def test_net_damage_holds_where_all_weapons_bear(self):
        """Maximise Net Damage holds at the SHORTEST mounted range -
        the range where ALL weapons bear
        (docs/research-battle-doctrine.md:39) - so a mixed battery
        keeps closing until its short guns come up."""
        engine, stacks, wolf, runner = self._setup(
            "Maximise Net Damage", runner_x=680)
        runner.token.design.weapons = [MockWeapon(range=1),
                                       MockWeapon(range=4)]
        battle = BattleReport()

        # Wolf 200 -> 300; distance 380 is far beyond the 1-square
        # hold range, so the runner closes - under the old max() bug
        # it halted here and the range-1 gun never fired
        # (docs/research-engagement-range.md:19)
        self._round(engine, stacks, 5, battle)
        assert (runner.position.x, runner.position.y) == (580, 200)

    def test_damage_ratio_holds_at_the_longest_range(self):
        """Maximise Damage Ratio 'only considers the longest range
        weapon' (docs/research-engagement-range.md:17): the same mixed
        battery at the same distance holds."""
        engine, stacks, wolf, runner = self._setup(
            "Maximise Damage Ratio", runner_x=680)
        runner.token.design.weapons = [MockWeapon(range=1),
                                       MockWeapon(range=4)]
        battle = BattleReport()

        # Wolf 200 -> 300; distance 380 sits inside [360, 400]
        self._round(engine, stacks, 5, battle)
        assert (runner.position.x, runner.position.y) == (680, 200)

    # -- 3: Salvo then Close -----------------------------------------

    def test_salvo_holds_at_longest_range_before_the_trigger(self):
        engine, stacks, wolf, runner = self._setup(
            "Salvo then Close", runner_x=680)
        battle = BattleReport()

        # Wolf at full armour: no commitment, hold like Maximise
        # Damage Ratio (distance 380 inside [360, 400])
        self._round(engine, stacks, 5, battle)
        assert (runner.position.x, runner.position.y) == (680, 200)
        assert wolf.key not in runner.salvo_committed

    def test_salvo_commits_at_half_armour_and_stays_committed(self):
        engine, stacks, wolf, runner = self._setup(
            "Salvo then Close", runner_x=680)
        battle = BattleReport()

        # Armour at exactly the threshold (100 of 200 = 50%): the
        # trigger fires ("falls to or below",
        # docs/research-engagement-range.md:51) and the stack closes
        wolf.token.armor = 100.0
        self._round(engine, stacks, 5, battle)
        assert wolf.key in runner.salvo_committed
        assert (runner.position.x, runner.position.y) == (580, 200)

        # The report shows WHY the fleet closed: the switch round's
        # movement step carries the motive
        moves = [s for s in battle.steps
                 if isinstance(s, BattleStepMovement)
                 and s.stack_key == runner.key]
        assert moves[-1].motive == \
            "closing for the kill - target below 50% armour"

        # One-way per target: even with the armour reading back above
        # the threshold the commitment holds for the rest of the
        # battle. Wolf 300 -> 400, runner 580 -> 480 keeps closing
        wolf.token.armor = 200.0
        self._round(engine, stacks, 6, battle)
        assert (runner.position.x, runner.position.y) == (480, 200)

    def test_salvo_commits_when_the_target_disengages(self):
        """The second trigger: a broken enemy walking off the board is
        the one case where closing is unambiguously right
        (docs/research-engagement-range.md:59)."""
        engine, stacks, wolf, runner = self._setup(
            "Salvo then Close", runner_x=680)
        battle = BattleReport()

        wolf.flee_rounds = 1
        self._round(engine, stacks, 5, battle)
        assert wolf.key in runner.salvo_committed
        assert (runner.position.x, runner.position.y) == (580, 200)
        moves = [s for s in battle.steps
                 if isinstance(s, BattleStepMovement)
                 and s.stack_key == runner.key]
        assert moves[-1].motive == \
            "closing for the kill - target disengaging"


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


# =============================================================================
# Beam Range Dissipation (DEF-24) and Initiative Order (DEF-25)
# =============================================================================

class TestBeamRangeDissipation:
    """Beam damage falls off with range, so closing beats standing off.

    Canon (BATTLE.TXT, quoted in docs/research-battle-doctrine.md):
    a beam does full damage in the target's own square and loses 10
    percent of its damage at the weapon's maximum range.
    """

    SCALE = RonBattleEngine.GRID_SCALE

    def _attack_at(self, separation, weapon_range=3):
        """One beam attack with the target `separation` squares away."""
        attacker = Stack()
        attacker.key = 1
        attacker.owner = 0
        attacker.position = NovaPoint(0, 0)
        attacker.token = StackToken()
        attacker.token.design = MockDesign()
        attacker.token.quantity = 1
        attacker.token.armor = 10000.0
        attacker.token.shields = 10000.0

        target = Stack()
        target.key = 2
        target.owner = 1
        target.position = NovaPoint(int(separation * self.SCALE), 0)
        target.token = StackToken()
        target.token.design = MockDesign()
        target.token.quantity = 1
        # Deep shields so all damage lands in a single shields step
        target.token.armor = 10000.0
        target.token.shields = 10000.0

        attack = WeaponDetails()
        attack.source_stack = attacker
        attack.target_stack = TargetPercent(target, 100)
        attack.weapon = MockWeapon(power=100, range=weapon_range)
        return attack

    def _damage_at(self, separation, weapon_range=3):
        engine = RonBattleEngine(MockServerData(), [])
        battle = BattleReport()
        engine._execute_attack(self._attack_at(separation, weapon_range),
                               battle)
        return sum(s.damage for s in battle.steps
                   if isinstance(s, BattleStepWeapons))

    def test_point_blank_beam_does_full_damage(self):
        assert self._damage_at(0) == pytest.approx(100.0)

    def test_beam_at_range_does_strictly_less_than_point_blank(self):
        assert self._damage_at(3) < self._damage_at(0)
        assert self._damage_at(1) < self._damage_at(0)

    def test_falloff_matches_canonical_curve_at_each_step(self):
        """Range-3 beam: dispersal is 100 - 10 * (d / range)^2 percent,
        so 100 / 98.888 / 95.555 / 90 percent at 0 / 1 / 2 / 3 squares."""
        for separation, percent in ((0, 100.0), (1, 100 - 10 / 9),
                                    (2, 100 - 40 / 9), (3, 90.0)):
            assert self._damage_at(separation) == \
                pytest.approx(percent, rel=1e-9)

    def test_falloff_is_strictly_decreasing_in_range(self):
        damages = [self._damage_at(d) for d in range(4)]
        assert all(a > b for a, b in zip(damages, damages[1:]))

    def test_max_range_loses_ten_percent_for_every_weapon_range(self):
        """The 10 percent loss is across the weapon's full range, so a
        range-1 and a range-4 beam both do 90 percent at their max."""
        for weapon_range in (1, 2, 3, 4):
            assert self._damage_at(weapon_range, weapon_range) == \
                pytest.approx(90.0)


class TestInitiativeOrder:
    """Weapons fire highest initiative first (BATTLE.TXT round order)."""

    def _shooter(self, key, initiative, target):
        stack = Stack()
        stack.key = key
        stack.owner = 0
        stack.position = NovaPoint(0, 0)
        stack.token = StackToken()
        stack.token.design = MockDesign(
            weapons=[MockWeapon(power=10, range=3, initiative=initiative)])
        stack.token.quantity = 1
        stack.token.armor = 100.0
        stack.token.shields = 0.0
        stack.target_list = [target]
        return stack

    def test_high_initiative_fires_before_low(self):
        target = Stack()
        target.key = 9
        target.owner = 1
        target.position = NovaPoint(0, 0)
        target.token = StackToken()
        target.token.design = MockDesign(weapons=[])
        target.token.quantity = 1
        target.token.armor = 1000.0
        target.token.shields = 0.0

        slow = self._shooter(1, 10, target)
        fast = self._shooter(2, 200, target)

        engine = RonBattleEngine(MockServerData(), [])
        # Source order puts the slow weapon first, so only the sort
        # can put the fast one at the front
        attacks = engine._generate_attacks([slow, fast, target])

        initiatives = [a.weapon.initiative for a in attacks]
        assert initiatives == [200, 10]
        assert attacks[0].source_stack.key == fast.key


class TestBattleReportYear:
    """Every battle report carries the year it was fought (DEF-23)."""

    def _one_battle_report(self, engine_class):
        server = MockServerData()
        server.turn_year = 2455

        for i in range(2):
            empire = MockEmpire(id=i, turn_year=2455)
            empire.battle_plans["Default"] = BattlePlan(attack="Everyone")
            empire.empire_reports[1 - i] = {"relation": "Enemy"}

            design = MockDesign(key=1, name="Warship",
                                weapons=[MockWeapon(power=10, range=3)])
            empire.designs[1] = design

            fleet = Fleet()
            fleet.key = empire.get_next_fleet_key()
            fleet.owner = i
            fleet.name = f"Battle Fleet {i}"
            fleet.position = NovaPoint(100, 100)
            fleet.battle_plan = "Default"

            token = ShipToken()
            token.design_key = 1
            token.design_name = "Warship"
            token.quantity = 5
            token.armor = 100
            token.shields = 50
            # Non-zero mass so the standard engine's attractiveness
            # (cost / defences) is above zero and a target is picked
            token.mass = 100
            token.has_weapons = True
            fleet.tokens[token.design_key] = token

            empire.owned_fleets[fleet.key] = fleet
            server.all_empires[i] = empire

        reports: List[BattleReport] = []
        engine_class(server, reports).run()
        return reports

    def test_ron_engine_stamps_the_turn_year(self):
        reports = self._one_battle_report(RonBattleEngine)
        assert reports
        assert all(r.year == 2455 for r in reports)

    def test_standard_engine_stamps_the_turn_year(self):
        reports = self._one_battle_report(BattleEngine)
        assert reports
        assert all(r.year == 2455 for r in reports)


class TestDamageSurvivesTheBattleBoundary:
    """
    Armour lost in battle 1 is the armour battle 2 starts with (DEF-34).

    Canon holds the fleet's own token by reference (Stack.cs:125), so
    damage persists for free. The web port copies the token into a
    StackToken, so from_ship_token must read damage_percent back or
    every fleet enters every battle at full armour.
    """

    def _fleet_in_a_server(self, armor=200, quantity=3):
        server = MockServerData()
        empire = MockEmpire(id=1)
        server.all_empires[1] = empire

        fleet = Fleet()
        fleet.key = empire.get_next_fleet_key()
        fleet.owner = 1
        fleet.position = NovaPoint(100, 100)
        token = ShipToken(design_key=7, design_name="Warship",
                          quantity=quantity, armor=armor, shields=50,
                          mass=100, has_weapons=True)
        fleet.tokens[token.design_key] = token
        empire.owned_fleets[fleet.key] = fleet
        return server, fleet, token

    def test_battle_two_starts_at_battle_one_exit_armor(self):
        server, fleet, token = self._fleet_in_a_server()
        engine = RonBattleEngine(server, [])

        stack = Stack.from_fleet(fleet, 1, token)
        assert stack.token.armor == 600.0  # full at first contact

        # Battle 1 shoots the pool down to 350, engine writes it back
        stack.token.armor = 350.0
        engine._write_back_damage([stack])

        # Battle 2 rebuilds the stack from the fleet token
        second = Stack.from_fleet(fleet, 2, token)
        assert second.token.armor == pytest.approx(350.0)
        assert second.token.initial_armor == pytest.approx(350.0)

    def test_a_fleet_that_fights_nobody_twice_does_not_decay(self):
        server, fleet, token = self._fleet_in_a_server()
        token.damage_percent = 40.0
        engine = RonBattleEngine(server, [])

        for stack_id in (1, 2):
            stack = Stack.from_fleet(fleet, stack_id, token)
            assert stack.token.armor == pytest.approx(360.0)
            # No shot fired; the write-back must be a no-op
            engine._write_back_damage([stack])
            assert token.damage_percent == pytest.approx(40.0)


class TestPerShipAttrition:
    """
    Enough armour damage kills whole ships out of a token (DEF-35).

    The rule the C# reference names for itself and declines
    (BattleEngine.cs:857 and :713, both in its BUGS.txt), and the one
    mines and storms already apply. surviving = ceil(armor / per_ship);
    the shield pool scales with the survivors so dead ships stop
    shielding, and the kills land in battle.losses as they happen.
    """

    def _stack(self, owner=1, quantity=7, per_ship_armor=250.0,
               shields=700.0):
        stack = Stack()
        stack.key = (owner << 32) | 1
        stack.owner = owner
        stack.token = StackToken()
        stack.token.design_key = 7
        stack.token.quantity = quantity
        stack.token.initial_quantity = quantity
        stack.token.armor = per_ship_armor * quantity
        stack.token.initial_armor = per_ship_armor * quantity
        stack.token.shields = shields
        return stack

    def test_armor_damage_kills_whole_ships_and_scales_shields(self):
        engine = RonBattleEngine(MockServerData(), [])
        attacker = self._stack(owner=2)
        target = self._stack(owner=1)
        battle = BattleReport()

        # 600 off a 1750 pool leaves 1150: ceil(1150/250) = 5 survive
        engine._damage_armor(attacker, target, 600.0, battle)
        assert target.token.quantity == 5
        assert target.token.shields == pytest.approx(700.0 * 5 / 7)
        assert battle.losses[1] == 2

        # 149 more does not cross the next 250 boundary
        engine._damage_armor(attacker, target, 149.0, battle)
        assert target.token.quantity == 5
        assert battle.losses[1] == 2

    def test_annihilation_counts_every_ship_exactly_once(self):
        engine = RonBattleEngine(MockServerData(), [])
        attacker = self._stack(owner=2)
        target = self._stack(owner=1)
        battle = BattleReport()

        engine._damage_armor(attacker, target, 1750.0, battle)
        assert target.token.quantity == 0
        assert target.token.shields == 0.0
        assert battle.losses[1] == 7
        assert target.is_destroyed

    def test_kills_land_on_the_fleet_token_at_write_back(self):
        server = MockServerData()
        empire = MockEmpire(id=1)
        server.all_empires[1] = empire

        fleet = Fleet()
        fleet.key = empire.get_next_fleet_key()
        fleet.owner = 1
        fleet.position = NovaPoint(100, 100)
        token = ShipToken(design_key=7, design_name="Warship",
                          quantity=7, armor=250, shields=100,
                          mass=100, has_weapons=True)
        fleet.tokens[token.design_key] = token
        empire.owned_fleets[fleet.key] = fleet

        engine = RonBattleEngine(server, [])
        stack = Stack.from_fleet(fleet, 1, token)
        attacker = self._stack(owner=2)
        battle = BattleReport()

        # 1200 off the 1750 pool: 550 left, ceil(550/250) = 3 survive
        # carrying 550 of their 750 -> 26.67% damage
        engine._damage_armor(attacker, stack, 1200.0, battle)
        engine._write_back_damage([stack])

        assert token.quantity == 3
        assert token.damage_percent == pytest.approx(100.0 * (1 - 550 / 750))


class TestClosingMoveDoesNotOvershoot:
    """
    A stack closing on a target lands on it, never past it.

    Canonical: PointUtilities.BattleMoveTo:224-247 steps an axis only
    while it is strictly farther away, so a closing stack converges and
    stops. The Ron engine moves a fixed-length vector instead, so
    without the cap two stacks closing on each other jump past one
    another every round and the engagement drifts across the board at
    full battle speed - which is the mechanism behind DEF-30.
    """

    def _pair(self, gap, battle_speed=1.0):
        server = MockServerData()
        for i in range(2):
            empire = MockEmpire(id=i)
            empire.battle_plans["Default"] = BattlePlan(attack="Everyone")
            server.all_empires[i] = empire
        engine = RonBattleEngine(server, [])
        left = _make_battle_stack(0, 1, 0, 0, battle_speed=battle_speed)
        right = _make_battle_stack(1, 2, gap, 0, battle_speed=battle_speed)
        return engine, [left, right], left, right

    def test_a_closing_stack_stops_on_its_target(self):
        """One battle speed is GRID_SCALE units of movement, so a stack
        25 units from its target must close 25, not 100.

        The scenario needs LEFT to move first: at equal masses the
        _move_order juggle makes that a coin flip, and when right won
        it, right closed onto left instead and left (already in
        contact) rightly stayed at 0 - a flake in the expectation, not
        the engine. Masses more than 30 percent apart never swap
        (ron_battle_engine.py _move_order), so the heavier left always
        moves first and the assertion is deterministic."""
        engine, stacks, left, right = self._pair(25)
        left.token.mass = 200
        battle = BattleReport()
        engine._select_targets(stacks)

        # Round 5+ is past the opening random-flip rounds
        engine._move_stacks(stacks, 5, battle)

        assert left.position.x == 25, (
            f"closing stack jumped to {left.position.x}, past its target "
            f"at 25")

    def test_two_closing_stacks_do_not_drift_across_the_board(self):
        """The bias mechanism itself: once in contact, a pair that
        leapfrogs travels a full battle speed every round in the
        direction the first mover was heading, dragging the engagement
        away from every stack still catching up."""
        engine, stacks, left, right = self._pair(25)
        battle = BattleReport()

        for battle_round in range(5, 25):
            engine._select_targets(stacks)
            engine._move_stacks(stacks, battle_round, battle)

        span = engine.GRID_SCALE
        assert abs(left.position.x) <= span and abs(right.position.x) <= span, (
            f"pair drifted to {left.position.x} / {right.position.x} after "
            f"20 rounds; the engagement should stay where it was joined")

    def _runner(self, gap):
        server = MockServerData()
        for i in range(2):
            empire = MockEmpire(id=i)
            empire.battle_plans["Default"] = BattlePlan(attack="Everyone")
            server.all_empires[i] = empire
        server.all_empires[1].battle_plans["Run"] = BattlePlan(
            name="Run", tactic="Disengage", attack="Everyone")
        engine = RonBattleEngine(server, [])

        wolf = _make_battle_stack(0, 1, 0, 0)
        runner = _make_battle_stack(1, 2, gap, 0, battle_plan="Run")
        return engine, [wolf, runner], wolf, runner

    def test_a_fleeing_stack_still_runs_at_full_speed(self):
        """The cap applies to closing only - nothing is overshot by
        moving away, so a disengaging stack keeps its legs."""
        engine, stacks, wolf, runner = self._runner(400)
        engine._select_targets(stacks)
        engine._move_stacks(stacks, 5, BattleReport())

        # The wolf closed one battle speed to 100; the runner broke off
        # a full battle speed from where the wolf now is
        assert wolf.position.x == engine.GRID_SCALE
        assert runner.position.x == 400 + engine.GRID_SCALE

    def test_a_stack_run_down_in_its_own_square_still_breaks_off(self):
        """A capped closing step lands the wolf ON the runner, so
        there is no "away" left to point at. Canon covers it - a token
        that can neither open nor hold the range moves to a random
        square (Guts of the Battle Engine) - and without that the
        runner would be pinned and could never disengage.

        The run-down only happens if the wolf moves BEFORE the runner
        breaks off; at equal masses the _move_order juggle makes that
        a coin flip and the runner escaping first is a different (and
        untested) scenario. Masses more than 30 percent apart never
        swap (ron_battle_engine.py _move_order), so the heavier wolf
        always moves first and the run-down is deterministic."""
        engine, stacks, wolf, runner = self._runner(25)
        wolf.token.mass = 200
        engine._select_targets(stacks)
        engine._move_stacks(stacks, 5, BattleReport())

        assert wolf.position.x == 25, "the wolf should stop on the runner"
        assert (runner.position.x, runner.position.y) != (25, 0), \
            "a run-down stack is pinned and can never disengage"
        assert runner.flee_rounds == 1
