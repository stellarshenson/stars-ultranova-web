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

from ...core.data_structures import NovaPoint, Resources, Cargo
from ...core.game_objects import Fleet, ShipToken
from ...core.globals import MAX_WEAPON_RANGE

from .battle_step import (
    BattleStepMovement,
    BattleStepTarget,
    BattleStepWeapons,
    BattleStepDestroy,
    WeaponTarget,
    TokenDefence,
)
from .battle_report import BattleReport
from .battle_plan import BattlePlan, Victims
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

        self._update_intel_designs(battling_stacks, empires)

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

    def _select_targets(self, battling_stacks: List[Stack]) -> int:
        """Select targets using priority-based system."""
        number_of_targets = 0

        for wolf in battling_stacks:
            if wolf.token is None or wolf.token.quantity <= 0:
                continue

            wolf.target = None
            wolf.target_list = []

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
        """Check if target matches the given priority type."""
        if target.is_starbase and priority == Victims.STARBASE:
            return True
        if target.has_bombers and priority == Victims.BOMBER:
            return True

        # Check power rating for capital vs escort
        power_rating = 0
        if target.token and target.token.design:
            power_rating = target.token.design.power_rating

        if power_rating > 2000 and target.is_armed:
            if priority == Victims.CAPITAL_SHIP:
                return True
        elif power_rating <= 2000 and target.is_armed:
            if priority == Victims.ESCORT:
                return True

        if target.is_armed and priority == Victims.ARMED_SHIP:
            return True
        if priority == Victims.ANY_SHIP:
            return True
        if not target.is_armed and priority == Victims.SUPPORT_SHIP:
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
        """Move stacks using Ron's improved movement system."""
        for stack in battling_stacks:
            if stack is None or stack.token is None or stack.token.quantity <= 0:
                continue

            if stack.target is None or stack.is_starbase:
                continue

            vector_to_target = NovaPoint(
                stack.target.position.x - stack.position.x,
                stack.target.position.y - stack.position.y
            )

            # Calculate heading
            new_heading = self._battle_speed_vector(
                vector_to_target,
                stack.battle_speed * self.GRID_SCALE
            )

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
                        new_heading = NovaPoint(-new_heading.x, -new_heading.y)
                elif tactic == "Disengage":
                    # Unarmed disengaging stack flees the board instead
                    # of merely keeping out of weapon range
                    new_heading = NovaPoint(-new_heading.x, -new_heading.y)
                    self._count_flee_move(stack)
                elif stack.distance_to(stack.target) / self.GRID_SCALE < MAX_WEAPON_RANGE:
                    # Run away from armed enemy
                    new_heading = NovaPoint(-new_heading.x, -new_heading.y)
                else:
                    new_heading = NovaPoint(0, 0)
            elif tactic == "Disengage":
                # Armed disengaging stack flees its target
                new_heading = NovaPoint(-new_heading.x, -new_heading.y)
                self._count_flee_move(stack)
            elif tactic in ("Minimise Damage to Self", "Maximise Damage Ratio",
                            "Maximise Net Damage"):
                # Stand-off tactics: close only until the target is
                # inside our own longest weapon range, then hold;
                # "Minimise Damage to Self" additionally falls back
                # while its shields are down. Canonical-approx
                # heuristics - the exact Stars! math is unpublished and
                # the C# reference has no implementation.
                weapon_range = 0
                if stack.token.design is not None:
                    weapon_range = max(
                        (w.range for w in stack.token.design.weapons),
                        default=0)
                if (tactic == "Minimise Damage to Self"
                        and stack.token.shields <= 0):
                    new_heading = NovaPoint(-new_heading.x, -new_heading.y)
                elif (stack.distance_to(stack.target)
                        <= weapon_range * self.GRID_SCALE):
                    new_heading = NovaPoint(0, 0)
            # "Maximise Damage" (default) keeps the closing heading

            # Initialize velocity if needed
            if stack.velocity_vector is None:
                stack.velocity_vector = new_heading

            # Update position
            stack.position = NovaPoint(
                stack.position.x + new_heading.x,
                stack.position.y + new_heading.y
            )

            # Record movement if significant
            if new_heading.x != 0 or new_heading.y != 0 or battle_round < 5:
                report = BattleStepMovement()
                report.stack_key = stack.key
                report.position = NovaPoint(stack.position.x, stack.position.y)
                battle.steps.append(report)

    def _effective_tactic(self, stack: Stack) -> str:
        """
        Resolve the stack's plan tactic for this round.

        "Disengage if Challenged" behaves as Maximise Damage until the
        stack has taken damage, then switches to Disengage (canonical
        Stars! rule; C# absent).
        """
        if stack.owner not in self.server_state.all_empires:
            return "Maximise Damage"
        empire = self.server_state.all_empires[stack.owner]
        plan = empire.battle_plans.get(stack.battle_plan)
        if plan is None:
            return "Maximise Damage"
        if plan.tactic == "Disengage if Challenged":
            return "Disengage" if stack.damage_taken else "Maximise Damage"
        return plan.tactic

    def _count_flee_move(self, stack: Stack) -> None:
        """
        Count a flee move; after DISENGAGE_MOVES the stack has left.

        Canonical Stars!: 7 squares of battle board movement to leave
        the battle; one flee move per round at battle speed
        approximates one square per round (canonical-approx). While
        still present the stack can be fired upon.
        """
        stack.flee_rounds += 1
        if stack.flee_rounds >= self.DISENGAGE_MOVES:
            stack.disengaged = True

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

        for stack in battling_stacks:
            if stack.is_destroyed:
                continue
            # A disengaged stack has left the battle and fires nothing
            if stack.disengaged:
                continue
            if not stack.token or not stack.token.design:
                continue

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
                    range_sq = weapon.range ** 2 * self.GRID_SCALE_SQUARED

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
                        all_attacks.append(attack)

                        percent_fired += percent_to_fire

                    target_index += 1

        all_attacks.sort()
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
        battle.steps.append(report)

        if attack.weapon is None:
            return

        percent = attack.target_stack.percent_to_fire / 100.0
        hit_power = attack.weapon.power * attacker.token.quantity * percent

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
            self._fire_missile(attacker, target, hit_power, accuracy, battle)
        else:
            # Capacitors boost / deflectors cut beam damage (canonical
            # Stars! rule; C# stub at BattleEngine.cs:880-908)
            hit_power *= attack.beam_power_modifier(
                source_design, target_design)
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
        # Scale down damage (10 rounds per turn)
        hit_power = hit_power / 10

        # Random accuracy variation
        probability = self._random.randint(-50, 50)
        percent_hit = accuracy + (probability / 100.0) * accuracy / 2.0
        percent_hit = max(0.0, min(1.0, percent_hit))

        # Misses do splash damage
        miss_damage = hit_power * (1 - percent_hit) / 8
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
