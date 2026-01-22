"""
Stars Nova Web - Turn Generator
Ported from ServerState/TurnGenerator.cs (749 lines)

Processes a new turn by reading player orders, applying them,
and generating the new game state.
"""

import random
import math
from typing import List, Dict, Optional, TYPE_CHECKING
from collections import OrderedDict

from .turn_steps import (
    ITurnStep,
    FirstStep,
    ScanStep,
    BombingStep,
    PostBombingStep,
    StarUpdateStep,
    SplitFleetStep,
    ScrapFleetStep
)
from ..core.commands.base import Message
from ..core.globals import NOBODY
from ..core.waypoints.waypoint import WaypointTask, get_task_type, Waypoint, NoTaskObj

if TYPE_CHECKING:
    from .server_data import ServerData
    from ..core.game_objects.fleet import Fleet
    from ..core.race.race import Race


# Turn step ordering constants (from TurnGenerator.cs)
FIRST_STEP = 0
STAR_STEP = 12
BOMBING_STEP = 19
COLONISE_STEP = 92
SCAN_STEP = 99


class TurnGenerator:
    """
    Processes turn generation.

    Turn sequence (must match C# exactly):
    1. Read player orders
    2. Parse commands (waypoint 0)
    3. Split/merge fleets
    4. Lay mines
    5. Scrap fleets
    6. Move fleets
    7. Check minefields
    8. Resolve battles
    9. Victory check
    10. Increment turn year
    11. Run turn steps (star update, bombing, colonize, scan)
    12. Move mineral packets
    13. Update minefield visibility
    14. Generate intel

    Ported from TurnGenerator.cs.
    """

    def __init__(self, server_state: 'ServerData'):
        """
        Initialize turn generator.

        Args:
            server_state: The game state to process.
        """
        self.server_state = server_state
        self.rand = random.Random()

        # Turn steps ordered by priority
        self.turn_steps: Dict[int, ITurnStep] = OrderedDict()
        self.turn_steps[STAR_STEP] = StarUpdateStep()
        self.turn_steps[BOMBING_STEP] = BombingStep()
        self.turn_steps[COLONISE_STEP] = PostBombingStep()
        self.turn_steps[SCAN_STEP] = ScanStep()

    def generate(self):
        """
        Generate a new turn.

        Reads player orders, processes the turn sequence,
        and updates the game state for the new year.
        """
        # Parse and apply commands
        self._parse_commands()

        # Process waypoint zero actions
        messages = SplitFleetStep().process(self.server_state)
        self.server_state.all_messages.extend(messages)

        # Lay mines
        messages = FirstStep().process(self.server_state)
        self.server_state.all_messages.extend(messages)

        # Scrap fleets
        messages = ScrapFleetStep().process(self.server_state)
        self.server_state.all_messages.extend(messages)

        # Move fleets
        destroyed_fleets: List['Fleet'] = []
        for fleet in list(self.server_state.iterate_all_fleets()):
            if fleet.name == "Mineral Packet":
                continue
            if getattr(fleet, 'is_starbase', False):
                continue

            if self._process_fleet(fleet):
                destroyed_fleets.append(fleet)

        # Check for minefields
        for fleet_key in list(self.server_state.iterate_all_fleet_keys()):
            empire_id = fleet_key >> 32
            if empire_id in self.server_state.all_empires:
                fleet = self.server_state.all_empires[empire_id].owned_fleets.get(fleet_key)
                if fleet is not None and fleet.name != "Mineral Packet":
                    self._check_minefield(fleet)

        self.server_state.cleanup_fleets()

        # Clear old battle reports
        for empire in self.server_state.all_empires.values():
            if hasattr(empire, 'battle_reports'):
                empire.battle_reports.clear()

        # Run battle engine
        if self.server_state.use_ron_battle_engine:
            self._run_ron_battle_engine()
        else:
            self._run_battle_engine()

        self.server_state.cleanup_fleets()

        # Victory check
        self._victory_check()

        # Increment turn year
        self.server_state.turn_year += 1

        for empire in self.server_state.all_empires.values():
            empire.turn_year = self.server_state.turn_year
            empire.turn_submitted = False

        # Run turn steps in priority order
        for step in self.turn_steps.values():
            messages = step.process(self.server_state)
            if messages:
                self.server_state.all_messages.extend(messages)

        # Move mineral packets
        self._move_mineral_packets()

        self.server_state.cleanup_fleets()

        # Update minefield visibility
        self._update_minefield_visibility()

    def assemble_empire_data(self):
        """
        Utility function to set intel for the first turn.
        """
        messages = FirstStep().process(self.server_state)
        self.server_state.all_messages.extend(messages)

        messages = ScanStep().process(self.server_state)
        self.server_state.all_messages.extend(messages)

    def _parse_commands(self):
        """
        Validate and apply all commands sent by clients.
        """
        for empire in self.server_state.all_empires.values():
            if empire.id not in self.server_state.all_commands:
                continue

            command_stack = self.server_state.all_commands[empire.id]

            while command_stack:
                command = command_stack.pop()

                valid, message = command.is_valid(empire)

                if valid:
                    if message is not None:
                        self.server_state.all_messages.append(message)

                    result = command.apply_to_state(empire)
                    if result is not None:
                        self.server_state.all_messages.append(result)
                else:
                    if message is not None:
                        self.server_state.all_messages.append(message)

                    error_msg = Message(
                        audience=empire.id,
                        text=f"Invalid {type(command).__name__} command for {empire.race.name if empire.race else 'Unknown'}",
                        message_type="Invalid Command"
                    )
                    self.server_state.all_messages.append(error_msg)

            self.server_state.cleanup_fleets()

            # Sync owned stars with all_stars
            for star in empire.owned_stars.values():
                self.server_state.all_stars[star.name] = star

    def _process_fleet(self, fleet: 'Fleet') -> bool:
        """
        Process the elapse of one year for a fleet.

        Args:
            fleet: The fleet to process.

        Returns:
            True if the fleet was destroyed.
        """
        if fleet is None:
            return True

        # Update fleet (movement)
        destroyed = self._update_fleet(fleet)

        if destroyed:
            return True

        # Refuel and repair
        self._regenerate_fleet(fleet)

        return False

    def _update_fleet(self, fleet: 'Fleet') -> bool:
        """
        Update fleet position and handle waypoint movement.

        Args:
            fleet: The fleet to update.

        Returns:
            True if destroyed.
        """
        if len(fleet.waypoints) == 0:
            return False

        empire = self.server_state.all_empires.get(fleet.owner)
        if empire is None:
            return False

        race = empire.race

        # Get current position waypoint
        first_waypoint = fleet.waypoints[0]

        # Remove useless waypoints at start (same position, no task)
        while (len(fleet.waypoints) > 0 and
               get_task_type(fleet.waypoints[0].task) == WaypointTask.NO_TASK and
               self._same_position(fleet.position, fleet.waypoints[0])):
            fleet.waypoints.pop(0)

        if len(fleet.waypoints) == 0:
            return False

        waypoint_zero = fleet.waypoints[0]

        # Check for Cheap Engines failure
        if race is not None and race.has_trait("CE"):
            if waypoint_zero.warp_factor > 6 and self.rand.randint(0, 9) == 0:
                # Engine failure
                msg = Message(
                    audience=fleet.owner,
                    text=f"Fleet {fleet.name}'s engines failed to start. "
                         "Fleet has not moved this turn.",
                    message_type="Cheap Engines",
                    fleet_key=fleet.key
                )
                self.server_state.all_messages.append(msg)
                return False

        # Calculate movement
        available_time = 1.0
        messages = []

        travel_status = self._move_fleet(fleet, available_time, race, messages)
        self.server_state.all_messages.extend(messages)

        if travel_status == "in_transit":
            # Still moving
            new_position = Waypoint(
                position_x=fleet.position.x,
                position_y=fleet.position.y,
                destination=f"Space at {fleet.position.x:.0f},{fleet.position.y:.0f}",
                task=NoTaskObj()
            )
            fleet.waypoints.insert(0, new_position)
            fleet.in_orbit = None
        else:
            # Arrived
            self.server_state.set_fleet_orbit(fleet)

            if fleet.in_orbit is not None:
                fleet.waypoints[0].position_x = fleet.in_orbit.position.x
                fleet.waypoints[0].position_y = fleet.in_orbit.position.y
                fleet.waypoints[0].destination = fleet.in_orbit.name

        # Update bearing for next waypoint
        if len(fleet.waypoints) > 1:
            next_wp = fleet.waypoints[1]
            dx = fleet.position.x - next_wp.position_x
            dy = fleet.position.y - next_wp.position_y
            fleet.bearing = math.degrees(math.atan2(dy, dx)) + 90

        return False

    def _move_fleet(self, fleet: 'Fleet', available_time: float,
                    race: Optional['Race'], messages: List[Message]) -> str:
        """
        Move fleet towards next waypoint.

        Args:
            fleet: Fleet to move.
            available_time: Time available for movement (1.0 = full turn).
            race: Fleet owner's race.
            messages: List to append messages to.

        Returns:
            Travel status: "arrived" or "in_transit".
        """
        if len(fleet.waypoints) == 0:
            return "arrived"

        waypoint = fleet.waypoints[0]
        target_x = waypoint.position_x
        target_y = waypoint.position_y

        # Calculate distance
        dx = target_x - fleet.position.x
        dy = target_y - fleet.position.y
        distance = math.sqrt(dx * dx + dy * dy)

        if distance < 0.01:
            return "arrived"

        # Calculate speed (warp factor squared = ly per turn)
        warp = waypoint.warp_factor
        speed = warp * warp  # ly per turn

        if speed <= 0:
            return "in_transit"

        # Calculate how far we can travel this turn
        travel_distance = speed * available_time

        if travel_distance >= distance:
            # Arrive at destination
            fleet.position.x = target_x
            fleet.position.y = target_y

            # Consume fuel
            self._consume_fuel(fleet, distance, warp)

            return "arrived"
        else:
            # Partial movement
            ratio = travel_distance / distance
            fleet.position.x += dx * ratio
            fleet.position.y += dy * ratio

            # Consume fuel
            self._consume_fuel(fleet, travel_distance, warp)

            return "in_transit"

    def _consume_fuel(self, fleet: 'Fleet', distance: float, warp: int):
        """
        Calculate and consume fuel for movement.

        Args:
            fleet: Moving fleet.
            distance: Distance traveled in light years.
            warp: Warp factor used.
        """
        # Fuel consumption depends on mass and engine efficiency
        # Simplified implementation
        mass = getattr(fleet, 'total_mass', 100)
        fuel_per_ly = mass * warp / 200  # Simplified fuel formula

        fuel_consumed = int(fuel_per_ly * distance)
        fleet.fuel_available = max(0, fleet.fuel_available - fuel_consumed)

    def _regenerate_fleet(self, fleet: 'Fleet'):
        """
        Refuel and repair fleet.

        Args:
            fleet: Fleet to regenerate.
        """
        if fleet is None:
            return

        star = fleet.in_orbit
        if star is not None:
            star = self.server_state.all_stars.get(star.name)

        # Refuel if at friendly starbase with dock
        if (star is not None and
                star.owner == fleet.owner and
                star.starbase is not None and
                getattr(star.starbase, 'can_refuel', False)):
            fleet.fuel_available = fleet.total_fuel_capacity

        # Repair
        repair_rate = self._get_repair_rate(fleet, star)

        for token in fleet.composition.values():
            # Restore shields fully
            if token.design is not None:
                token.shields = token.design.shield * token.quantity

                # Repair armor
                if repair_rate > 0:
                    max_armor = token.design.armor * token.quantity
                    repair_amount = max(max_armor * repair_rate // 100, 1)
                    token.armor = min(token.armor + repair_amount, max_armor)

    def _get_repair_rate(self, fleet: 'Fleet', star) -> int:
        """
        Get repair rate based on location.

        Args:
            fleet: Fleet to check.
            star: Star fleet is orbiting (or None).

        Returns:
            Repair rate percentage.
        """
        if star is not None:
            if star.owner == fleet.owner:
                if star.starbase is not None:
                    if getattr(star.starbase, 'can_refuel', False):
                        return 20  # Orbiting own planet with dock
                    return 8  # Orbiting own planet with starbase but no dock
                return 5  # Orbiting own planet, no starbase
            return 3  # Orbiting enemy planet
        else:
            if len(fleet.waypoints) == 0:
                return 2  # Stopped in space
            return 1  # Moving through space

    def _same_position(self, pos1, waypoint) -> bool:
        """Check if position matches waypoint position."""
        return (abs(pos1.x - waypoint.position_x) < 0.01 and
                abs(pos1.y - waypoint.position_y) < 0.01)

    def _check_minefield(self, fleet: 'Fleet'):
        """
        Check if fleet hits a minefield.

        Args:
            fleet: Fleet to check.
        """
        # Simplified - actual implementation checks movement path
        for minefield in self.server_state.all_minefields.values():
            if minefield.owner == fleet.owner:
                continue

            # Check if fleet is inside minefield
            dx = fleet.position.x - minefield.position_x
            dy = fleet.position.y - minefield.position_y
            distance = math.sqrt(dx * dx + dy * dy)

            if distance < minefield.radius:
                # Hit minefield - calculate damage
                hit_chance = 0.003  # 0.3% per ly per warp factor
                # Actual formula is more complex
                if self.rand.random() < hit_chance * minefield.radius:
                    msg = Message(
                        audience=fleet.owner,
                        text=f"{fleet.name} has hit a minefield!",
                        message_type="Minefield Hit",
                        fleet_key=fleet.key
                    )
                    self.server_state.all_messages.append(msg)
                    # TODO: Apply damage

    def _run_battle_engine(self):
        """Run standard battle engine."""
        # Simplified - actual implementation in BattleEngine class
        pass

    def _run_ron_battle_engine(self):
        """Run Ron's battle engine variant."""
        # Simplified - actual implementation in RonBattleEngine class
        pass

    def _victory_check(self):
        """Check for victory conditions."""
        # Simplified - actual implementation checks various conditions
        pass

    def _move_mineral_packets(self):
        """Move mineral packets after they are created."""
        exploded_packets: List['Fleet'] = []

        for fleet in self.server_state.iterate_all_fleets():
            if "Mineral Packet" not in fleet.name:
                continue

            # Move packet
            self._process_fleet(fleet)
            self.server_state.set_fleet_orbit(fleet)

            if fleet.in_orbit is not None:
                # Packet arrived - destroy population
                star = fleet.in_orbit
                msg1 = Message(
                    audience=fleet.owner,
                    text=f"Your Mineral Packet destroyed 3/4 of the population of {star.name}",
                    message_type="Star",
                    fleet_key=fleet.key
                )
                self.server_state.all_messages.append(msg1)

                if star.owner != NOBODY:
                    msg2 = Message(
                        audience=star.owner,
                        text=f"A Mineral Packet destroyed 3/4 of your population on {star.name}",
                        message_type="Star"
                    )
                    self.server_state.all_messages.append(msg2)

                star.colonists = star.colonists // 4
                exploded_packets.append(fleet)
            else:
                # Erode packet in space (5% loss)
                if hasattr(fleet.cargo, 'scale'):
                    fleet.cargo.scale(0.95)

            # Update fleet report
            empire = self.server_state.all_empires.get(fleet.owner)
            if empire is not None and fleet.key in empire.fleet_reports:
                empire.fleet_reports[fleet.key] = {
                    "key": fleet.key,
                    "name": fleet.name,
                    "position_x": fleet.position.x,
                    "position_y": fleet.position.y,
                    "year": self.server_state.turn_year
                }

        # Remove exploded packets
        for packet in exploded_packets:
            for empire in self.server_state.all_empires.values():
                if packet.key in empire.fleet_reports:
                    del empire.fleet_reports[packet.key]

            empire = self.server_state.all_empires.get(packet.owner)
            if empire is not None and packet.key in empire.owned_fleets:
                del empire.owned_fleets[packet.key]

    def _update_minefield_visibility(self):
        """Update which minefields are visible to each empire."""
        for empire in self.server_state.all_empires.values():
            empire.visible_minefields = {}

            # Own minefields are always visible
            for minefield in self.server_state.all_minefields.values():
                if minefield.owner == empire.id:
                    empire.visible_minefields[minefield.key] = minefield

            # Minefields within scan range
            for fleet in empire.owned_fleets.values():
                scan_range = 0
                for token in fleet.composition.values():
                    if token.design is not None:
                        scan_range = max(scan_range,
                                         getattr(token.design, 'scan_range', 0))

                for minefield in self.server_state.all_minefields.values():
                    dx = fleet.position.x - minefield.position_x
                    dy = fleet.position.y - minefield.position_y
                    distance = math.sqrt(dx * dx + dy * dy)

                    if distance <= scan_range + minefield.radius:
                        empire.visible_minefields[minefield.key] = minefield

            # Minefields within planetary scan range
            for star in empire.owned_stars.values():
                scan_range = getattr(star, 'scan_range', 0)

                for minefield in self.server_state.all_minefields.values():
                    dx = star.position.x - minefield.position_x
                    dy = star.position.y - minefield.position_y
                    distance = math.sqrt(dx * dx + dy * dy)

                    if distance <= scan_range + minefield.radius:
                        empire.visible_minefields[minefield.key] = minefield
