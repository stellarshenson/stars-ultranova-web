"""
Anti-degeneracy: no stance, posture or standard plan wins every matchup.

This game has already been beaten once by a dominant strategy (DEF-8,
escort spam outscoring expansion), and that lesson is why this test
exists. A doctrine layer whose best option is the same option in every
fight is not a decision, it is a chore.

The proof is a seeded round-robin. Every option meets every other over
several seeds across nine force pairings - each archetype against
itself and against both of the others in both role assignments, so
neither option is handed the better force. Forces are equal-cost by
construction (identical total armour and shields per side, asserted
below); the doctrine option is the only variable.

Outcome measure, per side:

    score = enemy ships destroyed / enemy ships
          - own ships destroyed / own ships
          - damage carried out of the battle by the survivors

Both permanent losses this game books are charged. Ships destroyed are
gone; the armour a survivor lost is carried out of the battle on
ShipToken.damage_percent (RonBattleEngine._write_back_damage, the
canonical rule - C# hands the fleet's own token to the stack) and
costs the repair step turns to heal, with a withdrawal adding
WITHDRAWAL_DAMAGE_PERCENT on top. Charging carried damage is what
makes "take less damage" an order worth giving: without it the only
currency is kills, and every axis collapses into whichever option
buys the most damage output.

The measure pays for killing AND for not dying: a plan that runs away
intact scores zero rather than winning by default, and a plan that
trades evenly scores zero rather than winning by aggression.

Each side fields three fleets so destruction is granular rather than
all-or-nothing, and so target selection has real choices to make.

Run with `-s` to print the three matrices.
"""

import random
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import pytest

from backend.core.data_structures import NovaPoint
from backend.core.game_objects import Fleet, ShipToken
from backend.core.waypoints.waypoint import Waypoint, NoTaskObj
from backend.server.battle import BattleReport, RonBattleEngine
from backend.server.battle.battle_plan import (
    ADMIRALTY_PLANS,
    POSTURES,
    STANCES,
    WITHDRAWAL_DAMAGE_PERCENT,
    BattlePlan,
)

from .test_battle_engine import MockDesign, MockEmpire, MockWeapon

SEEDS = (20260728, 31337, 4242)


@dataclass
class Squadron:
    """One fleet in a task force: a hull profile and how many of it."""
    label: str
    quantity: int
    armor: int
    shields: int
    power_rating: int
    armed: bool
    cargo_capacity: int = 0
    power_multiplier: float = 1.0
    # Weapon initiative relative to the archetype's. Real fleets are
    # not uniform - heavy mounts fire late, light ones early - and a
    # force where every gun shares one initiative would let a stance's
    # small initiative shift reorder every exchange deterministically,
    # which is an artefact of the force, not of the doctrine
    initiative_delta: int = 0


# Every task force is this composition, whatever it is armed with, so
# both sides are equal-cost by construction (asserted in
# test_the_forces_are_equal_cost) and the doctrine option is the only
# variable. The mix matters: a plan's target tiers name real classes
# (ship_role.py), so a plan that spends its fire on the wrong class
# pays for it - with a single-role force the tiers would be inert and
# the matrix would only measure stance and posture
TASK_FORCE = (
    Squadron("Capital", 2, 250, 100, 3000, True, power_multiplier=2.0,
             initiative_delta=-2),
    Squadron("Escort", 5, 60, 30, 1000, True, initiative_delta=+2),
    Squadron("Freighter", 3, 40, 0, 0, False, cargo_capacity=200),
)

TASK_FORCE_SHIPS = sum(s.quantity for s in TASK_FORCE)


@dataclass
class Archetype:
    """What a task force is armed with. Defence is fixed by TASK_FORCE,
    so archetypes differ only in reach, firing order and how the damage
    is delivered - the differently-armed enemy the doctrine axes trade
    against."""
    name: str
    power: int
    weapon_range: int
    initiative: int
    accuracy: int
    group: str
    battle_speed: float


