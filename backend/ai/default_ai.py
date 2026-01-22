"""
Stars Nova Web - Default AI
Ported from Nova/Ai/DefaultAi.cs (1143 lines)

Main AI orchestrator for computer opponents.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, TYPE_CHECKING

from .abstract_ai import AbstractAI
from .default_ai_planner import DefaultAIPlanner
from .default_planet_ai import DefaultPlanetAI
from .default_fleet_ai import DefaultFleetAI
from ..core.commands.base import CommandMode
from ..core.commands.research import ResearchCommand
from ..core.data_structures import NovaPoint
from ..core.data_structures.tech_level import TechLevel
from ..core import globals as g

if TYPE_CHECKING:
    from ..core.data_structures.empire_data import EmpireData
    from ..core.game_objects.star import Star
    from ..core.game_objects.fleet import Fleet
    from ..core.components.ship_design import ShipDesign
    from ..core.commands.base import Command


class DefaultAI(AbstractAI):
    """
    Default AI implementation for computer opponents.

    Orchestrates planet and fleet sub-AIs, handles research,
    ship design, and overall strategic decisions.

    Ported from DefaultAi.cs.
    """

    def __init__(self):
        """Initialize the default AI."""
        super().__init__()
        self.ai_plan: Optional[DefaultAIPlanner] = None
        self.planet_ais: Dict[str, DefaultPlanetAI] = {}
        self.fleet_ais: Dict[int, DefaultFleetAI] = {}
        self.fuel_stations: Dict[int, 'Fleet'] = {}

    def initialize(self, empire_data: 'EmpireData'):
        """
        Initialize the AI with empire data.

        Creates the planner and sub-AIs.

        Args:
            empire_data: The empire data for the AI player

        Ported from DefaultAi.cs constructor and Initialize().
        """
        super().initialize(empire_data)
        self.ai_plan = DefaultAIPlanner(empire_data)

        # Build fuel station list
        self.fuel_stations = {}
        for fleet in empire_data.owned_fleets.values():
            if fleet.can_refuel:
                self.fuel_stations[fleet.key] = fleet

        # Create planet AIs
        self.planet_ais = {}
        for star in empire_data.owned_stars.values():
            self.planet_ais[star.key] = DefaultPlanetAI(
                planet=star,
                empire_data=empire_data,
                ai_plan=self.ai_plan
            )

        # Create fleet AIs
        self.fleet_ais = {}
        for fleet in empire_data.owned_fleets.values():
            if not fleet.is_starbase:
                self.fleet_ais[fleet.key] = DefaultFleetAI(
                    fleet=fleet,
                    empire_data=empire_data,
                    fuel_stations=self.fuel_stations
                )

    def do_move(self) -> List['Command']:
        """
        Generate commands for this turn.

        Main AI turn processing. Handles all aspects of empire management:
        - Ship designs
        - Planet production
        - Fleet movement (scouting, colonizing, combat)
        - Research priorities

        Returns:
            List of commands to execute

        Ported from DefaultAi.cs DoMove().
        """
        self.commands = []

        if self.empire_data is None:
            return self.commands

        # Count and classify existing fleets
        self._count_fleets()

        # Handle ship designs first
        self._handle_ship_design()

        # Handle production for all planets
        self._handle_production()

        # Handle fleet operations
        self._handle_scouting()
        self._handle_armed_scouting()
        self._handle_colonizing()
        self._handle_population_surplus()
        self._handle_fuel_impoverished_fleets()

        # Handle research
        self._handle_research()

        return self.commands

    def _count_fleets(self):
        """
        Count and classify all owned fleets.

        Updates the AI planner with fleet counts.

        Ported from DefaultAi.cs CountFleets().
        """
        if self.ai_plan is None:
            return

        self.ai_plan._reset_counts()
        for fleet in self.empire_data.owned_fleets.values():
            self.ai_plan.count_fleet(fleet)

    def _handle_production(self):
        """
        Handle production for all planets.

        Delegates to planet AIs.

        Ported from DefaultAi.cs HandleProduction().
        """
        for planet_ai in self.planet_ais.values():
            planet_ai.handle_production()
            self.commands.extend(planet_ai.commands)
            planet_ai.commands = []

    def _handle_scouting(self):
        """
        Send scouts to unexplored stars.

        Ported from DefaultAi.cs HandleScouting().
        """
        # Find idle scouts
        excluded_stars = []

        for fleet_key, fleet_ai in self.fleet_ais.items():
            fleet = self.empire_data.owned_fleets.get(fleet_key)
            if fleet is None:
                continue

            # Check if this is a scout
            is_scout = (
                "Scout" in fleet.name or
                "Long Range Scout" in fleet.name or
                g.AI_SCOUT in fleet.name
            )
            if not is_scout:
                continue

            # Check if idle (no waypoints or at destination)
            if len(fleet.waypoints) > 1:
                continue

            # Send to scout
            target = fleet_ai.scout(excluded_stars)
            if target:
                excluded_stars.append(target)
                self.commands.extend(fleet_ai.commands)
                fleet_ai.commands = []

    def _handle_armed_scouting(self):
        """
        Send armed ships to scout (can defend themselves).

        Ported from DefaultAi.cs HandleArmedScouting().
        """
        excluded_stars = []

        for fleet_key, fleet_ai in self.fleet_ais.items():
            fleet = self.empire_data.owned_fleets.get(fleet_key)
            if fleet is None:
                continue

            # Check if armed but not a dedicated combat ship
            if not fleet.is_armed:
                continue

            # Skip dedicated combat ships
            is_combat = (
                g.AI_DEFENSIVE_DESTROYER in fleet.name or
                g.AI_DEFENSIVE_CRUISER in fleet.name or
                g.AI_DEFENSIVE_BATTLE_CRUISER in fleet.name or
                g.AI_BOMBER in fleet.name
            )
            if is_combat:
                continue

            # Check if idle
            if len(fleet.waypoints) > 1:
                continue

            # Send to armed scout
            target = fleet_ai.armed_scout(excluded_stars)
            if target:
                excluded_stars.append(target)
                self.commands.extend(fleet_ai.commands)
                fleet_ai.commands = []

    def _handle_colonizing(self):
        """
        Send colonizers to colonize suitable planets.

        Ported from DefaultAi.cs HandleColonizing().
        """
        # Find colonizable planets
        colonizable = []
        race = self.empire_data.race

        for star_name, report in self.empire_data.star_reports.items():
            owner = report.get("owner", g.NOBODY)
            if owner != g.NOBODY:
                continue

            # Check habitability
            if race:
                hab_value = self._calc_hab_from_report(race, report)
                if hab_value > DefaultAIPlanner.MIN_HAB_VALUE:
                    colonizable.append(report)

        # Find idle colonizers
        for fleet_key, fleet_ai in self.fleet_ais.items():
            fleet = self.empire_data.owned_fleets.get(fleet_key)
            if fleet is None:
                continue

            if not fleet.can_colonize:
                continue

            # Check if idle
            if len(fleet.waypoints) > 1:
                continue

            if not colonizable:
                break

            # Find best target (closest that can be reached)
            best_target = None
            best_distance = float('inf')

            for target in colonizable:
                if not fleet_ai.can_reach(target):
                    continue

                target_pos = NovaPoint(
                    x=target.get("position_x", 0),
                    y=target.get("position_y", 0)
                )
                distance = self._distance_to(fleet.position, target_pos)
                if distance < best_distance:
                    best_distance = distance
                    best_target = target

            if best_target:
                fleet_ai.colonise(best_target)
                colonizable.remove(best_target)
                self.commands.extend(fleet_ai.commands)
                fleet_ai.commands = []

    def _handle_population_surplus(self):
        """
        Move excess population from crowded planets.

        Ported from DefaultAi.cs HandlePopulationSurplus().
        """
        # Find planets with surplus population
        race = self.empire_data.race
        if race is None:
            return

        surplus_planets = []
        for star in self.empire_data.owned_stars.values():
            capacity = star.capacity(race)
            if capacity > 50:  # More than 50% full
                max_pop = star.max_population(race)
                surplus = star.colonists - (max_pop // 2)
                if surplus > 0:
                    surplus_planets.append((star, surplus))

        if not surplus_planets:
            return

        # Find empty freighters to transport population
        for fleet_key, fleet_ai in self.fleet_ais.items():
            fleet = self.empire_data.owned_fleets.get(fleet_key)
            if fleet is None:
                continue

            # Check if freighter
            if fleet.total_cargo_capacity == 0:
                continue
            if fleet.can_colonize:  # Colonizers handled separately
                continue

            # Check if idle with empty cargo
            if len(fleet.waypoints) > 1:
                continue
            if fleet.cargo.mass > fleet.total_cargo_capacity // 2:
                continue

            # TODO: Send freighter to pick up population and deliver
            # This would need more complex waypoint management
            pass

    def _handle_fuel_impoverished_fleets(self):
        """
        Rescue fleets that are out of fuel.

        Ported from DefaultAi.cs HandleFuelImpoverishedFleets().
        """
        for fleet_key, fleet_ai in self.fleet_ais.items():
            fleet = self.empire_data.owned_fleets.get(fleet_key)
            if fleet is None:
                continue

            # Check if out of fuel
            if fleet.fuel_available > 100:
                continue

            # Check if at a refueling point
            if fleet.in_orbit and fleet.in_orbit.owner == fleet.owner:
                continue  # Will refuel at planet

            # Check if can make fuel (free warp)
            if fleet.free_warp_speed > 1:
                continue

            # Find nearest fuel station
            nearest_fuel = fleet_ai._closest_fuel()
            if nearest_fuel:
                # Already handled by fleet AI in scout/armed_scout
                pass

    def _handle_research(self):
        """
        Manage research priorities.

        Simple strategy: focus on propulsion early, then construction,
        then weapons.

        Ported from DefaultAi.cs HandleResearch().
        """
        research_levels = self.empire_data.research_levels

        # Default budget
        budget = 15

        # Prioritize propulsion early (for better engines)
        propulsion_level = research_levels.levels.get("Propulsion", 0)
        construction_level = research_levels.levels.get("Construction", 0)
        weapons_level = research_levels.levels.get("Weapons", 0)

        if propulsion_level < 5:
            topics = TechLevel(levels={
                "Biotechnology": 0, "Electronics": 0, "Energy": 0,
                "Propulsion": 10, "Weapons": 0, "Construction": 0
            })
        elif construction_level < 5:
            topics = TechLevel(levels={
                "Biotechnology": 0, "Electronics": 0, "Energy": 0,
                "Propulsion": 0, "Weapons": 0, "Construction": 10
            })
        elif weapons_level < 5:
            topics = TechLevel(levels={
                "Biotechnology": 0, "Electronics": 0, "Energy": 0,
                "Propulsion": 0, "Weapons": 10, "Construction": 0
            })
        else:
            # Balanced
            topics = TechLevel(levels={
                "Biotechnology": 1, "Electronics": 2, "Energy": 2,
                "Propulsion": 2, "Weapons": 2, "Construction": 1
            })

        # Create research command
        command = ResearchCommand(budget=budget, topics=topics)
        valid, msg = command.is_valid(self.empire_data)
        if valid:
            command.apply_to_state(self.empire_data)
            self.commands.append(command)

    def _handle_ship_design(self):
        """
        Create new ship designs based on available technology.

        Creates basic designs for scouts, colonizers, freighters,
        and combat ships as tech allows.

        Ported from DefaultAi.cs HandleShipDesign().
        """
        # Check if we already have basic designs
        has_scout = self.ai_plan.scout_design is not None
        has_colonizer = self.ai_plan.colonizer_design is not None
        has_transport = self.ai_plan.any_transport_design is not None
        has_defender = self.ai_plan.defense_design is not None

        # For now, assume designs are created at game start
        # Full implementation would create designs based on available
        # hulls and components from component loader

        # TODO: Implement design creation when missing
        # This requires the component/hull system to select best available
        # components and create ShipDesign instances

        pass

    def _calc_hab_from_report(self, race, report: dict) -> float:
        """
        Calculate habitability from a star report (dict).

        Creates a temporary object to pass to race.hab_value().

        Args:
            race: The race to calculate for
            report: Star report dictionary

        Returns:
            Habitability value (-1 to 1)
        """
        class _TempStar:
            """Temporary object to hold star data for hab calculation."""
            def __init__(self, data: dict):
                self.gravity = data.get("gravity", 50)
                self.temperature = data.get("temperature", 50)
                self.radiation = data.get("radiation", 50)

        temp_star = _TempStar(report)
        return race.hab_value(temp_star)

    @staticmethod
    def _distance_to(p1: NovaPoint, p2: NovaPoint) -> float:
        """Calculate distance between two points."""
        dx = p2.x - p1.x
        dy = p2.y - p1.y
        return (dx * dx + dy * dy) ** 0.5
