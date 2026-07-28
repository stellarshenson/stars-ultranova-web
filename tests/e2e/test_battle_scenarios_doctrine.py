"""
Seeded e2e: battle doctrine scenario suite.

Twenty-five scenarios, one per row of a single table, each pinning one
canonical behaviour of the doctrine layer - the nine stance x posture
combinations, the six admiralty standard plans, the five target
priority tiers, the four withdrawal thresholds (including the
MIN_DISENGAGE_MOVES floor under the reductions stance and posture stack
up), and the empire default plan a newly built fleet inherits.

Every row stages the same way: a seeded GameHarness against the real
FastAPI app, plans installed through the player command API, fleets
placed on a deep-space point by state surgery (the harness pattern from
test_battle_plans.py). One test body stages the row and hands the
battlefield to the row's own check, which is what the row's expected
outcome is written in.

The checks drive RonBattleEngine directly instead of generating a turn.
The doctrine axes are round-level effects - the shield pool a stack
enters the battle with, its place in the firing order, how far its
weapons reach, how many board moves it needs to break off - and turn
generation neither exposes them nor is needed to reach them. The one
row that genuinely needs turn generation (production handing a new
fleet the empire default) runs turns.

Nothing here asserts a table value against itself: every row reads its
expectation off the stack the engine is about to fight with, the order
the attacks came out in, the target a plan tier picked, the ship that
died first, or the round a stack left the board.
"""

import random
from dataclasses import dataclass, replace
from typing import Callable, Tuple

import pytest

from backend.core.data_structures import NovaPoint
from backend.server.battle import BattleReport, RonBattleEngine
from backend.server.battle.battle_plan import (
    MIN_DISENGAGE_MOVES,
    POSTURE_MODIFIERS,
    STANCE_MODIFIERS,
    WITHDRAWAL_DAMAGE_PERCENT,
    Victims,
)

from .test_battle_plans import _deep_space_point, _spawn_fleet

SEED = 20260729

# Battle board units per square (RonBattleEngine.GRID_SCALE)
GRID = RonBattleEngine.GRID_SCALE

# Starting-design stats the scenarios lean on (ship_specs.py)
STALWART_BEAM_RANGE = 3
STALWART_WEAPONS = 2


# =============================================================================
# Staging - identical for every row
# =============================================================================

@dataclass(frozen=True)
class FleetSpec:
    """One fleet placed on the battle point by state surgery."""
    empire: int
    design: str
    name: str
    quantity: int = 1
    plan: str = "Default"
    parked: bool = False


@dataclass(frozen=True)
class Scenario:
    """One row: what to stage, and what the outcome must be."""
    id: str
    doc: str
    check: Callable
    plans: Tuple = ()      # (empire_id, plan payload) pairs
    defaults: Tuple = ()   # (empire_id, plan name) pairs
    fleets: Tuple = ()


class Battlefield:
    """A staged battle: real empires, real designs, real plans.

    Stacks are built from the spawned fleets and driven straight into
    RonBattleEngine, so a check can read the doctrine state the engine
    itself is working from.
    """

    def __init__(self, harness, monkeypatch, server_data, engine,
                 by_name, battle):
        self.harness = harness
        self.monkeypatch = monkeypatch
        self.server_data = server_data
        self.engine = engine
        self.by_name = by_name
        self.stacks = list(by_name.values())
        self.battle = battle

    # -- lookups ------------------------------------------------------

    def stack(self, name):
        return self.by_name[name]

    def plan(self, empire_id, name):
        return self.server_data.all_empires[empire_id].battle_plans[name]

    def fleet(self, empire_id, name):
        empire = self.server_data.all_empires[empire_id]
        for fleet in empire.owned_fleets.values():
            if fleet.name == name:
                return fleet
        return None

    def steps(self, step_type):
        return [s for s in self.battle.steps if s.step_type == step_type]

    # -- driving the engine -------------------------------------------

    def place(self, name, anchor, squares):
        """Put `name`'s stack `squares` squares east of `anchor`'s."""
        origin = self.stack(anchor).position
        self.stack(name).position = NovaPoint(
            origin.x + int(squares * GRID), origin.y)

    def gather(self, anchor):
        """Bring every other stack a square from `anchor`.

        Without it the ship that dies first is the one that closed
        first - an armed escort walks into beam range while a freighter
        runs - and the order would say nothing about the plan's tiers.
        """
        for name in self.by_name:
            if name != anchor:
                self.place(name, anchor, 1)

    def attacks(self, name):
        """Attacks `name` would generate this round, in firing order."""
        source = self.stack(name)
        self.engine._select_targets(self.stacks)
        return [a for a in self.engine._generate_attacks(self.stacks)
                if a.source_stack is source]

    def volley(self, source_name, target_name):
        """Fire one weapon at `target_name`; return the damage done.

        The target is restored afterwards, so the same shot can be
        repeated under a different doctrine and the two compared.
        """
        target = self.stack(target_name)
        shields, armor = target.token.shields, target.token.armor
        attacks = [a for a in self.attacks(source_name)
                   if a.target_stack.target is target]
        assert attacks, f"{source_name} generated no attack on {target_name}"
        self.engine._execute_attack(attacks[0], self.battle)
        dealt = (shields + armor) - (target.token.shields
                                     + target.token.armor)
        target.token.shields, target.token.armor = shields, armor
        target.damage_taken = False
        return dealt

    def rounds(self, first, last):
        """Drive target selection and movement for a range of rounds."""
        for battle_round in range(first, last + 1):
            self.engine._select_targets(self.stacks)
            self.engine._move_stacks(self.stacks, battle_round, self.battle)

    def hit(self, source_name, target_name, damage):
        """Put `damage` on a stack through the engine's own damage path."""
        self.engine._damage_armor(self.stack(source_name),
                                  self.stack(target_name),
                                  damage, self.battle)

    def fight(self):
        """Run the battle to its end, then charge for any withdrawal."""
        self.engine._do_battle(self.stacks, self.battle)
        self.engine._apply_withdrawal_consequences(self.stacks, self.battle)