BEAM_LINE = Archetype("Beam Line", 30, 2, 5, 75, "standardBeam", 1.0)
MISSILE_BOAT = Archetype("Missile Boat", 45, 5, 3, 45, "torpedo", 0.75)
SABRE_WING = Archetype("Sabre Wing", 18, 1, 9, 75, "standardBeam", 1.5)

ARCHETYPES = (BEAM_LINE, MISSILE_BOAT, SABRE_WING)

# Nine pairings: each archetype against itself, and every cross pairing
# in BOTH role assignments so no option is systematically handed the
# better force
PAIRINGS: Tuple[Tuple[Archetype, Archetype], ...] = tuple(
    (a, b) for a in ARCHETYPES for b in ARCHETYPES
)


@dataclass
class MatrixServer:
    """ServerData surface both the engine and the doctrine layer read."""
    all_empires: Dict = field(default_factory=dict)
    all_stars: Dict = field(default_factory=dict)
    all_minefields: Dict = field(default_factory=dict)
    all_messages: List = field(default_factory=list)
    turn_year: int = 2400

    def iterate_all_fleets(self):
        for empire in self.all_empires.values():
            yield from empire.owned_fleets.values()


def _build_task_force(empire: MockEmpire, arch: Archetype,
                      plan_name: str) -> List[Fleet]:
    """One fleet per squadron, so destruction is granular and target
    selection has real classes to choose between."""
    fleets = []
    for index, squadron in enumerate(TASK_FORCE, start=1):
        design = MockDesign(key=index, name=f"{arch.name} {squadron.label}",
                            mass=100, battle_speed=arch.battle_speed,
                            has_weapons=squadron.armed,
                            power_rating=squadron.power_rating)
        design.weapons = [MockWeapon(
            power=int(arch.power * squadron.power_multiplier),
            range=arch.weapon_range,
            initiative=arch.initiative + squadron.initiative_delta,
            accuracy=arch.accuracy, group=arch.group)] if squadron.armed \
            else []
        # Read by the role cascade (ship_role.infer_battle_role) - a
        # hold with no weapons is what makes a freighter Logistics
        design.cargo_capacity = squadron.cargo_capacity
        empire.designs[design.key] = design

        fleet = Fleet()
        fleet.key = empire.get_next_fleet_key()
        fleet.owner = empire.id
        fleet.name = f"{design.name} {empire.id}"
        fleet.position = NovaPoint(500.0, 500.0)
        fleet.battle_plan = plan_name
        fleet.tokens[design.key] = ShipToken(
            design_key=design.key, design_name=design.name,
            quantity=squadron.quantity, armor=squadron.armor,
            shields=squadron.shields, mass=100,
            cargo_capacity=squadron.cargo_capacity,
            has_weapons=squadron.armed)
        fleet.waypoints = [
            Waypoint(position_x=500.0, position_y=500.0,
                     warp_factor=0, task=NoTaskObj()),
            Waypoint(position_x=510.0, position_y=500.0,
                     warp_factor=5, task=NoTaskObj()),
        ]
        empire.owned_fleets[fleet.key] = fleet
        fleets.append(fleet)
    return fleets


