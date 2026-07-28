"""
Boarding: universal capability, components, the hull class, and the
battle action itself.

Web-only extension (user directive - "add boarding ships and boarding
battle plans - to take over ships - but at great risk to self", "every
ship can have it, but we must have some components that make it
better", "and we can have special class of boarding ships too"). The
C# reference has no boarding of any kind, so there is no canon to
match - only the acc-crit contract and the balance bar.
"""

import random
from dataclasses import dataclass, field
from typing import Dict, List

import pytest

from backend.core.components.boarding import (
    BOARDER_MULTIPLIER_THRESHOLD,
    BOARDING_CREW_PER_SLOT,
    BOARDING_CREW_PER_TROOP_BAY,
    BOARDING_MULTIPLIER_MAXIMUM,
    base_boarding_strength,
    is_boarding_specialist,
)
from backend.core.components.ship_role import (
    ShipRole, battle_role_of, infer_battle_role)
from backend.core.data_structures import NovaPoint
from backend.core.data_structures.empire_data import EmpireData
from backend.core.data_structures.tech_level import TechLevel
from backend.core.game_objects import Fleet, ShipToken
from backend.server.battle import BattleReport, RonBattleEngine
from backend.server.battle.battle_plan import (
    BOARDING_FAILURE_ARMOR_PERCENT,
    BOARDING_MAX_CHANCE,
    BOARDING_MIN_CHANCE,
    BOARDING_ORDERS,
    BOARDING_PRIZE_DAMAGE_PERCENT,
    BattlePlan,
    VICTIMS_LABELS,
    Victims,
)
from backend.server.battle.stack import Stack
from backend.services.design_builder import build_ship_design
from backend.services.ship_specs import SimpleDesign, make_token

from .test_battle_engine import MockDesign, MockEmpire, MockWeapon

ENGINE_SLOT = {"cell_number": 1, "component": "Long Hump 6", "count": 1}


@pytest.fixture
def designer_empire():
    """An empire with enough research to build anything in the catalog."""
    empire = EmpireData()
    empire.id = 1
    empire.research_levels = TechLevel.from_values(30, 30, 30, 30, 30, 30)
    return empire


def _design(empire, name, hull, slots):
    design, error = build_ship_design(empire, name, hull, slots)
    assert error is None, error
    return design


def _troop_bays(count, component="Marine Barracks"):
    return [ENGINE_SLOT] + [
        {"cell_number": cell, "component": component, "count": 1}
        for cell in range(3, 3 + count)
    ]


class TestUniversalBoardingCapability:
    """Every ship musters a party from what it already is."""

    def test_strength_is_computed_from_hull_size(self):
        assert base_boarding_strength(3) == 3 * BOARDING_CREW_PER_SLOT
        assert base_boarding_strength(13) == 13 * BOARDING_CREW_PER_SLOT
        # A troop bay is a slot AND carries marines of its own
        assert base_boarding_strength(11, 6) == (
            11 * BOARDING_CREW_PER_SLOT + 6 * BOARDING_CREW_PER_TROOP_BAY)

    def test_a_dreadnought_crew_outmuscles_a_scout_crew(self, designer_empire):
        scout = _design(designer_empire, "Picket", "Scout",
                        [{"cell_number": 11, "component": "Long Hump 6",
                          "count": 1}])
        heavy = _design(designer_empire, "Line", "Cruiser",
                        [{"cell_number": 10, "component": "Long Hump 6",
                          "count": 1}])
        assert scout.base_boarding_strength == 30
        assert heavy.base_boarding_strength == 70
        assert heavy.boarding_strength > scout.boarding_strength

    def test_every_armed_ship_can_board_without_a_fitting(
            self, designer_empire):
        """No special component is required: a bare warship has a party
        and a bare warship's odds against another are a coin flip."""
        bare = _design(designer_empire, "Bare", "Cruiser",
                       [{"cell_number": 10, "component": "Long Hump 6",
                         "count": 1}])
        assert bare.boarding_multiplier == 1.0
        assert bare.boarding_strength == bare.base_boarding_strength > 0

    def test_a_starting_design_has_a_party_from_its_hull(self):
        """SimpleDesign derives the party from the catalog hull it
        names, so nothing has to be persisted or migrated."""
        scout = SimpleDesign(name="Long Range Scout", hull_name="Scout")
        assert scout.base_boarding_strength == 30
        assert scout.boarding_strength == 30.0
        assert SimpleDesign(name="Nameless").base_boarding_strength == 0