def _stage(harness, monkeypatch, scenario) -> Battlefield:
    """Create the game, install the plans, place the fleets, build the
    stacks and put them on the battle board."""
    from backend.services.game_manager import get_game_manager

    harness.create_game(seed=SEED, size="tiny", players=2)

    for empire_id, payload in scenario.plans:
        result = harness.submit(empire_id, "battle_plan",
                                {"mode": "set", "plan": payload})
        assert result["status"] == "applied", result
    for empire_id, name in scenario.defaults:
        result = harness.submit(empire_id, "battle_plan",
                                {"mode": "default", "name": name})
        assert result["status"] == "applied", result

    px, py = _deep_space_point(harness)
    for spec in scenario.fleets:
        _spawn_fleet(harness, spec.empire, spec.design, spec.name, px, py,
                     quantity=spec.quantity, battle_plan=spec.plan,
                     parked=spec.parked)

    manager = get_game_manager()
    server_data = manager._load_game_state(harness.game_id)

    # Seeded before construction: the engine derives its own generator
    # from the global one (RonBattleEngine.__init__)
    random.seed(SEED)
    engine = RonBattleEngine(server_data, [])

    battle = BattleReport()
    battle.year = server_data.turn_year
    battle.location = "deep space (scenario)"

    by_name = {}
    for spec in scenario.fleets:
        fleet = None
        empire = server_data.all_empires[spec.empire]
        for owned in empire.owned_fleets.values():
            if owned.name == spec.name:
                fleet = owned
                break
        assert fleet is not None, f"fleet '{spec.name}' was not placed"
        built = engine._build_fleet_stacks(fleet)
        assert len(built) == 1, f"'{spec.name}' is not a single stack"
        by_name[spec.name] = built[0]

    field = Battlefield(harness, monkeypatch, server_data, engine,
                        by_name, battle)
    if field.stacks:
        # Sets starting positions and applies the doctrine every stack
        # enters the battle with (shield pool, outnumbered flag)
        engine._position_stacks(field.stacks, battle)
    return field


# =============================================================================
# The nine stance x posture combinations
# =============================================================================

@dataclass(frozen=True)
class Axes:
    """What one stance x posture combination buys, as the battle shows
    it: the shield pool multiplier, the initiative every attack it
    generates carries, the board moves a break-off needs, whether it
    ever moves, the multiplier on its own hit power, whether its
    weapons reach a square further, and whether it may run at all."""
    shields: float
    initiative: int
    disengage_moves: int
    holds_position: bool
    damage_dealt: float
    range_bonus: int
    may_disengage: bool


DOCTRINE_FLEETS = (
    FleetSpec(2, "Stalwart Defender", "Doctrine Wing", 2, "Doctrine"),
    FleetSpec(1, "Stalwart Defender", "Opposing Line", 2),
)


def _doctrine_plan(stance, posture):
    return {"name": "Doctrine", "stance": stance, "posture": posture,
            "tactic": "Maximise Damage", "attack": "Enemies"}


