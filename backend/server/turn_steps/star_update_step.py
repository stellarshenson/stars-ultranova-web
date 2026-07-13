"""
Stars Nova Web - Star Update Step
Ported from ServerState/TurnSteps/StarUpdateStep.cs (246 lines)

Updates stars - mining, resources, research, manufacturing, and
population growth. Uses the C#-ported Star methods (update_minerals,
update_research, update_resources, update_population) so the formulas
match the original game.
"""

from typing import List, Optional, TYPE_CHECKING

from .base import ITurnStep
from ...core.commands.base import Message
from ...core.globals import (
    NOBODY,
    DEFENSE_IRONIUM_COST,
    DEFENSE_BORANIUM_COST,
    DEFENSE_GERMANIUM_COST,
    DEFENSE_ENERGY_COST,
    MAX_DEFENSES,
)
from ...core.data_structures.tech_level import ResearchField
from ...core.data_structures.resources import Resources
from ...core.production.production_queue import ProductionOrder, ProductionType

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

            # Keep race reference linked (needed by all Star math)
            if star.this_race is None:
                star.this_race = empire.race

            # Update minerals (mining with concentration depletion)
            star.update_minerals()

            # Research allocation, then this year's resources (energy)
            star.update_research(empire.research_budget)
            star.update_resources()

            # Contribute allocated research
            self._contribute_allocated_research(star, empire)

            # Update population
            initial_population = star.colonists
            if empire.race is not None:
                star.update_population(empire.race)
            final_population = star.colonists

            if final_population < initial_population:
                died = initial_population - final_population
                messages.append(Message(
                    audience=star.owner,
                    text=f"{died:,} of your colonists have been killed by the "
                         f"environment on {star.name}",
                    message_type="Star"
                ))

            # Manufacturing
            manufacture_messages = self._manufacture_items(star, empire)
            messages.extend(manufacture_messages)

            # Contribute leftover research
            self._contribute_leftover_research(star, empire)

        return messages

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
        Apply leftover production resources to research.

        Only when the star is flagged to contribute leftovers
        (matches the original 'Contribute only leftover resources
        to research' checkbox semantics).

        Args:
            star: Contributing star.
            empire: Receiving empire.
        """
        if star.owner == NOBODY:
            return
        if not star.only_leftover:
            return

        target_area = self._get_research_target(empire)

        leftover = star.resources_on_hand.energy
        star.resources_on_hand.energy = 0

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
                    text=f"Your scientists have completed research into Tech Level "
                         f"{next_level} in the {area.value} field",
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

    # =========================================================================
    # Manufacturing
    # =========================================================================

    def _manufacture_items(self, star: 'Star', empire: 'EmpireData') -> List[Message]:
        """
        Process the star's production queue.

        Spends this year's resources (resources_on_hand.energy) and
        surface minerals on queued orders, in queue order. Incomplete
        orders carry partial progress to the next year.

        Args:
            star: Manufacturing star.
            empire: Owning empire.

        Returns:
            Messages from manufacturing.
        """
        messages: List[Message] = []

        queue = star.manufacturing_queue
        if queue is None or len(queue.orders) == 0:
            return messages

        completed_orders = []

        for order in queue.orders:
            if star.resources_on_hand.energy <= 0:
                break

            unit_cost = self._get_order_cost(order, star, empire)
            if unit_cost is None or unit_cost.energy <= 0:
                # Unknown item - drop it from the queue
                completed_orders.append(order)
                messages.append(Message(
                    audience=star.owner,
                    text=f"{star.name} could not build '{order.name}' - unknown item",
                    message_type="Star"
                ))
                continue

            built = 0
            while order.quantity > 0:
                remaining = unit_cost.energy - order.partial_resources_spent
                spend = min(remaining, star.resources_on_hand.energy)

                if spend < remaining:
                    # Not enough resources to finish this unit - bank progress
                    order.partial_resources_spent += spend
                    star.resources_on_hand.energy -= spend
                    break

                # Check minerals for one unit
                if (star.resources_on_hand.ironium < unit_cost.ironium or
                        star.resources_on_hand.boranium < unit_cost.boranium or
                        star.resources_on_hand.germanium < unit_cost.germanium):
                    # Blocked on minerals - stop processing this order
                    break

                # Pay for the unit
                star.resources_on_hand.energy -= spend
                star.resources_on_hand.ironium -= unit_cost.ironium
                star.resources_on_hand.boranium -= unit_cost.boranium
                star.resources_on_hand.germanium -= unit_cost.germanium
                order.partial_resources_spent = 0
                order.quantity -= 1
                built += 1

                if star.resources_on_hand.energy <= 0 and order.quantity > 0:
                    break

            if built > 0:
                item_messages = self._create_manufactured_items(
                    order, star, empire, built
                )
                messages.extend(item_messages)

            if order.quantity <= 0:
                completed_orders.append(order)

            if star.resources_on_hand.energy <= 0:
                break

        # Remove completed orders
        for order in completed_orders:
            if order in queue.orders:
                queue.orders.remove(order)

        return messages

    def _get_order_cost(self, order: ProductionOrder, star: 'Star',
                        empire: 'EmpireData') -> Optional[Resources]:
        """
        Get the full unit cost for a production order.

        Returns:
            Resources with energy (resource) and mineral costs,
            or None if the order cannot be priced (unknown design).
        """
        race = empire.race

        if order.production_type == ProductionType.FACTORY:
            factory_cost = race.factory_cost if race else 10
            return Resources(ironium=0, boranium=0, germanium=4, energy=factory_cost)

        if order.production_type == ProductionType.MINE:
            mine_cost = race.mine_cost if race else 5
            return Resources(ironium=0, boranium=0, germanium=0, energy=mine_cost)

        if order.production_type == ProductionType.DEFENSE:
            return Resources(
                ironium=DEFENSE_IRONIUM_COST,
                boranium=DEFENSE_BORANIUM_COST,
                germanium=DEFENSE_GERMANIUM_COST,
                energy=DEFENSE_ENERGY_COST
            )

        if order.production_type in (ProductionType.SHIP, ProductionType.STARBASE):
            design = empire.designs.get(order.design_key)
            if design is None:
                return None
            cost = getattr(design, 'cost', None)
            if cost is None:
                return None
            return Resources(
                ironium=cost.ironium,
                boranium=cost.boranium,
                germanium=cost.germanium,
                energy=cost.energy
            )

        return None

    def _create_manufactured_items(self, order: ProductionOrder, star: 'Star',
                                   empire: 'EmpireData',
                                   count: int) -> List[Message]:
        """Create manufactured items and return messages."""
        messages: List[Message] = []

        if order.production_type == ProductionType.FACTORY:
            star.factories += count
            messages.append(Message(
                audience=star.owner,
                text=f"{star.name} has built {count} factor"
                     f"{'ies' if count > 1 else 'y'}",
                message_type="Star"
            ))

        elif order.production_type == ProductionType.MINE:
            star.mines += count
            messages.append(Message(
                audience=star.owner,
                text=f"{star.name} has built {count} mine{'s' if count > 1 else ''}",
                message_type="Star"
            ))

        elif order.production_type == ProductionType.DEFENSE:
            star.defenses = min(star.defenses + count, MAX_DEFENSES)
            messages.append(Message(
                audience=star.owner,
                text=f"{star.name} has built {count} defense"
                     f"{'s' if count > 1 else ''}",
                message_type="Star"
            ))

        elif order.production_type in (ProductionType.SHIP, ProductionType.STARBASE):
            messages.extend(self._build_ships(order, star, empire, count))

        return messages

    def _build_ships(self, order: ProductionOrder, star: 'Star',
                     empire: 'EmpireData', count: int) -> List[Message]:
        """Build ships from a design and place them in a new fleet at the star."""
        from ...core.game_objects.fleet import Fleet
        from ...services.ship_specs import make_token

        messages: List[Message] = []

        design = empire.designs.get(order.design_key)
        if design is None:
            return messages

        token = make_token(design, quantity=count)

        if order.production_type == ProductionType.STARBASE or getattr(design, 'is_starbase', False):
            # Starbase orbits the star directly
            fleet = Fleet()
            fleet.key = empire.get_next_fleet_key()
            fleet.name = design.name
            fleet.position = star.position.copy()
            fleet.in_orbit_name = star.name
            fleet.tokens[token.design_key] = token
            fleet.fuel_available = 0
            empire.owned_fleets[fleet.key] = fleet
            star.starbase_key = fleet.key
            messages.append(Message(
                audience=star.owner,
                text=f"{star.name} has built a new {design.name}",
                message_type="Star"
            ))
            return messages

        fleet = Fleet()
        fleet.key = empire.get_next_fleet_key()
        fleet.name = f"{design.name} #{fleet.id}"
        fleet.position = star.position.copy()
        fleet.in_orbit_name = star.name
        fleet.tokens[token.design_key] = token
        fleet.fuel_available = fleet.total_fuel_capacity
        empire.owned_fleets[fleet.key] = fleet

        messages.append(Message(
            audience=star.owner,
            text=f"{star.name} has built {count} new {design.name}"
                 f"{'s' if count > 1 else ''}",
            message_type="Star",
            fleet_key=fleet.key
        ))

        return messages