class TestBoardingComponents:
    """Fittable gear multiplies the party and costs slots and mass."""

    def test_the_catalog_ships_three_boarding_components(self):
        from backend.services.design_builder import ensure_components_loaded
        loader = ensure_components_loaded()
        for name, value, mass in (("Breaching Gear", 1.25, 10),
                                  ("Assault Pod", 1.4, 20),
                                  ("Marine Barracks", 1.6, 35)):
            component = loader.get_component(name)
            assert component is not None, name
            assert component.get_property("Boarding").values["Value"] == value
            assert component.mass == mass

    def test_gear_multiplies_and_stacks_geometrically(self, designer_empire):
        one = _design(designer_empire, "One", "Assault Transport",
                      _troop_bays(1))
        two = _design(designer_empire, "Two", "Assault Transport",
                      _troop_bays(2))
        three = _design(designer_empire, "Three", "Assault Transport",
                        _troop_bays(3))
        assert one.boarding_multiplier == pytest.approx(1.6)
        assert two.boarding_multiplier == pytest.approx(1.6 ** 2)
        assert three.boarding_multiplier == pytest.approx(1.6 ** 3)

    def test_the_multiplier_is_clamped(self, designer_empire):
        full = _design(designer_empire, "Full", "Assault Transport",
                       _troop_bays(6))
        assert full.boarding_multiplier == BOARDING_MULTIPLIER_MAXIMUM

    def test_gear_costs_slots_and_mass(self, designer_empire):
        """The trade: a boarder buys capture capability with the mass
        and the slots that would otherwise be combat capability."""
        bare = _design(designer_empire, "Bare", "Assault Transport",
                       [ENGINE_SLOT])
        armed = _design(designer_empire, "Fitted", "Assault Transport",
                        _troop_bays(4))
        assert armed.mass > bare.mass
        assert armed.cost.energy > bare.cost.energy

    def test_gear_fits_a_general_purpose_slot_on_any_hull(
            self, designer_empire):
        """Universal capability plus components: a plain warship hull
        can fit boarding gear, and pays a general purpose slot for it."""
        raider = _design(designer_empire, "Raider", "Privateer", [
            {"cell_number": 10, "component": "Long Hump 6", "count": 1},
            {"cell_number": 6, "component": "Marine Barracks", "count": 1},
            {"cell_number": 16, "component": "Marine Barracks", "count": 1},
        ])
        assert raider.mass > _design(
            designer_empire, "Plain", "Privateer",
            [{"cell_number": 10, "component": "Long Hump 6",
              "count": 1}]).mass
        assert raider.boarding_multiplier == pytest.approx(1.6 ** 2)