def _check_stance_posture(stance, posture, axes):
    def check(field):
        subject = field.stack("Doctrine Wing")
        control = field.stack("Opposing Line")
        plan = field.plan(2, "Doctrine")

        # 1. The shield pool the stack enters the battle with, measured
        #    against an identical stack on the stock plan. Armour is
        #    never scaled - a stance touching both pools would be the
        #    symmetric multiplier the doctrine research rejected
        assert subject.token.shields == pytest.approx(
            control.token.shields * axes.shields)
        assert subject.token.armor == pytest.approx(control.token.armor)

        # 2. Initiative, read off the attacks the engine ordered. A
        #    stack killed before it fires contributes nothing, so
        #    firing order is not a symmetric damage multiplier
        field.place("Doctrine Wing", "Opposing Line", 0)
        generated = field.attacks("Doctrine Wing")
        assert len(generated) == STALWART_WEAPONS
        assert [a.initiative_bonus for a in generated] == \
            [axes.initiative] * STALWART_WEAPONS

        # 3. Hit power: the concentration of fire a spread-out
        #    formation trades away. Pinned against the weapon's own
        #    undispersed power in the target's square, NOT against a
        #    second volley under another posture - every reference
        #    volley available here is itself a Standard-posture stack
        #    (the control flies the stock plan), so a ratio would
        #    cancel the Standard multiplier out and pin nothing on the
        #    three Standard rows
        weapon = subject.token.design.weapons[0]
        full_power = weapon.power * subject.token.quantity
        dealt = field.volley("Doctrine Wing", "Opposing Line")
        reference = field.volley("Opposing Line", "Doctrine Wing")
        assert reference == pytest.approx(full_power)
        assert dealt == pytest.approx(full_power * axes.damage_dealt)

        # 4. Weapon reach: a braced stack fights from a fixed
        #    emplacement, so it gets the starbase range bonus. One
        #    square past the beam's own range, only Brace can fire
        field.place("Doctrine Wing", "Opposing Line",
                    STALWART_BEAM_RANGE + 1)
        assert bool(field.attacks("Doctrine Wing")) is (axes.range_bonus > 0)

        # 5. Board moves a break-off needs, and whether one is allowed
        assert field.engine._disengage_moves_required(subject) == \
            axes.disengage_moves

        plan.tactic = "Disengage"
        field.place("Doctrine Wing", "Opposing Line", 6)
        start_x = subject.position.x
        field.rounds(5, 5 + axes.disengage_moves + 2)

        if axes.holds_position:
            # Never closes, so it can never accumulate the moves a
            # disengagement needs - the cost the posture is paying
            assert subject.position.x == start_x
            assert subject.flee_rounds == 0
            assert subject.disengaged is False
        elif not axes.may_disengage:
            # The sharpest cost of the stance: it cannot run even when
            # the plan says Disengage outright
            assert field.engine._effective_tactic(subject) == \
                "Maximise Damage"
            assert subject.flee_rounds == 0
            assert subject.disengaged is False
            assert subject.position.x < start_x
        else:
            assert subject.position.x > start_x
            # Exactly the required moves: three further rounds were
            # driven, and a stack that has left the board stops
            # accumulating them
            assert subject.flee_rounds == axes.disengage_moves
            assert subject.disengaged is True
            assert field.steps("Withdraw")

    return check


def _stance_posture_scenario(stance, posture, axes):
    return Scenario(
        id=f"stance-{stance.lower()}-posture-{posture.lower()}",
        doc=(f"{stance} stance under the {posture} posture: shields "
             f"x{axes.shields}, initiative {axes.initiative:+d}, "
             f"{axes.disengage_moves} board moves to break off."),
        plans=((2, _doctrine_plan(stance, posture)),),
        fleets=DOCTRINE_FLEETS,
        check=_check_stance_posture(stance, posture, axes),
    )


STANCE_POSTURE_SCENARIOS = [
    _stance_posture_scenario("Aggressive", "Standard", Axes(
        shields=0.80, initiative=2, disengage_moves=7, holds_position=False,
        damage_dealt=1.0, range_bonus=0, may_disengage=False)),
    _stance_posture_scenario("Aggressive", "Brace", Axes(
        shields=1.04, initiative=2, disengage_moves=7, holds_position=True,
        damage_dealt=0.80, range_bonus=1, may_disengage=False)),
    _stance_posture_scenario("Aggressive", "Scatter", Axes(
        shields=0.80, initiative=2, disengage_moves=5, holds_position=False,
        damage_dealt=0.85, range_bonus=0, may_disengage=False)),
    _stance_posture_scenario("Balanced", "Standard", Axes(
        shields=1.0, initiative=0, disengage_moves=7, holds_position=False,
        damage_dealt=1.0, range_bonus=0, may_disengage=True)),
    _stance_posture_scenario("Balanced", "Brace", Axes(
        shields=1.30, initiative=0, disengage_moves=7, holds_position=True,
        damage_dealt=0.80, range_bonus=1, may_disengage=True)),
    _stance_posture_scenario("Balanced", "Scatter", Axes(
        shields=1.0, initiative=0, disengage_moves=5, holds_position=False,
        damage_dealt=0.85, range_bonus=0, may_disengage=True)),
    _stance_posture_scenario("Defensive", "Standard", Axes(
        shields=1.25, initiative=-2, disengage_moves=5, holds_position=False,
        damage_dealt=1.0, range_bonus=0, may_disengage=True)),
    _stance_posture_scenario("Defensive", "Brace", Axes(
        shields=1.625, initiative=-2, disengage_moves=5, holds_position=True,
        damage_dealt=0.80, range_bonus=1, may_disengage=True)),
    _stance_posture_scenario("Defensive", "Scatter", Axes(
        shields=1.25, initiative=-2, disengage_moves=MIN_DISENGAGE_MOVES,
        holds_position=False, damage_dealt=0.85, range_bonus=0,
        may_disengage=True)),
]


# =============================================================================
# The six admiralty standard plans
# =============================================================================

CONVOY_FIELD = (
    FleetSpec(1, "Teamster", "Convoy", 4),          # Logistics, 100 armour
    FleetSpec(1, "Armed Probe", "Picket", 5),       # Escort, 100 armour
)


