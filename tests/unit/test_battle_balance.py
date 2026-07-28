"""
Battle balance: the properties a fight must have before orders matter.

test_battle_degeneracy.py asks the narrower question - that no doctrine
option wins every matchup. This file asks whether the FIGHT underneath
is balanced at all. An engine can pass every degeneracy check and still
be broken: if beams beat torpedoes at every tech level then no order
rescues a torpedo fleet, and if the weapon pairing decides the battle
outright then the doctrine layer is decoration on a settled result.

Forces are bought, not declared. Each side spends the same resource
budget on identical hulls and differs only in which weapon out of
`backend/data/components.xml` it mounts, so a cheaper weapon buys more
hulls. That makes "is this class worth its cost" the question the
matrix answers, and it keeps the test honest about real game content -
`test_weapon_table_matches_the_catalogue` fails if the catalogue moves
underneath these numbers.

Outcome measure is the one test_battle_degeneracy.py uses, and for the
same reason: ships destroyed plus the armour survivors carry out of
the battle, both divided by the force size. Charging carried damage is
what stops "kill count" being the only currency.

Run with `-s` to print the matrices.
"""

import random
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

from backend.core.data_structures import NovaPoint
from backend.core.game_objects import Fleet, ShipToken
from backend.core.waypoints.waypoint import Waypoint, NoTaskObj
from backend.server.battle import BattleReport, RonBattleEngine
from backend.server.battle.battle_plan import ADMIRALTY_PLANS, BattlePlan

from .test_battle_engine import MockDesign, MockEmpire, MockWeapon

SEEDS = tuple(range(20260728, 20260728 + 8))

# Seeds for the antisymmetry half of test_no_side_bias_in_a_symmetric_battle.
# Deliberately far more than SEEDS, because that assertion is on a MEAN and
# a single mirror margin is noisy. Measured on this engine: over 8 seeds the
# summed mean margin swings between -0.53 and +0.56 with no bias present at
# all, which is wider than the +0.30 a live, proven side bias read at the
# same 8 seeds - so at 8 seeds no tolerance can tell the two apart.
#
# Calibration (2026-07-28, no bias present, attrition and damage
# read-back in the engine). The earlier pin of 32 seeds / 0.5 sat 2.1
# sigma from its own noise: over 8 independent 32-seed blocks the
# no-bias total ranged -0.25 to +0.63 (mean +0.19, sd 0.28), so one
# clean block in eight already read past the 0.5 tolerance. Over 12
# independent 128-seed blocks the no-bias total ranged -0.18 to +0.35
# (mean +0.02, sd 0.20), while the proven list-order bias read +0.84 to
# +1.34 at 32 seeds and concentrates near its +1.1 mean as seeds grow.
# The tolerance below sits 3.2 sigma above the measured no-bias mean
# and below the +0.84 low end of the bias signature, so it still
# catches the +1.0 bias while clearing every clean block observed.
#
# Re-verified 2026-07-29 on the engagement-range engine (give-ground,
# _cap_step, salvo tactic in the Balanced plan): 6 fresh 128-seed
# blocks at offsets 20270101+128k read mean +0.05, sd 0.12, range
# -0.11 to +0.16 - a tighter noise floor than the calibration above,
# so 0.65 now sits about 5 sigma out and the margin only widened
ANTISYMMETRY_SEEDS = tuple(range(SEEDS[0], SEEDS[0] + 128))
ANTISYMMETRY_TOLERANCE = 0.65

COMPONENTS_XML = Path(__file__).resolve().parents[2] / "backend" / "data" \
    / "components.xml"

# One budget, spent identically by both sides. Large enough that the
# cheapest weapon still buys a force with granular losses rather than
# an all-or-nothing wipe
BUDGET = 3000

# The hull every ship in this file is built on. Fixed, so the weapon is
# the only variable and the cost difference between classes shows up as
# a difference in how many hulls the budget buys
HULL_COST = 100
HULL_ARMOR = 250
HULL_SHIELDS = 100