class TestBoardingShipClass:
    """The dedicated hull, and the role cascade that names it."""

    def test_the_hull_carries_boarding_only_troop_bays(self):
        from backend.core.components.boarding import TROOP_BAY_SLOT
        from backend.services.design_builder import (
            ensure_components_loaded, slot_accepts)
        from backend.core.game_objects.item import ItemType

        loader = ensure_components_loaded()
        hull = loader.get_component("Assault Transport")
        modules = hull.get_property("Hull").values["modules"]
        bays = [m for m in modules
                if m["component_type"] == TROOP_BAY_SLOT]
        assert len(bays) == 6
        # Boarding only - a troop bay takes no weapon, armour or engine
        assert slot_accepts(TROOP_BAY_SLOT, ItemType.BOARDING)
        for rejected in (ItemType.BEAM_WEAPONS, ItemType.ARMOR,
                         ItemType.SHIELD, ItemType.ENGINE):
            assert not slot_accepts(TROOP_BAY_SLOT, rejected)

    def test_the_hull_has_high_crew_and_poor_firepower(
            self, designer_empire):
        """High crew capacity, one weapon mount: it takes ships rather
        than killing them."""
        from backend.services.design_builder import ensure_components_loaded
        loader = ensure_components_loaded()
        modules = loader.get_component(
            "Assault Transport").get_property("Hull").values["modules"]
        weapon_capable = [m for m in modules
                          if "General Purpose" in m["component_type"]
                          or "Weapon" in m["component_type"]]
        assert len(weapon_capable) == 1

        assault = _design(designer_empire, "Assault", "Assault Transport",
                          [ENGINE_SLOT])
        heavy = _design(designer_empire, "Heavy", "Cruiser",
                        [{"cell_number": 10, "component": "Long Hump 6",
                          "count": 1}])
        assert assault.base_boarding_strength > heavy.base_boarding_strength

    def test_the_role_cascade_names_boarding_ships(self):
        assert ShipRole.BOARDER == "Boarding Ship"
        assert infer_battle_role(is_boarder=True) == ShipRole.BOARDER
        # A specialisation this deep outranks what the ship is armed
        # with, so an anti-capital order stops covering it
        assert infer_battle_role(is_boarder=True, has_weapons=True,
                                 power_rating=99999) == ShipRole.BOARDER
        # But not a starbase or a bomber, which are earlier in the chain
        assert infer_battle_role(is_boarder=True,
                                 is_starbase=True) == ShipRole.STARBASE
        assert infer_battle_role(is_boarder=True,
                                 is_bomber=True) == ShipRole.BOMBER

    def test_a_fitted_boarder_classifies_as_one(self, designer_empire):
        light = _design(designer_empire, "Light", "Assault Transport",
                        _troop_bays(2))
        heavy = _design(designer_empire, "Heavy", "Assault Transport",
                        _troop_bays(4))
        # One or two components is a fitting, not a class
        assert not light.is_boarder
        assert battle_role_of(light) != ShipRole.BOARDER
        assert heavy.is_boarder
        assert battle_role_of(heavy) == ShipRole.BOARDER
        assert is_boarding_specialist(BOARDER_MULTIPLIER_THRESHOLD)

    def test_target_class_orders_can_name_boarders(self):
        assert VICTIMS_LABELS[Victims.BOARDER] == "Boarding Ship"


# --------------------------------------------------------------------
# The battle action
# --------------------------------------------------------------------

@dataclass
class BoardingEmpire(MockEmpire):
    """MockEmpire plus the design-key allocator a capture needs."""
    _design_counter: int = 100

    def get_next_design_key(self) -> int:
        self._design_counter += 1
        return self._design_counter | (self.id << 32)


@dataclass
class BoardingServer:
    """ServerData surface the engine and the boarding layer read."""
    all_empires: Dict = field(default_factory=dict)
    all_stars: Dict = field(default_factory=dict)
    all_minefields: Dict = field(default_factory=dict)
    all_messages: List = field(default_factory=list)
    turn_year: int = 2400

    def iterate_all_fleets(self):
        for empire in self.all_empires.values():
            yield from empire.owned_fleets.values()


def _hold_plan():
    """The other side's plan: it shoots, it never boards, so a test
    measures exactly one boarding party."""
    return _boarding_plan(name="Hold", board="Never")


def _boarding_plan(name="Board", **axes):
    plan = BattlePlan.from_dict({
        "name": name,
        "primary_target": int(Victims.ANY_SHIP),
        "secondary_target": int(Victims.ANY_SHIP),
        "tertiary_target": int(Victims.ANY_SHIP),
        "quaternary_target": int(Victims.ANY_SHIP),
        "quinary_target": int(Victims.ANY_SHIP),
        "attack": "Everyone",
        "board": "When Able",
        **axes,
    })
    return plan


def _make_fleet(empire, plan_name, *, boarding_strength, quantity=1,
                armor=200, shields=0, armed=True, name="Ship"):
    design = MockDesign(key=empire.id * 10 + len(empire.designs) + 1,
                        name=f"{name} {empire.id}", mass=100,
                        battle_speed=1.0, has_weapons=armed,
                        power_rating=1000)
    design.weapons = [MockWeapon(power=20, range=2, initiative=5)] \
        if armed else []
    design.boarding_strength = boarding_strength
    empire.designs[design.key] = design

    fleet = Fleet()
    fleet.key = empire.get_next_fleet_key()
    fleet.owner = empire.id
    fleet.name = f"{design.name} fleet"
    fleet.position = NovaPoint(500.0, 500.0)
    fleet.battle_plan = plan_name
    fleet.tokens[design.key] = ShipToken(
        design_key=design.key, design_name=design.name, quantity=quantity,
        armor=armor, shields=shields, mass=100, has_weapons=armed,
        boarding_strength=boarding_strength)
    empire.owned_fleets[fleet.key] = fleet
    return fleet, design


