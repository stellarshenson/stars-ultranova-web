"""
Seeded e2e: twenty-five scenarios on the fight itself.

test_battle_plans.py and test_battle_roles.py pin the ORDER layer -
that a plan is stored, assigned and honored. This file pins the layer
underneath it: what the four weapon classes do to shields and armour,
what range costs a beam, what a starbase is worth, and what happens at
the edges (an unarmed force, a lone ship, a 250-ship stack, three
empires at one point, two lines that can never reach each other).

Every scenario is a row in SCENARIOS, driven by one test body. A row
names real designs built through the real design command out of
backend/data/components.xml, places them by state surgery at a deep
space point (the harness pattern from test_battle_plans.py), and then
calls RonBattleEngine directly instead of generating a turn - a turn
adds nothing a fight scenario reads, and 32 battles run in under a
second that way. Rows that need a control (does a capacitor raise
damage? does standing off cost damage?) carry a second force list and
fight it under the same seed.

Distances are the engine's own metric: NovaPoint.distance_to is
|dx| + |dy| (NovaPoint.cs:255-262, preserved in the port), scaled by
RonBattleEngine.GRID_SCALE units per weapon-range square.

Three rows are xfail: a canonical mechanic the engine does not have
yet. They are written as they must pass once it lands, not weakened
into something that passes now.
"""

import random
from dataclasses import dataclass
from typing import Callable, Tuple

import pytest

from backend.server.battle import RonBattleEngine
from backend.server.battle.battle_step import TokenDefence

from .test_battle_plans import _deep_space_point

SEED = 20260801

RESEARCH_FIELDS = ("Biotechnology", "Electronics", "Energy",
                   "Propulsion", "Weapons", "Construction")

# Hull cells, from the catalogue's Hull property:
#   Destroyer       2/22 Weapon, 6 Mechanical, 10 Engine, 11 Armor(2),
#                   12 General Purpose, 16 Electrical
#   Battleship      10 Engine(4), 7/17 Weapon(6), 12 Armor(6),
#                   6/16 Electrical(3), 14 Scanner Electrical Mechanical
#   Space Station   1 Shield(16), 9/15 Shield or Armor(16),
#                   7/17 Electrical(3)
#   Orbital Fort    7/17 Weapon(12), 11/13 Shield or Armor(12)
#   Small Freighter 10 Engine, Scout 11 Engine
ENGINE = "Trans-Star 10"


def _cell(number, component, count=1):
    return {"cell_number": number, "component": component, "count": count}


