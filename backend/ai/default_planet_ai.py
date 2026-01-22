"""
Stars Nova Web - Default Planet AI
Ported from Nova/Ai/DefaultPlanetAI.cs (462 lines)

AI sub-component to manage a planet's production queue.
"""

from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING

from ..core.commands.base import CommandMode, Message
from ..core.commands.production import ProductionCommand
from ..core.production.production_queue import ProductionOrder, ProductionType
from ..core.data_structures import Resources
from ..core import globals as g

if TYPE_CHECKING:
    from ..core.data_structures.empire_data import EmpireData
    from ..core.game_objects.star import Star
    from ..core.components.ship_design import ShipDesign
    from ..core.commands.base import Command
    from .default_ai_planner import DefaultAIPlanner


# Production queue precedence constants
FACTORY_PRODUCTION_PRECEDENCE = 0
MINE_PRODUCTION_PRECEDENCE = 1


@dataclass
class DefaultPlanetAI:
    """
    AI sub-component to manage a planet's production.

    Handles building factories, mines, ships, defenses, and terraforming.

    Ported from DefaultPlanetAI.cs.
    """
    planet: 'Star' = None
    empire_data: 'EmpireData' = None
    ai_plan: 'DefaultAIPlanner' = None
    commands: List['Command'] = field(default_factory=list)
    _transport_design: Optional['ShipDesign'] = None

    def __init__(
        self,
        planet: 'Star',
        empire_data: 'EmpireData',
        ai_plan: 'DefaultAIPlanner'
    ):
        """
        Initialize the planet AI.

        Args:
            planet: The planet to manage
            empire_data: The empire data
            ai_plan: The AI planner with designs and priorities
        """
        self.planet = planet
        self.empire_data = empire_data
        self.ai_plan = ai_plan
        self.commands = []

    def handle_production(self):
        """
        Main production handling for the planet.

        Clears non-ship items from queue and rebuilds based on priorities.

        Ported from DefaultPlanetAI.cs HandleProduction().
        """
        production_index = 0

        # Clear the current manufacturing queue (except for partially built ships)
        self._clear_queue()

        # Check if we should skip production for research
        # If population is high and we don't have good freighters yet, focus on research
        race = self.empire_data.race
        capacity = self.planet.capacity(race) if race else 0
        research_levels = self.empire_data.research_levels

        # Check freighter tech thresholds
        has_medium_freighters = (
            research_levels.levels.get("Construction", 0) >= 3 and
            research_levels.levels.get("Propulsion", 0) >= 5
        )
        has_large_freighters = (
            research_levels.levels.get("Construction", 0) >= 8 and
            research_levels.levels.get("Propulsion", 0) >= 7
        )

        # Skip production if population is high and lacking freighter tech
        should_produce = (
            (capacity < 55 or has_medium_freighters) and
            (capacity < 80 or has_large_freighters)
        )

        if capacity < 55 or has_medium_freighters:
            production_index = self._build_transport(production_index)

        if should_produce:
            # Calculate production multipliers based on game year
            turn_year = self.empire_data.turn_year
            early_factory_multiplier = 1.0  # Rush factories for first 8 years

            if turn_year > 2106:
                early_factory_multiplier = 0.3  # Then rush scouts
            if turn_year > 2115:
                early_factory_multiplier = 0.5  # Then build a mix
            if turn_year > 2120:
                early_factory_multiplier = 0.65
            if turn_year > 2130:
                early_factory_multiplier = 0.7

            # Build factories (limited by Germanium)
            production_index = self._build_factories(
                production_index, early_factory_multiplier
            )

            # Min terraform if habitability is low
            if self.planet.min_value(race) < 10 if race else False:
                production_index = self._build_terraform(production_index, 100)

            # Build mines
            early_mine_multiplier = early_factory_multiplier
            if turn_year > 2135:
                early_mine_multiplier = 0.95
            production_index = self._build_mines(
                production_index, early_mine_multiplier
            )

            # Max terraform if capacity is low or has starbase
            if capacity < 25 or self.planet.starbase_key is not None:
                production_index = self._build_terraform(production_index, 100)

            # Build ships
            production_index = self._build_ships(production_index)

            # Build defenses (commented out in original - build specifically)
            # production_index = self._build_defenses(production_index)

    def _clear_queue(self):
        """
        Clear non-ship production items that haven't started.

        Ported from DefaultPlanetAI.cs HandleProduction() clear section.
        """
        to_remove = []
        for i, order in enumerate(self.planet.manufacturing_queue.orders):
            # Keep partially built ships
            if order.production_type == ProductionType.SHIP:
                continue
            if order.partial_resources_spent == 0:
                to_remove.append(i)

        # Remove in reverse order to maintain indices
        for i in reversed(to_remove):
            command = ProductionCommand(
                mode=CommandMode.DELETE,
                star_key=self.planet.key,
                index=i
            )
            valid, msg = command.is_valid(self.empire_data)
            if valid:
                command.apply_to_state(self.empire_data)
                self.commands.append(command)

    def _build_factories(
        self, production_index: int, multiplier: float
    ) -> int:
        """
        Add factories to the production queue.

        Args:
            production_index: Current queue position
            multiplier: Production multiplier (0-1)

        Returns:
            Updated production index

        Ported from DefaultPlanetAI.cs HandleProduction() factory section.
        """
        race = self.empire_data.race
        if self.planet.resources_on_hand.germanium <= 50:
            return production_index

        # Calculate factory build cost in germanium
        factory_cost_germ = 3 if race and race.has_trait("CF") else 4

        # Calculate how many we can build
        factories_to_build = (
            (self.planet.resources_on_hand.germanium - 50) // factory_cost_germ
        )

        # Limit to operable factories * multiplier
        max_factories = int(
            self.planet.get_operable_factories() * multiplier
        ) - self.planet.factories
        factories_to_build = min(factories_to_build, max_factories)

        if factories_to_build > 0:
            order = ProductionOrder(
                production_type=ProductionType.FACTORY,
                quantity=factories_to_build,
                name="Factory"
            )
            command = ProductionCommand(
                mode=CommandMode.ADD,
                production_order=order,
                star_key=self.planet.key,
                index=FACTORY_PRODUCTION_PRECEDENCE
            )
            valid, msg = command.is_valid(self.empire_data)
            if valid:
                command.apply_to_state(self.empire_data)
                self.commands.append(command)
                production_index += 1

        return production_index

    def _build_mines(self, production_index: int, multiplier: float) -> int:
        """
        Add mines to the production queue.

        Args:
            production_index: Current queue position
            multiplier: Production multiplier (0-1)

        Returns:
            Updated production index

        Ported from DefaultPlanetAI.cs HandleProduction() mine section.
        """
        max_mines = int(self.planet.get_operable_mines() * multiplier)
        mines_to_build = max_mines - self.planet.mines

        if mines_to_build > 0:
            order = ProductionOrder(
                production_type=ProductionType.MINE,
                quantity=mines_to_build,
                name="Mine"
            )
            command = ProductionCommand(
                mode=CommandMode.ADD,
                production_order=order,
                star_key=self.planet.key,
                index=min(production_index, MINE_PRODUCTION_PRECEDENCE)
            )
            valid, msg = command.is_valid(self.empire_data)
            if valid:
                command.apply_to_state(self.empire_data)
                self.commands.append(command)
                production_index += 1

        return production_index

    def _build_terraform(self, production_index: int, quantity: int) -> int:
        """
        Add terraforming to the production queue.

        Args:
            production_index: Current queue position
            quantity: Terraforming units to build

        Returns:
            Updated production index

        Ported from DefaultPlanetAI.cs HandleProduction() terraform section.
        """
        order = ProductionOrder(
            production_type=ProductionType.TERRAFORM,
            quantity=quantity,
            name="Terraform"
        )
        command = ProductionCommand(
            mode=CommandMode.ADD,
            production_order=order,
            star_key=self.planet.key,
            index=production_index
        )
        valid, msg = command.is_valid(self.empire_data)
        if valid:
            command.apply_to_state(self.empire_data)
            self.commands.append(command)
            production_index += 1

        return production_index

    def _build_defenses(self, production_index: int) -> int:
        """
        Add defenses to the production queue.

        Args:
            production_index: Current queue position

        Returns:
            Updated production index

        Ported from DefaultPlanetAI.cs HandleProduction() defense section.
        """
        defenses_to_build = g.MAX_DEFENSES - self.planet.defenses

        if defenses_to_build > 0:
            order = ProductionOrder(
                production_type=ProductionType.DEFENSE,
                quantity=defenses_to_build,
                name="Defense"
            )
            command = ProductionCommand(
                mode=CommandMode.ADD,
                production_order=order,
                star_key=self.planet.key,
                index=production_index
            )
            valid, msg = command.is_valid(self.empire_data)
            if valid:
                command.apply_to_state(self.empire_data)
                self.commands.append(command)
                production_index += 1

        return production_index

    def _build_ships(self, production_index: int) -> int:
        """
        Build ships based on planet's starbase and needs.

        Args:
            production_index: Current queue position

        Returns:
            Updated production index

        Ported from DefaultPlanetAI.cs BuildShips().
        """
        if self.planet.starbase_key is None:
            # No starbase - build minimal one first
            production_index = self._build_minimal_starbase(production_index)
        else:
            # Has starbase - build various ships
            production_index = self._build_scout(production_index)
            production_index = self._build_colonizer(production_index)
            production_index = self._build_transport(production_index)
            production_index = self._build_suitable_fleet(production_index)
            production_index = self._build_refueler(production_index)

        return production_index

    def _build_scout(self, production_index: int) -> int:
        """
        Add a scout to the production queue if needed.

        Args:
            production_index: Current queue position

        Returns:
            Updated production index

        Ported from DefaultPlanetAI.cs BuildScout().
        """
        early_scouts = max(
            self.ai_plan.EARLY_SCOUTS,
            len(self.empire_data.star_reports) // 8
        )

        if (self.planet.get_resource_rate() > self.ai_plan.LOW_PRODUCTION and
                self.ai_plan.scout_count < early_scouts):
            design = self.ai_plan.scout_design
            if design:
                production_index = self._add_ship_to_queue(
                    design, production_index
                )

        return production_index

    def _build_colonizer(self, production_index: int) -> int:
        """
        Add a colonizer to the production queue if needed.

        Builds colonizers in batches every 5 years.

        Args:
            production_index: Current queue position

        Returns:
            Updated production index

        Ported from DefaultPlanetAI.cs BuildColonizer().
        """
        if (self.planet.get_resource_rate() > self.ai_plan.LOW_PRODUCTION and
                self.ai_plan.colonizer_count < self.ai_plan.planets_to_colonize):
            design = self.ai_plan.colonizer_design

            # Build in batches every 5 years
            if design and (self.empire_data.turn_year % 5) == 0:
                for _ in range(min(10, self.ai_plan.planets_to_colonize)):
                    production_index = self._add_ship_to_queue(
                        design, production_index
                    )

        return production_index

    def _build_transport(self, production_index: int) -> int:
        """
        Add a transport to the production queue if needed.

        Args:
            production_index: Current queue position

        Returns:
            Updated production index

        Ported from DefaultPlanetAI.cs BuildTransport().
        """
        design = self.ai_plan.any_transport_design
        if design is None:
            return production_index

        if self.planet.starbase_key is None:
            return production_index

        # Check starbase dock capacity
        # TODO: Would need to resolve starbase_key to get actual dock capacity
        # For now, assume we can build

        race = self.empire_data.race
        capacity = self.planet.capacity(race) if race else 0

        if (self.planet.get_resource_rate() > self.ai_plan.LOW_PRODUCTION and
                capacity > 25 and
                not self.planet.has_free_transport_in_orbit):
            production_index = self._add_ship_to_queue(design, production_index)

        return production_index

    def _build_refueler(self, production_index: int) -> int:
        """
        Add a refueler to the production queue if needed.

        Args:
            production_index: Current queue position

        Returns:
            Updated production index

        Ported from DefaultPlanetAI.cs BuildRefueler().
        """
        if (self.planet.get_resource_rate() > self.ai_plan.LOW_PRODUCTION and
                not self.planet.has_refueler_in_orbit):
            design = self.ai_plan.current_refueler_design
            if design:
                production_index = self._add_ship_to_queue(
                    design, production_index
                )

        return production_index

    def _build_minimal_starbase(self, production_index: int) -> int:
        """
        Build a minimal starbase if none exists.

        Args:
            production_index: Current queue position

        Returns:
            Updated production index

        Ported from DefaultPlanetAI.cs BuidMinimalStarbase().
        """
        # Check queue energy cost
        queue_energy = sum(
            order.partial_resources_spent
            for order in self.planet.manufacturing_queue.orders
            if order.production_type == ProductionType.MINE
        )
        queue_years = queue_energy // max(
            1, self.planet.resources_on_hand.energy
        )
        if queue_years > 1:
            return production_index

        design = self.ai_plan.current_minimal_starbase_design
        if design is None:
            return production_index

        # Check if already in queue
        for order in self.planet.manufacturing_queue.orders:
            if order.name == design.name:
                return production_index

        production_index = self._add_ship_to_queue(design, production_index)
        return production_index

    def _build_suitable_fleet(self, production_index: int) -> int:
        """
        Build combat ships based on empire priorities.

        Chooses between defenders, bombers, bomber cover, or starbase upgrade.

        Args:
            production_index: Current queue position

        Returns:
            Updated production index

        Ported from DefaultPlanetAI.cs BuidSuitableFleet().
        """
        # Check queue time
        queue_energy = sum(
            order.partial_resources_spent
            for order in self.planet.manufacturing_queue.orders
        )
        queue_years = queue_energy // max(
            1, self.planet.resources_on_hand.energy
        )
        if queue_years > 1:
            return production_index

        race = self.empire_data.race

        # Calculate production scores for each ship type
        def how_many_can_build(design):
            """Estimate how many of a design can be built in 8 years."""
            if design is None:
                return 0
            resources = Resources(
                ironium=self.planet.resources_on_hand.ironium,
                boranium=self.planet.resources_on_hand.boranium,
                germanium=self.planet.resources_on_hand.germanium,
                energy=self.planet.resources_on_hand.energy
            )
            # Add 8 years of production
            rate = self.planet.get_resource_rate()
            resources.energy += 8 * rate
            # Rough estimate based on energy
            if design.cost and design.cost.energy > 0:
                return resources.energy / design.cost.energy
            return 0

        # Calculate weighted scores
        defense_score = (
            how_many_can_build(self.ai_plan.current_defender_design) *
            self.ai_plan.interceptor_production_priority *
            (race.ai_proclivities_interceptors / 50.0 if race else 1.0)
        )
        bomber_score = (
            how_many_can_build(self.ai_plan.current_bomber_design) *
            self.ai_plan.bomber_production_priority *
            (race.ai_proclivities_bombers if race else 1.0)
        )
        bomber_cover_score = (
            how_many_can_build(self.ai_plan.current_bomber_cover_design) *
            self.ai_plan.bomber_cover_production_priority *
            (race.ai_proclivities_escorts if race else 1.0)
        )
        starbase_score = (
            how_many_can_build(self.ai_plan.current_starbase_design) *
            self.ai_plan.starbase_upgrade_priority *
            (race.ai_proclivities_starbases if race else 1.0)
        )

        # Choose best option
        chosen_design = None
        chosen_qty = 1

        scores = [
            (defense_score, self.ai_plan.current_defender_design),
            (bomber_score, self.ai_plan.current_bomber_design),
            (bomber_cover_score, self.ai_plan.current_bomber_cover_design),
            (starbase_score, self.ai_plan.current_starbase_design),
        ]

        best_score = 0
        for score, design in scores:
            if score > best_score and design is not None:
                best_score = score
                chosen_design = design
                chosen_qty = max(1, int(score))

        if chosen_design is not None:
            # Don't add if already in queue
            for order in self.planet.manufacturing_queue.orders:
                if order.name == chosen_design.name:
                    return production_index

            for _ in range(chosen_qty):
                production_index = self._add_ship_to_queue(
                    chosen_design, production_index
                )

        return production_index

    def _add_ship_to_queue(
        self, design: 'ShipDesign', production_index: int
    ) -> int:
        """
        Add a ship design to the production queue.

        Args:
            design: Ship design to build
            production_index: Current queue position

        Returns:
            Updated production index
        """
        order = ProductionOrder(
            production_type=ProductionType.SHIP,
            quantity=1,
            design_key=design.key,
            name=design.name
        )
        command = ProductionCommand(
            mode=CommandMode.ADD,
            production_order=order,
            star_key=self.planet.key,
            index=production_index
        )
        valid, msg = command.is_valid(self.empire_data)
        if valid:
            command.apply_to_state(self.empire_data)
            self.commands.append(command)
            production_index += 1

        return production_index

    @property
    def transport_design(self) -> Optional['ShipDesign']:
        """
        Get the transport design.

        Ported from DefaultPlanetAI.cs TransportDesign property.
        """
        if self._transport_design is None:
            self._transport_design = self.ai_plan.any_transport_design
        return self._transport_design
