"""
Stars Nova Web - Star Update Step
Ported from ServerState/TurnSteps/StarUpdateStep.cs (246 lines)

Updates stars - manufacturing, research, and population growth.
"""

from typing import List, Dict, TYPE_CHECKING

from .base import ITurnStep
from ...core.commands.base import Message
from ...core.globals import NOBODY
from ...core.data_structures.tech_level import ResearchField, RESEARCH_KEYS

if TYPE_CHECKING:
    from ..server_data import ServerData
    from ...core.data_structures import EmpireData
    from ...core.game_objects.star import Star


class StarUpdateStep(ITurnStep):
    """
    Star update turn step.

    Processes:
    - Mineral mining
    - Resource generation
    - Research contribution
    - Manufacturing
    - Population growth

    Ported from StarUpdateStep.cs.
    """

    def __init__(self):
        self.server_state = None

    def process(self, server_state: 'ServerData') -> List[Message]:
        """
        Process star updates.

        Args:
            server_state: Current game state.

        Returns:
            List of messages generated.
        """
        self.server_state = server_state
        messages: List[Message] = []

        for star in server_state.all_stars.values():
            if star.owner == NOBODY or star.colonists == 0:
                continue

            empire = server_state.all_empires.get(star.owner)
            if empire is None:
                continue

            # Update minerals (mining)
            self._update_minerals(star)

            # Update research allocation
            self._update_research(star, empire)

            # Update resources (from colonists and factories)
            self._update_resources(star, empire)

            # Contribute allocated research
            self._contribute_allocated_research(star, empire)

            # Update population
            initial_population = star.colonists
            self._update_population(star, empire)
            final_population = star.colonists

            if final_population < initial_population:
                died = initial_population - final_population
                messages.append(Message(
                    audience=star.owner,
                    text=f"{died} of your colonists have been killed by the "
                         f"environment on {star.name}",
                    message_type="Star"
                ))

            # Manufacturing
            manufacture_messages = self._manufacture_items(star, empire)
            messages.extend(manufacture_messages)

            # Contribute leftover research
            self._contribute_leftover_research(star, empire)

            # Final resource update
            self._update_research(star, empire)
            self._update_resources(star, empire)

        return messages

    def _update_minerals(self, star: 'Star'):
        """
        Update mineral stockpiles from mining.

        Args:
            star: Star to update.
        """
        # Mining rate depends on mines, concentration, and population
        # Simplified implementation
        mines = getattr(star, 'mines', 0)
        if mines <= 0:
            return

        # Get mineral concentrations
        iron_conc = getattr(star, 'ironium_concentration', 0) / 100.0
        bor_conc = getattr(star, 'boranium_concentration', 0) / 100.0
        germ_conc = getattr(star, 'germanium_concentration', 0) / 100.0

        # Calculate mining output
        # Simplified: each mine produces up to concentration % of base rate
        base_rate = 10  # Base minerals per mine per year

        iron_mined = int(mines * iron_conc * base_rate)
        bor_mined = int(mines * bor_conc * base_rate)
        germ_mined = int(mines * germ_conc * base_rate)

        star.resources_on_hand.ironium += iron_mined
        star.resources_on_hand.boranium += bor_mined
        star.resources_on_hand.germanium += germ_mined

        # Concentration decreases slightly over time
        # Actual formula is more complex
        if iron_conc > 0.01:
            star.ironium_concentration = max(1, star.ironium_concentration - 1)
        if bor_conc > 0.01:
            star.boranium_concentration = max(1, star.boranium_concentration - 1)
        if germ_conc > 0.01:
            star.germanium_concentration = max(1, star.germanium_concentration - 1)

    def _update_research(self, star: 'Star', empire: 'EmpireData'):
        """
        Calculate research allocation for the star.

        Args:
            star: Star to update.
            empire: Owning empire.
        """
        # Research budget is percentage of resources
        budget = empire.research_budget / 100.0
        resources = getattr(star, 'resources_per_year', 0)

        star.research_allocation = int(resources * budget)

    def _update_resources(self, star: 'Star', empire: 'EmpireData'):
        """
        Calculate resource generation.

        Args:
            star: Star to update.
            empire: Owning empire.
        """
        # Resources from colonists (1 per 1000 colonists)
        colonist_resources = star.colonists // 1000

        # Resources from factories (depends on race)
        factories = getattr(star, 'factories', 0)
        factory_output = getattr(empire.race, 'factory_output', 10) if empire.race else 10
        factory_resources = factories * factory_output // 10

        star.resources_per_year = colonist_resources + factory_resources

    def _update_population(self, star: 'Star', empire: 'EmpireData'):
        """
        Update population with growth.

        Args:
            star: Star to update.
            empire: Owning empire.
        """
        # Call star's population update method if it exists
        if hasattr(star, 'update_population') and empire.race is not None:
            star.update_population(empire.race)
        else:
            # Simplified growth calculation
            hab_value = self._calculate_habitability(star, empire)

            if hab_value <= 0:
                # Hostile environment - population dies
                death_rate = abs(hab_value) / 100.0 * 0.05  # Up to 5% death rate
                deaths = int(star.colonists * death_rate)
                star.colonists = max(0, star.colonists - deaths)
            else:
                # Population grows
                growth_rate = (empire.race.growth_rate if empire.race else 15) / 100.0
                growth_rate *= hab_value / 100.0  # Scale by habitability

                # Crowding factor - max_population can be a method or attribute
                max_pop = 1000000  # Default
                if hasattr(star, 'max_population'):
                    max_pop_attr = getattr(star, 'max_population')
                    if callable(max_pop_attr) and empire.race is not None:
                        max_pop = max_pop_attr(empire.race)
                    elif isinstance(max_pop_attr, (int, float)):
                        max_pop = int(max_pop_attr)
                if star.colonists > max_pop * 0.25:
                    crowding = 1 - ((star.colonists - max_pop * 0.25) / (max_pop * 0.75))
                    crowding = max(0, crowding)
                    growth_rate *= crowding

                growth = int(star.colonists * growth_rate)
                star.colonists = min(star.colonists + growth, max_pop)

    def _calculate_habitability(self, star: 'Star', empire: 'EmpireData') -> int:
        """
        Calculate habitability value for a star.

        Args:
            star: Star to evaluate.
            empire: Empire to evaluate for.

        Returns:
            Habitability percentage (-45 to 100).
        """
        if empire.race is None:
            return 50  # Default

        # Get star environment
        gravity = getattr(star, 'gravity', 50)
        temperature = getattr(star, 'temperature', 50)
        radiation = getattr(star, 'radiation', 50)

        # Use race's hab_value method if available
        if hasattr(empire.race, 'hab_value'):
            return empire.race.hab_value(gravity, temperature, radiation)

        # Simplified calculation
        return 50  # Default to moderate habitability

    def _contribute_allocated_research(self, star: 'Star', empire: 'EmpireData'):
        """
        Apply allocated research resources.

        Args:
            star: Contributing star.
            empire: Receiving empire.
        """
        if star.owner == NOBODY:
            return

        # Find target research area
        target_area = self._get_research_target(empire)

        # Add research points
        current = empire.research_resources.get_level(target_area)
        empire.research_resources.set_level(target_area, current + star.research_allocation)
        star.research_allocation = 0

        # Check for level up
        self._check_tech_level_up(target_area, empire)

    def _contribute_leftover_research(self, star: 'Star', empire: 'EmpireData'):
        """
        Apply leftover resources to research.

        Args:
            star: Contributing star.
            empire: Receiving empire.
        """
        if star.owner == NOBODY:
            return

        target_area = self._get_research_target(empire)

        # Leftover energy goes to research
        leftover = 0
        resources = getattr(star, 'resources_on_hand', None)
        if resources is not None and hasattr(resources, 'energy'):
            leftover = resources.energy
            resources.energy = 0

        if leftover > 0:
            current = empire.research_resources.get_level(target_area)
            empire.research_resources.set_level(target_area, current + leftover)

            self._check_tech_level_up(target_area, empire)

    def _get_research_target(self, empire: 'EmpireData') -> ResearchField:
        """
        Get the empire's current research target.

        Args:
            empire: Empire to check.

        Returns:
            Target research field.
        """
        # Find first priority area
        for field in ResearchField:
            if empire.research_topics.get_level(field) == 1:
                return field

        # Default to Energy
        return ResearchField.ENERGY

    def _check_tech_level_up(self, area: ResearchField, empire: 'EmpireData'):
        """
        Check if empire has enough research to level up.

        Args:
            area: Research area to check.
            empire: Empire to check.
        """
        while True:
            current_level = empire.research_levels.get_level(area)
            next_level = current_level + 1

            # Calculate cost for next level
            # Simplified cost formula
            cost = self._research_cost(area, empire, next_level)

            if empire.research_resources.get_level(area) >= cost:
                # Level up
                empire.research_levels.set_level(area, next_level)
                empire.research_resources.set_level(
                    area,
                    empire.research_resources.get_level(area) - cost
                )

                self.server_state.all_messages.append(Message(
                    audience=empire.id,
                    text=f"Your race has advanced to Tech Level {next_level} "
                         f"in the {area.value} field",
                    message_type="TechAdvance"
                ))
            else:
                break

    def _research_cost(self, area: ResearchField, empire: 'EmpireData',
                       target_level: int) -> int:
        """
        Calculate research cost for a level.

        Args:
            area: Research area.
            empire: Empire (for trait adjustments).
            target_level: Target level.

        Returns:
            Resource cost for level.
        """
        # Base cost increases exponentially
        # Simplified formula
        base_cost = 50
        return int(base_cost * (1.75 ** target_level))

    def _manufacture_items(self, star: 'Star', empire: 'EmpireData') -> List[Message]:
        """
        Process manufacturing queue.

        Args:
            star: Manufacturing star.
            empire: Owning empire.

        Returns:
            Messages from manufacturing.
        """
        messages: List[Message] = []

        # Get manufacturing queue
        queue = getattr(star, 'manufacturing_queue', None)
        if queue is None or not hasattr(queue, 'queue') or len(queue.queue) == 0:
            return messages

        # Resources available for manufacturing
        available_resources = star.resources_per_year - star.research_allocation
        if available_resources <= 0:
            return messages

        # Process queue items
        completed = []

        for order in queue.queue:
            if available_resources <= 0:
                break

            # Check if order can be processed
            cost = self._get_order_cost(order, empire)

            if cost > available_resources:
                # Not enough resources for one unit
                # Check if auto-build (doesn't block)
                if not getattr(order, 'auto_build', False):
                    break
                continue

            # Process as many as possible
            units_possible = available_resources // cost
            units_to_build = min(units_possible, order.quantity)

            if units_to_build > 0:
                available_resources -= units_to_build * cost
                order.quantity -= units_to_build

                # Create the items
                item_messages = self._create_manufactured_items(
                    order, star, empire, units_to_build
                )
                messages.extend(item_messages)

            if order.quantity <= 0:
                completed.append(order)

        # Remove completed orders
        for order in completed:
            queue.queue.remove(order)

        return messages

    def _get_order_cost(self, order, empire: 'EmpireData') -> int:
        """Get resource cost for a production order."""
        # Simplified - actual cost comes from the unit type
        return getattr(order, 'cost', 100)

    def _create_manufactured_items(self, order, star: 'Star',
                                   empire: 'EmpireData',
                                   count: int) -> List[Message]:
        """Create manufactured items and return messages."""
        messages: List[Message] = []

        item_type = getattr(order, 'unit_type', 'Unknown')

        messages.append(Message(
            audience=star.owner,
            text=f"{star.name} has produced {count} {item_type}",
            message_type="Star"
        ))

        return messages