# Every design this file fights with. Weapon stats quoted in the
# comments are the catalogue's own (backend/data/components.xml).
DESIGNS = {
    # Colloidal Phaser: standardBeam, power 26, range 3, initiative 5
    "Beam Destroyer": ("Destroyer", [
        _cell(10, ENGINE), _cell(2, "Colloidal Phaser"),
        _cell(11, "Crobmnium", 2)]),
    # 2x Energy Capacitor stack to 21 percent
    "Capacitor Destroyer": ("Destroyer", [
        _cell(10, ENGINE), _cell(2, "Colloidal Phaser"),
        _cell(11, "Crobmnium", 2), _cell(16, "Energy Capacitor"),
        _cell(12, "Energy Capacitor")]),
    # Laser: standardBeam, power 10, range 1, initiative 9
    "Laser Destroyer": ("Destroyer", [
        _cell(10, ENGINE), _cell(2, "Laser"), _cell(22, "Laser"),
        _cell(11, "Crobmnium", 2)]),
    # Mark IV Blaster: standardBeam, power 66, range 2, initiative 7
    "Blaster Destroyer": ("Destroyer", [
        _cell(10, ENGINE), _cell(2, "Mark IV Blaster"),
        _cell(11, "Crobmnium", 2)]),
    # Gatling Gun: gatlingGun, power 31, range 2, initiative 12
    "Gatling Destroyer": ("Destroyer", [
        _cell(10, ENGINE), _cell(2, "Gatling Gun"),
        _cell(11, "Crobmnium", 2)]),
    # Mega Disruptor: standardBeam, power 169, range 3
    "Disruptor Destroyer": ("Destroyer", [
        _cell(10, ENGINE), _cell(2, "Mega Disruptor"),
        _cell(22, "Mega Disruptor"), _cell(11, "Crobmnium", 2)]),
    # Epsilon Torpedo: torpedo, power 48, range 5, accuracy 65
    "Torpedo Destroyer": ("Destroyer", [
        _cell(10, ENGINE), _cell(2, "Epsilon Torpedo"),
        _cell(22, "Epsilon Torpedo"), _cell(11, "Crobmnium", 2)]),
    # 2x Battle Computer stack to 36 percent accuracy
    "Computer Destroyer": ("Destroyer", [
        _cell(10, ENGINE), _cell(2, "Epsilon Torpedo"),
        _cell(22, "Epsilon Torpedo"), _cell(11, "Crobmnium", 2),
        _cell(16, "Battle Computer"), _cell(12, "Battle Computer")]),
    # Single-tube variants for the electronics ratio rows. Their
    # exact-ratio checks need the target to ride out the full round
    # cap in BOTH seeded runs (an early kill desynchronises the paired
    # accuracy rolls), and at canonical torpedo power (the /10 was the
    # DEF-33 divisor, lifted) one Epsilon tube throws 48 x 0.65 = 31.2
    # expected per round - 1872 over 60 rounds against the Bare
    # Station's 2900 (500 hull + 32 x 75 Crobmnium)
    "Light Torpedo Destroyer": ("Destroyer", [
        _cell(10, ENGINE), _cell(2, "Epsilon Torpedo"),
        _cell(11, "Crobmnium", 2)]),
    "Light Computer Destroyer": ("Destroyer", [
        _cell(10, ENGINE), _cell(2, "Epsilon Torpedo"),
        _cell(11, "Crobmnium", 2),
        _cell(16, "Battle Computer"), _cell(12, "Battle Computer")]),
    # Juggernaut Missile: missile, power 150, range 5, accuracy 20
    "Missile Destroyer": ("Destroyer", [
        _cell(10, ENGINE), _cell(2, "Juggernaut Missile"),
        _cell(11, "Crobmnium", 2)]),
    # Doomsday Missile: missile, power 280, range 6
    "Doomsday Destroyer": ("Destroyer", [
        _cell(10, ENGINE), _cell(2, "Doomsday Missile"),
        _cell(22, "Doomsday Missile"), _cell(11, "Crobmnium", 2)]),
    # Power rating 2433 clears CAPITAL_SHIP_POWER_RATING, so the role
    # cascade files this as a Capital Ship and not an Escort
    "Capital Ship": ("Battleship", [
        _cell(10, ENGINE, 4), _cell(7, "Mega Disruptor", 6),
        _cell(17, "Mega Disruptor", 6), _cell(12, "Crobmnium", 6)]),
    # Same rating, bare hull armour - killable inside one battle, so
    # the cascade can be watched moving down its tiers
    "Thin Capital": ("Battleship", [
        _cell(10, ENGINE, 4), _cell(7, "Mega Disruptor", 6),
        _cell(17, "Mega Disruptor", 6)]),
    "Freighter": ("Small Freighter", [_cell(10, ENGINE)]),
    "Picket": ("Scout", [_cell(11, ENGINE)]),
    # Immobile anvils: a starbase never moves (RonBattleEngine
    # _move_stacks skips it), so an unarmed one is a fixed target and
    # the geometry of a run is reproducible
    "Bare Station": ("Space Station", [
        _cell(9, "Crobmnium", 16), _cell(15, "Crobmnium", 16)]),
    "Shielded Station": ("Space Station", [
        _cell(9, "Crobmnium", 16), _cell(15, "Crobmnium", 16),
        _cell(1, "Complete Phase Shield", 16)]),
    # 6x Jammer 20 stack to 1 - 0.8^6 = 73.7856 percent
    "Jammed Station": ("Space Station", [
        _cell(9, "Crobmnium", 16), _cell(15, "Crobmnium", 16),
        _cell(7, "Jammer 20", 3), _cell(17, "Jammer 20", 3)]),
    "War Fort": ("Orbital Fort", [
        _cell(7, "Mega Disruptor", 12), _cell(11, "Crobmnium", 12)]),
    # Delta Torpedo: torpedo, range 4 - one square short of a raider
    # standing off at 410 board units
    "Delta Fort": ("Orbital Fort", [
        _cell(7, "Delta Torpedo", 6), _cell(11, "Crobmnium", 12)]),
    # Brace anvils. Brace holds a FIRING position, so it holds an
    # ARMED hull only (RonBattleEngine._move_stacks, DEF-31) - an
    # unarmed one keeps the canonical run-from-the-guns behaviour and
    # would never stand still to be shot at. One Laser (power 10,
    # range 1) is what makes them armed; what it shoots back is noise
    # against Crobmnium and every row carries it in its control too
    "Plain Battleship": ("Battleship", [
        _cell(10, ENGINE, 4), _cell(12, "Crobmnium", 6),
        _cell(7, "Laser")]),
    "Deflector Battleship": ("Battleship", [
        _cell(10, ENGINE, 4), _cell(12, "Crobmnium", 6),
        _cell(7, "Laser"), _cell(14, "Beam Deflector")]),
    "Jammed Battleship": ("Battleship", [
        _cell(10, ENGINE, 4), _cell(12, "Crobmnium", 6),
        _cell(7, "Laser"),
        _cell(6, "Jammer 20", 3), _cell(16, "Jammer 20", 3)]),
}


# Plans the rows fight under. Tiers are Victims values; a plan that
# names no matching tier does not engage at all, which is what the
# "matches no role" row rests on.
ANY_TIERS = {"primary_target": 0, "secondary_target": 4,
             "tertiary_target": 5, "quaternary_target": 5,
             "quinary_target": 5}
STAND_OFF = dict(ANY_TIERS, name="Stand Off",
                 tactic="Maximise Damage Ratio")
CLOSE_IN = dict(ANY_TIERS, name="Close In", tactic="Maximise Damage")
BRACE = dict(ANY_TIERS, name="Brace", posture="Brace")
CASCADE = {"name": "Cascade", "primary_target": 2, "secondary_target": 3,
           "tertiary_target": 7, "quaternary_target": 7,
           "quinary_target": 7}
ESCORTS_ONLY = {"name": "Escorts Only", "primary_target": 3,
                "secondary_target": 3, "tertiary_target": 3,
                "quaternary_target": 3, "quinary_target": 3}
BOMBERS_ONLY = {"name": "Bombers Only", "primary_target": 1,
                "secondary_target": 1, "tertiary_target": 1,
                "quaternary_target": 1, "quinary_target": 1}
# Every tier names Starbase, so the gatling can engage nothing else -
# which is what makes any damage to the escort beside it a sweep and
# not ordinary target selection
STARBASE_ONLY = {"name": "Starbase Only", "primary_target": 0,
                 "secondary_target": 0, "tertiary_target": 0,
                 "quaternary_target": 0, "quinary_target": 0}


@dataclass(frozen=True)
class Force:
    """One fleet placed at the rendezvous."""
    empire: int
    design: str
    quantity: int = 1
    plan: str = "Balanced"


