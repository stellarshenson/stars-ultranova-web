"""
Stars Nova Web - Ron Battle Engine
Ported from ServerState/RonBattleEngine.cs (1134 lines)

Alternative battle engine with improved movement mechanics.

The standard battle engine has issues where fleet 1 has a tremendous
advantage and weapon range is largely ignored as fleets move too far
in one battle step. Ron's engine uses a larger grid (1000 units with
100 scale) and 60 rounds for more realistic ship positioning.
"""

import random
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

from ...core.commands.base import Message
from ...core.components.ship_role import ShipRole
from ...core.data_structures import NovaPoint, Resources, Cargo
from ...core.game_objects import Fleet, ShipToken
from ...core.globals import MAX_WEAPON_RANGE

from .battle_step import (
    BattleStepBoard,
    BattleStepMovement,
    BattleStepTarget,
    BattleStepWeapons,
    BattleStepDestroy,
    BattleStepWithdraw,
    WeaponTarget,
    TokenDefence,
)
from .battle_report import BattleReport
from .battle_plan import (
    BattlePlan,
    Victims,
    CLOSE_FOR_KILL_ARMOUR_PERCENT,
    BOARDING_FAILURE_ARMOR_PERCENT,
    BOARDING_MAX_CHANCE,
    BOARDING_MIN_CHANCE,
    BOARDING_PRIZE_DAMAGE_PERCENT,
    MIN_DISENGAGE_MOVES,
    OUTNUMBERED_RATIO,
    WITHDRAWAL_DAMAGE_PERCENT,
)
from .stack import Stack, StackToken
from .weapon_details import WeaponDetails, TargetPercent
from .space_allocator import SpaceAllocator

if TYPE_CHECKING:
    from ..server_data import ServerData


@dataclass
class TargetRow:
    """Target selection row with priority and attractiveness."""
    fleet: Stack
    priority: int
    attractiveness: float