def _fight(plan_a: BattlePlan, arch_a: Archetype,
           plan_b: BattlePlan, arch_b: Archetype, seed: int) -> float:
    """One battle. Returns side A's score minus side B's score."""
    server = MatrixServer()
    for empire_id, plan in ((1, plan_a), (2, plan_b)):
        empire = MockEmpire(id=empire_id)
        empire.battle_plans[plan.name] = plan
        server.all_empires[empire_id] = empire

    fleets = {
        1: _build_task_force(server.all_empires[1], arch_a, plan_a.name),
        2: _build_task_force(server.all_empires[2], arch_b, plan_b.name),
    }

    engine = RonBattleEngine(server, [])
    engine._random = random.Random(seed)

    battle = BattleReport()
    stacks = engine._generate_stacks(fleets[1] + fleets[2],
                                     NovaPoint(500.0, 500.0))
    engine._position_stacks(stacks, battle)
    engine._do_battle(stacks, battle)
    engine._apply_withdrawal_consequences(stacks, battle)

    cost: Dict[int, float] = {1: 0.0, 2: 0.0}
    for owner in (1, 2):
        ships = float(TASK_FORCE_SHIPS)
        destroyed = battle.losses.get(owner, 0)
        # A withdrawal carries damage out of the battle: charge it on
        # the ships that survived to carry it
        carried = 0.0
        for fleet in fleets[owner]:
            for token in fleet.tokens.values():
                carried += (token.quantity * token.damage_percent / 100.0)
        cost[owner] = (destroyed + carried) / ships

    return cost[2] - cost[1]


def _round_robin(options: Dict[str, Tuple[BattlePlan, ...]]
                 ) -> Tuple[Dict[Tuple[int, str, str], int], List[str], int]:
    """
    Wins of every option against every other, kept per force pairing.

    wins[(pairing, A, B)] counts the runs A beat B when the forces are
    that pairing, over every seed and every doctrine context. A and B
    meet in both role assignments of each cross pairing, so the count
    is symmetric in opportunity - a lopsided cell is the option
    talking, not the force.
    """
    names = list(options)
    contexts = len(next(iter(options.values())))
    wins: Dict[Tuple[int, str, str], int] = {}

    for index, (arch_a, arch_b) in enumerate(PAIRINGS):
        for a in names:
            for b in names:
                if a == b:
                    continue
                count = 0
                for context in range(contexts):
                    for seed in SEEDS:
                        margin = _fight(options[a][context], arch_a,
                                        options[b][context], arch_b, seed)
                        if margin > 1e-9:
                            count += 1
                wins[(index, a, b)] = count

    return wins, names, len(SEEDS) * contexts


def _render(title: str, wins: Dict[Tuple[int, str, str], int],
            names: List[str], runs: int) -> str:
    """Per-pairing win/loss record of every option, then the totals."""
    width = max(len(n) for n in names) + 2
    lines = [f"{title} (wins out of {runs} per cell)"]

    for index, (arch_a, arch_b) in enumerate(PAIRINGS):
        lines.append(f"  {arch_a.name} vs {arch_b.name}")
        for a in names:
            row = f"    {a:<{width}}"
            for b in names:
                if a == b:
                    row += "          -"
                else:
                    row += f"{wins[(index, a, b)]:>11}"
            lines.append(row)

    lines.append("  totals")
    for a in names:
        total = sum(wins[(i, a, b)] for i in range(len(PAIRINGS))
                    for b in names if b != a)
        lines.append(f"    {a:<{width}}{total:>11}")
    return "\n".join(lines)


def _assert_non_degenerate(title, result, max_spread=None):
    """
    No option is the right order against every force it can meet.

    The bar is per MATCHUP - one force pairing at a time - and not on
    the summed matrix. The sum is the wrong quantity to test: options
    that trade wins pairing for pairing end up a win or two apart out
    of a hundred and sixty, so a summed-matrix test reads noise as
    domination and can only be satisfied by fitting a modifier table
    to a seed list. What the criterion asks is that no option "wins
    every matchup": every option must have a force pairing where
    another option would have been the better order, and every option
    must be the better order somewhere.

    `max_spread` additionally caps how far the best option's total may
    run ahead of the worst, which is the guard against a slow runaway
    that per-matchup counting alone would tolerate. It is applied to
    the general-purpose axes (stance, posture) and not to the standard
    plans, where the specialists - Commerce Raid hunting freighters,
    Fighting Retreat leaving early - are meant to lose a stand-up
    fight they were never written for.
    """
    wins, names, runs = result
    rendered = _render(title, wins, names, runs)
    print("\n" + rendered)

    pairings = range(len(PAIRINGS))
    beaten = {a: [(i, b) for i in pairings for b in names
                  if b != a and wins[(i, b, a)] > wins[(i, a, b)]]
              for a in names}
    victor = {a: [(i, b) for i in pairings for b in names
                  if b != a and wins[(i, a, b)] > wins[(i, b, a)]]
              for a in names}

    unbeaten = [a for a in names if not beaten[a]]
    assert not unbeaten, (
        f"{title}: {unbeaten} wins every matchup\n{rendered}")

    inert = [a for a in names if not victor[a]]
    assert not inert, (
        f"{title}: {inert} never wins a matchup\n{rendered}")

    if max_spread is not None:
        totals = {a: sum(wins[(i, a, b)] for i in pairings
                         for b in names if b != a) for a in names}
        spread = max(totals.values()) / max(1, min(totals.values()))
        assert spread <= max_spread, (
            f"{title}: totals spread {spread:.2f} exceeds {max_spread}"
            f"\n{rendered}")


