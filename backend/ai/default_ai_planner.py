"""
Stars Nova Web - Default AI Planner
Ported from Nova/Ai/DefaultAIPlanner.cs (443 lines)

AI sub-component to manage planning and state tracking.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, TYPE_CHECKING

from ..core import globals as g

if TYPE_CHECKING:
    from ..core.data_structures.empire_data import EmpireData
    from ..core.game_objects.star import Star
    from ..core.game_objects.fleet import Fleet
    from ..core.components.ship_design import ShipDesign


@dataclass
class DefaultAIPlanner:
    """
    AI planner for state tracking and design selection.

    Tracks counts of various fleet types, production priorities,
    and caches ship designs for building.

    The default AI is stateless - it does not persist any information
    between turns other than what is in an ordinary player's state.

    Ported from DefaultAIPlanner.cs.
    """
    # Constants - ported from DefaultAIPlanner.cs
    EARLY_SCOUTS: int = 5
    LOW_PRODUCTION: int = 100
    MIN_HAB_VALUE: float = 0.05

    # Fleet counts
    scout_count: int = 0
    colonizer_count: int = 0
    transport_count: int = 0
    refueler_count: int = 0
    repairer_count: int = 0
    bomber_count: int = 0
    defender_count: int = 0
    bomber_cover_count: int = 0
    mine_sweeper_count: int = 0
    mine_layer_count: int = 0
    visible_minefields: int = 0

    # Target ratings for invasion planning
    euthanasia_target_rating: int = 0
    euthanasia_target_population: int = 0

    # Production priorities (0-100)
    interceptor_production_priority: int = 5
    starbase_upgrade_priority: int = 30
    coloniser_production_priority: int = 10
    mine_layer_production_priority: int = 5
    mine_sweeper_production_priority: int = 5
    bomber_production_priority: int = 3
    bomber_cover_production_priority: int = 5

    # Cached designs
    current_transport_design: Optional['ShipDesign'] = None
    current_coloniser_design: Optional['ShipDesign'] = None
    current_scout_design: Optional['ShipDesign'] = None
    current_defender_design: Optional['ShipDesign'] = None
    current_bomber_design: Optional['ShipDesign'] = None
    current_bomber_cover_design: Optional['ShipDesign'] = None
    current_refueler_design: Optional['ShipDesign'] = None
    current_repairer_design: Optional['ShipDesign'] = None
    current_mine_layer_design: Optional['ShipDesign'] = None
    current_mine_sweeper_design: Optional['ShipDesign'] = None
    current_starbase_design: Optional['ShipDesign'] = None
    current_minimal_starbase_design: Optional['ShipDesign'] = None

    # Private state
    _total_transport_kt: int = 0
    _planets_to_colonize: int = -1
    _empire_data: Optional['EmpireData'] = None

    def __init__(self, empire_data: 'EmpireData'):
        """
        Initialize the planner with empire data.

        Args:
            empire_data: The empire data to plan for
        """
        self._empire_data = empire_data
        self._reset_counts()

    def _reset_counts(self):
        """Reset all counts to zero."""
        self.scout_count = 0
        self.colonizer_count = 0
        self.transport_count = 0
        self.refueler_count = 0
        self.repairer_count = 0
        self.bomber_count = 0
        self.defender_count = 0
        self.bomber_cover_count = 0
        self.mine_sweeper_count = 0
        self.mine_layer_count = 0
        self._total_transport_kt = 0
        self._planets_to_colonize = -1

    @property
    def total_transport_kt(self) -> int:
        """
        Total capacity of transport fleets in kilotons.

        Ported from DefaultAIPlanner.cs TotalTransportKt property.
        """
        return self._total_transport_kt

    @property
    def surplus_population_kt(self) -> int:
        """
        Calculate surplus population across all planets in kilotons.

        Population above 50% capacity is considered surplus for transport.

        Ported from DefaultAIPlanner.cs SurplusPopulationKT property.
        """
        if self._empire_data is None:
            return 0

        surplus = 0
        race = self._empire_data.race
        for star in self._empire_data.owned_stars.values():
            capacity = star.capacity(race) if race else 0
            if capacity > 50:
                max_pop = star.max_population(race) if race else 0
                surplus += star.colonists - (max_pop // 2)

        return surplus // g.COLONISTS_PER_KILOTON

    @property
    def transport_kt_required(self) -> int:
        """
        Transport capacity required to move surplus population.

        Ported from DefaultAIPlanner.cs TransportKtRequired property.
        """
        return self.surplus_population_kt

    @property
    def planets_to_colonize(self) -> int:
        """
        Count of known planets suitable for colonization.

        Planets must be unowned and have > 5% habitability.

        Ported from DefaultAIPlanner.cs PlanetsToColonize property.
        """
        if self._planets_to_colonize < 0:
            self._planets_to_colonize = 0
            if self._empire_data is None:
                return 0

            race = self._empire_data.race
            for star_report in self._empire_data.star_reports.values():
                owner = star_report.get("owner", g.NOBODY)
                if owner == g.NOBODY:
                    if race:
                        hab_value = self._calc_hab_from_report(race, star_report)
                        if hab_value > self.MIN_HAB_VALUE:
                            self._planets_to_colonize += 1
                    else:
                        # No race info, count all unowned
                        self._planets_to_colonize += 1

        return self._planets_to_colonize

    @property
    def scout_design(self) -> Optional['ShipDesign']:
        """
        Get the current scout design to use.

        Searches for designs with names containing Scout, Long Range Scout,
        or the AI scout prefix.

        Ported from DefaultAIPlanner.cs ScoutDesign property.
        """
        if self.current_scout_design is not None:
            return self.current_scout_design

        if self._empire_data is None:
            return None

        # Search for scout designs in order of preference
        for design in self._empire_data.designs.values():
            if g.AI_SCOUT in design.name:
                self.current_scout_design = design
                return design

        for design in self._empire_data.designs.values():
            if "Long Range Scout" in design.name:
                self.current_scout_design = design
                return design

        for design in self._empire_data.designs.values():
            if "Scout" in design.name:
                self.current_scout_design = design
                return design

        return self.current_scout_design

    @property
    def colonizer_design(self) -> Optional['ShipDesign']:
        """
        Get the current colonizer design to use.

        Prefers designs with highest cargo capacity, then speed.

        Ported from DefaultAIPlanner.cs ColonizerDesign property.
        """
        if self.current_coloniser_design is not None:
            return self.current_coloniser_design

        if self._empire_data is None:
            return None

        colonizers = []
        for design in self._empire_data.designs.values():
            if design.can_colonize:
                colonizers.append(design)

        if not colonizers:
            return None

        # Pick best colonizer: highest cargo, then highest speed
        best = colonizers[0]
        for design in colonizers[1:]:
            if design.cargo_capacity > best.cargo_capacity:
                best = design
            elif design.cargo_capacity == best.cargo_capacity:
                if design.battle_speed > best.battle_speed:
                    best = design

        self.current_coloniser_design = best
        return self.current_coloniser_design

    @property
    def any_transport_design(self) -> Optional['ShipDesign']:
        """
        Get any available transport design.

        Prefers Large Freighter over Medium Freighter.
        Prefers ram scoop engines, then higher optimal speed.

        Ported from DefaultAIPlanner.cs AnyTransportDesign property.
        """
        if self.current_transport_design is not None:
            return self.current_transport_design

        if self._empire_data is None:
            return None

        # Search for Large Freighter first
        transport = self._find_best_freighter("Large Freighter")
        if transport is None:
            transport = self._find_best_freighter("Medium Freighter")

        self.current_transport_design = transport
        return self.current_transport_design

    def _find_best_freighter(self, name_contains: str) -> Optional['ShipDesign']:
        """
        Find the best freighter design containing the given name.

        Prefers ram scoop engines, then higher optimal speed.

        Args:
            name_contains: String that must be in the design name

        Returns:
            Best matching design or None
        """
        if self._empire_data is None:
            return None

        best = None
        for design in self._empire_data.designs.values():
            if name_contains in design.name:
                if best is None:
                    best = design
                    continue

                # Prefer ram scoop engines
                has_ram_scoop = design.engine and design.engine.ram_scoop
                best_has_ram_scoop = best.engine and best.engine.ram_scoop

                if has_ram_scoop and not best_has_ram_scoop:
                    best = design
                elif has_ram_scoop == best_has_ram_scoop:
                    # Compare optimal speed
                    design_speed = design.engine.optimal_speed if design.engine else 0
                    best_speed = best.engine.optimal_speed if best.engine else 0
                    if design_speed > best_speed:
                        best = design

        return best

    @property
    def defense_design(self) -> Optional['ShipDesign']:
        """
        Get the current defense/interceptor design.

        Searches for Cruiser, then Frigate, then Destroyer.

        Ported from DefaultAIPlanner.cs defenseDesign property.
        """
        if self.current_defender_design is not None:
            return self.current_defender_design

        if self._empire_data is None:
            return None

        # Search in order of preference
        for ship_type in ["Cruiser", "Frigate", "Destroyer"]:
            design = self._find_best_armed_ship(ship_type)
            if design:
                self.current_defender_design = design
                return design

        return None

    def _find_best_armed_ship(self, name_contains: str) -> Optional['ShipDesign']:
        """
        Find the best armed ship design containing the given name.

        Prefers ram scoop engines, then higher optimal speed.

        Args:
            name_contains: String that must be in the design name

        Returns:
            Best matching design or None
        """
        if self._empire_data is None:
            return None

        best = None
        for design in self._empire_data.designs.values():
            if name_contains in design.name:
                if best is None:
                    best = design
                    continue

                # Prefer ram scoop engines
                has_ram_scoop = design.engine and design.engine.ram_scoop
                best_has_ram_scoop = best.engine and best.engine.ram_scoop

                if has_ram_scoop and not best_has_ram_scoop:
                    best = design
                elif has_ram_scoop == best_has_ram_scoop:
                    # Compare optimal speed
                    design_speed = design.engine.optimal_speed if design.engine else 0
                    best_speed = best.engine.optimal_speed if best.engine else 0
                    if design_speed > best_speed:
                        best = design

        return best

    def _calc_hab_from_report(self, race: 'Race', report: dict) -> float:
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

    def count_fleet(self, fleet: 'Fleet'):
        """
        Count and classify an owned fleet.

        Updates the appropriate counter based on fleet capabilities.

        Ported from DefaultAIPlanner.cs CountFleet().

        Args:
            fleet: Fleet to classify and count
        """
        if fleet.can_colonize:
            self.colonizer_count += 1
        elif ("Scout" in fleet.name or
              "Long Range Scout" in fleet.name or
              g.AI_SCOUT in fleet.name):
            self.scout_count += 1
        elif g.AI_REFUELER in fleet.name and len(fleet.waypoints) > 1:
            self.refueler_count += 1
        elif g.AI_REPAIRER in fleet.name and len(fleet.waypoints) > 1:
            self.repairer_count += 1
        elif fleet.has_bombers:
            self.bomber_count += 1
        elif fleet.total_cargo_capacity > 0:
            self.transport_count += 1
            self._total_transport_kt += fleet.total_cargo_capacity
        elif (g.AI_DEFENSIVE_BATTLE_CRUISER in fleet.name or
              g.AI_DEFENSIVE_CRUISER in fleet.name or
              g.AI_DEFENSIVE_DESTROYER in fleet.name):
            self.defender_count += 1