class RonBattleEngine:
    """
    Alternative battle engine with improved movement mechanics.

    Uses a larger grid (1000 units) with finer movement control.
    Fleets advance until opponents are in weapon range, then maneuver.
    Ported from RonBattleEngine.cs.
    """

    MAX_BATTLE_ROUNDS = 60
    GRID_SIZE = 1000
    GRID_SCALE = 100  # Must be GRID_SIZE / 10
    GRID_SCALE_SQUARED = 10000
    SALVAGE_NAME = "S A L V A G E"
    # Canonical Stars!: a disengaging token needs 7 squares of battle
    # board movement to leave the battle (C# absent - BattleEngine.cs
    # line 603 TODO admits fleeing is unimplemented)
    DISENGAGE_MOVES = 7
    # Stand-off band: a stack holds while its target sits between
    # DEADBAND * R and R of its hold range R, closes beyond it and
    # gives ground inside it. A single value oscillates - one unit
    # inside steps out, overshoots, steps back, and the stack spends
    # the battle in transit firing from neither position
    # (docs/research-engagement-range.md:37; the Stellaris 70-90
    # percent formation band is the precedent,
    # docs/research-battle-doctrine.md:96)
    HOLD_RANGE_DEADBAND = 0.9

    def __init__(self, server_state: 'ServerData', battle_reports: List[BattleReport]):
        """
        Initialize battle engine.

        Args:
            server_state: Game state
            battle_reports: List to append battle reports to
        """
        self.server_state = server_state
        self.battles = battle_reports
        self.stack_id = 0
        self.battle_round = 0
        # Seed derived from the global random module so seeded games
        # (re-seeded per turn in GameManager.generate_turn) get
        # deterministic battles; unseeded games stay random.
        self._random = random.Random(random.getrandbits(64))

    def run(self) -> None:
        """
        Process all fleet battles.

        Unlike standard engine, Ron's engine starts battles based on
        weapon range proximity rather than exact position.
        """
        # Find fleets within weapon range
        potential_battles = self._determine_weapon_range_fleets()
        if not potential_battles:
            return

        # Filter to locations with multiple races
        engagements = self._eliminate_single_races(potential_battles)
        if not engagements:
            return

        # Process each engagement
        for battling_fleets in engagements:
            previous_locations: List[NovaPoint] = []

            for fleet in battling_fleets:
                if fleet is None or not fleet.tokens:
                    continue

                battle_location = fleet.position
                if battle_location in previous_locations:
                    continue

                battle = BattleReport()
                battle.year = self.server_state.turn_year
                previous_locations.append(battle_location)

                battling_stacks = self._generate_stacks(
                    battling_fleets, battle_location
                )

                if self._select_targets(battling_stacks) == 0:
                    continue

                self.stack_id = 0
                sample = battling_fleets[0]

                if sample.in_orbit:
                    battle.location = sample.in_orbit.name
                elif sample.in_orbit_name:
                    battle.location = sample.in_orbit_name
                else:
                    battle.location = (
                        f"deep space ({int(sample.position.x)}, "
                        f"{int(sample.position.y)})"
                    )

                self._position_stacks(battling_stacks, battle)

                # Copy stacks for report
                battle.stacks.clear()
                for stack in battling_stacks:
                    battle.stacks[stack.key] = Stack.copy(stack)

                self._do_battle(battling_stacks, battle)
                self._apply_withdrawal_consequences(battling_stacks, battle)
                self._summarize_outcomes(battling_stacks, battle)
                self._report_battle(battle)

    def _determine_weapon_range_fleets(self) -> List[List[Fleet]]:
        """Find all groups of fleets at the same position."""
        all_in_range: List[List[Fleet]] = []
        fleet_done: Dict[int, bool] = {}

        for fleet_a in self.server_state.iterate_all_fleets():
            if fleet_a.name == self.SALVAGE_NAME:
                fleet_done[fleet_a.key] = True
            if fleet_a.key in fleet_done:
                continue

            in_range: List[Fleet] = []
            for fleet_b in self.server_state.iterate_all_fleets():
                if fleet_b.name == self.SALVAGE_NAME:
                    continue
                if fleet_b.position != fleet_a.position:
                    continue

                in_range.append(fleet_b)
                fleet_done[fleet_b.key] = True

            if len(in_range) > 1:
                all_in_range.append(in_range)

        return all_in_range

    def _eliminate_single_races(
        self, all_colocated: List[List[Fleet]]
    ) -> List[List[Fleet]]:
        """Filter to locations with multiple races."""
        engagements: List[List[Fleet]] = []

        for colocated in all_colocated:
            empires: Dict[int, bool] = {}
            for fleet in colocated:
                empires[fleet.owner] = True

            if len(empires) > 1:
                engagements.append(colocated)

        return engagements

    def _build_fleet_stacks(self, fleet: Fleet) -> List[Stack]:
        """Convert a fleet to stacks (one per ship design)."""
        stacks: List[Stack] = []

        designs: Dict[int, 'ShipDesign'] = {}
        if fleet.owner in self.server_state.all_empires:
            empire = self.server_state.all_empires[fleet.owner]
            designs = empire.designs

        for token in fleet.tokens.values():
            design = designs.get(token.design_key)
            stack = Stack.from_fleet(fleet, self.stack_id, token, design)
            stacks.append(stack)
            self.stack_id += 1

        return stacks

    def _generate_stacks(
        self, colocated_fleets: List[Fleet], battle_location: NovaPoint
    ) -> List[Stack]:
        """Generate stacks for fleets near battle location."""
        battling_stacks: List[Stack] = []

        for fleet in colocated_fleets:
            dist_sq = battle_location.distance_to_squared(fleet.position)
            if dist_sq <= 2 and fleet.tokens:
                stacks = self._build_fleet_stacks(fleet)
                battling_stacks.extend(stacks)

        return battling_stacks

    def _position_stacks(
        self, battling_stacks: List[Stack], battle: BattleReport
    ) -> None:
        """Set initial positions for all stacks."""
        empires: Dict[int, int] = {}
        race_positions: Dict[int, Tuple[int, int]] = {}

        for stack in battling_stacks:
            empires[stack.owner] = stack.owner
            if stack.token and stack.token.design:
                stack.token.design.update()

        allocator = SpaceAllocator(len(empires))
        space_size = allocator.grid_axis_count * MAX_WEAPON_RANGE
        allocator.allocate_space(self.GRID_SIZE)
        battle.space_size = space_size
        battle.grid_size = self.GRID_SCALE

        for index, empire_id in enumerate(empires.values()):
            box = allocator.get_box(index, len(empires))
            position = (
                box.x + (box.width // 2),
                box.y + (box.height // 2)
            )
            race_positions[empire_id] = position
            battle.losses[empire_id] = 0

        for stack in battling_stacks:
            pos = race_positions[stack.owner]
            stack.position = NovaPoint(pos[0], pos[1])

        self._apply_doctrine(battling_stacks)
        self._update_intel_designs(battling_stacks, empires)

    def _plan_of(self, stack: Stack) -> BattlePlan:
        """
        The battle plan a stack is fighting under.

        A stack whose empire or plan name cannot be resolved falls back
        to a stock plan, whose doctrine axes are all no-modifier
        values, so an unresolvable plan never changes the fight.
        """
        empire = self.server_state.all_empires.get(stack.owner)
        if empire is None:
            return BattlePlan()
        return empire.battle_plans.get(stack.battle_plan) or BattlePlan()

    def _apply_doctrine(self, battling_stacks: List[Stack]) -> None:
        """
        Apply the doctrine state a stack enters the battle with.

        Two things are fixed before the first round: the shield pool
        (stance and posture both scale it, and they stack), and
        whether the stack's own side is outnumbered, which is what the
        "Outnumbered" withdrawal threshold reads. Armour is never
        scaled - a stance that touched both pools would be the
        symmetric multiplier docs/research-battle-doctrine.md rejects.
        """
        armed_by_owner: Dict[int, int] = {}
        for stack in battling_stacks:
            if stack.token is None or not stack.is_armed:
                continue
            armed_by_owner[stack.owner] = (
                armed_by_owner.get(stack.owner, 0) + stack.token.quantity)

        total_armed = sum(armed_by_owner.values())

        for stack in battling_stacks:
            if stack.token is None:
                continue
            plan = self._plan_of(stack)
            stack.token.shields *= (plan.stance_modifiers.shields
                                    * plan.posture_modifiers.shields)

            own = armed_by_owner.get(stack.owner, 0)
            hostile = total_armed - own
            stack.outnumbered = (
                own == 0 or hostile >= own * OUTNUMBERED_RATIO)

    def _withdraw_threshold_met(self, stack: Stack) -> bool:
        """
        Whether this stack's withdrawal threshold has been reached.

        Generalises the canonical "Disengage if Challenged" tactic,
        which is the "On Damage" threshold expressed as a tactic.
        """
        threshold = self._plan_of(stack).withdraw

        if threshold == "On Damage":
            return stack.damage_taken
        if threshold == "Half Armour":
            if stack.token is None:
                return False
            baseline = stack.token.initial_armor or stack.token.armor
            if baseline <= 0:
                return False
            return stack.token.armor <= baseline / 2.0
        if threshold == "Outnumbered":
            return stack.outnumbered
        return False

    def _disengage_moves_required(self, stack: Stack) -> int:
        """
        Board moves this stack needs to leave the battle.

        Canonical 7 (DISENGAGE_MOVES); Defensive stance and the
        Scatter posture each shorten it, never below
        MIN_DISENGAGE_MOVES.
        """
        plan = self._plan_of(stack)
        moves = (plan.stance_modifiers.disengage_moves
                 + plan.posture_modifiers.disengage_moves_delta)
        return max(MIN_DISENGAGE_MOVES, moves)

    def _update_intel_designs(
        self, battling_stacks: List[Stack], empires: Dict[int, int]
    ) -> None:
        """
        Update known enemy ship designs after battle.

        Port of BattleEngine.cs:347-368: every participating empire
        records the FULL design (components included) of every enemy
        stack, add-or-replace into EmpireReports[owner].Designs - a
        battle upgrades any hull-only record learned by scanning.
        Records are plain dicts under empire_reports[owner]["designs"]
        keyed by hex design key.
        """
        for empire_id in empires.values():
            if empire_id not in self.server_state.all_empires:
                continue
            empire = self.server_state.all_empires[empire_id]

            for stack in battling_stacks:
                if stack.owner == empire_id:
                    continue
                if not stack.token or not stack.token.design:
                    continue

                design = stack.token.design
                reports = empire.empire_reports.setdefault(stack.owner, {})
                designs = reports.setdefault("designs", {})
                designs[hex(design.key)] = {
                    "key": hex(design.key),
                    "name": getattr(design, 'name', ''),
                    "hull_name": getattr(design, 'hull_name', '') or (
                        design.blueprint.name
                        if getattr(design, 'blueprint', None) else ''),
                    "owner": stack.owner,
                    "scope": "full",
                    "year": self.server_state.turn_year,
                    "design": (design.to_dict()
                               if hasattr(design, 'to_dict') else None),
                }

    def _do_battle(
        self, battling_stacks: List[Stack], battle: BattleReport
    ) -> None:
        """Execute battle with Ron's movement rules."""
        for self.battle_round in range(1, self.MAX_BATTLE_ROUNDS + 1):
            if self._select_targets(battling_stacks) == 0:
                break

            self._move_stacks(battling_stacks, self.battle_round, battle)
            all_attacks = self._generate_attacks(battling_stacks)

            for attack in all_attacks:
                self._process_attack(attack, battle)

            # Boarding resolves after the round's fire, because the
            # airlock only opens once the shields are down
            self._resolve_boarding(battling_stacks, battle)

        self._write_back_damage(battling_stacks)

    def _write_back_damage(self, battling_stacks: List[Stack]) -> None:
        """
        Carry the armour a survivor lost out of the battle.

        C# Nova hands the fleet's own ShipToken to the stack by
        reference (BattleEngine.cs:264, `new Stack(fleet, stackId,
        token)`), so armour lost in a battle stays lost on the fleet
        and ShipToken.Damage reads it straight back as a percentage
        (ShipToken.cs:70-75). The web port builds StackToken copies,
        so every survivor walked out of a battle untouched - a fleet
        could be shot to one armour point and be whole again next
        turn, which made every "take less damage" order worthless.

        Damage compounds with what the token already carried, and the
        repair step heals it exactly as it heals withdrawal damage.

        Per-ship attrition (DEF-35) makes ships-lost part of the same
        write-back: the surviving quantity lands on the fleet token the
        way mine and storm kills already do (turn_generator.py:1540,
        :1348), and damage_percent is recomputed against the SURVIVORS'
        full armour - the dead took their share of the pool with them.
        """
        for stack in battling_stacks:
            if stack.token is None or stack.token.initial_armor <= 0:
                continue

            survivors = stack.token.quantity
            if survivors <= 0:
                # Annihilated whole - _destroy_stack already removed
                # the fleet token
                continue
            if (stack.token.armor >= stack.token.initial_armor
                    and survivors >= stack.token.initial_quantity):
                continue

            empire = self.server_state.all_empires.get(stack.owner)
            if empire is None:
                continue
            fleet = empire.owned_fleets.get(stack.parent_key)
            if fleet is None:
                continue
            token = fleet.tokens.get(stack.token.design_key)
            if token is None:
                continue

            token.quantity = survivors

            # Share of a survivor's entry armour it still carries. With
            # no ships lost this is the old armor / initial_armor ratio;
            # attrition shrinks the denominator with the dead, who took
            # their share of the pool with them. Compounds with the
            # damage the token entered carrying, exactly as before
            initial_quantity = stack.token.initial_quantity or survivors
            per_ship_entry = stack.token.initial_armor / initial_quantity
            remaining = max(0.0, stack.token.armor) \
                / (survivors * per_ship_entry)
            undamaged = (1.0 - token.damage_percent / 100.0) * remaining
            token.damage_percent = min(
                99.0, max(0.0, 100.0 * (1.0 - undamaged)))

    def _summarize_outcomes(
        self, battling_stacks: List[Stack], battle: BattleReport
    ) -> None:
        """
        Write the per-design outcome ledger onto the report.

        One entry per stack, comparing what it entered with (the
        pre-battle snapshot in battle.stacks) against what walked out,
        so the battle message can read "N x Design -> K destroyed,
        M survived at X% damage" instead of a bare loss count.
        Runs after the damage write-back and withdrawal consequences,
        so damage_percent is read from the fleet token they landed on.
        """
        for stack in battling_stacks:
            snapshot = battle.stacks.get(stack.key)
            if snapshot is None or snapshot.token is None:
                continue
            initial = snapshot.token.quantity

            survived = 0
            damage_percent = 0.0
            if stack.token is not None and stack.token.quantity > 0:
                survived = stack.token.quantity
                empire = self.server_state.all_empires.get(stack.owner)
                fleet = (empire.owned_fleets.get(stack.parent_key)
                         if empire else None)
                token = (fleet.tokens.get(stack.token.design_key)
                         if fleet else None)
                if token is not None:
                    damage_percent = token.damage_percent

            battle.outcomes.append({
                "owner": stack.owner,
                "design_name": snapshot.token.design_name,
                "initial": initial,
                "destroyed": max(0, initial - survived),
                "survived": survived,
                "damage_percent": damage_percent,
            })

    def _resolve_boarding(
        self, battling_stacks: List[Stack], battle: BattleReport
    ) -> None:
        """
        Let every stack under a boarding order try for a prize.

        Web-only extension (user directive - "add boarding ships and
        boarding battle plans - to take over ships - but at great risk
        to self"; the C# reference has no boarding of any kind).

        Four gates keep boarding a gamble rather than a free action,
        and together they are why mass boarding is not a dominant
        strategy:

        1. the plan has to ask for it - "Never" is the default, so a
           commander who never opens the battle screen never risks a
           crew
        2. the prize must be in the boarder's own square, which means
           closing to zero range through everything the enemy has
        3. its SHIELDS must be down, so boarding rides on top of a
           fleet's firepower and can never replace it
        4. one attempt per stack per battle - the party crosses once,
           so a stack of ten boarders takes one prize, not ten, while
           all ten pay the failure

        A starbase neither boards nor is boarded: it cannot close, and
        a captured emplacement belongs to the star, not to a fleet.
        """
        for stack in battling_stacks:
            if stack.boarding_spent or stack.disengaged or stack.is_destroyed:
                continue
            if stack.is_starbase:
                continue
            if self._plan_of(stack).board != "When Able":
                continue

            prize = self._boarding_target(stack)
            if prize is not None:
                self._attempt_boarding(stack, prize, battle)

    def _boarding_target(self, stack: Stack) -> Optional[Stack]:
        """
        The best prize this stack can reach, or None.

        The candidates are the stack's own target list, so the plan's
        target tiers choose the prize exactly as they choose what to
        shoot at - an order to hunt capital ships boards capital ships.
        """
        for candidate in stack.target_list:
            if candidate.is_destroyed or candidate.disengaged:
                continue
            if candidate.is_starbase or candidate.token is None:
                continue
            if candidate.token.shields > 0:
                continue
            dist_sq = stack.position.distance_to_squared(candidate.position)
            if dist_sq <= self.GRID_SCALE_SQUARED:
                return candidate
        return None

    def _boarding_chance(self, attacker: Stack, defender: Stack) -> float:
        """
        Odds one boarding attempt succeeds.

        A strength ratio: each side's per-ship party (hull-derived and
        multiplied by fitted gear, boarding.py) times how many ships it
        has, so a like-for-like attempt is a coin flip and the fight is
        symmetric - the crew that repels boarders is the crew that
        makes them. Clamped at both ends: overwhelming marines still
        lose one attempt in seven.
        """
        ours = attacker.boarding_strength * attacker.token.quantity
        theirs = defender.boarding_strength * defender.token.quantity
        total = ours + theirs
        if total <= 0:
            return BOARDING_MIN_CHANCE
        return max(BOARDING_MIN_CHANCE,
                   min(BOARDING_MAX_CHANCE, ours / total))

    def _attempt_boarding(
        self, attacker: Stack, prize: Stack, battle: BattleReport
    ) -> None:
        """Roll one boarding attempt and pay for the outcome."""
        chance = self._boarding_chance(attacker, prize)
        # The party crosses once whichever way the roll goes
        attacker.boarding_spent = True
        success = self._random.random() < chance

        step = BattleStepBoard()
        step.stack_key = attacker.key
        step.target_key = prize.key
        step.chance = chance
        step.success = success
        step.design_name = prize.token.design_name
        battle.steps.append(step)

        if success:
            self._capture_ship(attacker, prize, battle)
            return

        # Failure destroys the boarding party and heavily damages the
        # boarder: half the armour it entered the battle with, applied
        # at once and able to kill it outright. The severity is the
        # point - a boarding order has to be a real gamble
        damage = (attacker.token.initial_armor
                  * BOARDING_FAILURE_ARMOR_PERCENT / 100.0)
        self._damage_armor(prize, attacker, damage, battle)
        if attacker.token.armor <= 0:
            self._destroy_stack(prize, attacker, battle)

        self._message_boarding(attacker, prize, battle, taken=False)

    def _capture_ship(
        self, captor: Stack, prize: Stack, battle: BattleReport
    ) -> None:
        """
        Transfer ONE ship of the prize token to the captor.

        The prize crosses as a new single-ship fleet at the battle
        location with a prize crew aboard - it takes no further part in
        the battle. Its design is copied into the captor's design list
        so the ship can be flown; the copy is marked obsolete because
        BUILDING a captured design is tech transfer, a separate
        criterion. The design itself is already revealed to every
        participant by _update_intel_designs at battle start.
        """
        quantity = prize.token.quantity
        design = prize.token.design
        captor_empire = self.server_state.all_empires.get(captor.owner)
        if quantity <= 0 or design is None or captor_empire is None:
            return

        # Take the prize's share of the stack's pools with it, so the
        # rest of the battle and the damage write-back stay consistent
        prize.token.armor -= prize.token.armor / quantity
        prize.token.initial_armor -= prize.token.initial_armor / quantity
        prize.token.quantity -= 1
        self._remove_captured_ship(prize)

        captured = self._register_captured_design(captor_empire, design)
        from ...services.ship_specs import make_token
        token = make_token(captured, quantity=1)
        # The prize is taken battered, not intact
        token.damage_percent = BOARDING_PRIZE_DAMAGE_PERCENT

        fleet = Fleet()
        fleet.key = captor_empire.get_next_fleet_key()
        fleet.owner = captor.owner
        fleet.position = NovaPoint(prize.position.x, prize.position.y)
        fleet.name = f"Prize {captured.name}"
        fleet.turn_year = self.server_state.turn_year
        fleet.battle_plan = getattr(
            captor_empire, 'default_battle_plan', 'Default')
        fleet.tokens[token.design_key] = token
        captor_empire.add_or_update_fleet(fleet)

        self._message_boarding(captor, prize, battle, taken=True)

    def _remove_captured_ship(self, prize: Stack) -> None:
        """Take the captured ship off its owner's fleet."""
        empire = self.server_state.all_empires.get(prize.owner)
        if empire is None:
            return
        fleet = empire.owned_fleets.get(prize.parent_key)
        if fleet is None:
            return
        token = fleet.tokens.get(prize.token.design_key)
        if token is None:
            return
        token.quantity -= 1
        if token.quantity <= 0:
            del fleet.tokens[prize.token.design_key]
            if not fleet.tokens:
                del empire.owned_fleets[prize.parent_key]

    def _register_captured_design(self, empire, design):
        """
        Give the captor a design record for the prize it just took.

        One record per captured design, reused by later captures of the
        same class, so a running war does not fill the design list.
        """
        import copy

        name = f"{getattr(design, 'name', 'Unknown')} (captured)"
        for existing in empire.designs.values():
            if existing.name == name:
                return existing

        captured = copy.deepcopy(design)
        captured.key = empire.get_next_design_key()
        captured.name = name
        captured.obsolete = True
        empire.designs[captured.key] = captured
        return captured

    def _message_boarding(
        self, boarder: Stack, prize: Stack, battle: BattleReport,
        taken: bool
    ) -> None:
        """Tell both sides how the boarding action went."""
        design = prize.token.design_name if prize.token else "a ship"
        if taken:
            captor_text = (f"Boarders from {boarder.name} took {design} "
                           f"at {battle.location}.")
            victim_text = (f"{design} was boarded and captured at "
                           f"{battle.location}.")
        else:
            captor_text = (f"The boarding party from {boarder.name} was "
                           f"destroyed attacking {design} at "
                           f"{battle.location}, and the boarder was "
                           f"crippled breaking off.")
            victim_text = (f"{design} repelled boarders at "
                           f"{battle.location}.")

        for audience, text in ((boarder.owner, captor_text),
                               (prize.owner, victim_text)):
            self.server_state.all_messages.append(Message(
                audience=audience,
                text=text,
                message_type="Battle",
                star_name=battle.location
            ))

    def _select_targets(self, battling_stacks: List[Stack]) -> int:
        """Select targets using priority-based system."""
        number_of_targets = 0

        for wolf in battling_stacks:
            if wolf.token is None or wolf.token.quantity <= 0:
                continue

            wolf.target = None
            wolf.target_list = []
            wolf.target_priorities = {}

            # A disengaged stack has left the battle: it neither picks
            # targets nor fires (canonical Stars! disengage;
            # simplification: it stops firing while fleeing)
            if wolf.disengaged:
                continue

            selected_targets: List[TargetRow] = []

            for lamb in battling_stacks:
                if lamb.token is None or lamb.token.quantity <= 0:
                    continue
                if lamb.token.armor <= 0:
                    continue
                if lamb.disengaged:
                    # Left the board - no longer targetable
                    continue

                if self._are_enemies(wolf, lamb):
                    priority = self._get_priority(lamb, wolf)
                    if wolf.is_armed:
                        # Target types define what an armed stack may
                        # shoot at: a lamb matching none of the plan's
                        # five tiers (priority 0) is not engaged
                        # (canonical Stars! rule; BattleEngine.cs never
                        # consumed the tiers)
                        if priority == 0:
                            continue
                        attractiveness = self._get_attractiveness(lamb)
                    else:
                        # Unarmed ships move away from closest armed
                        dist_sq = wolf.position.distance_to_squared(lamb.position)
                        attractiveness = abs(1000.0 / (dist_sq + 1))

                    selected_targets.append(TargetRow(lamb, priority, attractiveness))

            if selected_targets:
                # Only ARMED wolves count as battle triggers - C#
                # SelectTargets skips unarmed wolves before any target
                # assignment (BattleEngine.cs:412-415), so unarmed-vs-
                # unarmed co-location yields 0 targets and no battle.
                # The unarmed wolf still gets its flee target/list so
                # movement works when armed enemies are present.
                if wolf.is_armed:
                    number_of_targets += 1
                # Sort by priority then attractiveness
                selected_targets.sort(
                    key=lambda t: (t.priority, t.attractiveness)
                )
                wolf.target = selected_targets[-1].fleet
                # Fire allocation (_generate_attacks) consumes the list
                # from the front: highest priority tier first, spilling
                # leftover percent onto lower tiers
                wolf.target_list = [t.fleet
                                    for t in reversed(selected_targets)]
                # Keep the tier that matched each target so the report
                # can name it (the engine used to discard it here)
                wolf.target_priorities = {t.fleet.key: t.priority
                                          for t in selected_targets}

        return number_of_targets

    def _get_priority(self, target: Stack, source: Stack) -> int:
        """Get targeting priority based on battle plan."""
        if target is None or target.is_destroyed:
            return 0

        if source.owner not in self.server_state.all_empires:
            return 0

        empire = self.server_state.all_empires[source.owner]
        plan = empire.battle_plans.get(source.battle_plan)

        if source.is_armed:
            if plan is None:
                return 0

            if self._target_matches_priority(plan.primary_target, target):
                return 7
            if self._target_matches_priority(plan.secondary_target, target):
                return 6
            if self._target_matches_priority(plan.tertiary_target, target):
                return 5
            if self._target_matches_priority(plan.quaternary_target, target):
                return 4
            if self._target_matches_priority(plan.quinary_target, target):
                return 3
            return 0
        elif target.is_armed and not target.is_starbase:
            return 7
        else:
            return 0

    def _target_matches_priority(self, priority: int, target: Stack) -> bool:
        """
        Check if target matches the given priority type.

        The class tiers test the target's inferred battle role (the
        ship_role.py cascade, one role per design), so an order may
        name a real class. ARMED_SHIP and ANY_SHIP stay the broad
        catch-alls they always were and cut across roles.
        """
        role = target.battle_role

        if priority == Victims.STARBASE:
            return role == ShipRole.STARBASE
        if priority == Victims.BOMBER:
            return role == ShipRole.BOMBER
        if priority == Victims.CAPITAL_SHIP:
            return role == ShipRole.CAPITAL
        if priority == Victims.ESCORT:
            return role == ShipRole.ESCORT
        if priority == Victims.LOGISTICS:
            return role == ShipRole.LOGISTICS
        if priority == Victims.BOARDER:
            return role == ShipRole.BOARDER
        if priority == Victims.SUPPORT_SHIP:
            return role == ShipRole.SUPPORT
        if priority == Victims.ARMED_SHIP:
            return target.is_armed
        if priority == Victims.ANY_SHIP:
            return True

        return False

    def _get_attractiveness(self, target: Stack) -> float:
        """Calculate how attractive a stack is to attack."""
        if target is None or target.is_destroyed:
            return 0.0

        cost = target.mass + target.total_cost.energy
        dp = target.defenses
        if dp == 0:
            return float('inf')

        return cost / dp

    def _are_enemies(self, wolf: Stack, lamb: Stack) -> bool:
        """Check if lamb is a valid target for wolf."""
        if wolf.owner == lamb.owner:
            return False

        if wolf.owner not in self.server_state.all_empires:
            return False

        wolf_data = self.server_state.all_empires[wolf.owner]
        plan = wolf_data.battle_plans.get(wolf.battle_plan, BattlePlan())

        if plan.attack == "Everyone":
            return True
        elif plan.target_id == lamb.owner:
            return True
        elif plan.attack == "Enemies":
            # Check relation - empire_reports holds plain dicts;
            # unknown empires default to Enemy (relations proper are
            # a later gap)
            relation = wolf_data.empire_reports.get(
                lamb.owner, {}).get("relation", "Enemy")
            if relation == "Enemy":
                return True
        elif plan.attack == "Enemies and Neutrals":
            # Option exists in the C# dialog (BattlePlans.Designer.cs
            # line 149) but BattleEngine.cs:479-493 never consumed it -
            # canonical Stars! rule
            relation = wolf_data.empire_reports.get(
                lamb.owner, {}).get("relation", "Enemy")
            if relation in ("Enemy", "Neutral"):
                return True

        return False

    def _move_stacks(
        self,
        battling_stacks: List[Stack],
        battle_round: int,
        battle: BattleReport
    ) -> None:
        """Move stacks using Ron's improved movement system.

        Stacks are walked in _move_order, not in the order
        battling_stacks was built. This loop mutates Stack.Position as
        it goes, exactly as the C# does (BattleEngine.cs:501-600), so
        a stack reads its target where the target ALREADY MOVED this
        round whenever the target came earlier in the walk. Moving
        last is therefore an advantage: the last mover closes on where
        its enemy actually ended up, while the first mover commits to
        where the enemy no longer is. _generate_stacks builds the list
        by walking colocated_fleets, which is one empire's fleets then
        the other's, so that advantage went to the same empire every
        round of every battle. In the C# it is a 1-square error on a
        10-square board; the Ron engine moves a whole battle speed per
        round, which turned it into a systematic side bias (measured
        at +1.02 summed mean mirror margin over 32 seeds).

        The fix is canon's own, the one line the C# left undone at
        BattleEngine.cs:524 - "TODO (priority 5) - Move in order of
        ship mass, juggle by 15%". Order by a ship property with a
        random tiebreak and the last-mover advantage still exists but
        is dealt out by mass and chance instead of being handed to
        whoever the list happened to start with.

        Resolving every heading against a round-start snapshot instead
        was tried and rejected. It removes the ordering effect outright
        but it also removes convergence: two stacks closing head-on
        each step onto the square the other just left, so they swap
        places and keep swapping, never co-locating. Canonical
        movement converges precisely BECAUSE it is sequential -
        PointUtilities.BattleMoveTo:224-247 steps an axis only while it
        is strictly farther away, so the second mover of a closing pair
        sees the first has arrived and stops. Measured cost of the
        snapshot: boarding captured nothing in any run of
        test_a_boarding_heavy_force_does_not_beat_a_balanced_one,
        because no two stacks ever shared a square.
        """
        for stack in self._move_order(battling_stacks):
            if stack is None or stack.token is None or stack.token.quantity <= 0:
                continue

            if stack.target is None or stack.is_starbase:
                continue

            # Brace posture: an ARMED stack holds its position for the
            # whole battle. It never closes, so a short-ranged design
            # braced against a longer-ranged enemy never gets to fire -
            # the positional commitment the posture is paying for - and
            # it can never accumulate the moves a disengagement needs.
            # What the posture fixes is a FIRING position, so it has
            # nothing to say to an unarmed hull, which keeps the
            # canonical behaviour of staying out of weapon range
            # (BATTLE.TXT gives new unarmed fleets Default-Defense,
            # whose "initial behavior is to try to avoid combat
            # entirely"). Bracing them too parked a third of every task
            # force in the open (DEF-31)
            if stack.is_armed and \
                    self._plan_of(stack).posture_modifiers.holds_position:
                continue

            vector_to_target = NovaPoint(
                stack.target.position.x - stack.position.x,
                stack.target.position.y - stack.position.y
            )

            # Calculate heading
            speed = stack.battle_speed * self.GRID_SCALE
            new_heading = self._battle_speed_vector(vector_to_target, speed)

            # Why this stack moved the way it did, when there is a
            # reason worth reporting (the Salvo then Close commitment)
            motive = ""
            # A give-ground step keeps a stand-off band; it is clamped
            # to the board and never counts as fleeing
            gives_ground = False

            # Plan tactic for this round (canonical Stars! rules; the
            # C# reference never consumed Tactic - BattleEngine.cs:603
            # TODO). The round<5 random flip keeps precedence: it
            # models the initial maneuvering of every stack.
            tactic = self._effective_tactic(stack)

            # Unarmed ships have special behavior
            if not stack.is_armed or battle_round < 5:
                if battle_round < 5:
                    # Random movement early in battle
                    choice = self._random.randint(1, 3)
                    if choice == 2:
                        new_heading = self._break_off_heading(
                            new_heading, speed)
                elif tactic == "Disengage":
                    # Unarmed disengaging stack flees the board instead
                    # of merely keeping out of weapon range
                    new_heading = self._break_off_heading(new_heading, speed)
                    self._count_flee_move(stack, battle)
                elif stack.distance_to(stack.target) / self.GRID_SCALE < MAX_WEAPON_RANGE:
                    # Run away from armed enemy
                    new_heading = self._break_off_heading(new_heading, speed)
                else:
                    new_heading = NovaPoint(0, 0)
            elif tactic == "Disengage":
                # Armed disengaging stack flees its target
                new_heading = self._break_off_heading(new_heading, speed)
                self._count_flee_move(stack, battle)
            elif tactic in ("Minimise Damage to Self", "Maximise Damage Ratio",
                            "Maximise Net Damage", "Salvo then Close"):
                # Stand-off tactics maintain their range band BOTH
                # ways: close while the target is beyond the hold
                # range, give ground when it presses inside the band
                # (canon, docs/research-battle-doctrine.md:39 - "if
                # your weapons are longer range then try to stay at
                # maximum range"; the old approach-and-halt shape was
                # the one-way ratchet measured in
                # docs/research-engagement-range.md:19).
                # "Minimise Damage to Self" additionally falls back
                # while its shields are down. "Salvo then Close" opens
                # like Maximise Damage Ratio and commits to the run-in
                # per target. Canonical-approx heuristics - the exact
                # Stars! math is unpublished and the C# reference has
                # no implementation.
                if (tactic == "Salvo then Close"
                        and stack.target.key not in stack.salvo_committed):
                    motive = self._close_for_kill_reason(stack.target)
                    if motive:
                        stack.salvo_committed.add(stack.target.key)
                if (tactic == "Salvo then Close"
                        and stack.target.key in stack.salvo_committed):
                    # Committed: close like Maximise Damage against
                    # this target for the rest of the battle - keep
                    # the closing heading
                    pass
                else:
                    hold_range = self._hold_range(stack, tactic)
                    band_floor = self.HOLD_RANGE_DEADBAND * hold_range
                    distance = stack.distance_to(stack.target)
                    if (tactic == "Minimise Damage to Self"
                            and stack.token.shields <= 0):
                        new_heading = self._break_off_heading(
                            new_heading, speed)
                        gives_ground = True
                    elif distance > hold_range:
                        # Keep the closing heading, but stop ON the
                        # band instead of a full battle speed past it:
                        # uncapped, a 100+ unit step leapfrogs the
                        # 30-unit deadband entirely and two stand-off
                        # stacks bounce in and out of each other's
                        # range forever, firing almost never. Canon
                        # holds AT maximum range
                        # (docs/research-battle-doctrine.md:39)
                        new_heading = self._cap_step(
                            new_heading, distance - band_floor)
                    elif distance < band_floor:
                        # Give ground: step away along the closing
                        # vector. NOT a flee move - fleeing is a
                        # declared act; a stack keeping its band must
                        # never touch _count_flee_move or it silently
                        # becomes a withdrawal
                        # (docs/research-engagement-range.md:44)
                        new_heading = self._cap_step(
                            self._break_off_heading(new_heading, speed),
                            hold_range - distance)
                        gives_ground = True
                    else:
                        new_heading = NovaPoint(0, 0)
            # "Maximise Damage" (default) keeps the closing heading

            if gives_ground:
                new_heading = self._clamp_to_board(
                    stack.position, new_heading)

            # A closing step lands ON the target and never carries the
            # stack past it, which is what canonical movement does:
            # PointUtilities.BattleMoveTo:224-247 steps an axis only
            # while it is strictly farther away, so a stack converges
            # on its target and stops there. Uncapped, two stacks
            # closing on each other jump past one another every round
            # and the engaged pair then travels a full battle speed
            # per round in the direction the first mover was heading,
            # carrying the battle away from every stack that has not
            # caught up yet - which is DEF-30, the systematic side
            # advantage the balance matrices were measuring
            new_heading = self._cap_at_target(new_heading, vector_to_target)

            # Initialize velocity if needed
            if stack.velocity_vector is None:
                stack.velocity_vector = new_heading

            # Update position
            stack.position = NovaPoint(
                stack.position.x + new_heading.x,
                stack.position.y + new_heading.y
            )

            # Record movement if significant; a motive is always
            # recorded, so the Salvo then Close commitment shows in
            # the report even when the committing stack is already on
            # top of its target
            if new_heading.x != 0 or new_heading.y != 0 \
                    or battle_round < 5 or motive:
                report = BattleStepMovement()
                report.stack_key = stack.key
                report.position = NovaPoint(stack.position.x, stack.position.y)
                report.motive = motive
                battle.steps.append(report)

    def _move_order(self, battling_stacks: List[Stack]) -> List[Stack]:
        """
        The order stacks are walked in for movement.

        Canon: BattleEngine.cs:524 "TODO (priority 5) - Move in order
        of ship mass, juggle by 15%" - never implemented in the C#,
        which walks the list as built. docs/research-battle-doctrine.md:47
        records the rule it stands for: movement resolves heaviest
        first with "a random fudge factor" (under a 15 percent weight
        difference the lighter token may go first, more likely the
        closer the weights). Perturbing each mass by up to 15 percent
        before sorting reproduces exactly that: stacks more than 30
        percent apart never swap, closer ones swap with a probability
        that rises as the gap closes, and equal masses - a mirror
        match, where the empire's position in the list would otherwise
        decide everything - come out in random order.
        """
        juggled = [(stack.mass * self._random.uniform(0.85, 1.15), index,
                    stack)
                   for index, stack in enumerate(battling_stacks)]
        juggled.sort(key=lambda row: (-row[0], row[1]))
        return [row[2] for row in juggled]

    def _effective_tactic(self, stack: Stack) -> str:
        """
        Resolve the stack's plan tactic for this round.

        "Disengage if Challenged" behaves as Maximise Damage until the
        stack has taken damage, then switches to Disengage (canonical
        Stars! rule; C# absent).

        Two doctrine axes ride on top. The plan's withdrawal threshold
        turns any tactic into Disengage once it is met. An Aggressive
        stance forfeits disengagement entirely - it is the sharpest
        cost of the stance and it overrides everything, including a
        plan that asked to Disengage outright.
        """
        if stack.owner not in self.server_state.all_empires:
            return "Maximise Damage"
        empire = self.server_state.all_empires[stack.owner]
        plan = empire.battle_plans.get(stack.battle_plan)
        if plan is None:
            return "Maximise Damage"

        if plan.tactic == "Disengage if Challenged":
            tactic = "Disengage" if stack.damage_taken else "Maximise Damage"
        else:
            tactic = plan.tactic

        if tactic != "Disengage" and self._withdraw_threshold_met(stack):
            tactic = "Disengage"

        if tactic == "Disengage" and not plan.stance_modifiers.may_disengage:
            return "Maximise Damage"

        return tactic

    def _count_flee_move(self, stack: Stack, battle: BattleReport) -> None:
        """
        Count a flee move; after DISENGAGE_MOVES the stack has left.

        Canonical Stars!: 7 squares of battle board movement to leave
        the battle, shortened by a Defensive stance or a Scatter
        posture (_disengage_moves_required); one flee move per round
        at battle speed
        approximates one square per round (canonical-approx). While
        still present the stack can be fired upon. Leaving the board
        is recorded as its own report step, so a withdrawal reads as a
        withdrawal instead of movement that silently stops.
        """
        stack.flee_rounds += 1
        required = self._disengage_moves_required(stack)
        if stack.flee_rounds >= required and not stack.disengaged:
            stack.disengaged = True
            withdraw = BattleStepWithdraw()
            withdraw.stack_key = stack.key
            battle.steps.append(withdraw)

    def _cap_at_target(
        self, heading: NovaPoint, to_target: NovaPoint
    ) -> NovaPoint:
        """
        Shorten a closing step so the stack stops on its target.

        Canonical Stars! movement steps one square at a time and only
        while the square is strictly farther away
        (PointUtilities.BattleMoveTo:224-247), so a closing stack can
        never end a move past the thing it is closing on. The Ron
        engine moves a fixed-length vector instead and needs the cap
        applied explicitly.

        Only a step that points at the target can overshoot it, so a
        stack breaking off is left alone.
        """
        span = math.hypot(to_target.x, to_target.y)
        step = math.hypot(heading.x, heading.y)
        if step == 0 or step <= span:
            return heading
        if heading.x * to_target.x + heading.y * to_target.y <= 0:
            return heading

        scale = span / step
        return NovaPoint(int(heading.x * scale), int(heading.y * scale))

    def _cap_step(self, heading: NovaPoint, max_step: float) -> NovaPoint:
        """
        Shorten a stand-off step to a Manhattan length, keeping its
        direction.

        Battle distances are Manhattan (NovaPoint.distance_to:255-258),
        so the cap is applied to the heading's Manhattan length: a
        closing step capped at (distance - band floor) lands inside
        the [0.9R, R] hold band, and a give-ground step capped at
        (R - distance) backs off to the band's outer edge and no
        further - "try to stay at maximum range"
        (docs/research-battle-doctrine.md:39). Truncation loses at
        most 2 units, well inside the band's 0.1R width, and both
        caps are at least 0.1R when they engage, so a capped step is
        never rounded to a standstill.
        """
        step = abs(heading.x) + abs(heading.y)
        if step == 0 or step <= max_step:
            return heading
        scale = max_step / step
        return NovaPoint(int(heading.x * scale), int(heading.y * scale))

    def _break_off_heading(
        self, heading: NovaPoint, speed: float
    ) -> NovaPoint:
        """
        Heading for a stack moving away from its target.

        Straight back down the closing heading, except when the two
        share a square and there is no "away" to point at. Canonical
        Stars! covers that case explicitly - a disengaging token that
        can neither open the range nor hold it "move[s] to a random
        square" (Guts of the Battle Engine, disengage rules) - and it
        arises here because a capped closing step lands on the target.
        """
        if heading.x or heading.y:
            return NovaPoint(-heading.x, -heading.y)

        bearing = self._random.uniform(0.0, 2.0 * math.pi)
        return NovaPoint(int(speed * math.cos(bearing)),
                         int(speed * math.sin(bearing)))

    def _hold_range(self, stack: Stack, tactic: str) -> float:
        """
        The stand-off hold distance for a tactic, in grid units.

        "Maximise Net Damage" holds at the range where ALL its
        weapons bear - the SHORTEST mounted range (canon: "If in
        range with all weapons them move as to maximise
        damage_done/damage_taken", docs/research-battle-doctrine.md:39).
        Every other stand-off tactic holds at the LONGEST ("as
        Maximise Net Damage but only considers the longest range
        weapon", docs/research-engagement-range.md:17). Using max()
        for all three made Maximise Net Damage behave as Maximise
        Damage Ratio, so a mixed beam-plus-torpedo design never
        closed far enough to bring its beams up
        (docs/research-engagement-range.md:19).
        """
        if stack.token is None or stack.token.design is None:
            return 0.0
        ranges = [w.range for w in stack.token.design.weapons]
        if not ranges:
            return 0.0
        if tactic == "Maximise Net Damage":
            return min(ranges) * self.GRID_SCALE
        return max(ranges) * self.GRID_SCALE

    def _close_for_kill_reason(self, target: Stack) -> str:
        """
        Why a "Salvo then Close" stack commits to the run-in, or ""
        while it should keep holding range.

        Two conditions, both fixed
        (docs/research-engagement-range.md:51): the target has begun
        disengaging - the one case where closing is unambiguously
        right, a broken enemy walking off the board with your kills
        aboard (:59) - or its armour has fallen to or below
        CLOSE_FOR_KILL_ARMOUR_PERCENT of what it entered the battle
        with. Armour never heals during a battle, so the trigger is
        monotonic: it fires once and never un-fires (:53).
        """
        if target.flee_rounds > 0 or target.disengaged:
            return "closing for the kill - target disengaging"
        token = target.token
        if token is not None and token.initial_armor > 0 \
                and (token.armor / token.initial_armor * 100.0
                     <= CLOSE_FOR_KILL_ARMOUR_PERCENT):
            return ("closing for the kill - target below "
                    f"{CLOSE_FOR_KILL_ARMOUR_PERCENT:.0f}% armour")
        return ""

    def _clamp_to_board(
        self, position: NovaPoint, heading: NovaPoint
    ) -> NovaPoint:
        """
        Shorten a give-ground step at the board wall.

        The 1000-unit grid is the whole board (GRID_SIZE - canon's
        10x10 squares at GRID_SCALE). The wall is what keeps kiting
        beatable: the engagement-range review measured uncapped
        retreat leaving the pursuing beam side at +0.04 mean margin
        against +0.72 with the board clamped
        (docs/research-engagement-range.md:345-352), so a stack gives
        ground only to the edge and then stands.
        """
        clamped_x = min(max(position.x + heading.x, 0), self.GRID_SIZE)
        clamped_y = min(max(position.y + heading.y, 0), self.GRID_SIZE)
        return NovaPoint(clamped_x - position.x, clamped_y - position.y)

    def _battle_speed_vector(
        self, direction: NovaPoint, speed: float
    ) -> NovaPoint:
        """Calculate velocity vector for battle movement."""
        length = math.sqrt(direction.x ** 2 + direction.y ** 2)
        if length == 0:
            return NovaPoint(0, 0)

        scale = speed / length
        return NovaPoint(
            int(direction.x * scale),
            int(direction.y * scale)
        )

    def _generate_attacks(self, battling_stacks: List[Stack]) -> List[WeaponDetails]:
        """Generate weapon attacks with Ron's percentage-based system."""
        all_attacks: List[WeaponDetails] = []

        # Equal initiative is a tie, and a tie has to be broken by
        # something other than the order empires occupy in
        # battling_stacks. The sort below is stable, so walking the
        # list as built handed every tie to whichever empire
        # _generate_stacks listed first - and in a mirror match, where
        # every weapon carries the same initiative, that is the entire
        # firing order. Firing first is worth a great deal (a stack
        # killed before it fires contributes nothing), so this is the
        # same defect as the movement one and needs the same answer:
        # the tie goes to a random stack, exactly as canon breaks the
        # equivalent movement tie (BattleEngine.cs:524 "juggle by
        # 15%"). Within one stack the sequence is left alone - it is
        # the target-priority spill order, not a tie.
        firing_stacks = list(battling_stacks)
        self._random.shuffle(firing_stacks)

        for stack in firing_stacks:
            if stack.is_destroyed:
                continue
            # A disengaged stack has left the battle and fires nothing
            if stack.disengaged:
                continue
            if not stack.token or not stack.token.design:
                continue

            # A braced stack fights from a fixed emplacement, so it
            # gets the range bonus canonical Stars! gives a starbase
            # (battle_plan.POSTURE_MODIFIERS)
            range_bonus = self._plan_of(
                stack).posture_modifiers.weapon_range_bonus

            for weapon in stack.token.design.weapons:
                percent_fired = 0
                target_index = 0

                while percent_fired < 100 and target_index < len(stack.target_list):
                    target = stack.target_list[target_index]
                    # A target that completed its disengage this round
                    # is gone (canonical: fleeing tokens can be fired
                    # upon only while still present)
                    if target.disengaged:
                        target_index += 1
                        continue
                    dist_sq = stack.position.distance_to_squared(target.position)
                    range_sq = ((weapon.range + range_bonus) ** 2
                                * self.GRID_SCALE_SQUARED)

                    if dist_sq <= range_sq and target.total_armor_strength > 0:
                        # Calculate percentage of fire needed
                        if weapon.is_missile:
                            damage_needed = target.total_shield_strength + target.total_armor_strength
                            damage_per = weapon.power * stack.token.quantity / 10.0
                            percent_to_fire = int(115.0 * damage_needed / damage_per)
                        else:
                            damage_needed = target.total_shield_strength + target.total_armor_strength
                            damage_per = weapon.power * stack.token.quantity / 10.0
                            percent_to_fire = int(101.0 * damage_needed / damage_per)

                        percent_to_fire = min(100, percent_to_fire)
                        percent_to_fire = min(100 - percent_fired, percent_to_fire)

                        attack = WeaponDetails()
                        attack.source_stack = stack
                        attack.target_stack = TargetPercent(target, percent_to_fire)
                        attack.weapon = weapon
                        # Stance shifts when this weapon resolves in
                        # the round; a stack killed before it fires
                        # contributes nothing, which is why firing
                        # order is not a symmetric damage multiplier
                        attack.initiative_bonus = (
                            self._plan_of(stack).stance_modifiers.initiative)
                        all_attacks.append(attack)

                        percent_fired += percent_to_fire

                    target_index += 1

        # Highest initiative fires first (BATTLE.TXT: each round is
        # target selection, movement, then weapon fire ordered
        # highest-initiative-to-lowest). WeaponDetails.__lt__ compares
        # initiative ascending, so the descending order is reverse=True
        all_attacks.sort(reverse=True)
        return all_attacks

    def _process_attack(
        self, attack: WeaponDetails, battle: BattleReport
    ) -> bool:
        """Process a weapon attack."""
        if attack.target_stack.target is None:
            return False
        if attack.target_stack.target.is_destroyed:
            return False
        if attack.source_stack is None or attack.source_stack.is_destroyed:
            return False

        self._execute_attack(attack, battle)
        return True

    def _execute_attack(
        self, attack: WeaponDetails, battle: BattleReport
    ) -> None:
        """Execute weapon attack."""
        attacker = attack.source_stack
        target = attack.target_stack.target

        report = BattleStepTarget()
        report.stack_key = attacker.key
        report.target_key = target.key
        report.percent_to_fire = attack.target_stack.percent_to_fire
        report.priority = attacker.target_priorities.get(target.key, 0)
        report.target_role = str(target.battle_role)
        battle.steps.append(report)

        if attack.weapon is None:
            return

        percent = attack.target_stack.percent_to_fire / 100.0
        hit_power = attack.weapon.power * attacker.token.quantity * percent

        # A Scatter posture spreads the stack out, so it cannot
        # concentrate its own fire (battle_plan.POSTURE_MODIFIERS)
        attacker_plan = self._plan_of(attacker)
        hit_power *= attacker_plan.posture_modifiers.damage_dealt

        # Electronics modifiers read per-design aggregates, never
        # multiplied by token quantity (C# passes Token.Design to both
        # Calculate* functions, BattleEngine.cs:698-699)
        source_design = attacker.token.design if attacker.token else None
        target_design = target.token.design if target.token else None

        if attack.weapon.is_missile:
            # Computers vs jammers modify torpedo accuracy (canonical
            # Stars! rule; C# stub at BattleEngine.cs:920-929)
            accuracy = attack.missile_accuracy(
                source_design, target_design,
                attack.weapon.accuracy / 100.0)
            # Stance trades accuracy, which is worth nothing to a beam
            # fleet - the enemy's weapon class decides its value. A
            # Scatter posture on the far side is spread out, which is
            # harder to guide a torpedo into and does nothing at all
            # against beams (battle_plan.POSTURE_MODIFIERS)
            accuracy = max(0.0, min(
                1.0,
                accuracy * attacker_plan.stance_modifiers.missile_accuracy
                * self._plan_of(
                    target).posture_modifiers.incoming_missile_accuracy))
            self._fire_missile(attacker, target, hit_power, accuracy, battle)
        else:
            # Capacitors boost / deflectors cut beam damage (canonical
            # Stars! rule; C# stub at BattleEngine.cs:880-908)
            hit_power *= attack.beam_power_modifier(
                source_design, target_design)
            # Beam damage dissipates with range: full power in the
            # target's own square, 10 percent lost at the weapon's
            # maximum range (BATTLE.TXT - "a weapon that will do 100dp
            # in the same square as its target will only do 90dp one
            # square away", quoted in docs/research-battle-doctrine.md;
            # the C# consumer is the commented-out stub at
            # BattleEngine.cs:880-908). Ron positions are GRID_SCALE
            # units per square, so the squared distance is compared
            # against range^2 * GRID_SCALE^2
            dist_sq = attacker.position.distance_to_squared(target.position)
            hit_power *= attack.beam_dispersal_ron(
                dist_sq, self.GRID_SCALE_SQUARED) / 100.0
            self._fire_beam(attacker, target, hit_power, battle)

        if target.token and target.token.armor <= 0:
            self._destroy_stack(attacker, target, battle)

    def _fire_beam(
        self,
        attacker: Stack,
        target: Stack,
        hit_power: float,
        battle: BattleReport
    ) -> None:
        """Fire beam weapon."""
        hit_power = self._damage_shields(attacker, target, hit_power, battle)

        if target.token and target.token.shields > 0:
            return
        if hit_power <= 0:
            return

        self._damage_armor(attacker, target, hit_power, battle)

    def _fire_missile(
        self,
        attacker: Stack,
        target: Stack,
        hit_power: float,
        accuracy: float,
        battle: BattleReport
    ) -> None:
        """Fire missile weapon with Ron's accuracy system."""
        # Hit power is applied directly, exactly as the C# FireMissile
        # does (BattleEngine.cs:794-808). A former "10 rounds per turn"
        # /10 here had no beam equivalent and no C# ancestor, deleting
        # 90 percent of torpedo damage (DEF-33)

        # Random accuracy variation
        probability = self._random.randint(-50, 50)
        percent_hit = accuracy + (probability / 100.0) * accuracy / 2.0
        percent_hit = max(0.0, min(1.0, percent_hit))

        # Misses do splash damage - the engine's area effect, which a
        # Scatter posture is spread out to blunt
        miss_damage = hit_power * (1 - percent_hit) / 8
        miss_damage *= self._plan_of(target).posture_modifiers.splash_taken
        self._damage_shields(attacker, target, miss_damage, battle)

        # Hits split between shields and armor
        shields_hit = hit_power * percent_hit / 2
        armor_hit = (hit_power * percent_hit / 2) + \
            self._damage_shields(attacker, target, shields_hit, battle)
        self._damage_armor(attacker, target, armor_hit, battle)

    def _damage_shields(
        self,
        attacker: Stack,
        target: Stack,
        hit_power: float,
        battle: BattleReport
    ) -> float:
        """Apply damage to shields."""
        if target.token is None or target.token.shields <= 0:
            return hit_power

        initial = target.token.shields
        target.token.shields -= hit_power
        if target.token.shields < 0:
            target.token.shields = 0

        damage_done = initial - target.token.shields
        if damage_done > 0:
            # Drives "Disengage if Challenged" (canonical Stars! rule)
            target.damage_taken = True

        step = BattleStepWeapons()
        step.damage = damage_done
        step.targeting = TokenDefence.SHIELDS
        step.weapon_target = WeaponTarget(attacker.key, target.key)
        battle.steps.append(step)

        return hit_power - damage_done

    def _damage_armor(
        self,
        attacker: Stack,
        target: Stack,
        hit_power: float,
        battle: BattleReport
    ) -> None:
        """Apply damage to armor."""
        if target.token is None:
            return

        target.token.armor -= hit_power
        if hit_power > 0:
            # Drives "Disengage if Challenged" (canonical Stars! rule)
            target.damage_taken = True

        # Per-ship attrition (DEF-35): enough armour damage kills whole
        # ships out of the token, not just the token whole at the end.
        # This is the rule the C# reference names for itself and
        # declines - "Should destroy whole ships first, then spread
        # remaining damage" (BattleEngine.cs:857) and "What about
        # losses of a single ship within the token???"
        # (BattleEngine.cs:713), both tracked in the reference's
        # BUGS.txt - and the rule mines and storms already apply
        # (turn_generator.py:1540, :1348). Firepower reads quantity,
        # so a silenced gun follows for free; the shield pool is
        # scaled with the survivors so dead ships stop shielding.
        token = target.token
        if token.initial_quantity > 0 and token.initial_armor > 0:
            per_ship_armor = token.initial_armor / token.initial_quantity
            surviving = math.ceil(max(0.0, token.armor) / per_ship_armor)
            if surviving < token.quantity:
                killed = token.quantity - surviving
                token.shields *= surviving / token.quantity
                token.quantity = surviving
                battle.losses[target.owner] = \
                    battle.losses.get(target.owner, 0) + killed

        step = BattleStepWeapons()
        step.damage = hit_power
        step.targeting = TokenDefence.ARMOR
        step.weapon_target = WeaponTarget(attacker.key, target.key)
        battle.steps.append(step)

    def _destroy_stack(
        self,
        attacker: Stack,
        target: Stack,
        battle: BattleReport
    ) -> None:
        """Handle stack destruction."""
        if target.token is None:
            return

        battle.losses[target.owner] = \
            battle.losses.get(target.owner, 0) + target.token.quantity

        destroy = BattleStepDestroy()
        destroy.stack_key = target.key
        battle.steps.append(destroy)

        # Handle starbase destruction
        if target.is_starbase and target.in_orbit:
            if target.owner in self.server_state.all_empires:
                empire = self.server_state.all_empires[target.owner]
                if target.in_orbit.name in empire.owned_stars:
                    empire.owned_stars[target.in_orbit.name].starbase = None

        # Remove from fleet
        if target.owner in self.server_state.all_empires:
            empire = self.server_state.all_empires[target.owner]
            if target.parent_key in empire.owned_fleets:
                fleet = empire.owned_fleets[target.parent_key]
                if target.token.design_key in fleet.tokens:
                    del fleet.tokens[target.token.design_key]

                # Create salvage
                star = self._find_star_at_position(target.position)
                if star:
                    cost = target.total_cost
                    star.resources_on_hand.ironium += int(0.9 * cost.ironium)
                    star.resources_on_hand.boranium += int(0.9 * cost.boranium)
                    star.resources_on_hand.germanium += int(0.9 * cost.germanium)
                else:
                    self._create_salvage(
                        target.position, target.total_cost, target.cargo, target.owner
                    )

                if not fleet.tokens:
                    del empire.owned_fleets[target.parent_key]

        target.token = None

    def _apply_withdrawal_consequences(
        self, battling_stacks: List[Stack], battle: BattleReport
    ) -> None:
        """
        Charge a fleet for leaving the battle.

        Withdrawal used to be a battle-local flag: the stack stopped
        firing, the battle ended, and the same fleet sailed on to fight
        again the next turn for free. Every system that makes retreat
        work charges for it in one of three currencies (rounds of
        exposure, hull damage, strategic position - see
        docs/research-battle-doctrine.md section 5). The board moves
        already charge exposure; this charges the other two:

        - every surviving ship carries WITHDRAWAL_DAMAGE_PERCENT of
          damage away, on the same damage_percent the repair step
          heals
        - the fleet's remaining waypoint orders are cancelled, so a
          fleet that broke off does not sail straight back into the
          engagement it just fled. Waypoint zero is the fleet's own
          position and is kept

        Charged once per fleet however many of its stacks withdrew.
        """
        withdrawn: Dict[int, int] = {}
        for stack in battling_stacks:
            if stack.disengaged:
                withdrawn[stack.parent_key] = stack.owner

        for fleet_key, owner in withdrawn.items():
            empire = self.server_state.all_empires.get(owner)
            if empire is None:
                continue
            fleet = empire.owned_fleets.get(fleet_key)
            if fleet is None:
                continue

            fleet.withdrawn_year = self.server_state.turn_year
            if len(fleet.waypoints) > 1:
                del fleet.waypoints[1:]

            for token in fleet.tokens.values():
                token.damage_percent = min(
                    99.0, token.damage_percent + WITHDRAWAL_DAMAGE_PERCENT)

            self.server_state.all_messages.append(Message(
                audience=owner,
                text=f"{fleet.name} withdrew from the battle at "
                     f"{battle.location}. Its remaining orders were "
                     f"cancelled and its ships took "
                     f"{int(WITHDRAWAL_DAMAGE_PERCENT)}% damage breaking "
                     f"off.",
                message_type="Battle",
                fleet_key=fleet.key,
                star_name=battle.location
            ))

    def _find_star_at_position(self, position: NovaPoint) -> Optional['Star']:
        """Find star at position."""
        for star in self.server_state.all_stars.values():
            if star.position.distance_to_squared(position) < 2.0:
                return star
        return None

    def _create_salvage(
        self,
        position: NovaPoint,
        salvage: Resources,
        cargo: Cargo,
        empire_id: int
    ) -> None:
        """Create salvage fleet."""
        if empire_id not in self.server_state.all_empires:
            return

        empire = self.server_state.all_empires[empire_id]

        salvage_design = None
        for design in empire.designs.values():
            if self.SALVAGE_NAME in design.name:
                salvage_design = design
                break

        if salvage_design is None:
            return

        token = ShipToken(
            design_key=salvage_design.key,
            design_name=salvage_design.name,
            quantity=1,
            mass=salvage_design.mass
        )
        fleet = Fleet()
        fleet.key = empire.get_next_fleet_key()
        fleet.owner = empire_id
        fleet.position = NovaPoint(position.x, position.y)
        fleet.name = self.SALVAGE_NAME
        fleet.turn_year = empire.turn_year
        fleet.tokens[token.design_key] = token

        # Salvage includes cargo and resources
        fleet.cargo.ironium = int(salvage.ironium * 0.75)
        fleet.cargo.boranium = int(salvage.boranium * 0.75)
        fleet.cargo.germanium = int(salvage.germanium * 0.75)
        fleet.cargo.colonists = int(cargo.colonists * 0.75)

        empire.add_or_update_fleet(fleet)

    def _report_battle(self, battle: BattleReport) -> None:
        """
        Report the battle to the turn generator.

        Distribution to each participant's battle_reports (as dicts)
        happens in TurnGenerator._execute_battles; appending the raw
        BattleReport object here would break JSON persistence.
        """
        self.battles.append(battle)
