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
    ALCHEMY_RESOURCE_COST,
    ALCHEMY_RESOURCE_COST_MA,
    ALCHEMY_MINERALS_PER_UNIT,
    ISB_STARBASE_CLOAK,
)
from ...core.data_structures.tech_level import ResearchField, TechLevel
from ...core.data_structures.resources import Resources
from ...core.research import research_cost
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
        # Per-empire terraform ability cache, reset every process()
        self._terraform_abilities = {}

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
        self._terraform_abilities = {}

        for star in server_state.all_stars.values():
            if star.owner == NOBODY or star.colonists == 0:
                continue

            empire = server_state.all_empires.get(star.owner)
            if empire is None:
                continue

            # Keep race reference linked (needed by all Star math)
            if star.this_race is None:
                star.this_race = empire.race

            # Terraform ability (also refreshes the empire's serialized
            # mod-capability fields once per empire per turn)
            ability = self._get_terraform_ability(empire)

            # CA instaforming: 1 free click per environment variable
            # per year toward optimum, within terraform tech limits.
            # Canonical Stars! CA rule - C# has no implementation
            # (PrimaryTraits.cs:56 is description-only)
            if empire.race is not None and empire.race.primary_trait == "CA":
                from ...services.terraforming import instaform
                shifts = instaform(star, empire.race, ability)
                if shifts:
                    detail = ", ".join(
                        f"{var} {old}->{new}" for var, old, new in shifts)
                    messages.append(Message(
                        audience=star.owner,
                        text=f"{star.name} has been instaformed ({detail})",
                        message_type="Star"
                    ))

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

            # Recompute next year's allocation and resources
            # (StarUpdateStep.cs:85-86)
            star.update_research(empire.research_budget)
            star.update_resources()

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

        Called for EVERY owned star (StarUpdateStep.cs:83); the
        only_leftover flag affects only the allocation computed by
        star.update_research, not this contribution.

        Args:
            star: Contributing star.
            empire: Receiving empire.
        """
        if star.owner == NOBODY:
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
        # The per-field bank is CUMULATIVE (EmpireData.cs:73 "current
        # cumulative resources on technologies"): Research.Cost() is
        # the cumulative threshold to attain a level and TechLevelUp
        # (StarUpdateStep.cs:186-237) never deducts from the bank, so
        # leftover points automatically spill toward the next level.
        # The while loop (StarUpdateStep.cs:125-137) allows multiple
        # level-ups per turn; there is no level cap (the 26 cap is
        # ResearchDialog.cs display-only).
        while True:
            current_level = empire.research_levels.get_level(area)
            next_level = current_level + 1

            # Cost to attain the next level (Research.cs:43-62)
            cost = research_cost(area, empire.race,
                                 empire.research_levels, next_level)

            if empire.research_resources.get_level(area) >= cost:
                # Level up - bank is NOT deducted
                old_levels = empire.research_levels.clone()
                empire.research_levels.set_level(area, next_level)

                self.server_state.all_messages.append(Message(
                    audience=empire.id,
                    text=f"Your scientists have completed research into Tech Level "
                         f"{next_level} in the {area.value} field",
                    message_type="TechAdvance"
                ))

                # Report newly available components and auto-upgrade
                # planetary scanners / defenses
                # (StarUpdateStep.cs:200-236)
                self._report_new_components(empire, old_levels)
            else:
                break

    def _report_new_components(self, empire: 'EmpireData',
                               old_levels: TechLevel):
        """
        Report newly available components and auto-upgrade planetary
        scanner and defense types on every owned star.

        Port of StarUpdateStep.cs TechLevelUp (lines 200-236): a
        component becomes newly available when
        oldResearchLevel < RequiredTech <= newResearchLevel using the
        TechLevel partial ordering (line 204). Documented deviations
        where the C# is a stub:
        - components the race cannot use (RaceRestriction) are
          filtered out (C# reports them regardless);
        - the scanner sweep installs the BEST usable planetary scanner
          and updates scan_range/pen_scan_range (C# lines 217-224
          install whichever scanner just unlocked, with no better-than
          check, and never touch ScanRange - StarMapInitialiser.cs:464
          TODO). The C# guard `ScannerType != string.Empty` is always
          true (the Star default is "None"), so ALL owned stars are
          swept - kept;
        - the defense type ladder is applied (canonical rule; C# never
          upgrades DefenseType - see core/defenses.best_defense_type).
        """
        from ...core.defenses import (
            DEFENSE_BASE_COVERAGE, best_defense_type,
            best_planetary_scanner, race_trait_codes
        )
        from ...core.game_objects.item import ItemType
        from ...services.design_builder import ensure_components_loaded

        loader = ensure_components_loaded()
        new_levels = empire.research_levels
        race_traits = race_trait_codes(empire.race)

        scanner_unlocked = False
        for component in loader.components.values():
            if not (old_levels < component.required_tech
                    and new_levels >= component.required_tech):
                continue
            if not component.is_available_to_race(race_traits):
                continue
            if (component.item_type == ItemType.PLANETARY_INSTALLATIONS
                    and component.has_property("Scanner")):
                # Replacement message emitted once below
                scanner_unlocked = True
                continue
            self.server_state.all_messages.append(Message(
                audience=empire.id,
                text=f"You now have available the {component.name} "
                     f"{component.item_type.name} component",
                message_type="NewComponentMessage"
            ))

        if scanner_unlocked:
            best = best_planetary_scanner(race_traits, new_levels)
            if best is not None:
                replaced = False
                for star in empire.owned_stars.values():
                    if getattr(star, 'scanner_type', "None") == best.name:
                        continue
                    star.scanner_type = best.name
                    star.scan_range = best.scan_range_normal
                    star.pen_scan_range = best.scan_range_penetrating
                    replaced = True
                if replaced:
                    # Message text per StarUpdateStep.cs:213
                    self.server_state.all_messages.append(Message(
                        audience=empire.id,
                        text=f"All existing planetary scanners have been "
                             f"replaced by {best.name}",
                        message_type="NewComponentMessage"
                    ))

        new_best = best_defense_type(new_levels, race_traits)
        upgraded = False
        for star in empire.owned_stars.values():
            current = getattr(star, 'defense_type', "None")
            if (DEFENSE_BASE_COVERAGE.get(new_best, 0.0)
                    > DEFENSE_BASE_COVERAGE.get(current, 0.0)):
                star.defense_type = new_best
                upgraded = True
        if upgraded:
            self.server_state.all_messages.append(Message(
                audience=empire.id,
                text=f"Your planetary defenses have been upgraded "
                     f"to {new_best}",
                message_type="NewComponentMessage"
            ))

    # =========================================================================
    # Manufacturing
    # =========================================================================

    def _get_terraform_ability(self, empire: 'EmpireData') -> dict:
        """Per-empire terraform ability, cached for this turn step."""
        from ...services.terraforming import (
            terraform_ability, update_empire_terraform_capability, VARIABLES
        )
        ability = self._terraform_abilities.get(empire.id)
        if ability is None:
            if empire.race is None:
                ability = {var: (0, 0) for var in VARIABLES}
            else:
                ability = terraform_ability(
                    empire.race, empire.research_levels)
                update_empire_terraform_capability(empire)
            self._terraform_abilities[empire.id] = ability
        return ability

    def _is_skipped(self, order: ProductionOrder, star: 'Star',
                    unit_cost: Optional[Resources],
                    pending: int = 0) -> bool:
        """
        True when the order cannot construct a unit this year.

        Ports each C# unit's IsSkipped exactly. A skipped non-auto
        order blocks the whole queue (ProductionOrder.IsBlocking); a
        skipped auto-build order is passed over with quantity intact.

        C# Construct increments star.Factories/Mines/Defenses per unit
        (FactoryProductionUnit.cs:108-142); the web applies the counts
        in a batch after the order's loop, so `pending` carries the
        units built this pass for the cap comparisons.
        """
        on_hand = star.resources_on_hand

        if order.production_type == ProductionType.FACTORY:
            # FactoryProductionUnit.cs:90-103
            return (star.factories + pending >= star.get_operable_factories()
                    or on_hand.energy <= 0 or on_hand.germanium <= 0)

        if order.production_type == ProductionType.MINE:
            # MineProductionUnit.cs:95-108
            return (star.mines + pending >= star.get_operable_mines()
                    or on_hand.energy <= 0)

        if order.production_type == ProductionType.DEFENSE:
            # DefenseProductionUnit.cs:87-100
            return (star.defenses + pending >= MAX_DEFENSES
                    or on_hand.energy <= 0 or on_hand.ironium <= 0
                    or on_hand.boranium <= 0 or on_hand.germanium <= 0)

        # SHIP/STARBASE (ShipProductionUnit.cs:116-131): skip only when
        # a NEEDED resource is fully exhausted; merely insufficient
        # amounts trigger a partial build instead. The web's
        # energy-only ALCHEMY/TERRAFORM orders (C# units are stubs)
        # take the same shape.
        if unit_cost is None:
            return True
        return ((on_hand.energy <= 0 and unit_cost.energy > 0)
                or (on_hand.germanium <= 0 and unit_cost.germanium > 0)
                or (on_hand.boranium <= 0 and unit_cost.boranium > 0)
                or (on_hand.ironium <= 0 and unit_cost.ironium > 0))

    def _manufacture_items(self, star: 'Star', empire: 'EmpireData') -> List[Message]:
        """
        Process the star's production queue.

        Spends this year's resources (resources_on_hand.energy) and
        surface minerals on queued orders, in queue order. Incomplete
        orders carry partial progress to the next year.

        Loop shape ports Manufacture.cs Items() (lines 50-84): a
        skipped order blocks the queue unless it is auto-build
        (ProductionOrder.IsBlocking, ProductionOrder.cs:96-99);
        skipped auto-build orders persist untouched and processing
        continues with the next order; completed orders (quantity 0,
        auto-build included) are removed after the loop.

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
            if order.production_type == ProductionType.TERRAFORM:
                # TerraformProductionUnit.IsSkipped intent (the C#
                # unit is a stub, TerraformProductionUnit.cs:61-64):
                # when no variable is improvable, spend nothing and
                # drop the order with a completion message
                from ...services.terraforming import select_terraform_target
                ability = self._get_terraform_ability(empire)
                if (empire.race is None
                        or select_terraform_target(
                            star, empire.race, ability) is None):
                    completed_orders.append(order)
                    messages.append(Message(
                        audience=star.owner,
                        text=f"{star.name} has completed terraforming",
                        message_type="Star"
                    ))
                    continue

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

            if self._is_skipped(order, star, unit_cost):
                if not order.is_auto_build:
                    # Skipped non-auto orders block the queue
                    # (Manufacture.cs:56-61, ProductionOrder.cs:96-99)
                    break
                # Auto-build orders never block: skipped with quantity
                # intact, order stays in the queue for next year
                continue

            built = 0
            while order.quantity > 0:
                # Re-check per unit (ProductionOrder.cs:107-126 checks
                # IsSkipped at the top of every unit iteration) so
                # operable/max caps and exhausted resources stop
                # mid-stack
                if self._is_skipped(order, star, unit_cost, built):
                    break

                remaining = unit_cost.energy - order.partial_resources_spent
                spend = min(remaining, star.resources_on_hand.energy)

                if spend < remaining:
                    # Not enough resources to finish this unit - bank progress
                    order.partial_resources_spent += spend
                    star.resources_on_hand.energy -= spend
                    break

                # Check minerals for one unit. Web deviation: C# banks
                # per-resource RemainingCost with proportional mineral
                # spend (FactoryProductionUnit.cs:108-142); the web
                # model banks energy only, minerals are all-or-nothing
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

            if built > 0:
                item_messages = self._create_manufactured_items(
                    order, star, empire, built
                )
                messages.extend(item_messages)

            if order.quantity <= 0:
                completed_orders.append(order)

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
            # Race.cs GetFactoryResources (lines 275-279): factories
            # cost 3 germanium with the CF trait, 4 otherwise
            germanium = 3 if race is not None and race.has_trait("CF") else 4
            return Resources(ironium=0, boranium=0, germanium=germanium,
                             energy=factory_cost)

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

        if order.production_type == ProductionType.TERRAFORM:
            if race is None:
                return None
            from ...services.terraforming import select_terraform_target
            ability = self._get_terraform_ability(empire)
            target = select_terraform_target(star, race, ability)
            if target is None:
                return None
            # Cost per point = resource cost of the best terraform
            # component for the selected variable: 100 resources
            # (dedicated component), 70 for TT races via Total
            # components; no minerals (components.xml Terraforming
            # entries carry only <Energy>). Deviation note: the unit
            # cost is fixed for the year even if the cheapest variable
            # caps out mid-year.
            return Resources(ironium=0, boranium=0, germanium=0,
                             energy=ability[target][1])

        if order.production_type == ProductionType.ALCHEMY:
            # Canonical Stars! rule (AlchemyProductionUnit.cs is a
            # stub): 100 resources per unit, 25 with the MA LRT
            # (GameInitialiser.cs:315-318). Costs no minerals, so it
            # can never be blocked by mineral scarcity
            cost = (ALCHEMY_RESOURCE_COST_MA
                    if race is not None and race.has_trait("MA")
                    else ALCHEMY_RESOURCE_COST)
            return Resources(ironium=0, boranium=0, germanium=0, energy=cost)

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

        elif order.production_type == ProductionType.ALCHEMY:
            # 1 kT of each mineral per completed unit onto the surface
            # (canonical Stars! rule; the C# effect would live in
            # AlchemyProductionUnit.Construct, a stub). Lands after
            # this year's mining (update_minerals runs first), per
            # StarUpdateStep.cs ordering
            star.resources_on_hand.ironium += count * ALCHEMY_MINERALS_PER_UNIT
            star.resources_on_hand.boranium += count * ALCHEMY_MINERALS_PER_UNIT
            star.resources_on_hand.germanium += count * ALCHEMY_MINERALS_PER_UNIT
            messages.append(Message(
                audience=star.owner,
                text=f"{star.name} has transmuted resources into "
                     f"{count} kT of each mineral",
                message_type="Star"
            ))

        elif order.production_type == ProductionType.TERRAFORM:
            # Each completed point shifts the worst improvable
            # environment variable 1 click toward the race optimum
            # (canonical rule; TerraformProductionUnit.cs Construct is
            # a stub). Points beyond the tech cap within this final
            # year's batch are wasted - kept simple and deterministic
            from ...services.terraforming import (
                VARIABLES, terraform_one_point
            )
            ability = self._get_terraform_ability(empire)
            old = {var: getattr(star, var) for var in VARIABLES}
            for _ in range(count):
                if terraform_one_point(star, empire.race, ability) is None:
                    break
            detail = ", ".join(
                f"{var} {old[var]}->{getattr(star, var)}"
                for var in VARIABLES if getattr(star, var) != old[var]
            )
            if detail:
                messages.append(Message(
                    audience=star.owner,
                    text=f"{star.name} has been terraformed ({detail})",
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
            # ISB starbases are built 20% cloaked
            # (Manufacture.cs:126-134: fleet.Cloaked = 20 when the
            # empire's race has the ISB trait)
            if empire.has_trait("ISB"):
                fleet.cloaked = ISB_STARBASE_CLOAK
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