@dataclass(frozen=True)
class Scenario:
    name: str
    doc: str
    forces: Tuple[Force, ...]
    check: Callable
    plans: Tuple[dict, ...] = ()
    control: Tuple[Force, ...] = ()
    players: int = 2
    xfail: str = ""


# ---------------------------------------------------------------- setup


def _grant_tech(harness, level=26):
    """Set every research field of every empire so the whole catalogue
    validates (pattern from test_electronics_battle.py)."""
    from backend.services.game_manager import get_game_manager

    manager = get_game_manager()
    server_data = manager._load_game_state(harness.game_id)
    for empire in server_data.all_empires.values():
        for tech_field in RESEARCH_FIELDS:
            empire.research_levels.levels[tech_field] = level
    manager._save_game_state(harness.game_id, server_data)


def _register(harness, empire_id, design_name):
    hull, slots = DESIGNS[design_name]
    result = harness.submit(empire_id, "design", {
        "mode": "Add",
        "design": {"name": design_name, "hull": hull, "slots": slots},
    })
    assert result["status"] == "applied", (design_name, result)


def _spawn(server_data, force, position):
    """Place a fleet by state surgery; returns the fleet."""
    from backend.core.data_structures import NovaPoint
    from backend.core.game_objects import Fleet
    from backend.services.ship_specs import find_design, make_token

    empire = server_data.all_empires[force.empire]
    design = find_design(empire, force.design)
    assert design is not None, f"no design '{force.design}'"

    fleet = Fleet()
    fleet.key = empire.get_next_fleet_key()
    fleet.owner = force.empire
    fleet.name = force.design
    fleet.turn_year = empire.turn_year
    fleet.position = NovaPoint(*position)
    fleet.battle_plan = force.plan
    token = make_token(design, force.quantity)
    fleet.tokens[token.design_key] = token
    fleet.fuel_available = fleet.total_fuel_capacity
    empire.owned_fleets[fleet.key] = fleet
    return fleet


# -------------------------------------------------------------- outcome


@dataclass
class Outcome:
    """What one battle left behind."""
    reports: list
    server_data: object
    control: "Outcome" = None

    @property
    def report(self):
        assert self.reports, "no battle was fought"
        return self.reports[0]

    def _steps(self, kind):
        return [s for s in self.report.steps
                if s.__class__.__name__ == kind]

    def weapons(self, owner=None, defence=None):
        """Weapon-fire steps, optionally by firing empire and by which
        pool they landed on."""
        steps = self._steps("BattleStepWeapons")
        if owner is not None:
            steps = [s for s in steps
                     if (s.weapon_target.stack_key >> 32) == owner]
        if defence is not None:
            steps = [s for s in steps if s.targeting == defence]
        return steps

    def damage(self, owner=None, defence=None):
        return sum(s.damage for s in self.weapons(owner, defence))

    def targets(self, owner=None):
        steps = self._steps("BattleStepTarget")
        if owner is not None:
            steps = [s for s in steps if (s.stack_key >> 32) == owner]
        return steps

    def movements(self, owner=None):
        steps = self._steps("BattleStepMovement")
        if owner is not None:
            steps = [s for s in steps if (s.stack_key >> 32) == owner]
        return steps

    def destroyed(self):
        return self._steps("BattleStepDestroy")

    def stacks(self, owner=None):
        """The report's pre-battle stack copies."""
        return {key: stack for key, stack in self.report.stacks.items()
                if owner is None or (key >> 32) == owner}

    def role_of(self, stack_key):
        return str(self.report.stacks[stack_key].battle_role)

    def survivor(self, empire_id, design_name):
        """(quantity, damage percent) of a spawned fleet, or None if
        the battle destroyed it."""
        empire = self.server_data.all_empires[empire_id]
        for fleet in empire.owned_fleets.values():
            if fleet.name == design_name:
                token = next(iter(fleet.tokens.values()))
                return token.quantity, token.damage_percent
        return None

    def rounds(self):
        """Steps grouped into battle rounds. A round is movement then
        fire (RonBattleEngine._do_battle), so a movement step after a
        target step opens the next round.

        Movement alone is not enough to find the boundary: a stack that
        has closed onto its target stops, and a stack that stops emits
        no movement step at all, so a whole battle of stationary fire
        collapses into one group. Each weapon also fires once per round
        (_generate_attacks walks the stack's weapons once), so a stack
        firing a second time opens the next round too.
        """
        grouped, current, fired = [], [], set()
        for step in self.report.steps:
            kind = step.__class__.__name__
            boundary = (kind == "BattleStepMovement" and fired) or (
                kind == "BattleStepTarget" and step.stack_key in fired)
            if boundary:
                grouped.append(current)
                current, fired = [], set()
            if kind == "BattleStepTarget":
                fired.add(step.stack_key)
            current.append(step)
        grouped.append(current)
        return grouped


def _fight(harness, forces, plans, players):
    """Create the game, register the designs, place the fleets and run
    the battle engine on the loaded state."""
    from backend.services.game_manager import get_game_manager

    harness.create_game(seed=SEED, size="tiny", players=players)
    _grant_tech(harness)

    # Plans go to every empire: a row names them by string on either
    # side of the fight
    for plan in plans:
        for empire_id in range(1, players + 1):
            result = harness.submit(empire_id, "battle_plan",
                                    {"mode": "set", "plan": plan})
            assert result["status"] == "applied", (empire_id, plan)

    for empire_id, design_name in sorted({(f.empire, f.design)
                                          for f in forces}):
        _register(harness, empire_id, design_name)

    position = _deep_space_point(harness)
    server_data = get_game_manager()._load_game_state(harness.game_id)
    for force in forces:
        _spawn(server_data, force, position)

    # The engine draws its own generator from the global one, so
    # seeding here makes the fight reproducible (GameManager does the
    # same per turn)
    random.seed(SEED)
    reports = []
    RonBattleEngine(server_data, reports).run()
    return Outcome(reports, server_data)