@dataclass(frozen=True)
class WeaponSpec:
    """A weapon as the catalogue ships it. `cost` is the sum of the four
    minerals, which is what a hull actually pays at the queue."""
    name: str
    group: str
    power: int
    range: int
    initiative: int
    accuracy: int
    cost: int
    tech: int


# Three tech tiers, each holding one weapon per class available at that
# tier. Missiles start at Weapons 12 (Jihad), so the early tier has no
# missile entry - that is the catalogue's shape, not an omission
TIERS: Dict[str, Tuple[WeaponSpec, ...]] = {
    "early": (
        WeaponSpec("Laser", "standardBeam", 10, 1, 9, 100, 11, 0),
        WeaponSpec("Beta Torpedo", "torpedo", 12, 4, 1, 45, 34, 5),
        WeaponSpec("Mini Gun", "gatlingGun", 13, 2, 12, 100, 26, 5),
    ),
    "mid": (
        WeaponSpec("Mark IV Blaster", "standardBeam", 66, 2, 7, 100, 27, 14),
        WeaponSpec("Epsilon Torpedo", "torpedo", 48, 5, 2, 65, 56, 14),
        WeaponSpec("Juggernaut Missile", "missile", 150, 5, 1, 20, 91, 16),
        WeaponSpec("Gatling Gun", "gatlingGun", 31, 2, 12, 100, 33, 11),
    ),
    "late": (
        WeaponSpec("Mega Disruptor", "standardBeam", 169, 3, 6, 100, 63, 22),
        WeaponSpec("Upsilon Torpedo", "torpedo", 169, 5, 3, 75, 78, 22),
        WeaponSpec("Doomsday Missile", "missile", 280, 6, 2, 25, 113, 20),
        WeaponSpec("Big Mutha Cannon", "gatlingGun", 204, 2, 13, 100, 59, 23),
    ),
}


@dataclass
class BalanceServer:
    """ServerData surface the engine reads."""
    all_empires: Dict = field(default_factory=dict)
    all_stars: Dict = field(default_factory=dict)
    all_minefields: Dict = field(default_factory=dict)
    all_messages: List = field(default_factory=list)
    turn_year: int = 2400

    def iterate_all_fleets(self):
        for empire in self.all_empires.values():
            yield from empire.owned_fleets.values()


def _hulls_for(weapon: WeaponSpec, budget: int = BUDGET) -> int:
    """How many hulls the budget buys once the weapon is mounted."""
    return budget // (HULL_COST + weapon.cost)


def _split(total: int, parts: int) -> List[int]:
    """Spread `total` hulls over `parts` fleets as evenly as possible, so
    losses are granular and target selection has more than one stack to
    choose between."""
    base, extra = divmod(total, parts)
    return [base + (1 if i < extra else 0) for i in range(parts)]


def _build_force(empire: MockEmpire, weapon: WeaponSpec, hulls: int,
                 plan_name: str) -> List[Fleet]:
    """One fleet per group of hulls, every ship identical apart from the
    weapon under test."""
    fleets = []
    for index, quantity in enumerate(_split(hulls, 3), start=1):
        if quantity == 0:
            continue
        design = MockDesign(key=index, name=f"{weapon.name} Group {index}",
                            mass=100, battle_speed=1.0, has_weapons=True,
                            power_rating=3000)
        design.weapons = [MockWeapon(
            power=weapon.power, range=weapon.range,
            initiative=weapon.initiative, accuracy=weapon.accuracy,
            group=weapon.group)]
        design.cargo_capacity = 0
        empire.designs[design.key] = design

        fleet = Fleet()
        fleet.key = empire.get_next_fleet_key()
        fleet.owner = empire.id
        fleet.name = f"{design.name} {empire.id}"
        fleet.position = NovaPoint(500.0, 500.0)
        fleet.battle_plan = plan_name
        fleet.tokens[design.key] = ShipToken(
            design_key=design.key, design_name=design.name,
            quantity=quantity, armor=HULL_ARMOR, shields=HULL_SHIELDS,
            mass=100, cargo_capacity=0, has_weapons=True)
        fleet.waypoints = [
            Waypoint(position_x=500.0, position_y=500.0,
                     warp_factor=0, task=NoTaskObj()),
            Waypoint(position_x=510.0, position_y=500.0,
                     warp_factor=5, task=NoTaskObj()),
        ]
        empire.owned_fleets[fleet.key] = fleet
        fleets.append(fleet)
    return fleets