def _check_aggressive_assault(field):
    """Hunts warships, hits first, and will not break off."""
    wing = field.stack("Assault Wing")
    line = field.stack("Escort Line")
    train = field.stack("Supply Train")

    # Paid for in shields (Aggressive, x0.80), against an identical
    # stack on the stock plan
    assert wing.token.shields == pytest.approx(line.token.shields * 0.80)

    # Warships before freighters: Armed Ship is the plan's secondary
    # tier, a freighter matches only the Any Ship tier at the bottom
    field.place("Assault Wing", "Escort Line", 0)
    field.engine._select_targets(field.stacks)
    assert wing.target is line
    assert wing.target_priorities[line.key] == 6
    assert wing.target_priorities[train.key] == 3

    # Fires ahead of a Balanced enemy of identical design
    generated = field.attacks("Assault Wing")
    assert generated and all(a.initiative_bonus == 2 for a in generated)
    ordered = field.engine._generate_attacks(field.stacks)
    assert ordered[0].source_stack is wing

    # Will not break off, even ordered to outright
    field.plan(2, "Aggressive Assault").tactic = "Disengage"
    assert field.engine._effective_tactic(wing) == "Maximise Damage"
    field.place("Assault Wing", "Escort Line", 6)
    start_x = wing.position.x
    field.rounds(5, 12)
    assert wing.flee_rounds == 0
    assert wing.disengaged is False
    assert wing.position.x < start_x


def _check_balanced(field):
    """Moves none of the four levers - an empire whose default is
    Balanced hunts exactly what the legacy Default plan hunted. Its
    TACTIC deliberately differs: Salvo then Close is the
    engagement-range doctrine (docs/research-engagement-range.md),
    where legacy Default always closed to contact."""
    wing = field.stack("Line Wing")
    legacy = field.plan(2, "Default")
    balanced = field.plan(2, "Balanced")

    assert wing.token.shields == pytest.approx(
        field.stack("Opposing Line").token.shields)
    for tier in ("primary_target", "secondary_target", "tertiary_target",
                 "quaternary_target", "quinary_target"):
        assert getattr(balanced, tier) == getattr(legacy, tier)
    assert balanced.attack == legacy.attack
    assert (balanced.tactic, legacy.tactic) == ("Salvo then Close",
                                                "Maximise Damage")

    field.place("Line Wing", "Opposing Line", 0)
    generated = field.attacks("Line Wing")
    assert generated and all(a.initiative_bonus == 0 for a in generated)

    # No emplacement bonus: one square past the beam's range it is mute
    field.place("Line Wing", "Opposing Line", STALWART_BEAM_RANGE + 1)
    assert not field.attacks("Line Wing")

    # Canonical seven board moves, and it closes like any line ship
    assert field.engine._disengage_moves_required(wing) == 7
    field.place("Line Wing", "Opposing Line", 6)
    start_x = wing.position.x
    field.rounds(5, 8)
    assert wing.position.x < start_x
    assert wing.flee_rounds == 0


def _check_defensive_hold(field):
    """Fights as an emplacement: a deeper shield pool and a square more
    reach, paid for by never moving - which is also why its Half Armour
    threshold can never carry it off the board."""
    bastion = field.stack("Bastion")

    assert bastion.token.shields == pytest.approx(
        field.stack("Assault Line").token.shields * 1.25 * 1.30)

    field.place("Bastion", "Assault Line", 0)
    generated = field.attacks("Bastion")
    assert generated and all(a.initiative_bonus == -2 for a in generated)

    # One square past the beam's own range it still fires
    field.place("Bastion", "Assault Line", STALWART_BEAM_RANGE + 1)
    assert field.attacks("Bastion")

    # Shot to half armour, its threshold is met and its tactic turns to
    # Disengage - and it still never leaves, because it never moves
    field.hit("Assault Line", "Bastion", bastion.token.initial_armor / 2.0)
    assert field.engine._withdraw_threshold_met(bastion) is True
    assert field.engine._effective_tactic(bastion) == "Disengage"

    field.place("Bastion", "Assault Line", 6)
    start = (bastion.position.x, bastion.position.y)
    field.rounds(5, 20)
    assert (bastion.position.x, bastion.position.y) == start
    assert bastion.flee_rounds == 0
    assert bastion.disengaged is False
    assert not field.steps("Withdraw")
    assert not [s for s in field.steps("Movement")
                if s.stack_key == bastion.key]


def _check_commerce_raid(field):
    """Primary tier is Logistics: the freighters die first and the
    escort is only the fourth thing it looks at."""
    pack = field.stack("Raider Pack")
    convoy = field.stack("Convoy")
    picket = field.stack("Picket")

    field.engine._select_targets(field.stacks)
    assert pack.target is convoy
    assert pack.target_priorities[convoy.key] == 7
    assert pack.target_priorities[picket.key] == 4

    field.gather("Raider Pack")
    field.fight()
    destroyed = field.steps("Destroy")
    assert destroyed, "the raid destroyed nothing"
    assert destroyed[0].stack_key == convoy.key
    assert field.fleet(1, "Convoy") is None


