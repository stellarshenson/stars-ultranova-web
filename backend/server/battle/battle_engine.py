"""
Stars Nova Web - Battle Engine
Ported from ServerState/BattleEngine.cs (1001 lines)

Standard combat resolution system.
"""

import random
from dataclasses import dataclass, field
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
from .battle_plan import BattlePlan
from .stack import Stack, StackToken
from .weapon_details import WeaponDetails, TargetPercent
from .space_allocator import SpaceAllocator

if TYPE_CHECKING:
    from ..server_data import ServerData
    from ...core.data_structures import EmpireData
    from ...core.components import ShipDesign


# Movement table from BattleEngine.cs lines 44-73
# 9 rows (battle speed 0.5 to 2.5+) x 8 columns (round % 8)
# Round 8 moved to first position, we use battleRound % 8
MOVEMENT_TABLE = [
    [0, 1, 0, 1, 0, 1, 0, 1],  # 0.5
    [1, 1, 1, 0, 1, 1, 1, 0],  # 0.75
    [1, 1, 1, 1, 1, 1, 1, 1],  # 1.0
    [1, 2, 1, 1, 1, 2, 1, 1],  # 1.25
    [1, 2, 1, 2, 1, 2, 1, 2],  # 1.5
    [2, 2, 2, 1, 2, 2, 2, 1],  # 1.75
    [2, 2, 2, 2, 2, 2, 2, 2],  # 2.0
    [2, 3, 2, 2, 2, 3, 2, 2],  # 2.25
    [2, 3, 2, 3, 2, 3, 2, 3],  # 2.5+
]