def _engine_for(plans, seed=1):
    server = BoardingServer()
    for empire_id, plan in plans.items():
        empire = BoardingEmpire(id=empire_id)
        empire.battle_plans[plan.name] = plan
        server.all_empires[empire_id] = empire
    engine = RonBattleEngine(server, [])
    engine._random = random.Random(seed)
    return server, engine


def _adjacent_stacks(engine, fleets):
    """Stacks placed in one square, which is what a boarding attempt
    needs (the engine's movement converges there on its own)."""
    battle = BattleReport()
    stacks = engine._generate_stacks(fleets, NovaPoint(500.0, 500.0))
    engine._position_stacks(stacks, battle)
    for stack in stacks:
        stack.position = NovaPoint(500.0, 500.0)
    engine._select_targets(stacks)
    return stacks, battle


class TestBoardingOdds:
    """The success probability model."""

    def test_a_like_for_like_attempt_is_a_coin_flip(self):
        _, engine = _engine_for({1: _boarding_plan(), 2: _boarding_plan()})
        a = Stack(owner=1)
        b = Stack(owner=2)
        from backend.server.battle.stack import StackToken
        a.token = StackToken(quantity=3, boarding_strength=100.0)
        b.token = StackToken(quantity=3, boarding_strength=100.0)
        assert engine._boarding_chance(a, b) == pytest.approx(0.5)

    def test_odds_scale_with_party_size_and_are_clamped(self):
        from backend.server.battle.stack import StackToken
        _, engine = _engine_for({1: _boarding_plan(), 2: _boarding_plan()})
        strong = Stack(owner=1)
        strong.token = StackToken(quantity=10, boarding_strength=1740.0)
        weak = Stack(owner=2)
        weak.token = StackToken(quantity=1, boarding_strength=10.0)
        assert engine._boarding_chance(strong, weak) == BOARDING_MAX_CHANCE
        assert engine._boarding_chance(weak, strong) == BOARDING_MIN_CHANCE