# --------------------------------------------------------------- checks
#
# One per row. Each states the canonical behaviour the row pins and
# asserts something that changes if the mechanic changes.


def _nominal_beam_power(outcome, owner, power_per_ship):
    """Full-power damage of one volley: the dissipation band is a
    fraction of this."""
    stack = next(iter(outcome.stacks(owner).values()))
    return power_per_ship * stack.token.quantity


def check_beams_land_on_bare_armour(o):
    armour = o.weapons(owner=1, defence=TokenDefence.ARMOR)
    assert armour, "the beam line never hit armour"
    assert o.damage(owner=1, defence=TokenDefence.SHIELDS) == 0.0
    # Colloidal Phaser power 26; every hit keeps between 90 and 100
    # percent of it (BATTLE.TXT beam dissipation, DEF-24)
    nominal = _nominal_beam_power(o, 1, 26)
    for step in armour:
        assert 0.9 * nominal <= step.damage <= nominal, step.damage
    assert min(s.damage for s in armour) < nominal, \
        "no hit lost anything to range - dissipation is not applied"
    # The station rides out the battle, so the whole exchange is on
    # record and the armour it lost is carried out of the fight
    assert o.survivor(2, "Bare Station")[1] > 0


def check_shields_absorb_beams(o):
    assert o.damage(owner=1, defence=TokenDefence.SHIELDS) > 0
    assert o.damage(owner=1, defence=TokenDefence.ARMOR) == 0.0, \
        "a beam reached armour through a standing shield"
    assert o.survivor(2, "Shielded Station") == (1, 0.0)


def check_torpedoes_bleed_through_shields(o):
    station = next(iter(o.stacks(2).values()))
    shield_pool = station.token.shields
    assert o.damage(owner=1, defence=TokenDefence.SHIELDS) < shield_pool, \
        "the shield never held - nothing to bleed through"
    assert o.damage(owner=1, defence=TokenDefence.ARMOR) > 0, \
        "torpedoes did not split their damage past the shield"
    assert o.survivor(2, "Shielded Station")[1] > 0


def check_gatlings_fire_first(o):
    gatling, blaster = sorted(o.stacks(1))
    both, ordered = 0, 0
    for battle_round in o.rounds():
        firing = [s.stack_key for s in battle_round
                  if s.__class__.__name__ == "BattleStepTarget"]
        if gatling in firing and blaster in firing:
            both += 1
            ordered += firing.index(gatling) < firing.index(blaster)
    assert both >= 5, f"only {both} rounds had both weapons firing"
    assert ordered == both, \
        "the initiative-12 gatling did not fire before the beam"


def check_missiles_double_against_armour(o):
    """Canonical Stars!: a missile that finds shields down does double
    damage to armour. Hit power is power * quantity * percent (the /10
    this ceiling once carried was the DEF-33 divisor, lifted - canon
    applies hit power directly, BattleEngine.cs:794-808) and the
    accuracy roll caps at accuracy * 1.25, so anything above that
    ceiling can only come from the missile multiplier."""
    armour = o.weapons(owner=1, defence=TokenDefence.ARMOR)
    assert armour
    stack = next(iter(o.stacks(1).values()))
    # Juggernaut Missile: power 150, accuracy 20 percent
    ceiling = 150 * stack.token.quantity * 0.20 * 1.25
    assert max(s.damage for s in armour) > 1.5 * ceiling


def check_gatlings_sweep_the_field(o):
    """Canonical Stars!: a gatling sweeps every stack in range, not
    only the one it selected. The premise is asserted first, so the
    row can only fail on the sweep itself: the plan lets the gatling
    engage the starbase and nothing else, every volley goes 100
    percent into it, and it soaks them all - so under beam rules the
    escort beside it can never be touched."""
    picked = o.targets(owner=1)
    assert picked, "the gatling never fired"
    assert {s.target_role for s in picked} == {"Starbase"}, \
        f"the gatling engaged {[s.target_role for s in picked]}"
    assert all(s.percent_to_fire == 100 for s in picked), \
        "the volley was split, so fire could spill onto the escort"
    assert o.survivor(2, "Bare Station") is not None, \
        "the station died - the volley was never fully soaked"
    assert o.survivor(2, "Laser Destroyer")[1] > 0


def check_standing_off_costs_damage(o):
    closing = o.control
    stand_off = o.weapons(owner=1, defence=TokenDefence.ARMOR)
    assert stand_off, "the stand-off line never fired"
    assert o.damage(owner=1, defence=TokenDefence.ARMOR) < \
        closing.damage(owner=1, defence=TokenDefence.ARMOR), \
        "standing off cost nothing"

    # Holding station against an immobile target freezes the range, so
    # every shot lands the same damage - and it is exactly the
    # dissipation formula (WeaponDetails.beam_dispersal_ron) at that
    # range, which is what pins the 10 percent loss over a full square
    hits = {round(s.damage, 6) for s in stand_off}
    assert len(hits) == 1, f"the range moved under a stand-off: {hits}"

    station = next(iter(o.stacks(2).values())).position
    final = o.movements(owner=1)[-1].position
    # The engine's own metric (NovaPoint.cs:255-262)
    distance = abs(final.x - station.x) + abs(final.y - station.y)
    nominal = _nominal_beam_power(o, 1, 26)
    weapon_range = 3 * RonBattleEngine.GRID_SCALE
    expected = nominal * (100 - 10 * (distance ** 2)
                          / (weapon_range ** 2)) / 100
    assert stand_off[0].damage == pytest.approx(expected)
    assert 0.9 * nominal < stand_off[0].damage < nominal