def _check_escort_screen(field):
    """Same convoy, same raiders, opposite priority: the screen shoots
    the escort first and the freighters are the last tier."""
    wing = field.stack("Screen Wing")
    convoy = field.stack("Convoy")
    picket = field.stack("Picket")

    field.engine._select_targets(field.stacks)
    assert wing.target is picket
    assert wing.target_priorities[picket.key] == 6
    assert wing.target_priorities[convoy.key] == 3

    field.gather("Screen Wing")
    field.fight()
    destroyed = field.steps("Destroy")
    assert destroyed, "the screen destroyed nothing"
    assert destroyed[0].stack_key == picket.key


def _check_fighting_retreat(field):
    """Leaves early and leaves fast: the first damage turns its tactic
    to Disengage, and Defensive plus Scatter cut the break-off to the
    MIN_DISENGAGE_MOVES floor."""
    rearguard = field.stack("Rearguard")
    engine = field.engine

    assert engine._disengage_moves_required(rearguard) == MIN_DISENGAGE_MOVES

    # Undamaged it stands and fights its stand-off tactic
    field.place("Rearguard", "Pursuit", 6)
    start_x = rearguard.position.x
    field.rounds(5, 7)
    assert rearguard.flee_rounds == 0
    assert rearguard.position.x < start_x

    # One point of damage is the whole threshold
    field.hit("Pursuit", "Rearguard", 1.0)
    assert engine._withdraw_threshold_met(rearguard) is True

    field.place("Rearguard", "Pursuit", 6)
    field.rounds(8, 9)
    assert rearguard.flee_rounds == 2
    assert rearguard.disengaged is False
    field.rounds(10, 10)
    assert rearguard.flee_rounds == MIN_DISENGAGE_MOVES
    assert rearguard.disengaged is True
    assert field.steps("Withdraw")

    # And the break-off is charged for
    field.server_data.all_messages = []
    engine._apply_withdrawal_consequences(field.stacks, field.battle)
    fleet = field.fleet(2, "Rearguard")
    assert fleet.withdrawn_year == field.server_data.turn_year
    assert len(fleet.waypoints) == 1
    for token in fleet.tokens.values():
        assert token.damage_percent >= WITHDRAWAL_DAMAGE_PERCENT
    assert any("withdrew" in m.text
               for m in field.server_data.all_messages)


ADMIRALTY_SCENARIOS = [
    Scenario(
        id="admiralty-aggressive-assault",
        doc=("Aggressive Assault charges warships, fires ahead of a "
             "Balanced enemy, pays in shields, and cannot break off."),
        fleets=(
            FleetSpec(2, "Stalwart Defender", "Assault Wing", 2,
                      "Aggressive Assault"),
            FleetSpec(1, "Stalwart Defender", "Escort Line", 2),
            FleetSpec(1, "Teamster", "Supply Train", 4),
        ),
        check=_check_aggressive_assault,
    ),
    Scenario(
        id="admiralty-balanced",
        doc=("Balanced moves none of the doctrine levers and carries "
             "the legacy Default plan's tiers and attack; its tactic "
             "is the Salvo then Close engagement-range doctrine."),
        fleets=(
            FleetSpec(2, "Stalwart Defender", "Line Wing", 2, "Balanced"),
            FleetSpec(1, "Stalwart Defender", "Opposing Line", 2),
        ),
        check=_check_balanced,
    ),
    Scenario(
        id="admiralty-defensive-hold",
        doc=("Defensive Hold fights as an emplacement and holds the "
             "ground it was given, threshold or no threshold."),
        fleets=(
            FleetSpec(2, "Stalwart Defender", "Bastion", 2,
                      "Defensive Hold"),
            FleetSpec(1, "Stalwart Defender", "Assault Line", 2),
        ),
        check=_check_defensive_hold,
    ),
    Scenario(
        id="admiralty-commerce-raid",
        doc="Commerce Raid kills the freighters before the escort.",
        fleets=(
            FleetSpec(2, "Stalwart Defender", "Raider Pack", 3,
                      "Commerce Raid"),
        ) + CONVOY_FIELD,
        check=_check_commerce_raid,
    ),
    Scenario(
        id="admiralty-escort-screen",
        doc=("Escort Screen kills the escort before the freighters - "
             "the same field as Commerce Raid, the opposite outcome."),
        fleets=(
            FleetSpec(2, "Stalwart Defender", "Screen Wing", 3,
                      "Escort Screen"),
        ) + CONVOY_FIELD,
        check=_check_escort_screen,
    ),
    Scenario(
        id="admiralty-fighting-retreat",
        doc=("Fighting Retreat breaks off on first damage and needs "
             "only the floor of board moves to do it."),
        fleets=(
            FleetSpec(2, "Stalwart Defender", "Rearguard", 4,
                      "Fighting Retreat", parked=True),
            FleetSpec(1, "Stalwart Defender", "Pursuit", 2),
        ),
        check=_check_fighting_retreat,
    ),
]


# =============================================================================
# The five target priority tiers
# =============================================================================