class BattleEngine:
    """
    Standard battle engine for combat resolution.

    Ported from BattleEngine.cs.
    """

    MOVEMENT_PHASES_PER_ROUND = 3
    MAX_BATTLE_ROUNDS = 16
    SALVAGE_NAME = "S A L V A G E"

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
        self._random = random.Random()

    def run(self) -> None:
        """
        Process all fleet battles.

        Determines battle locations, builds stacks, and runs combat.
        """
        # Find co-located fleets
        potential_battles = self._determine_colocated_fleets()
        if not potential_battles:
            return

        # Filter to locations with multiple races
        engagements = self._eliminate_single_races(potential_battles)
        if not engagements:
            return

        # Process each battle
        for battling_fleets in engagements:
            battle = BattleReport()
            battling_stacks = self._generate_stacks(battling_fleets)

            # No targets means no battle
            if self._select_targets(battling_stacks) == 0:
                continue

            self.stack_id = 0
            sample = battling_fleets[0]

            if sample.in_orbit:
                battle.location = sample.in_orbit.name
            else:
                battle.location = f"coordinates {sample.position}"

            self._position_stacks(battling_stacks, battle)

            # Copy stacks for battle report
            for stack in battling_stacks:
                battle.stacks[stack.key] = Stack.copy(stack)

            self._do_battle(battling_stacks, battle)
            self._report_battle(battle)

    def _determine_colocated_fleets(self) -> List[List[Fleet]]:
        """Find all groups of fleets at the same position."""
        all_colocated: List[List[Fleet]] = []
        fleet_done: Dict[int, bool] = {}

        for fleet_a in self.server_state.iterate_all_fleets():
            if fleet_a.name == self.SALVAGE_NAME:
                fleet_done[fleet_a.key] = True
            if fleet_a.key in fleet_done:
                continue

            colocated: List[Fleet] = []
            for fleet_b in self.server_state.iterate_all_fleets():
                if fleet_b.name == self.SALVAGE_NAME:
                    continue
                if fleet_b.position != fleet_a.position:
                    continue

                colocated.append(fleet_b)
                fleet_done[fleet_b.key] = True

            if len(colocated) > 1:
                all_colocated.append(colocated)

        return all_colocated

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

        # Get designs from empire if available
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

    def _generate_stacks(self, colocated_fleets: List[Fleet]) -> List[Stack]:
        """Generate all battle stacks from co-located fleets."""
        battling_stacks: List[Stack] = []

        for fleet in colocated_fleets:
            if fleet.tokens:
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
        allocator.allocate_space(10)  # Standard Stars! battle board size
        battle.space_size = space_size

        # Allocate position for each race
        for index, empire_id in enumerate(empires.values()):
            box = allocator.get_box(index, len(empires))
            position = (
                box.x + (box.width // 2),
                box.y + (box.height // 2)
            )
            race_positions[empire_id] = position
            battle.losses[empire_id] = 0

        # Place stacks at their race positions
        for stack in battling_stacks:
            pos = race_positions[stack.owner]
            stack.position = NovaPoint(pos[0], pos[1])

        # Update enemy ship designs in intel
        self._update_intel_designs(battling_stacks, empires)

    def _update_intel_designs(
        self, battling_stacks: List[Stack], empires: Dict[int, int]
    ) -> None:
        """Update known enemy ship designs after battle."""
        for empire_id in empires.values():
            if empire_id not in self.server_state.all_empires:
                continue
            empire = self.server_state.all_empires[empire_id]

            for stack in battling_stacks:
                if stack.owner == empire_id:
                    continue
                if stack.owner not in empire.empire_reports:
                    continue
                if not stack.token or not stack.token.design:
                    continue

                report = empire.empire_reports[stack.owner]
                design = stack.token.design
                report.designs[design.key] = design

    def _do_battle(
        self, battling_stacks: List[Stack], battle: BattleReport
    ) -> None:
        """Execute the battle until resolved or max rounds."""
        for self.battle_round in range(1, self.MAX_BATTLE_ROUNDS + 1):
            if self._select_targets(battling_stacks) == 0:
                break

            self._move_stacks(battling_stacks, self.battle_round, battle)
            all_attacks = self._generate_attacks(battling_stacks)

            for attack in all_attacks:
                self._process_attack(attack, battle)

    def _select_targets(self, battling_stacks: List[Stack]) -> int:
        """Select targets for all armed stacks."""
        number_of_targets = 0

        for wolf in battling_stacks:
            if not wolf.composition:
                continue

            wolf.target = None

            if not wolf.is_armed:
                continue

            max_attractiveness = 0.0

            for lamb in battling_stacks:
                if not lamb.composition:
                    continue

                if self._are_enemies(wolf, lamb):
                    attractiveness = self._get_attractiveness(lamb)
                    if attractiveness > max_attractiveness:
                        wolf.target = lamb
                        max_attractiveness = attractiveness

            if wolf.target is not None:
                number_of_targets += 1

        return number_of_targets

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

        # Get battle plan
        plan = wolf_data.battle_plans.get(wolf.battle_plan, BattlePlan())

        if plan.attack == "Everyone":
            return True
        elif plan.target_id == lamb.owner:
            return True
        elif plan.attack == "Enemies":
            # Check relation
            if lamb.owner in wolf_data.empire_reports:
                relation = wolf_data.empire_reports[lamb.owner].relation
                if relation == "Enemy":
                    return True

        return False

    def _move_stacks(
        self,
        battling_stacks: List[Stack],
        battle_round: int,
        battle: BattleReport
    ) -> None:
        """Move stacks toward their targets."""
        for phase in range(1, self.MOVEMENT_PHASES_PER_ROUND + 1):
            for stack in battling_stacks:
                if stack is None or not stack.composition:
                    continue

                # Record position
                step = BattleStepMovement()
                step.stack_key = stack.key
                step.position = NovaPoint(stack.position.x, stack.position.y)
                battle.steps.append(step)

                if stack.target is None or stack.is_starbase:
                    continue

                from_pos = stack.position
                to_pos = stack.target.position

                # Determine moves this round based on battle speed
                moves_this_round = self._get_moves_for_speed(
                    stack.battle_speed, battle_round
                )

                # Check if should move this phase
                move_this_phase = False
                if phase == 1:
                    move_this_phase = moves_this_round == 3
                elif phase == 2:
                    move_this_phase = moves_this_round >= 2
                elif phase == 3:
                    move_this_phase = moves_this_round >= 1

                if move_this_phase:
                    stack.position = self._battle_move_to(from_pos, to_pos)

                    # Record movement
                    report = BattleStepMovement()
                    report.stack_key = stack.key
                    report.position = NovaPoint(
                        stack.position.x, stack.position.y
                    )
                    battle.steps.append(report)

    def _get_moves_for_speed(self, battle_speed: float, battle_round: int) -> int:
        """Get moves this round from the movement table."""
        round_index = battle_round % 8

        if battle_speed <= 0.5:
            return MOVEMENT_TABLE[0][round_index]
        elif battle_speed <= 0.75:
            return MOVEMENT_TABLE[1][round_index]
        elif battle_speed <= 1.0:
            return MOVEMENT_TABLE[2][round_index]
        elif battle_speed <= 1.25:
            return MOVEMENT_TABLE[3][round_index]
        elif battle_speed <= 1.5:
            return MOVEMENT_TABLE[4][round_index]
        elif battle_speed <= 1.75:
            return MOVEMENT_TABLE[5][round_index]
        elif battle_speed <= 2.0:
            return MOVEMENT_TABLE[6][round_index]
        elif battle_speed <= 2.25:
            return MOVEMENT_TABLE[7][round_index]
        else:
            return MOVEMENT_TABLE[8][round_index]

    def _battle_move_to(self, from_pos: NovaPoint, to_pos: NovaPoint) -> NovaPoint:
        """Move one step toward target position."""
        dx = to_pos.x - from_pos.x
        dy = to_pos.y - from_pos.y

        # Normalize to single step
        new_x = from_pos.x
        new_y = from_pos.y

        if dx != 0:
            new_x += 1 if dx > 0 else -1
        if dy != 0:
            new_y += 1 if dy > 0 else -1

        return NovaPoint(new_x, new_y)

    def _generate_attacks(self, battling_stacks: List[Stack]) -> List[WeaponDetails]:
        """Generate all weapon attacks for this round."""
        all_attacks: List[WeaponDetails] = []

        for stack in battling_stacks:
            if stack.is_destroyed:
                continue

            # Get weapons from design if available
            if stack.token and stack.token.design:
                for weapon in stack.token.design.weapons:
                    attack = WeaponDetails()
                    attack.source_stack = stack
                    attack.target_stack = TargetPercent(
                        target=stack.target, percent_to_fire=100
                    )
                    attack.weapon = weapon
                    all_attacks.append(attack)

        # Sort by initiative
        all_attacks.sort()
        return all_attacks

    def _process_attack(
        self, attack: WeaponDetails, battle: BattleReport
    ) -> bool:
        """Attempt a weapon attack."""
        if attack.target_stack.target is None:
            return False
        if attack.target_stack.target.is_destroyed:
            return False
        if attack.source_stack is None or attack.source_stack.is_destroyed:
            return False

        # Check range
        distance = attack.source_stack.position.distance_to(
            attack.target_stack.target.position
        )
        if attack.weapon and distance > attack.weapon.range:
            return False

        self._execute_attack(attack, battle)
        return True

    def _execute_attack(
        self, attack: WeaponDetails, battle: BattleReport
    ) -> None:
        """Execute a weapon attack."""
        attacker = attack.source_stack
        target = attack.target_stack.target

        # Report targeting
        report = BattleStepTarget()
        report.stack_key = attacker.key
        report.target_key = target.key
        battle.steps.append(report)

        if attack.weapon is None:
            return

        # Calculate power and accuracy
        hit_power = self._calculate_weapon_power(attack)
        accuracy = self._calculate_weapon_accuracy(attack)

        if attack.weapon.is_missile:
            self._fire_missile(attacker, target, hit_power, accuracy, battle)
        else:
            self._fire_beam(attacker, target, hit_power, battle)

        # Check if destroyed
        if target.token and target.token.armor <= 0:
            self._destroy_stack(attacker, target, battle)

    def _calculate_weapon_power(self, attack: WeaponDetails) -> float:
        """Calculate weapon damage output."""
        if attack.weapon is None:
            return 0.0
        return float(attack.weapon.power)

    def _calculate_weapon_accuracy(self, attack: WeaponDetails) -> float:
        """Calculate weapon accuracy (missiles)."""
        if attack.weapon is None:
            return 100.0
        return float(attack.weapon.accuracy)

    def _fire_beam(
        self,
        attacker: Stack,
        target: Stack,
        hit_power: float,
        battle: BattleReport
    ) -> None:
        """Fire a beam weapon."""
        # Damage shields first
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
        """Fire a missile weapon."""
        probability = self._random.randint(0, 100)

        if accuracy >= probability:
            # Hit
            shields_hit = hit_power / 2
            armor_hit = (hit_power / 2) + self._damage_shields(
                attacker, target, shields_hit, battle
            )
            self._damage_armor(attacker, target, armor_hit, battle)
        else:
            # Miss - minimum damage
            min_damage = hit_power / 8
            self._damage_shields(attacker, target, min_damage, battle)

    def _damage_shields(
        self,
        attacker: Stack,
        target: Stack,
        hit_power: float,
        battle: BattleReport
    ) -> float:
        """Apply damage to shields, return remaining power."""
        if target.token is None or target.token.shields <= 0:
            return hit_power

        initial_shields = target.token.shields
        target.token.shields -= hit_power

        if target.token.shields < 0:
            target.token.shields = 0

        damage_done = initial_shields - target.token.shields
        remaining_power = hit_power - damage_done

        # Report
        step = BattleStepWeapons()
        step.damage = damage_done
        step.targeting = TokenDefence.SHIELDS
        step.weapon_target = WeaponTarget(
            stack_key=attacker.key, target_key=target.key
        )
        battle.steps.append(step)

        return remaining_power

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

        # Report
        step = BattleStepWeapons()
        step.damage = hit_power
        step.targeting = TokenDefence.ARMOR
        step.weapon_target = WeaponTarget(
            stack_key=attacker.key, target_key=target.key
        )
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

        # Report losses
        battle.losses[target.owner] = (
            battle.losses.get(target.owner, 0) + target.token.quantity
        )

        # Report destruction
        destroy = BattleStepDestroy()
        destroy.stack_key = target.key
        battle.steps.append(destroy)

        # Remove from empire's fleet
        if target.owner in self.server_state.all_empires:
            empire = self.server_state.all_empires[target.owner]
            if target.parent_key in empire.owned_fleets:
                fleet = empire.owned_fleets[target.parent_key]
                if target.token.design_key in fleet.tokens:
                    del fleet.tokens[target.token.design_key]

                # Create salvage or add to planet
                star = self._find_star_at_position(target.position)
                if star:
                    # Add resources to planet
                    cost = target.total_cost
                    star.resources_on_hand.ironium += int(0.9 * cost.ironium)
                    star.resources_on_hand.boranium += int(0.9 * cost.boranium)
                    star.resources_on_hand.germanium += int(0.9 * cost.germanium)
                else:
                    # Create salvage fleet
                    self._create_salvage(
                        target.position, target.total_cost, target.cargo, target.owner
                    )

                # Remove fleet if empty
                if not fleet.tokens:
                    del empire.owned_fleets[target.parent_key]
                    if target.parent_key in empire.fleet_reports:
                        del empire.fleet_reports[target.parent_key]

        # Clear composition to mark as destroyed
        target.token = None

    def _find_star_at_position(self, position: NovaPoint) -> Optional['Star']:
        """Find a star at the given position."""
        for star in self.server_state.all_stars.values():
            dist_sq = star.position.distance_to_squared(position)
            if dist_sq < 2.0:  # sqrt(2) ~= 1.414
                return star
        return None

    def _create_salvage(
        self,
        position: NovaPoint,
        salvage: Resources,
        cargo: Cargo,
        empire_id: int
    ) -> None:
        """Create a salvage fleet from destroyed ships."""
        if empire_id not in self.server_state.all_empires:
            return

        empire = self.server_state.all_empires[empire_id]

        # Find salvage design
        salvage_design = None
        for design in empire.designs.values():
            if self.SALVAGE_NAME in design.name:
                salvage_design = design
                break

        if salvage_design is None:
            return

        # Create salvage token and fleet
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

        # Add salvage cargo
        fleet.cargo.ironium = int(salvage.ironium * 0.75)
        fleet.cargo.boranium = int(salvage.boranium * 0.75)
        fleet.cargo.germanium = int(salvage.germanium * 0.75)

        # Add to empire
        empire.add_or_update_fleet(fleet)

    def _report_battle(self, battle: BattleReport) -> None:
        """Report battle results to all participants."""
        for empire_id in battle.losses:
            if empire_id not in self.server_state.all_empires:
                continue

            empire = self.server_state.all_empires[empire_id]
            loss_count = battle.losses[empire_id]

            # Create message
            text = f"There was a battle at {battle.location}\n"
            if loss_count == 0:
                text += "None of your ships were destroyed"
            else:
                text += f"{loss_count} of your ships were destroyed"

            # Add to empire's battle reports
            empire.battle_reports.append(battle)

            # Add to main battle list
            self.battles.append(battle)