def check_longer_range_shoots_first(o):
    first_short = next((i for i, s in enumerate(o.targets())
                        if (s.stack_key >> 32) == 1), None)
    assert first_short is not None, "the beam line never closed"
    free = [s for s in o.targets()[:first_short]
            if (s.stack_key >> 32) == 2]
    assert len(free) >= 2, \
        f"range 6 bought only {len(free)} free shots over range 1"
    assert o.damage(owner=2) > 0


def check_braced_line_never_fires(o):
    assert o.weapons(owner=2) == [], \
        "a braced range-1 line reached a target standing off at range 5"
    assert o.movements(owner=2) == [], "a braced stack moved"
    # Free fire at canonical torpedo power (the /10 was the DEF-33
    # divisor, lifted) annihilates the line inside the round cap
    # where it used to bleed - the same punishment, taken to its end
    assert o.survivor(2, "Laser Destroyer") is None, \
        "the braced line was not punished for holding"


def check_starbase_breaks_a_raid(o):
    assert o.movements(owner=2) == [], "the starbase moved"
    assert o.report.losses[1] == 4, \
        f"the raid survived: losses {dict(o.report.losses)}"
    assert o.survivor(1, "Laser Destroyer") is None
    assert o.survivor(2, "War Fort") is not None


def check_starbase_out_ranges_a_ship(o):
    """Canonical Stars!: a starbase reaches one square further than the
    same weapon on a ship. The raider holds station at 410 board units
    - outside the fort's range-4 (400) weapon, inside the 500 the
    bonus would give it."""
    station = next(iter(o.stacks(2).values())).position
    final = o.movements(owner=1)[-1].position
    distance = abs(final.x - station.x) + abs(final.y - station.y)
    assert 400 < distance <= 500, f"raider stood off at {distance}"
    assert o.weapons(owner=2), "the starbase never answered"


def check_numbers_drown_a_capital(o):
    assert o.report.losses[1] == 1, "the capital ship survived the swarm"
    assert o.survivor(1, "Capital Ship") is None
    # 19, not the 20 that sailed in: per-ship attrition (DEF-35) lets
    # the capital's disruptor volleys kill a whole destroyer out of
    # the swarm token before it dies, where the old pooled model only
    # shaved armour nobody lost a hull to
    assert o.survivor(2, "Beam Destroyer")[0] == 19


def check_role_cascade_walks_its_tiers(o):
    picked = o.targets(owner=1)
    assert picked, "the hunters never picked a target"
    assert (picked[0].target_role, picked[0].priority) == \
        ("Capital Ship", 7)
    tiers = {}
    for step in picked:
        tiers.setdefault(step.target_role, step.priority)
    assert tiers == {"Capital Ship": 7, "Escort": 6, "Logistics": 5}, \
        f"tiers matched the wrong roles: {tiers}"
    order = [o.role_of(s.stack_key) for s in o.destroyed()]
    assert order == ["Capital Ship", "Escort", "Logistics"], \
        f"the cascade killed out of order: {order}"


def check_escort_plan_spares_the_rest(o):
    roles = {s.target_role for s in o.targets(owner=1)}
    assert roles == {"Escort"}, f"an escort plan engaged {roles}"
    assert o.survivor(2, "Laser Destroyer")[1] > 0
    assert o.survivor(2, "Capital Ship")[1] == 0.0
    assert o.survivor(2, "Freighter")[1] == 0.0


def check_unmatched_plan_starts_no_battle(o):
    assert o.reports == [], \
        "a plan whose every tier matches no role still fought"
    assert o.survivor(2, "Freighter") == (3, 0.0)
    assert o.survivor(1, "Laser Destroyer") == (4, 0.0)


def check_computers_land_more_torpedoes(o):
    plain = o.control.damage(owner=1)
    fitted = o.damage(owner=1)
    assert fitted > plain
    # Epsilon Torpedo accuracy 65 percent; 2x Battle Computer stack to
    # 36 percent, which cuts the MISS chance (WeaponDetails
    # .missile_accuracy), so hits scale by the accuracy ratio
    boosted = 1.0 - (1.0 - 0.65) * (1.0 - 0.36)
    assert fitted == pytest.approx(plain * boosted / 0.65, rel=1e-3)


def check_jammers_shrug_off_torpedoes(o):
    plain = o.control.damage(owner=1)
    jammed = o.damage(owner=1)
    assert jammed < plain
    # 6x Jammer 20 probability-stack, so the hit chance keeps 0.8^6
    assert jammed == pytest.approx(plain * 0.8 ** 6, rel=1e-3)


def check_capacitors_raise_beam_damage(o):
    fitted = o.weapons(owner=1, defence=TokenDefence.ARMOR)
    plain = o.control.weapons(owner=1, defence=TokenDefence.ARMOR)
    # Beams carry no accuracy roll, so the opening volley is exact:
    # 2x Energy Capacitor stack to 21 percent
    assert fitted[0].damage == pytest.approx(plain[0].damage * 1.21)
    assert len(fitted) < len(plain), \
        "the capacitor ship needed as many volleys as the plain one"


def check_deflectors_cut_beam_damage(o):
    fitted = o.weapons(owner=1, defence=TokenDefence.ARMOR)
    plain = o.control.weapons(owner=1, defence=TokenDefence.ARMOR)
    # One Beam Deflector: damage x (1 - 10/100)
    assert fitted[0].damage == pytest.approx(plain[0].damage * 0.9)
    assert len(fitted) > len(plain), \
        "the deflector cost the attacker no extra volleys"