# Roles no ship on the board carries, used to push the marked victim
# down to the tier under test. Repeating a tier is how a plan says
# "nothing further" - the Victims enum has no None value
ABSENT = (int(Victims.BOMBER), int(Victims.CAPITAL_SHIP),
          int(Victims.STARBASE), int(Victims.STARBASE))

TIER_FIELD = (
    FleetSpec(1, "Stalwart Defender", "Hunter", 6, "Tiers"),
    FleetSpec(2, "Teamster", "Convoy", 4),            # Logistics
    FleetSpec(2, "Armed Probe", "Picket", 5),         # Escort
    FleetSpec(2, "Long Range Scout", "Survey", 5),    # Support Ship
)

TIER_NAMES = ("primary_target", "secondary_target", "tertiary_target",
              "quaternary_target", "quinary_target")

# Priority the engine returns for each tier position (_get_priority)
TIER_PRIORITY = (7, 6, 5, 4, 3)


def _tier_plan(index, victim_tier, filler):
    """A plan whose tier `index` names `victim_tier`; the tiers above
    it name roles nobody on the board carries, the tiers below it are
    `filler`."""
    tiers = list(ABSENT[:index])
    tiers.append(int(victim_tier))
    tiers += [int(filler)] * (5 - len(tiers))
    payload = {"name": "Tiers", "tactic": "Maximise Damage",
               "attack": "Enemies"}
    payload.update(dict(zip(TIER_NAMES, tiers)))
    return payload


def _check_tier(index, marked, spared):
    def check(field):
        hunter = field.stack("Hunter")
        victim = field.stack(marked)

        field.engine._select_targets(field.stacks)
        assert hunter.target is victim, (
            f"tier {index + 1} did not pick the {marked}")
        assert hunter.target_priorities[victim.key] == TIER_PRIORITY[index]
        for name in spared:
            other = field.stack(name)
            assert (hunter.target_priorities.get(other.key, 0)
                    < TIER_PRIORITY[index])

        field.gather("Hunter")
        field.fight()

        destroyed = field.steps("Destroy")
        assert destroyed, "nothing was destroyed"
        assert destroyed[0].stack_key == victim.key, (
            f"the {marked} was not the first ship to die")

        # Every shot the hunter called was at the tier it named
        called = [s for s in field.steps("Target")
                  if s.stack_key == hunter.key]
        assert called, "the hunter never picked a target"
        assert called[0].target_key == victim.key
        assert called[0].priority == TIER_PRIORITY[index]

    return check


def _check_quinary_tier(field):
    """The bottom tier is the only tier that matches anything, so the
    ships no tier names are never engaged at all."""
    hunter = field.stack("Hunter")
    survey = field.stack("Survey")

    field.engine._select_targets(field.stacks)
    assert hunter.target is survey
    assert hunter.target_priorities[survey.key] == 3
    for name in ("Convoy", "Picket"):
        assert field.stack(name).key not in hunter.target_priorities

    field.gather("Hunter")
    field.fight()

    destroyed = field.steps("Destroy")
    assert destroyed and destroyed[0].stack_key == survey.key
    called = [s for s in field.steps("Target") if s.stack_key == hunter.key]
    assert called and all(s.target_key == survey.key for s in called)
    assert all(s.priority == 3 for s in called)
    assert field.fleet(2, "Convoy") is not None


TIER_SCENARIOS = [
    Scenario(
        id="tier-1-primary",
        doc=("The primary tier picks first: Logistics at tier one and "
             "everything else on Any Ship - the freighters die first."),
        plans=((1, _tier_plan(0, Victims.LOGISTICS, Victims.ANY_SHIP)),),
        fleets=TIER_FIELD,
        check=_check_tier(0, "Convoy", ("Picket", "Survey")),
    ),
    Scenario(
        id="tier-2-secondary",
        doc=("With the primary tier matching nothing on the board, the "
             "secondary tier decides - Support Ship dies first."),
        plans=((1, _tier_plan(1, Victims.SUPPORT_SHIP, Victims.ANY_SHIP)),),
        fleets=TIER_FIELD,
        check=_check_tier(1, "Survey", ("Convoy", "Picket")),
    ),
    Scenario(
        id="tier-3-tertiary",
        doc=("Two dead tiers above it, the tertiary tier names Escort - "
             "and the escort dies before the softer targets."),
        plans=((1, _tier_plan(2, Victims.ESCORT, Victims.ANY_SHIP)),),
        fleets=TIER_FIELD,
        check=_check_tier(2, "Picket", ("Convoy", "Survey")),
    ),
    Scenario(
        id="tier-4-quaternary",
        doc=("Three dead tiers above it, the quaternary tier names "
             "Logistics - the freighters die first again, at tier four."),
        plans=((1, _tier_plan(3, Victims.LOGISTICS, Victims.ANY_SHIP)),),
        fleets=TIER_FIELD,
        check=_check_tier(3, "Convoy", ("Picket", "Survey")),
    ),
    Scenario(
        id="tier-5-quinary",
        doc=("Only the bottom tier matches anything: the survey ships "
             "die and nothing else is ever engaged."),
        plans=((1, _tier_plan(4, Victims.SUPPORT_SHIP,
                              Victims.SUPPORT_SHIP)),),
        fleets=TIER_FIELD,
        check=_check_quinary_tier,
    ),
]


