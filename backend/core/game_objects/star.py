"""
Star class representing a star system.
Port of: Common/GameObjects/Star.cs
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Set, Callable, TYPE_CHECKING
import math

from .mappable import Mappable
from .item import ItemType
from ..data_structures import Resources, Cargo, NovaPoint
from ..production import ProductionQueue
from ..globals import (
    COLONISTS_PER_KILOTON,
    COLONISTS_PER_OPERABLE_FACTORY_UNIT,
    COLONISTS_PER_OPERABLE_MINING_UNIT,
    FACTORIES_PER_FACTORY_PRODUCTION_UNIT,
    MINES_PER_MINE_PRODUCTION_UNIT,
    BASE_CROWDING_FACTOR,
    POPULATION_FACTOR_HYPER_EXPANSION,
    GROWTH_FACTOR_HYPER_EXPANSION,
    MAX_DEFENSES
)

if TYPE_CHECKING:
    from ..race import Race


# Observer interface for star updates
StarObserver = Callable[["Star"], None]


@dataclass
class Star(Mappable):
    """
    This object represents a Star system, the basic unit of stars-nova settlement/expansion.

    Port of: Common/GameObjects/Star.cs
    """
    # Orbit flags
    has_fleets_in_orbit: bool = False
    has_refueler_in_orbit: bool = False
    has_free_transport_in_orbit: bool = False

    # Production and resources
    manufacturing_queue: ProductionQueue = field(default_factory=ProductionQueue)
    mineral_concentration: Resources = field(default_factory=Resources)
    resources_on_hand: Resources = field(default_factory=Resources)

    # Starbase reference (Fleet key, not full object to avoid circular deps)
    starbase_key: Optional[int] = None

    # Population and infrastructure
    colonists: int = 0
    _defenses: int = field(default=0, repr=False)
    only_leftover: bool = False  # Use only leftover resources for production
    factories: int = 0
    mines: int = 0
    research_allocation: int = 0
    scan_range: int = 0
    defense_type: str = "None"
    scanner_type: str = "None"

    # Environment values (0-100 percentage of permissible range)
    gravity: int = 0
    radiation: int = 0
    temperature: int = 0
    original_gravity: int = 0
    original_radiation: int = 0
    original_temperature: int = 0

    # Star classification (for visual rendering)
    # Spectral class: O, B, A, F, G, K, M (hottest to coolest)
    # Luminosity class: I (supergiant), II, III (giant), IV (subgiant), V (main sequence)
    spectral_class: str = "G"  # Default to Sun-like
    luminosity_class: str = "V"  # Default to main sequence
    star_temperature: int = 5778  # Kelvin (for color calculation)
    star_radius: float = 1.0  # Solar radii (for size)

    # Reference to owning race (for server convenience)
    this_race: Optional[Race] = field(default=None, repr=False)

    # Observer pattern for UI updates
    _observers: Set[StarObserver] = field(default_factory=set, repr=False)

    def __post_init__(self):
        """Initialize star-specific defaults."""
        super().__post_init__()
        self.item_type = ItemType.STAR
        if self.manufacturing_queue is None:
            self.manufacturing_queue = ProductionQueue()
        if self.mineral_concentration is None:
            self.mineral_concentration = Resources()
        if self.resources_on_hand is None:
            self.resources_on_hand = Resources()

    @property
    def defenses(self) -> int:
        """Get defense count (capped at MAX_DEFENSES)."""
        # Port of: Star.cs lines 526-552
        return min(self._defenses, MAX_DEFENSES)

    @defenses.setter
    def defenses(self, value: int) -> None:
        """Set defense count (capped at MAX_DEFENSES)."""
        self._defenses = min(value, MAX_DEFENSES)

    @property
    def key(self) -> str:
        """Stars use their Name as unique key."""
        # Port of: Star.cs lines 593-599
        return self.name

    # =========================================================================
    # Factory Operations
    # Port of: Star.cs lines 94-170
    # =========================================================================

    def get_operable_factories(self) -> int:
        """
        Determine the number of factories that can be operated.

        Port of: Star.cs lines 94-108
        """
        if self.this_race is None:
            return 0
        return int(
            (self.colonists / COLONISTS_PER_OPERABLE_FACTORY_UNIT) *
            self.this_race.operable_factories
        )

    def get_future_operable_factories(self) -> int:
        """
        Determine the number of factories that can be operated next turn
        considering growth.

        Port of: Star.cs lines 115-126
        """
        if self.this_race is None:
            return 0
        expected_growth = self.calculate_growth(self.this_race)
        return int(
            ((self.colonists + expected_growth) / COLONISTS_PER_OPERABLE_FACTORY_UNIT) *
            self.this_race.operable_factories
        )

    def get_factories_in_use(self) -> int:
        """
        Calculate the number of factories currently operated.

        Port of: Star.cs lines 166-170
        """
        potential_factories = self.get_operable_factories()
        return min(self.factories, potential_factories)

    # =========================================================================
    # Mine Operations
    # Port of: Star.cs lines 128-180
    # =========================================================================

    def get_operable_mines(self) -> int:
        """
        Calculate the number of mines that can be operated.

        Port of: Star.cs lines 132-142
        """
        if self.this_race is None:
            return 0
        return int(
            (self.colonists / COLONISTS_PER_OPERABLE_MINING_UNIT) *
            self.this_race.operable_mines
        )

    def get_future_operable_mines(self) -> int:
        """
        Determine the number of mines that can be operated next turn
        considering growth.

        Port of: Star.cs lines 149-160
        """
        if self.this_race is None:
            return 0
        expected_growth = self.calculate_growth(self.this_race)
        return int(
            ((self.colonists + expected_growth) / COLONISTS_PER_OPERABLE_MINING_UNIT) *
            self.this_race.operable_mines
        )

    def get_mines_in_use(self) -> int:
        """
        Calculate the number of mines currently operated.

        Port of: Star.cs lines 176-180
        """
        potential_mines = self.get_operable_mines()
        return min(self.mines, potential_mines)

    # =========================================================================
    # Resource Generation
    # Port of: Star.cs lines 186-265
    # =========================================================================

    def get_resource_rate(self) -> int:
        """
        Calculate the amount of resources currently generated.

        Port of: Star.cs lines 186-199
        """
        if self.this_race is None or self.colonists <= 0:
            return 0

        factories_in_use = self.get_factories_in_use()

        # Resources from colonists
        rate = int(self.colonists / self.this_race.colonists_per_resource)

        # Resources from factories
        rate += int(
            (factories_in_use / FACTORIES_PER_FACTORY_PRODUCTION_UNIT) *
            self.this_race.factory_production
        )

        return rate

    def get_future_resource_rate(self, extra_factories: int) -> int:
        """
        Calculate the amount of resources generated next turn accounting
        for growth and factory production.

        Port of: Star.cs lines 206-221
        """
        if self.this_race is None or self.colonists <= 0:
            return 0

        potential_factories = self.get_future_operable_factories()
        expected_growth = self.calculate_growth(self.this_race)
        factories_in_use = min(self.factories + extra_factories, potential_factories)

        rate = int(
            (self.colonists + expected_growth) / self.this_race.colonists_per_resource
        )
        rate += int(
            (factories_in_use / FACTORIES_PER_FACTORY_PRODUCTION_UNIT) *
            self.this_race.factory_production
        )

        return rate

    def get_mining_rate(self, concentration: int) -> int:
        """
        Calculate the amount of kT of minerals that can currently be mined.

        Port of: Star.cs lines 227-242
        """
        if self.this_race is None:
            return 0

        mines_in_use = self.get_mines_in_use()

        # Float conversion required to avoid zero from integer division
        rate = int(
            ((mines_in_use / MINES_PER_MINE_PRODUCTION_UNIT) *
             self.this_race.mine_production_rate) *
            (concentration / 100.0)
        )
        return rate

    def get_future_mining_rate(self, concentration: int, extra_mines: int) -> int:
        """
        Calculate the amount of kT of minerals that can be mined considering
        additional mines.

        Port of: Star.cs lines 249-265
        """
        if self.this_race is None:
            return 0

        potential_mines = self.get_future_operable_mines()
        mines_in_use = min(self.mines + extra_mines, potential_mines)

        rate = int(
            ((mines_in_use / MINES_PER_MINE_PRODUCTION_UNIT) *
             self.this_race.mine_production_rate) *
            (concentration / 100.0)
        )
        return rate

    # =========================================================================
    # Population and Growth
    # Port of: Star.cs lines 272-416
    # =========================================================================

    def max_population(self, race: Race) -> int:
        """
        Calculate the max population for this star given a race.

        Port of: Star.cs lines 272-291
        """
        if race.has_trait("AR"):
            # AR races have population limited by starbase
            # TODO: Need starbase.max_population when starbase reference is resolved
            return 0

        max_pop = float(race.max_population)

        if race.has_trait("HyperExpansion"):
            max_pop *= POPULATION_FACTOR_HYPER_EXPANSION

        # Negative hab worlds have reduced max population
        if race.hab_value(self) < 0.0:
            max_pop = 250000.0

        return int(max_pop)

    def capacity(self, race: Race) -> int:
        """
        Calculate the utilized capacity (as a percentage).

        Port of: Star.cs lines 299-317
        """
        max_pop = float(race.max_population)

        if race.has_trait("HyperExpansion"):
            max_pop *= POPULATION_FACTOR_HYPER_EXPANSION

        # Negative hab worlds
        if race.hab_value(self) < 0.0:
            max_pop = 25000.0

        capacity_pct = (self.colonists / max_pop) * 100
        return int(math.ceil(capacity_pct))

    def calculate_growth(self, race: Race) -> int:
        """
        Calculates the growth for the star.

        Port of: Star.cs lines 327-385
        """
        hab_value = race.hab_value(self)
        growth_rate = race.growth_rate

        if race.has_trait("HyperExpansion"):
            growth_rate *= GROWTH_FACTOR_HYPER_EXPANSION

        population_growth = 0.0
        capacity_pct = self.capacity(race) / 100.0

        if hab_value < 0.0:
            # Negative hab planet - population dies
            # Port of: Star.cs lines 341-345
            population_growth = 0.1 * self.colonists * hab_value
        elif capacity_pct < 0.25:
            # Low pop planet - full growth rate
            # Port of: Star.cs lines 346-350
            population_growth = self.colonists * growth_rate / 100.0 * hab_value
        elif 0.25 <= capacity_pct < 1.0:
            # Early crowding - reduced growth
            # Port of: Star.cs lines 351-357
            population_growth = self.colonists * growth_rate / 100.0 * hab_value
            crowding_factor = BASE_CROWDING_FACTOR * (1.0 - capacity_pct) ** 2
            population_growth *= crowding_factor
        elif capacity_pct == 1.0:
            # Full planet - no growth
            # Port of: Star.cs lines 358-362
            population_growth = 0
        elif 1.0 < capacity_pct < 4.0:
            # Over full planet - population dies
            # Port of: Star.cs lines 363-367
            population_growth = self.colonists * (capacity_pct - 1) * -4.0 / 100.0
        else:  # capacity >= 4.0
            # Very over full planet - crowding deaths cap at 12%
            # Port of: Star.cs lines 368-372
            population_growth = self.colonists * -0.12

        # Minimal colonist growth unit is 100 colonists
        # Port of: Star.cs lines 380-383
        final_growth = int(population_growth)
        final_growth = (final_growth // 100) * 100

        return final_growth

    def min_value(self, race: Race) -> int:
        """
        The unterraformed percentage value (% of Max growth rate).

        Port of: Star.cs lines 393-404
        """
        hab_value = race.hab_value(self)
        growth_rate = race.growth_rate

        if race.has_trait("HyperExpansion"):
            growth_rate *= GROWTH_FACTOR_HYPER_EXPANSION

        min_val = growth_rate * 100.0 * hab_value
        return int(min_val)

    def update_population(self, race: Race) -> None:
        """
        Update the population of a star system.

        Port of: Star.cs lines 413-416
        """
        self.colonists += self.calculate_growth(race)

    # =========================================================================
    # Resource Updates
    # Port of: Star.cs lines 418-524
    # =========================================================================

    def update_research(self, budget: int) -> None:
        """
        Updates the research allocation for the star.

        Port of: Star.cs lines 422-435
        """
        if not self.only_leftover:
            if 0 <= budget <= 100:
                self.research_allocation = (self.get_resource_rate() * budget) // 100
        else:
            self.research_allocation = 0

    def update_resources(self) -> None:
        """
        Update the resources available to a star system.

        Port of: Star.cs lines 443-461
        """
        self.resources_on_hand.energy = self.get_resource_rate()
        self.resources_on_hand.energy -= self.research_allocation

    def update_minerals(self) -> None:
        """
        Update the minerals available on a star system.

        Port of: Star.cs lines 469-474
        """
        self.resources_on_hand.ironium += self._mine_mineral("ironium")
        self.resources_on_hand.boranium += self._mine_mineral("boranium")
        self.resources_on_hand.germanium += self._mine_mineral("germanium")

    def _mine_mineral(self, mineral_type: str) -> int:
        """
        Mine minerals and update concentration.

        Port of: Star.cs lines 491-524
        """
        concentration = getattr(self.mineral_concentration, mineral_type)
        mined = self.get_mining_rate(concentration)

        # Reduce mineral concentration
        # Concentration drops by 1 point after 12500/concentration kT mined
        if concentration > 0:
            new_concentration = concentration - (mined * concentration // 12500)
            if new_concentration < 1:
                new_concentration = 1
            setattr(self.mineral_concentration, mineral_type, new_concentration)

        return mined

    # =========================================================================
    # Cargo Operations
    # Port of: Star.cs lines 554-570
    # =========================================================================

    def add_cargo(self, cargo: Cargo) -> None:
        """
        Add cargo to the star.

        Port of: Star.cs lines 554-561
        """
        self.resources_on_hand.ironium += cargo.ironium
        self.resources_on_hand.boranium += cargo.boranium
        self.resources_on_hand.germanium += cargo.germanium
        self.colonists += cargo.colonist_numbers
        self._notify_observers()

    def remove_cargo(self, cargo: Cargo) -> None:
        """
        Remove cargo from the star.

        Port of: Star.cs lines 563-570
        """
        self.resources_on_hand.ironium -= cargo.ironium
        self.resources_on_hand.boranium -= cargo.boranium
        self.resources_on_hand.germanium -= cargo.germanium
        self.colonists -= cargo.colonist_numbers
        self._notify_observers()

    # =========================================================================
    # Observer Pattern
    # Port of: Star.cs lines 572-588
    # =========================================================================

    def add_observer(self, observer: StarObserver) -> None:
        """Add an observer for star updates."""
        self._observers.add(observer)

    def remove_observer(self, observer: StarObserver) -> None:
        """Remove an observer."""
        self._observers.discard(observer)

    def _notify_observers(self) -> None:
        """Notify all observers of an update."""
        for observer in self._observers:
            observer(self)

    # =========================================================================
    # Serialization
    # =========================================================================

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        data = super().to_dict()
        data.update({
            "has_fleets_in_orbit": self.has_fleets_in_orbit,
            "has_refueler_in_orbit": self.has_refueler_in_orbit,
            "has_free_transport_in_orbit": self.has_free_transport_in_orbit,
            "manufacturing_queue": self.manufacturing_queue.to_dict(),
            "mineral_concentration": self.mineral_concentration.to_dict(),
            "resources_on_hand": self.resources_on_hand.to_dict(),
            "starbase_key": hex(self.starbase_key) if self.starbase_key else None,
            "colonists": self.colonists,
            "defenses": self.defenses,
            "only_leftover": self.only_leftover,
            "factories": self.factories,
            "mines": self.mines,
            "research_allocation": self.research_allocation,
            "scan_range": self.scan_range,
            "defense_type": self.defense_type,
            "scanner_type": self.scanner_type,
            "gravity": self.gravity,
            "radiation": self.radiation,
            "temperature": self.temperature,
            "original_gravity": self.original_gravity,
            "original_radiation": self.original_radiation,
            "original_temperature": self.original_temperature,
            "this_race_name": self.this_race.name if self.this_race else None
        })
        return data

    @classmethod
    def from_dict(cls, data: dict) -> Star:
        """Create Star from dictionary."""
        star = cls()

        # Item fields
        if "key" in data:
            key_str = data["key"]
            star._key = int(key_str, 16) if isinstance(key_str, str) else key_str
        star.name = data.get("name")
        if "type" in data:
            star.item_type = ItemType[data["type"]]

        # Mappable fields
        if "position" in data:
            star.position = NovaPoint.from_dict(data["position"])

        # Star-specific fields
        star.has_fleets_in_orbit = data.get("has_fleets_in_orbit", False)
        star.has_refueler_in_orbit = data.get("has_refueler_in_orbit", False)
        star.has_free_transport_in_orbit = data.get("has_free_transport_in_orbit", False)

        if "manufacturing_queue" in data:
            star.manufacturing_queue = ProductionQueue.from_dict(data["manufacturing_queue"])
        if "mineral_concentration" in data:
            star.mineral_concentration = Resources.from_dict(data["mineral_concentration"])
        if "resources_on_hand" in data:
            star.resources_on_hand = Resources.from_dict(data["resources_on_hand"])

        if data.get("starbase_key"):
            key_str = data["starbase_key"]
            star.starbase_key = int(key_str, 16) if isinstance(key_str, str) else key_str

        star.colonists = data.get("colonists", 0)
        star._defenses = data.get("defenses", 0)
        star.only_leftover = data.get("only_leftover", False)
        star.factories = data.get("factories", 0)
        star.mines = data.get("mines", 0)
        star.research_allocation = data.get("research_allocation", 0)
        star.scan_range = data.get("scan_range", 0)
        star.defense_type = data.get("defense_type", "None")
        star.scanner_type = data.get("scanner_type", "None")

        star.gravity = data.get("gravity", 0)
        star.radiation = data.get("radiation", 0)
        star.temperature = data.get("temperature", 0)
        star.original_gravity = data.get("original_gravity", 0)
        star.original_radiation = data.get("original_radiation", 0)
        star.original_temperature = data.get("original_temperature", 0)

        return star

    def __str__(self) -> str:
        """String representation."""
        return f"Star: {self.name}"