def _plan(name: str, **axes) -> BattlePlan:
    """The Balanced standard plan with named axes moved. `attack` is
    forced to Everyone because relation filtering is not under test."""
    base = ADMIRALTY_PLANS["Balanced"].to_dict()
    base.update(axes)
    base["name"] = name
    base["attack"] = "Everyone"
    return BattlePlan.from_dict(base)


def _fight(weapon_a: WeaponSpec, weapon_b: WeaponSpec, seed: int,
           plan_a: BattlePlan = None, plan_b: BattlePlan = None,
           budget_a: int = BUDGET, budget_b: int = BUDGET,
           order: Tuple[int, int] = (1, 2)) -> float:
    """One battle. Returns side A's advantage: positive means A came out
    of it better than B did.

    `order` is which empire's fleets go first into the stack list the
    engine works from. Nothing about the battle should depend on it -
    that is what test_no_side_bias_in_a_symmetric_battle asserts."""
    plan_a = plan_a or _plan("A")
    plan_b = plan_b or _plan("B")

    server = BalanceServer()
    for empire_id, plan in ((1, plan_a), (2, plan_b)):
        empire = MockEmpire(id=empire_id)
        empire.battle_plans[plan.name] = plan
        server.all_empires[empire_id] = empire

    hulls = {1: _hulls_for(weapon_a, budget_a),
             2: _hulls_for(weapon_b, budget_b)}
    fleets = {
        1: _build_force(server.all_empires[1], weapon_a, hulls[1],
                        plan_a.name),
        2: _build_force(server.all_empires[2], weapon_b, hulls[2],
                        plan_b.name),
    }

    engine = RonBattleEngine(server, [])
    engine._random = random.Random(seed)

    battle = BattleReport()
    stacks = engine._generate_stacks(fleets[order[0]] + fleets[order[1]],
                                     NovaPoint(500.0, 500.0))
    engine._position_stacks(stacks, battle)
    engine._do_battle(stacks, battle)
    engine._apply_withdrawal_consequences(stacks, battle)

    cost: Dict[int, float] = {}
    for owner in (1, 2):
        carried = sum(token.quantity * token.damage_percent / 100.0
                      for fleet in fleets[owner]
                      for token in fleet.tokens.values())
        cost[owner] = (battle.losses.get(owner, 0) + carried) / hulls[owner]

    return cost[2] - cost[1]


def _series(weapon_a: WeaponSpec, weapon_b: WeaponSpec, **kwargs) -> int:
    """How many of the seeded runs side A came out ahead."""
    return sum(1 for seed in SEEDS
               if _fight(weapon_a, weapon_b, seed, **kwargs) > 1e-9)


def _class_matrix(tier: str) -> Tuple[Dict[Tuple[str, str], int], List[str]]:
    """Wins of every weapon class against every other, at one tech tier.

    Each pairing is fought in BOTH role assignments and the counts are
    summed, so a side bias in the engine cannot show up as one class
    looking stronger than another.
    """
    weapons = {w.group: w for w in TIERS[tier]}
    names = list(weapons)
    wins: Dict[Tuple[str, str], int] = {}
    for a in names:
        for b in names:
            if a == b:
                continue
            wins[(a, b)] = _series(weapons[a], weapons[b]) + \
                (len(SEEDS) - _series(weapons[b], weapons[a]))
    return wins, names