# =============================================================================
# The withdrawal thresholds
# =============================================================================

def _threshold_plan(withdraw, stance="Balanced", posture="Standard"):
    return {"name": "Threshold", "withdraw": withdraw, "stance": stance,
            "posture": posture, "tactic": "Maximise Damage",
            "attack": "Enemies"}


def _threshold_fleets(pursuit_quantity=2):
    return (
        FleetSpec(2, "Stalwart Defender", "Rearguard", 4, "Threshold",
                  parked=True),
        FleetSpec(1, "Stalwart Defender", "Pursuit", pursuit_quantity),
    )


def _check_withdraw_never(field):
    """Never means never: shot below half armour and outnumbered, the
    stack still closes."""
    rearguard = field.stack("Rearguard")
    engine = field.engine

    field.place("Rearguard", "Pursuit", 6)
    start_x = rearguard.position.x
    field.rounds(5, 8)
    assert rearguard.flee_rounds == 0
    assert rearguard.position.x < start_x

    field.hit("Pursuit", "Rearguard", rearguard.token.initial_armor * 0.9)
    assert rearguard.damage_taken is True
    assert rearguard.token.armor < rearguard.token.initial_armor / 2.0
    assert engine._withdraw_threshold_met(rearguard) is False
    assert engine._effective_tactic(rearguard) == "Maximise Damage"

    field.place("Rearguard", "Pursuit", 6)
    resume_x = rearguard.position.x
    field.rounds(9, 20)
    assert rearguard.flee_rounds == 0
    assert rearguard.disengaged is False
    assert rearguard.position.x < resume_x
    assert not field.steps("Withdraw")


def _check_withdraw_on_damage(field):
    """The first point of damage turns any tactic into Disengage."""
    rearguard = field.stack("Rearguard")
    engine = field.engine

    field.place("Rearguard", "Pursuit", 6)
    start_x = rearguard.position.x
    field.rounds(5, 8)
    assert engine._withdraw_threshold_met(rearguard) is False
    assert rearguard.flee_rounds == 0
    assert rearguard.position.x < start_x

    field.hit("Pursuit", "Rearguard", 1.0)
    assert engine._withdraw_threshold_met(rearguard) is True
    assert engine._effective_tactic(rearguard) == "Disengage"

    field.place("Rearguard", "Pursuit", 6)
    resume_x = rearguard.position.x
    field.rounds(9, 9 + 7)
    assert rearguard.position.x > resume_x
    assert rearguard.flee_rounds == 7
    assert rearguard.disengaged is True
    assert field.steps("Withdraw")


def _check_withdraw_half_armour(field):
    """Half Armour holds one point above the line and breaks on it."""
    rearguard = field.stack("Rearguard")
    engine = field.engine
    baseline = rearguard.token.initial_armor

    field.hit("Pursuit", "Rearguard", baseline / 2.0 - 1.0)
    assert rearguard.token.armor == pytest.approx(baseline / 2.0 + 1.0)
    assert engine._withdraw_threshold_met(rearguard) is False
    assert engine._effective_tactic(rearguard) == "Maximise Damage"

    field.place("Rearguard", "Pursuit", 6)
    start_x = rearguard.position.x
    field.rounds(5, 8)
    assert rearguard.flee_rounds == 0
    assert rearguard.position.x < start_x

    field.hit("Pursuit", "Rearguard", 1.0)
    assert rearguard.token.armor == pytest.approx(baseline / 2.0)
    assert engine._withdraw_threshold_met(rearguard) is True

    field.place("Rearguard", "Pursuit", 6)
    field.rounds(9, 9 + 7)
    assert rearguard.flee_rounds == 7
    assert rearguard.disengaged is True


def _check_withdraw_outnumbered(field):
    """Outnumbered fires before a shot is taken - and on the deepest
    reduction the shipped tables allow (Defensive plus Scatter) the
    break-off still costs MIN_DISENGAGE_MOVES, because the floor holds
    it there."""
    rearguard = field.stack("Rearguard")
    engine = field.engine

    # Two-to-one in armed ships, decided before the first round
    assert rearguard.outnumbered is True
    assert field.stack("Pursuit").outnumbered is False
    assert engine._withdraw_threshold_met(rearguard) is True
    assert rearguard.damage_taken is False

    # The reductions stack to exactly the floor, and the floor is what
    # holds them there
    assert (STANCE_MODIFIERS["Defensive"].disengage_moves
            + POSTURE_MODIFIERS["Scatter"].disengage_moves_delta) == \
        MIN_DISENGAGE_MOVES
    assert engine._disengage_moves_required(rearguard) == MIN_DISENGAGE_MOVES
    field.monkeypatch.setitem(
        POSTURE_MODIFIERS, "Scatter",
        replace(POSTURE_MODIFIERS["Scatter"], disengage_moves_delta=-99))
    assert engine._disengage_moves_required(rearguard) == MIN_DISENGAGE_MOVES
    field.monkeypatch.undo()

    # Control: even the same stack closes once it is not outnumbered
    rearguard.outnumbered = False
    field.place("Rearguard", "Pursuit", 6)
    start_x = rearguard.position.x
    field.rounds(5, 7)
    assert rearguard.flee_rounds == 0
    assert rearguard.position.x < start_x

    rearguard.outnumbered = True
    field.place("Rearguard", "Pursuit", 6)
    field.rounds(8, 9)
    assert rearguard.flee_rounds == 2
    assert rearguard.disengaged is False
    field.rounds(10, 10)
    assert rearguard.flee_rounds == MIN_DISENGAGE_MOVES
    assert rearguard.disengaged is True
    assert field.steps("Withdraw")