def check_jammers_do_nothing_to_beams(o):
    """Jamming is a missile-guidance stat. If it ever leaks into the
    beam path this is the row that says so."""
    jammed = o.weapons(owner=1, defence=TokenDefence.ARMOR)
    plain = o.control.weapons(owner=1, defence=TokenDefence.ARMOR)
    # Both lists being empty would satisfy every comparison below
    assert jammed and plain, "neither run landed a volley to compare"
    assert len(jammed) == len(plain)
    assert o.damage(owner=1) == pytest.approx(o.control.damage(owner=1))


def check_unarmed_forces_never_fight(o):
    assert o.reports == [], "two unarmed forces started a battle"
    assert o.survivor(1, "Picket") == (2, 0.0)
    assert o.survivor(2, "Picket") == (2, 0.0)


def check_a_lone_ship_dies(o):
    assert o.report.losses[1] == 1
    assert o.survivor(1, "Laser Destroyer") is None
    quantity, damage = o.survivor(2, "Laser Destroyer")
    assert quantity == 40
    assert damage < 1.0, f"the wall was hurt: {damage} percent"


def check_three_empires_all_fight(o):
    assert len(o.reports) == 1, "one rendezvous produced several battles"
    assert {key >> 32 for key in o.report.stacks} == {1, 2, 3}
    pairs = {((s.stack_key >> 32), (s.target_key >> 32))
             for s in o.targets()}
    assert {(2, 1), (3, 1)} <= pairs, \
        "the fort was not engaged by both raiders"
    assert {(2, 3), (3, 2)} & pairs, \
        "the two raiders ignored each other"


def check_a_large_stack_stays_inside_the_cap(o):
    assert len(o.reports) == 1
    per_stack = {}
    for step in o.movements():
        per_stack[step.stack_key] = per_stack.get(step.stack_key, 0) + 1
    assert per_stack, "nobody moved"
    # A stack records at most one movement step per round, so the
    # movement count alone can never exceed the cap however broken the
    # loop is. What the cap actually bounds is FIRE: one weapon aimed
    # at one target resolves once a round, so a side that fires more
    # times than MAX_BATTLE_ROUNDS fought more rounds than it may -
    # and a side that fires far fewer collapsed before the cap
    for empire_id in (1, 2):
        volleys = len(o.targets(owner=empire_id))
        assert 40 <= volleys <= RonBattleEngine.MAX_BATTLE_ROUNDS, \
            f"empire {empire_id} fired {volleys} times"
    assert o.damage(owner=1) > 0 and o.damage(owner=2) > 0
    for empire_id in (1, 2):
        quantity, damage = o.survivor(empire_id, "Beam Destroyer")
        # Per-ship attrition (DEF-35): the armour a side loses to the
        # cap now kills a handful of whole ships out of the 250 where
        # the pooled model killed none - the bound is that the stack
        # rides out the cap essentially intact, not untouched
        assert 240 <= quantity < 250
        assert 0.0 < damage <= 99.0, damage


def check_neither_side_can_reach(o):
    assert o.reports, "two braced lines produced no battle at all"
    assert o.weapons() == [], "a braced range-1 line reached across"
    assert o.movements() == []
    assert o.report.losses == {1: 0, 2: 0}
    assert o.survivor(1, "Laser Destroyer") == (4, 0.0)
    assert o.survivor(2, "Laser Destroyer") == (4, 0.0)


# ------------------------------------------------------------ scenarios


