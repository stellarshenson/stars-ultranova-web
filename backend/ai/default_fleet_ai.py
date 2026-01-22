"""
Stars Nova Web - Default Fleet AI
Ported from Nova/Ai/DefaultFleetAI.cs (399 lines)

AI sub-component to manage a fleet.
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, TYPE_CHECKING

from ..core.commands.base import CommandMode
from ..core.commands.waypoint import WaypointCommand
from ..core.waypoints.waypoint import (
    Waypoint, NoTaskObj, ColoniseTaskObj, CargoTaskObj, CargoMode
)
from ..core.data_structures import NovaPoint, Cargo
from ..core import globals as g

if TYPE_CHECKING:
    from ..core.data_structures.empire_data import EmpireData
    from ..core.game_objects.fleet import Fleet
    from ..core.commands.base import Command


@dataclass
class DefaultFleetAI:
    """
    AI sub-component to manage a fleet.

    Handles scouting, colonization, and general fleet movement.

    Ported from DefaultFleetAI.cs.
    """
    fleet: 'Fleet' = None
    empire_data: 'EmpireData' = None
    fuel_stations: Dict[int, 'Fleet'] = field(default_factory=dict)
    commands: List['Command'] = field(default_factory=list)

    def __init__(
        self,
        fleet: 'Fleet',
        empire_data: 'EmpireData',
        fuel_stations: Optional[Dict[int, 'Fleet']] = None
    ):
        """
        Initialize the fleet AI.

        Args:
            fleet: The fleet to manage
            empire_data: The empire data
            fuel_stations: Dict of fleets that can refuel (key -> Fleet)
        """
        self.fleet = fleet
        self.empire_data = empire_data
        self.fuel_stations = fuel_stations or {}
        self.commands = []

    def scout(self, excluded_stars: List[dict]) -> Optional[dict]:
        """
        Send fleet to scout unexplored stars.

        Args:
            excluded_stars: List of star reports to exclude from targeting

        Returns:
            Star report being scouted, or None if no mission accepted

        Ported from DefaultFleetAI.cs Scout().
        """
        mission_accepted = False

        # Find a star to scout
        star_to_scout = self._closest_star(excluded_stars)
        if star_to_scout is None:
            return None

        # Do we need fuel first?
        if self.fleet.free_warp_speed > 1 or self.fleet.fuel_available > 100:
            # Scout can make fuel or has plenty of fuel
            self._send_fleet_to_star(star_to_scout, NoTaskObj())
            mission_accepted = True
        else:
            # Scout can't make fuel efficiently
            fuel_required = 0.0
            nearest_fuel = self._closest_fuel()

            if not self.fleet.can_refuel:
                # Calculate fuel needed to scout and return to refuel
                if nearest_fuel is not None:
                    best_warp = self.fleet.slowest_engine
                    speed_squared = (best_warp ** 2) ** 2
                    race = self.empire_data.race
                    fuel_consumption = self.fleet.fuel_consumption(best_warp, race)

                    # Distance to star and back to fuel
                    star_pos = NovaPoint(
                        x=star_to_scout.get("position_x", 0),
                        y=star_to_scout.get("position_y", 0)
                    )
                    distance_squared = self._distance_squared(
                        self.fleet.position, star_pos
                    )
                    distance_squared += self._distance_squared(
                        star_pos, nearest_fuel.position
                    )
                    time = math.sqrt(distance_squared / speed_squared) if speed_squared > 0 else 0
                    fuel_required = time * fuel_consumption

            if self.fleet.fuel_available > fuel_required:
                # Fuel is no problem
                self.fleet.speed = self.fleet.slowest_engine
                self._send_fleet_to_star(star_to_scout, NoTaskObj())
                mission_accepted = True
            else:
                # Refuel before scouting further
                if nearest_fuel:
                    self._send_fleet_to_fleet(nearest_fuel, NoTaskObj())

        if mission_accepted:
            return star_to_scout
        return None

    def armed_scout(self, excluded_stars: List[dict]) -> Optional[dict]:
        """
        Send armed fleet to scout unexplored stars.

        Similar to scout but may reduce speed slightly for fuel efficiency.

        Args:
            excluded_stars: List of star reports to exclude from targeting

        Returns:
            Star report being scouted, or None if no mission accepted

        Ported from DefaultFleetAI.cs ArmedScout().
        """
        mission_accepted = False

        star_to_scout = self._closest_star(excluded_stars)
        if star_to_scout is None:
            return None

        if self.fleet.free_warp_speed > 1 or self.fleet.fuel_available > 100:
            self._send_fleet_to_star(star_to_scout, NoTaskObj())
            mission_accepted = True
        else:
            fuel_required = 0.0
            nearest_fuel = self._closest_fuel()

            if not self.fleet.can_refuel and nearest_fuel is not None:
                best_warp = self.fleet.slowest_engine
                speed_squared = (best_warp ** 2) ** 2
                race = self.empire_data.race
                fuel_consumption = self.fleet.fuel_consumption(best_warp, race)

                star_pos = NovaPoint(
                    x=star_to_scout.get("position_x", 0),
                    y=star_to_scout.get("position_y", 0)
                )
                distance_squared = self._distance_squared(
                    self.fleet.position, star_pos
                )
                distance_squared += self._distance_squared(
                    star_pos, nearest_fuel.position
                )
                time = math.sqrt(distance_squared / speed_squared) if speed_squared > 0 else 0
                fuel_required = time * fuel_consumption

            if self.fleet.fuel_available > fuel_required:
                self.fleet.speed = self.fleet.slowest_engine
                # Armed scouts may slow down slightly
                if self.fleet.speed > 1:
                    self.fleet.speed -= 1
                self._send_fleet_to_star(star_to_scout, NoTaskObj())
                mission_accepted = True
            else:
                if nearest_fuel:
                    self._send_fleet_to_fleet(nearest_fuel, NoTaskObj())

        if mission_accepted:
            return star_to_scout
        return None

    def colonise(self, target_star: dict):
        """
        Send fleet to colonize a planet.

        Will load colonists and germanium if at a friendly star without cargo.

        Args:
            target_star: Star report of the target to colonize

        Ported from DefaultFleetAI.cs Colonise().
        """
        # Ensure we have some colonists
        if self.fleet.cargo.colonists_in_kilotons < 10:
            if (self.fleet.in_orbit is not None and
                    self.fleet.in_orbit.owner == self.fleet.owner):
                # At one of our planets, beam up colonists
                our_star = self.fleet.in_orbit

                # How much germanium to load to seed factory production?
                # 1/4 of cargo capacity, but leave room for 100 kT colonists
                germanium_to_load = min(
                    self.fleet.total_cargo_capacity // 4,
                    self.fleet.total_cargo_capacity - 100
                )
                # But leave at least 50 G behind
                germanium_to_load = min(
                    germanium_to_load,
                    our_star.resources_on_hand.germanium - 50
                )
                germanium_to_load = max(germanium_to_load, 0)

                # How many colonists to load?
                colonists_to_load_kt = self.fleet.total_cargo_capacity - germanium_to_load
                # Don't take the star below 250,000 (max % growth)
                colonists_to_load_kt = min(
                    colonists_to_load_kt,
                    (our_star.colonists - 500000) // g.COLONISTS_PER_KILOTON
                )
                colonists_to_load_kt = max(
                    colonists_to_load_kt,
                    (our_star.colonists - 250000) // 2 // g.COLONISTS_PER_KILOTON
                )
                # Ensure at least 1 kT of colonists
                colonists_to_load_kt = max(colonists_to_load_kt, 1000)
                colonists_to_load_kt = min(
                    self.fleet.total_cargo_capacity - germanium_to_load,
                    colonists_to_load_kt
                )

                # Create cargo load waypoint
                cargo_task = CargoTaskObj(
                    mode=CargoMode.LOAD,
                    amount=Cargo(
                        germanium=germanium_to_load,
                        colonists_in_kilotons=colonists_to_load_kt
                    ),
                    target_name=our_star.name
                )

                load_wp = Waypoint(
                    position_x=our_star.position.x,
                    position_y=our_star.position.y,
                    warp_factor=self.fleet.slowest_engine,
                    destination=our_star.name,
                    task=cargo_task
                )

                load_command = WaypointCommand(
                    mode=CommandMode.ADD,
                    waypoint=load_wp,
                    fleet_key=self.fleet.key
                )
                valid, msg = load_command.is_valid(self.empire_data)
                if valid:
                    load_command.apply_to_state(self.empire_data)
                    self.commands.append(load_command)

                # Now send to colonize
                self._send_fleet_to_star(target_star, ColoniseTaskObj())
            else:
                # TODO: Go get some colonists first
                pass
        else:
            # Already has colonists
            self._send_fleet_to_star(target_star, ColoniseTaskObj())

    def can_reach(self, destination: dict) -> bool:
        """
        Check if fleet can reach a destination.

        Args:
            destination: Star report with position

        Returns:
            True if fleet has enough fuel

        Ported from DefaultFleetAI.cs canReach().
        """
        dest_pos = NovaPoint(
            x=destination.get("position_x", 0),
            y=destination.get("position_y", 0)
        )
        destination_distance = self._distance_to(self.fleet.position, dest_pos)
        years_of_travel = destination_distance / (self.fleet.slowest_engine ** 2) if self.fleet.slowest_engine > 0 else float('inf')
        race = self.empire_data.race
        fuel_required = self.fleet.fuel_consumption_when_full(
            self.fleet.slowest_engine, race
        ) * years_of_travel
        return self.fleet.fuel_available > fuel_required

    def max_distance(self) -> float:
        """
        Calculate maximum distance fleet can travel.

        Returns:
            Maximum distance in light years

        Ported from DefaultFleetAI.cs maxDistance().
        """
        if self.fleet.slowest_engine == 0:
            return 0.0
        distance_per_year = self.fleet.slowest_engine ** 2
        race = self.empire_data.race
        fuel_per_year = self.fleet.fuel_consumption_when_full(
            self.fleet.slowest_engine, race
        )
        if fuel_per_year <= 0:
            return float('inf')
        return self.fleet.fuel_available / fuel_per_year * distance_per_year

    def _closest_star(self, excluded_stars: List[dict]) -> Optional[dict]:
        """
        Find closest star not in excluded list.

        Args:
            excluded_stars: Stars to skip

        Returns:
            Closest star report or None

        Ported from DefaultFleetAI.cs ClosestStar().
        """
        target = None
        min_distance = float('inf')

        for star_name, report in self.empire_data.star_reports.items():
            if report in excluded_stars:
                continue

            star_pos = NovaPoint(
                x=report.get("position_x", 0),
                y=report.get("position_y", 0)
            )
            distance = self._distance_to(self.fleet.position, star_pos)
            if distance < min_distance:
                target = report
                min_distance = distance

        return target

    def _closest_fuel(self) -> Optional['Fleet']:
        """
        Find closest refueling point.

        Returns:
            Closest fleet that can refuel (usually a starbase)

        Ported from DefaultFleetAI.cs ClosestFuel().
        """
        if not self.fuel_stations:
            # Build fuel station list
            for fleet in self.empire_data.owned_fleets.values():
                if fleet.can_refuel:
                    self.fuel_stations[fleet.key] = fleet

        if not self.fuel_stations:
            return None

        closest = None
        min_dist_sq = float('inf')

        for pump in self.fuel_stations.values():
            dist_sq = self._distance_squared(self.fleet.position, pump.position)
            if dist_sq < min_dist_sq:
                min_dist_sq = dist_sq
                closest = pump

        return closest

    def _send_fleet_to_position(self, position: NovaPoint, task):
        """
        Send fleet to a position.

        Args:
            position: Target position
            task: Waypoint task to perform

        Ported from DefaultFleetAI.cs SendFleet(NovaPoint, ...).
        """
        wp = Waypoint(
            position_x=position.x,
            position_y=position.y,
            warp_factor=self.fleet.slowest_engine,
            destination=str(position),
            task=task
        )

        command = WaypointCommand(
            mode=CommandMode.ADD,
            waypoint=wp,
            fleet_key=self.fleet.key
        )
        valid, msg = command.is_valid(self.empire_data)
        if valid:
            command.apply_to_state(self.empire_data)
            self.commands.append(command)

    def _send_fleet_to_fleet(self, target: 'Fleet', task):
        """
        Send fleet to another fleet.

        Args:
            target: Target fleet
            task: Waypoint task to perform

        Ported from DefaultFleetAI.cs SendFleet(Fleet, ...).
        """
        wp = Waypoint(
            position_x=target.position.x,
            position_y=target.position.y,
            warp_factor=self.fleet.slowest_engine,
            destination=target.name,
            task=task
        )

        command = WaypointCommand(
            mode=CommandMode.ADD,
            waypoint=wp,
            fleet_key=self.fleet.key
        )
        valid, msg = command.is_valid(self.empire_data)
        if valid:
            command.apply_to_state(self.empire_data)
            self.commands.append(command)

    def _send_fleet_to_star(self, star_report: dict, task):
        """
        Send fleet to a star.

        Adjusts warp factor based on fuel generation capability.

        Args:
            star_report: Star intel report
            task: Waypoint task to perform

        Ported from DefaultFleetAI.cs SendFleet(StarIntel, ...).
        """
        star_pos = NovaPoint(
            x=star_report.get("position_x", 0),
            y=star_report.get("position_y", 0)
        )
        star_name = star_report.get("name", str(star_pos))

        # Adjust warp factor based on fuel situation
        warp = self.fleet.slowest_engine
        race = self.empire_data.race
        fuel_consumption = self.fleet.fuel_consumption(warp, race)

        if fuel_consumption < 0:
            # Making fuel
            fuel_ratio = self.fleet.total_fuel_capacity / max(1, self.fleet.fuel_available)
            if fuel_ratio < 3:
                # Plenty of fuel, go faster
                warp = min(warp + 1, 9)
            elif fuel_ratio >= 5:
                # Low on fuel, slow down to generate more
                warp = max(warp - 1, 1)

        wp = Waypoint(
            position_x=star_pos.x,
            position_y=star_pos.y,
            warp_factor=warp,
            destination=star_name,
            task=task
        )

        # Clear existing waypoints first
        self.fleet.waypoints.clear()

        command = WaypointCommand(
            mode=CommandMode.ADD,
            waypoint=wp,
            fleet_key=self.fleet.key
        )
        valid, msg = command.is_valid(self.empire_data)
        if valid:
            command.apply_to_state(self.empire_data)
            self.commands.append(command)

    @staticmethod
    def _distance_to(p1: NovaPoint, p2: NovaPoint) -> float:
        """Calculate distance between two points."""
        dx = p2.x - p1.x
        dy = p2.y - p1.y
        return math.sqrt(dx * dx + dy * dy)

    @staticmethod
    def _distance_squared(p1: NovaPoint, p2: NovaPoint) -> float:
        """Calculate squared distance between two points."""
        dx = p2.x - p1.x
        dy = p2.y - p1.y
        return dx * dx + dy * dy