# Two doctrine contexts. A stance or posture that forfeits or shortens
# disengagement is worth nothing to a plan that never breaks off, so
# measuring only one of these would hide half of what the axis buys
STAND_AND_FIGHT = {"withdraw": "Never"}
BREAK_OFF = {"withdraw": "Half Armour"}
CONTEXTS = (STAND_AND_FIGHT, BREAK_OFF)


def _variants(name: str, **axes) -> Tuple[BattlePlan, ...]:
    """The Balanced standard plan with one axis moved, in each doctrine
    context, so a stance or posture matrix varies nothing else."""
    plans = []
    for context in CONTEXTS:
        base = ADMIRALTY_PLANS["Balanced"].to_dict()
        base.update(axes)
        base.update(context)
        base["name"] = name
        base["attack"] = "Everyone"
        plans.append(BattlePlan.from_dict(base))
    return tuple(plans)


def test_the_forces_are_equal_cost_and_carry_every_role():
    """The matrices only mean something if both sides field the same
    force - the doctrine option must be the only variable - and if the
    force carries more than one battle role, or the target tiers would
    be inert."""
    from backend.core.components.ship_role import ShipRole, battle_role_of

    server = MatrixServer()
    server.all_empires[1] = MockEmpire(id=1)
    server.all_empires[2] = MockEmpire(id=2)
    a = _build_task_force(server.all_empires[1], BEAM_LINE, "x")
    b = _build_task_force(server.all_empires[2], MISSILE_BOAT, "x")

    def defence(fleets):
        return sum(t.quantity * (t.armor + t.shields)
                   for f in fleets for t in f.tokens.values())

    assert defence(a) == defence(b) == 1270
    assert sum(t.quantity for f in a for t in f.tokens.values()) == \
        TASK_FORCE_SHIPS

    roles = {battle_role_of(d)
             for d in server.all_empires[1].designs.values()}
    assert roles == {ShipRole.CAPITAL, ShipRole.ESCORT, ShipRole.LOGISTICS}


def test_no_standard_plan_wins_every_matchup():
    plans = {}
    for name, plan in ADMIRALTY_PLANS.items():
        copy = BattlePlan.from_dict(plan.to_dict())
        # Every plan must be willing to engage in the abstract fight;
        # relation filtering is not the axis under test. Each plan
        # names its own withdrawal, so there is one context
        copy.attack = "Everyone"
        plans[name] = (copy,)

    _assert_non_degenerate("Admiralty standard plans", _round_robin(plans))


def test_no_stance_wins_every_matchup():
    stances = {name: _variants(name, stance=name) for name in STANCES}
    # Every stance is a general-purpose order, so the totals are held
    # within a quarter of each other as well
    _assert_non_degenerate("Stances", _round_robin(stances),
                           max_spread=1.25)


def test_no_posture_wins_every_matchup():
    postures = {name: _variants(name, posture=name) for name in POSTURES}
    _assert_non_degenerate("Postures", _round_robin(postures),
                           max_spread=1.25)