class TestBoardingInBattle:
    """The order, the capture, and the price of failure."""

    def test_no_boarding_without_the_order(self):
        """The default is Never, so a commander who never opens the
        battle screen never gambles a crew."""
        assert BOARDING_ORDERS[0] == "Never"
        assert BattlePlan().board == "Never"

        hold = _hold_plan()
        server, engine = _engine_for({1: hold, 2: hold})
        boarder, _ = _make_fleet(server.all_empires[1], hold.name,
                                 boarding_strength=5000.0)
        prize, _ = _make_fleet(server.all_empires[2], hold.name,
                               boarding_strength=1.0)
        stacks, battle = _adjacent_stacks(engine, [boarder, prize])
        engine._resolve_boarding(stacks, battle)

        assert not [s for s in battle.steps if s.step_type == "Board"]

    def test_shields_must_be_down(self):
        plan = _boarding_plan()
        server, engine = _engine_for({1: plan, 2: _hold_plan()})
        boarder, _ = _make_fleet(server.all_empires[1], plan.name,
                                 boarding_strength=5000.0)
        prize, _ = _make_fleet(server.all_empires[2], "Hold",
                               boarding_strength=1.0, shields=100)
        stacks, battle = _adjacent_stacks(engine, [boarder, prize])
        engine._resolve_boarding(stacks, battle)
        assert not [s for s in battle.steps if s.step_type == "Board"]

    def test_the_prize_must_be_in_the_same_square(self):
        plan = _boarding_plan()
        server, engine = _engine_for({1: plan, 2: _hold_plan()})
        boarder, _ = _make_fleet(server.all_empires[1], plan.name,
                                 boarding_strength=5000.0)
        prize, _ = _make_fleet(server.all_empires[2], "Hold",
                               boarding_strength=1.0)
        stacks, battle = _adjacent_stacks(engine, [boarder, prize])
        for stack in stacks:
            if stack.owner == 2:
                stack.position = NovaPoint(900.0, 900.0)
        engine._resolve_boarding(stacks, battle)
        assert not [s for s in battle.steps if s.step_type == "Board"]

    def test_success_transfers_the_ship_and_reveals_the_design(self):
        plan = _boarding_plan()
        server, engine = _engine_for({1: plan, 2: _hold_plan()})
        boarder, _ = _make_fleet(server.all_empires[1], plan.name,
                                 boarding_strength=5000.0, name="Assault")
        prize, prize_design = _make_fleet(
            server.all_empires[2], "Hold", boarding_strength=1.0,
            quantity=2, name="Cruiser")
        stacks, battle = _adjacent_stacks(engine, [boarder, prize])
        # Force the roll to succeed - the odds themselves are tested above
        engine._random = random.Random()
        engine._random.random = lambda: 0.0
        engine._resolve_boarding(stacks, battle)

        step = [s for s in battle.steps if s.step_type == "Board"][0]
        assert step.success is True
        assert step.design_name == prize_design.name

        # One ship left the loser's fleet
        assert prize.tokens[prize_design.key].quantity == 1
        # ... and joined the captor as its own fleet, battered
        captor = server.all_empires[1]
        prizes = [f for f in captor.owned_fleets.values()
                  if f.name.startswith("Prize")]
        assert len(prizes) == 1
        prize_token = list(prizes[0].tokens.values())[0]
        assert prize_token.quantity == 1
        assert prize_token.damage_percent == BOARDING_PRIZE_DAMAGE_PERCENT
        # The captured design is now the captor's, marked obsolete -
        # flying a prize is not the same as being able to build it
        captured = captor.designs[prize_token.design_key]
        assert captured.name.endswith("(captured)")
        assert captured.obsolete is True
        # The design is revealed: the battle intel step records it in
        # full for every participant
        record = captor.empire_reports[2]["designs"][hex(prize_design.key)]
        assert record["scope"] == "full"

    def test_failure_destroys_the_party_and_cripples_the_boarder(self):
        plan = _boarding_plan()
        server, engine = _engine_for({1: plan, 2: _hold_plan()})
        boarder, boarder_design = _make_fleet(
            server.all_empires[1], plan.name, boarding_strength=1.0,
            armor=1000, name="Assault")
        prize, _ = _make_fleet(server.all_empires[2], "Hold",
                               boarding_strength=5000.0, name="Cruiser")
        stacks, battle = _adjacent_stacks(engine, [boarder, prize])
        engine._random = random.Random()
        engine._random.random = lambda: 0.999
        boarder_stack = [s for s in stacks if s.owner == 1][0]
        initial = boarder_stack.token.initial_armor

        engine._resolve_boarding(stacks, battle)

        step = [s for s in battle.steps if s.step_type == "Board"][0]
        assert step.success is False
        assert boarder_stack.token.armor == pytest.approx(
            initial * (1 - BOARDING_FAILURE_ARMOR_PERCENT / 100.0))
        # The party is gone: no second attempt this battle
        assert boarder_stack.boarding_spent is True
        engine._resolve_boarding(stacks, battle)
        assert len([s for s in battle.steps if s.step_type == "Board"]) == 1

    def test_one_attempt_per_stack_per_battle(self):
        """A stack of ten boarders takes ONE prize, not ten - the
        single sharpest reason mass boarding does not dominate."""
        plan = _boarding_plan()
        server, engine = _engine_for({1: plan, 2: _hold_plan()})
        boarder, _ = _make_fleet(server.all_empires[1], plan.name,
                                 boarding_strength=5000.0, quantity=10)
        prize, prize_design = _make_fleet(
            server.all_empires[2], "Hold", boarding_strength=1.0,
            quantity=10)
        stacks, battle = _adjacent_stacks(engine, [boarder, prize])
        engine._random = random.Random()
        engine._random.random = lambda: 0.0
        for _ in range(5):
            engine._resolve_boarding(stacks, battle)
        assert len([s for s in battle.steps if s.step_type == "Board"]) == 1
        assert prize.tokens[prize_design.key].quantity == 9

    def test_the_rounds_resolve_boarding(self):
        """The whole battle loop, not just the helper: a fleet under a
        boarding order takes its prize during _do_battle."""
        plan = _boarding_plan()
        server, engine = _engine_for({1: plan, 2: _hold_plan()}, seed=4242)
        boarder, _ = _make_fleet(server.all_empires[1], plan.name,
                                 boarding_strength=5000.0, name="Assault")
        prize, prize_design = _make_fleet(
            server.all_empires[2], "Hold", boarding_strength=1.0,
            quantity=3, armor=400, name="Cruiser")

        battle = BattleReport()
        stacks = engine._generate_stacks([boarder, prize],
                                         NovaPoint(500.0, 500.0))
        engine._position_stacks(stacks, battle)
        engine._do_battle(stacks, battle)

        boards = [s for s in battle.steps if s.step_type == "Board"]
        assert len(boards) == 1
        if boards[0].success:
            assert any(f.name.startswith("Prize")
                       for f in server.all_empires[1].owned_fleets.values())

    def test_a_starbase_neither_boards_nor_is_boarded(self):
        plan = _boarding_plan()
        server, engine = _engine_for({1: plan, 2: _hold_plan()})
        boarder, _ = _make_fleet(server.all_empires[1], plan.name,
                                 boarding_strength=5000.0)
        base_fleet, base_design = _make_fleet(
            server.all_empires[2], "Hold", boarding_strength=5000.0)
        base_token = base_fleet.tokens[base_design.key]
        base_token.is_starbase = True
        base_design.is_starbase = True

        stacks, battle = _adjacent_stacks(engine, [boarder, base_fleet])
        engine._random = random.Random()
        engine._random.random = lambda: 0.0
        engine._resolve_boarding(stacks, battle)
        assert not [s for s in battle.steps if s.step_type == "Board"]