SCENARIOS = (
    Scenario(
        name="beams-land-full-power-on-bare-armour",
        doc="A beam with no shield in the way puts its whole hit on "
            "armour, scaled only by range dissipation.",
        forces=(Force(1, "Beam Destroyer", 2),
                Force(2, "Bare Station")),
        check=check_beams_land_on_bare_armour,
    ),
    Scenario(
        name="shields-absorb-beams-before-armour",
        doc="Beams are stopped by a standing shield: while the pool "
            "holds, not one point reaches armour.",
        forces=(Force(1, "Beam Destroyer", 4),
                Force(2, "Shielded Station")),
        check=check_shields_absorb_beams,
    ),
    Scenario(
        name="torpedoes-bleed-through-standing-shields",
        doc="The discriminating half of the pair above: a torpedo "
            "splits its hit between shields and armour, so armour "
            "bleeds while the shield is still up.",
        # One destroyer, not four: torpedo hit power lost its /10
        # divisor (DEF-33, canon applies it directly at
        # BattleEngine.cs:794-808), so four throw 10x what this row
        # was seeded against and sank the station whose survival the
        # check pins. One destroyer throws 2.5x the old four (2 tubes
        # x 48 power vs 8 x 48 / 10 = 38.4 per round), which the
        # station rides out with the shield still standing
        forces=(Force(1, "Torpedo Destroyer", 1),
                Force(2, "Shielded Station")),
        check=check_torpedoes_bleed_through_shields,
    ),
    Scenario(
        name="gatlings-fire-before-beams",
        doc="Fire inside a round is ordered highest initiative first "
            "(BATTLE.TXT), so the initiative-12 gatling always shoots "
            "before the initiative-7 blaster beside it.",
        forces=(Force(1, "Gatling Destroyer"),
                Force(1, "Blaster Destroyer"),
                Force(2, "Bare Station")),
        check=check_gatlings_fire_first,
    ),
    Scenario(
        name="missiles-double-their-damage-against-armour",
        doc="Canonical Stars!: a missile that finds shields down does "
            "double damage to armour, which a torpedo never does.",
        forces=(Force(1, "Missile Destroyer", 8),
                Force(2, "Bare Station")),
        check=check_missiles_double_against_armour,
        xfail="RonBattleEngine._fire_missile resolves the torpedo and "
              "missile groups identically - there is no missile-class "
              "armour multiplier anywhere in the engine, so armour "
              "damage can never exceed hit power times the accuracy "
              "roll ceiling",
    ),
    Scenario(
        name="gatlings-sweep-every-stack-in-range",
        doc="Canonical Stars!: a gatling gun sweeps every stack in "
            "range instead of concentrating on the one it selected.",
        forces=(Force(1, "Gatling Destroyer", 2, "Starbase Only"),
                Force(2, "Bare Station"),
                Force(2, "Laser Destroyer", 2)),
        plans=(STARBASE_ONLY,),
        check=check_gatlings_sweep_the_field,
        xfail="the engine reads only Weapon.is_missile; the gatlingGun "
              "group takes the ordinary beam path in "
              "RonBattleEngine._execute_attack and hits one selected "
              "target, so no sweep exists",
    ),
    Scenario(
        name="standing-off-costs-beam-damage",
        doc="DEF-24: a beam does full power in the target's square and "
            "about 90 percent at maximum range, so a stand-off tactic "
            "buys safety with damage. Control: the same line closing.",
        forces=(Force(1, "Beam Destroyer", 1, "Stand Off"),
                Force(2, "Bare Station")),
        control=(Force(1, "Beam Destroyer", 1, "Close In"),
                 Force(2, "Bare Station")),
        plans=(STAND_OFF, CLOSE_IN),
        check=check_standing_off_costs_damage,
    ),
    Scenario(
        name="the-longer-ranged-force-shoots-first",
        doc="Range bands: a range-6 missile line lands hits while a "
            "range-1 beam line is still closing.",
        forces=(Force(1, "Laser Destroyer", 4),
                Force(2, "Doomsday Destroyer", 4)),
        check=check_longer_range_shoots_first,
    ),
    Scenario(
        name="a-braced-short-range-line-never-fires",
        doc="Brace is a positional commitment: the line never closes, "
            "so a longer-ranged enemy standing off shoots it for free.",
        forces=(Force(1, "Torpedo Destroyer", 4, "Stand Off"),
                Force(2, "Laser Destroyer", 4, "Brace")),
        plans=(STAND_OFF, BRACE),
        check=check_braced_line_never_fires,
    ),
    Scenario(
        name="a-starbase-holds-its-ground-and-breaks-a-raid",
        doc="A starbase never moves and fights from its emplacement; "
            "four light raiders die on it.",
        forces=(Force(1, "Laser Destroyer", 4),
                Force(2, "War Fort")),
        check=check_starbase_breaks_a_raid,
    ),
    Scenario(
        name="a-starbase-out-ranges-a-ship-by-one-square",
        doc="Canonical Stars!: a starbase reaches one square further "
            "than the same weapon mounted on a ship, so a raider "
            "cannot park just outside its guns.",
        forces=(Force(1, "Torpedo Destroyer", 2, "Stand Off"),
                Force(2, "Delta Fort")),
        plans=(STAND_OFF,),
        check=check_starbase_out_ranges_a_ship,
        xfail="RonBattleEngine._generate_attacks takes range_bonus "
              "solely from the battle plan posture (POSTURE_MODIFIERS "
              "Brace); Stack.is_starbase grants no inherent reach, so "
              "a fort answers nothing beyond its printed range",
    ),
    Scenario(
        name="numbers-drown-a-capital-ship",
        doc="Numbers asymmetry: twenty light beam ships kill one "
            "capital ship and walk away.",
        forces=(Force(1, "Capital Ship"),
                Force(2, "Beam Destroyer", 20)),
        check=check_numbers_drown_a_capital,
    ),
    Scenario(
        name="the-role-cascade-walks-capital-escort-logistics",
        doc="A plan naming Capital Ship, Escort and Logistics engages "
            "them in that order and kills them in that order.",
        forces=(Force(1, "Disruptor Destroyer", 12, "Cascade"),
                Force(2, "Thin Capital"),
                Force(2, "Laser Destroyer", 3),
                Force(2, "Freighter", 2)),
        plans=(CASCADE,),
        check=check_role_cascade_walks_its_tiers,
    ),
    Scenario(
        name="an-escort-only-plan-spares-capital-and-convoy",
        doc="A tier that matches no role is never engaged: an "
            "escort-only plan leaves the capital ship and the "
            "freighters untouched.",
        forces=(Force(1, "Beam Destroyer", 8, "Escorts Only"),
                Force(2, "Capital Ship"),
                Force(2, "Laser Destroyer", 3),
                Force(2, "Freighter", 2)),
        plans=(ESCORTS_ONLY,),
        check=check_escort_plan_spares_the_rest,
    ),
    Scenario(
        name="a-plan-that-matches-no-role-starts-no-battle",
        doc="Every tier names Bomber and the enemy has none, so the "
            "armed force has no target and no battle is fought.",
        forces=(Force(1, "Laser Destroyer", 4, "Bombers Only"),
                Force(2, "Freighter", 3)),
        plans=(BOMBERS_ONLY,),
        check=check_unmatched_plan_starts_no_battle,
    ),
    Scenario(
        name="battle-computers-land-more-torpedoes",
        doc="A battle computer cuts the miss chance. Control: the same "
            "torpedo ship without one.",
        forces=(Force(1, "Light Computer Destroyer", 1),
                Force(2, "Bare Station")),
        control=(Force(1, "Light Torpedo Destroyer", 1),
                 Force(2, "Bare Station")),
        check=check_computers_land_more_torpedoes,
    ),
    Scenario(
        name="jammers-shrug-off-torpedoes",
        doc="A jammer cuts the hit chance. Control: the same station "
            "without jammers.",
        forces=(Force(1, "Light Torpedo Destroyer", 1),
                Force(2, "Jammed Station")),
        control=(Force(1, "Light Torpedo Destroyer", 1),
                 Force(2, "Bare Station")),
        check=check_jammers_shrug_off_torpedoes,
    ),
    Scenario(
        name="capacitors-raise-beam-damage",
        doc="An energy capacitor multiplies beam hit power. Control: "
            "the same ship without capacitors.",
        forces=(Force(1, "Capacitor Destroyer", 4),
                Force(2, "Bare Station")),
        control=(Force(1, "Beam Destroyer", 4),
                 Force(2, "Bare Station")),
        check=check_capacitors_raise_beam_damage,
    ),
    Scenario(
        name="beam-deflectors-cut-beam-damage",
        doc="A beam deflector cuts incoming beam power. Both targets "
            "brace, so the range at the opening volley is identical.",
        forces=(Force(1, "Beam Destroyer", 4),
                Force(2, "Deflector Battleship", 1, "Brace")),
        control=(Force(1, "Beam Destroyer", 4),
                 Force(2, "Plain Battleship", 1, "Brace")),
        plans=(BRACE,),
        check=check_deflectors_cut_beam_damage,
    ),
    Scenario(
        name="jammers-do-nothing-against-beams",
        doc="Negative control on the electronics wiring: jamming is a "
            "missile stat and must not touch a beam.",
        forces=(Force(1, "Beam Destroyer", 4),
                Force(2, "Jammed Battleship", 1, "Brace")),
        control=(Force(1, "Beam Destroyer", 4),
                 Force(2, "Plain Battleship", 1, "Brace")),
        plans=(BRACE,),
        check=check_jammers_do_nothing_to_beams,
    ),
    Scenario(
        name="two-unarmed-forces-never-join-battle",
        doc="Edge case: only an armed stack triggers a battle "
            "(BattleEngine.cs:412-415), so two unarmed forces meeting "
            "produce no engagement at all.",
        forces=(Force(1, "Picket", 2), Force(2, "Picket", 2)),
        check=check_unarmed_forces_never_fight,
    ),
    Scenario(
        name="a-lone-ship-dies-against-a-wall-of-steel",
        doc="Edge case: one ship against forty of its own class dies "
            "without scratching the wall.",
        forces=(Force(1, "Laser Destroyer", 1),
                Force(2, "Laser Destroyer", 40)),
        check=check_a_lone_ship_dies,
    ),
    Scenario(
        name="a-three-empire-battle-is-fought-by-all-three",
        doc="Edge case: three empires at one point fight ONE battle "
            "and every pair is hostile - both raiders shoot the fort "
            "and each other.",
        # Two 6-ship fleets per raider, not one: per-ship attrition
        # (DEF-35) lets the fort's disruptors silence a raider stack
        # gun by gun, and a single-stack raider side died whole in the
        # same rounds the fort did, so the raiders never exchanged
        # fire. A second stack keeps each empire alive past the fort
        # without raising per-stack attractiveness (a 12-ship stack
        # out-attracts the fort and the raiders ignore it instead).
        #
        # Seed history: under the pre-fix engine this row's cross-fire
        # assertion held at SEED only because the list-order bias
        # manufactured the asymmetry it asserts - a lucky pin, not the
        # mechanism. Audited 2026-07-28 on the fixed engine (bias
        # removed, attrition in): raider cross-fire occurs in BOTH
        # directions ((2,3) and (3,2)) at every seed 20260801-20260808,
        # so the pin stands on a seed where the mechanism genuinely
        # shows and is robust to the seed choice. Re-audited 2026-07-29
        # after the engagement-range wave (give-ground, _cap_step):
        # still both directions at all 8 seeds, one battle per seed
        forces=(Force(1, "War Fort"),
                Force(2, "Beam Destroyer", 6),
                Force(2, "Beam Destroyer", 6),
                Force(3, "Beam Destroyer", 6),
                Force(3, "Beam Destroyer", 6)),
        players=3,
        check=check_three_empires_all_fight,
    ),
    Scenario(
        name="a-very-large-stack-stays-inside-the-round-cap",
        doc="Edge case: 250 ships a side still resolve inside "
            "MAX_BATTLE_ROUNDS, with both sides firing to the cap and "
            "the armour they lost written back to the fleet. The 99 "
            "percent clamp is the bound the write-back is held to, "
            "not something this row reaches - a stack this large ends "
            "on single-digit damage.",
        forces=(Force(1, "Beam Destroyer", 250),
                Force(2, "Beam Destroyer", 250)),
        check=check_a_large_stack_stays_inside_the_cap,
    ),
    Scenario(
        name="neither-side-can-reach-the-other",
        doc="Edge case: two braced range-1 lines start fourteen "
            "squares apart and neither ever moves, so the battle is "
            "fought to its end without a shot.",
        forces=(Force(1, "Laser Destroyer", 4, "Brace"),
                Force(2, "Laser Destroyer", 4, "Brace")),
        plans=(BRACE,),
        check=check_neither_side_can_reach,
    ),
)


def _param(scenario):
    marks = ([pytest.mark.xfail(reason=scenario.xfail, strict=True)]
             if scenario.xfail else [])
    return pytest.param(scenario, id=scenario.name, marks=marks)


@pytest.mark.parametrize("scenario", [_param(s) for s in SCENARIOS])
def test_battle_scenario(harness, scenario):
    """Fight the row and hold the engine to what the row says the
    canonical outcome is. The docstring of each row is its claim."""
    outcome = _fight(harness, scenario.forces, scenario.plans,
                     scenario.players)
    if scenario.control:
        outcome.control = _fight(harness, scenario.control,
                                 scenario.plans, scenario.players)
    scenario.check(outcome)


def test_the_table_covers_twenty_five_scenarios():
    """The suite is a table, not a pile: names are unique and the
    count is the one the file claims."""
    assert len(SCENARIOS) == 25
    assert len({s.name for s in SCENARIOS}) == 25