WITHDRAWAL_SCENARIOS = [
    Scenario(
        id="withdraw-never",
        doc=("The Never threshold survives damage, half armour and "
             "being outnumbered without ever breaking off."),
        plans=((2, _threshold_plan("Never")),),
        fleets=_threshold_fleets(8),
        check=_check_withdraw_never,
    ),
    Scenario(
        id="withdraw-on-damage",
        doc="On Damage breaks off the moment armour is touched.",
        plans=((2, _threshold_plan("On Damage")),),
        fleets=_threshold_fleets(),
        check=_check_withdraw_on_damage,
    ),
    Scenario(
        id="withdraw-half-armour",
        doc="Half Armour holds above the line and breaks on it.",
        plans=((2, _threshold_plan("Half Armour")),),
        fleets=_threshold_fleets(),
        check=_check_withdraw_half_armour,
    ),
    Scenario(
        id="withdraw-outnumbered-floored",
        doc=("Outnumbered fires before a shot is taken, and the "
             "MIN_DISENGAGE_MOVES floor holds the Defensive plus "
             "Scatter reductions at three board moves."),
        plans=((2, _threshold_plan("Outnumbered", stance="Defensive",
                                   posture="Scatter")),),
        fleets=_threshold_fleets(8),
        check=_check_withdraw_outnumbered,
    ),
]


# =============================================================================
# The empire default plan
# =============================================================================

def _check_inherited_default(field):
    """A commander who never opens the battle screen still fights
    under the empire's doctrine: production hands every new fleet the
    empire default, and the engine reads that plan's axes off it."""
    from backend.services.game_manager import get_game_manager

    harness = field.harness
    assert harness.state(1)["default_battle_plan"] == "Commerce Raid"

    star = harness.my_stars(1)[0]
    before = {f["key"] for f in harness.my_fleets(1)}
    design = next(d for d in harness.state(1)["designs"]
                  if d["name"] == "Long Range Scout")
    assert harness.submit(1, "production", {
        "mode": "Add", "star_key": star["name"], "index": 0,
        "production_order": {"production_type": "SHIP", "quantity": 1,
                             "name": "Long Range Scout",
                             "design_key": design["key"]},
    })["status"] == "applied"

    built = []
    for _ in range(8):
        harness.generate_turn()
        built = [f for f in harness.my_fleets(1)
                 if f["key"] not in before]
        if built:
            break
    assert built, "nothing was built"
    for fleet in built:
        assert fleet["battle_plan"] == "Commerce Raid"

    # The inherited name is not decoration - the engine resolves the
    # doctrine axes through it
    server_data = get_game_manager()._load_game_state(harness.game_id)
    engine = RonBattleEngine(server_data, [])
    fleet_object = server_data.all_empires[1].owned_fleets[built[0]["key"]]
    stack = engine._build_fleet_stacks(fleet_object)[0]
    plan = engine._plan_of(stack)
    assert plan.name == "Commerce Raid"
    assert (plan.posture, plan.withdraw) == ("Scatter", "Outnumbered")
    assert engine._disengage_moves_required(stack) == 5


DEFAULT_PLAN_SCENARIOS = [
    Scenario(
        id="empire-default-inherited-by-new-fleet",
        doc=("Production hands a newly built fleet the empire default "
             "plan, and the engine fights it under that doctrine."),
        defaults=((1, "Commerce Raid"),),
        check=_check_inherited_default,
    ),
]


# =============================================================================
# The suite
# =============================================================================

SCENARIOS = (STANCE_POSTURE_SCENARIOS + ADMIRALTY_SCENARIOS
             + TIER_SCENARIOS + WITHDRAWAL_SCENARIOS
             + DEFAULT_PLAN_SCENARIOS)


def test_scenario_table_is_complete():
    """Twenty-five scenarios, every id distinct."""
    assert len(SCENARIOS) == 25
    assert len({s.id for s in SCENARIOS}) == 25


@pytest.mark.parametrize(
    "scenario", [pytest.param(s, id=s.id) for s in SCENARIOS])
def test_doctrine_scenario(harness, monkeypatch, scenario):
    """Stage the row's world, then let the row assert its own outcome.

    The scenario record carries the setup (plans, empire default,
    fleets) and the check that says what the engine must do with it.
    """
    field = _stage(harness, monkeypatch, scenario)
    scenario.check(field)