class TestBoardingSaveCompatibility:
    """Existing saves load and behave exactly as they did."""

    def test_a_plan_written_before_boarding_never_boards(self):
        legacy = BattlePlan.from_dict({
            "name": "Default", "tactic": "Maximise Damage",
            "attack": "Enemies", "primary_target": 0,
        })
        assert legacy.board == "Never"
        assert BattlePlan.from_dict(legacy.to_dict()).board == "Never"

    def test_a_token_written_before_boarding_falls_back_to_the_design(self):
        legacy = ShipToken.from_dict({
            "design_key": "0x1", "design_name": "Old", "quantity": 1,
            "armor": 100,
        })
        assert legacy.boarding_strength == 0.0

        design = MockDesign(key=1, name="Old")
        design.boarding_strength = 250.0
        stack = Stack.from_fleet(_legacy_fleet(legacy), 0, legacy, design)
        assert stack.boarding_strength == 250.0

    def test_a_simple_design_written_before_boarding_reloads(self):
        legacy = SimpleDesign.from_dict({
            "key": "0x1", "name": "Old Scout", "hull_name": "Scout",
        })
        assert legacy.boarding_multiplier == 1.0
        assert legacy.boarding_strength == 30.0
        assert not legacy.is_boarder

    def test_a_report_step_round_trips(self):
        from backend.server.battle.battle_step import BattleStepBoard
        step = BattleStepBoard()
        step.stack_key = 7
        step.target_key = 9
        step.chance = 0.42
        step.success = True
        step.design_name = "Prize"
        again = BattleStepBoard.from_dict(step.to_dict())
        assert (again.stack_key, again.target_key, again.success) == (7, 9,
                                                                     True)
        assert again.chance == pytest.approx(0.42)
        # A report written before boarding existed has no Board steps
        assert BattleStepBoard.from_dict({}).design_name == ""


def _legacy_fleet(token):
    fleet = Fleet()
    fleet.key = 1
    fleet.owner = 1
    fleet.position = NovaPoint(0.0, 0.0)
    fleet.tokens[token.design_key] = token
    return fleet


# --------------------------------------------------------------------
# Balance: boarding must not become the dominant strategy
# --------------------------------------------------------------------

BALANCE_SEEDS = (20260728, 31337, 4242, 90210, 5150, 1701, 60606)

# Both task forces cost the same. The balanced force spends its budget
# on guns; the boarding force spends BOARDING_SLOT_SHARE of the same
# budget on marines, which is a straight cut to its weapon power - the
# opportunity cost the criterion is really about. Defence is identical
# on both sides, so the boarding order is the only variable.
BOARDING_SLOT_SHARE = 0.5
BALANCED_POWER = 40