def _render(title: str, wins: Dict[Tuple[str, str], int],
            names: List[str], runs: int) -> str:
    width = max(len(n) for n in names) + 2
    lines = [f"{title} (wins out of {runs} per cell)",
             " " * (width + 4) + "".join(f"{n:>20}" for n in names)]
    for a in names:
        row = f"    {a:<{width}}"
        for b in names:
            row += "                   -" if a == b else f"{wins[(a, b)]:>20}"
        lines.append(row)
    return "\n".join(lines)


def test_weapon_table_matches_the_catalogue():
    """The tiers above are transcribed from components.xml. If the
    catalogue is retuned this fails, rather than the balance matrices
    quietly measuring numbers the game no longer ships."""
    root = ET.parse(COMPONENTS_XML).getroot()
    catalogue = {}
    for component in root.findall(".//Component"):
        prop = component.find("Property")
        if prop is None or prop.findtext("Group") is None:
            continue
        item, cost = component.find("Item"), component.find("Cost")
        catalogue[item.findtext("Name")] = WeaponSpec(
            name=item.findtext("Name"),
            group=prop.findtext("Group"),
            power=int(prop.findtext("Power")),
            range=int(prop.findtext("Range")),
            initiative=int(prop.findtext("Initiative")),
            accuracy=int(prop.findtext("Accuracy") or 100),
            cost=sum(int(cost.findtext(m) or 0)
                     for m in ("Boranium", "Ironium", "Germanium", "Energy")),
            tech=int(component.find("Tech").findtext("Weapons")))

    for tier, weapons in TIERS.items():
        for weapon in weapons:
            assert weapon.name in catalogue, \
                f"{tier}: '{weapon.name}' is no longer in the catalogue"
            assert catalogue[weapon.name] == weapon, (
                f"{tier}: '{weapon.name}' has been retuned\n"
                f"  catalogue: {catalogue[weapon.name]}\n"
                f"  this file: {weapon}")


def test_every_tier_buys_a_force_worth_fighting_with():
    """The matrices mean nothing if a class cannot afford enough hulls
    for losses to be granular."""
    for tier, weapons in TIERS.items():
        for weapon in weapons:
            hulls = _hulls_for(weapon)
            assert hulls >= 9, \
                f"{tier}: {weapon.name} buys only {hulls} hulls"


def test_no_weapon_class_dominates_at_equal_cost():
    """No class is the right purchase against every other class it can
    meet at its own tech tier.

    This is the balance question the doctrine layer sits on top of. A
    class that beats every rival at equal cost makes the shipyard
    decision fake in the same way a dominant stance makes the battle
    order fake, and no plan a commander writes can compensate.
    """
    failures = []
    for tier in TIERS:
        wins, names = _class_matrix(tier)
        runs = len(SEEDS) * 2
        rendered = _render(f"{tier} tier", wins, names, runs)
        print("\n" + rendered)

        for a in names:
            beaten_by = [b for b in names
                         if b != a and wins[(b, a)] > wins[(a, b)]]
            if not beaten_by:
                failures.append(f"{tier}: {a} beats every other class\n"
                                f"{rendered}")
    assert not failures, "\n\n".join(failures)