def _balance_force(empire, plan_name, *, boarding: bool):
    """Three squadrons a side, equal cost, differing only in whether
    the budget went into guns or into marines."""
    fleets = []
    squadrons = (("Line", 2, 250, 100), ("Escort", 5, 60, 30),
                 ("Freighter", 3, 40, 0))
    for index, (label, quantity, armor, shields) in enumerate(squadrons,
                                                              start=1):
        armed = label != "Freighter"
        power = int(BALANCED_POWER * (1 - BOARDING_SLOT_SHARE)) if boarding \
            else BALANCED_POWER
        design = MockDesign(key=index, name=f"{label} {empire.id}", mass=100,
                            battle_speed=1.0, has_weapons=armed,
                            power_rating=3000 if label == "Line" else 1000)
        design.weapons = [MockWeapon(power=power, range=2, initiative=5)] \
            if armed else []
        design.cargo_capacity = 200 if label == "Freighter" else 0
        # The marines the boarding force bought instead of guns. The
        # multiplier is the catalog clamp, so this is the strongest
        # boarding force the game can field
        base = 130
        design.boarding_strength = (
            base * BOARDING_MULTIPLIER_MAXIMUM if boarding else float(base))
        empire.designs[design.key] = design

        fleet = Fleet()
        fleet.key = empire.get_next_fleet_key()
        fleet.owner = empire.id
        fleet.name = f"{design.name} fleet"
        fleet.position = NovaPoint(500.0, 500.0)
        fleet.battle_plan = plan_name
        fleet.tokens[design.key] = ShipToken(
            design_key=design.key, design_name=design.name,
            quantity=quantity, armor=armor, shields=shields, mass=100,
            cargo_capacity=design.cargo_capacity, has_weapons=armed,
            boarding_strength=design.boarding_strength)
        empire.owned_fleets[fleet.key] = fleet
        fleets.append(fleet)
    return fleets


def _balance_fight(seed, boarding_side):
    """One battle, boarding force as side `boarding_side`. Returns the
    boarding side's score minus the balanced side's."""
    shooters = _boarding_plan(name="Shooters", board="Never")
    boarders = _boarding_plan(name="Boarders", board="When Able")

    server = BoardingServer()
    fleets = {}
    for empire_id in (1, 2):
        is_boarder = empire_id == boarding_side
        plan = boarders if is_boarder else shooters
        empire = BoardingEmpire(id=empire_id)
        empire.battle_plans[plan.name] = plan
        server.all_empires[empire_id] = empire
        fleets[empire_id] = _balance_force(empire, plan.name,
                                           boarding=is_boarder)

    engine = RonBattleEngine(server, [])
    engine._random = random.Random(seed)
    battle = BattleReport()
    stacks = engine._generate_stacks(fleets[1] + fleets[2],
                                     NovaPoint(500.0, 500.0))
    engine._position_stacks(stacks, battle)
    engine._do_battle(stacks, battle)

    def cost(owner):
        ships = 10.0
        lost = battle.losses.get(owner, 0)
        carried = 0.0
        held = 0
        for fleet in fleets[owner]:
            for token in fleet.tokens.values():
                carried += token.quantity * token.damage_percent / 100.0
                held += token.quantity
        # Ships that changed hands are losses too, and gains for the
        # captor - the whole point of a capture
        taken = ships - held - lost
        return (lost + carried + taken) / ships

    other = 1 if boarding_side == 2 else 2
    captures = sum(1 for step in battle.steps
                   if step.step_type == "Board" and step.success)
    return cost(other) - cost(boarding_side), captures


def test_a_boarding_heavy_force_does_not_beat_a_balanced_one():
    """The balance bar. This game has already been beaten once by a
    dominant strategy (DEF-8, escort spam), and that is why boarding
    is measured before it ships.

    A force that spends half its weapon budget on the strongest
    boarding gear in the catalog is run against a force of equal cost
    that spent all of it on guns, over seven seeds and in both role
    assignments. Boarding must not win the majority.
    """
    wins = 0
    runs = 0
    captures = 0
    for seed in BALANCE_SEEDS:
        for boarding_side in (1, 2):
            runs += 1
            margin, taken = _balance_fight(seed, boarding_side)
            captures += taken
            if margin > 1e-9:
                wins += 1

    # The bar is only worth anything if boarding actually happened -
    # a regression that silently stopped boarding would otherwise pass
    assert captures > 0, "no ship was captured in any run"
    assert wins <= runs // 2, (
        f"boarding-heavy force won {wins} of {runs} against an "
        f"equal-cost balanced force ({captures} ships captured)")