def test_no_side_bias_in_a_symmetric_battle():
    """Two identical forces on identical orders must not have a winner
    decided by which side the engine positioned first.

    Any such edge would contaminate every other matrix in this file and
    in test_battle_degeneracy.py, because an option would inherit the
    advantage of whichever side it happened to be assigned.

    Two assertions, and the second is the load-bearing one. Counting
    wins under a loose tolerance passes on a real bias as long as the
    bias is small - this test did exactly that against a live defect,
    where the engine moved every stack against positions its enemy had
    already vacated and handed the last-listed empire a measured
    advantage in every battle. What it could not survive is a claim
    about the SIZE of the advantage, so the second assertion runs each
    mirror with the fleet lists both ways round and requires the mean
    margin, summed over every weapon, to sit near zero either way. A
    battle whose outcome depends on the order empires happen to occupy
    in a list fails it; a battle that merely has a small residue of
    seed noise does not.
    """
    for tier, weapons in TIERS.items():
        for weapon in weapons:
            margins = [_fight(weapon, weapon, seed) for seed in SEEDS]
            a_wins = sum(1 for m in margins if m > 1e-9)
            b_wins = sum(1 for m in margins if m < -1e-9)
            assert abs(a_wins - b_wins) <= len(SEEDS) // 2, (
                f"{tier}/{weapon.name}: mirror match went {a_wins}-{b_wins} "
                f"to side A over {len(SEEDS)} seeds; the engine favours a "
                f"side\nmargins: {[round(m, 4) for m in margins]}")

    for order in ((1, 2), (2, 1)):
        per_weapon = {}
        for tier, weapons in TIERS.items():
            for weapon in weapons:
                margins = [_fight(weapon, weapon, seed, order=order)
                           for seed in ANTISYMMETRY_SEEDS]
                per_weapon[f"{tier}/{weapon.name}"] = \
                    sum(margins) / len(margins)

        total = sum(per_weapon.values())
        print(f"\nempire-{order[0]}-first: summed mean margin {total:+.4f}")
        assert abs(total) <= ANTISYMMETRY_TOLERANCE, (
            f"with empire {order[0]}'s fleets listed first the mirror "
            f"matches summed to a mean margin of {total:+.4f} over "
            f"{len(ANTISYMMETRY_SEEDS)} seeds, past the {ANTISYMMETRY_TOLERANCE} "
            f"noise floor; the engine's outcome depends on list order\n" +
            "\n".join(f"    {name:<28} {mean:+.4f}"
                      for name, mean in per_weapon.items()))


def test_a_bigger_budget_wins():
    """Half again the resources must tell. If it does not, the fight is
    decided by something other than what the commander bought."""
    for tier, weapons in TIERS.items():
        for weapon in weapons:
            richer = sum(1 for seed in SEEDS
                         if _fight(weapon, weapon, seed,
                                   budget_a=BUDGET * 3 // 2) > 1e-9)
            assert richer >= len(SEEDS) - 1, (
                f"{tier}/{weapon.name}: a 1.5x budget won only {richer} of "
                f"{len(SEEDS)}")


def test_higher_tech_wins_at_equal_cost():
    """Researching weapons must pay. The later weapon of a class, bought
    with the same resources, must beat its earlier self."""
    for early, late in (("early", "mid"), ("mid", "late")):
        shared = {w.group for w in TIERS[early]} & {w.group
                                                    for w in TIERS[late]}
        for group in sorted(shared):
            old = next(w for w in TIERS[early] if w.group == group)
            new = next(w for w in TIERS[late] if w.group == group)
            wins = _series(new, old)
            assert wins >= len(SEEDS) - 1, (
                f"{group}: {new.name} (tech {new.tech}) beat {old.name} "
                f"(tech {old.tech}) only {wins} of {len(SEEDS)} at equal cost")


def test_doctrine_changes_the_outcome():
    """Stance must move the result in most weapon pairings.

    The degeneracy matrix can be satisfied while doctrine is inert in
    most of the fights it measures - two options that never change
    anything tie everywhere, and a tie counts as neither a win nor a
    loss. This asserts the other half: that giving a different order
    actually changes how the battle comes out often enough for the
    order to be worth giving.
    """
    aggressive = _plan("Aggressive", stance="Aggressive")
    defensive = _plan("Defensive", stance="Defensive")

    live, total = 0, 0
    for tier, weapons in TIERS.items():
        for weapon_a in weapons:
            for weapon_b in weapons:
                total += 1
                changed = any(
                    abs(_fight(weapon_a, weapon_b, seed, plan_a=aggressive)
                        - _fight(weapon_a, weapon_b, seed, plan_a=defensive))
                    > 1e-9
                    for seed in SEEDS)
                if changed:
                    live += 1

    assert live >= total * 0.5, (
        f"stance changed the outcome in only {live} of {total} weapon "
        f"pairings; the order is inert in most fights")
