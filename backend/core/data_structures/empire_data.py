"""
Stars Nova Web - Empire Data
Ported from Common/DataStructures/EmpireData.cs (811 lines)

Central data structure holding all empire-specific game state.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, TYPE_CHECKING

from .tech_level import TechLevel
from ..globals import STARTING_YEAR

if TYPE_CHECKING:
    from ..race.race import Race
    from ..game_objects.star import Star
    from ..game_objects.fleet import Fleet
    from ..components.ship_design import ShipDesign


@dataclass
class EmpireData:
    """
    Race-specific data that changes from year to year.

    Contains all owned objects, designs, reports, and settings
    for a single empire (player).

    Ported from EmpireData.cs.
    """
    # Empire identification
    id: int = 0  # 0-127

    # Turn tracking
    turn_year: int = STARTING_YEAR
    turn_submitted: bool = False
    last_turn_submitted: int = 0

    # Race definition
    race: Optional['Race'] = None

    # Research settings
    research_budget: int = 10  # Percentage (0-100)
    research_levels: TechLevel = field(default_factory=TechLevel)
    research_resources: TechLevel = field(default_factory=TechLevel)
    research_topics: TechLevel = field(default_factory=TechLevel)

    # Ship designs
    designs: Dict[int, 'ShipDesign'] = field(default_factory=dict)

    # Owned objects
    owned_stars: Dict[str, 'Star'] = field(default_factory=dict)
    owned_fleets: Dict[int, 'Fleet'] = field(default_factory=dict)

    # Intel reports (what empire knows about others)
    star_reports: Dict[str, dict] = field(default_factory=dict)
    fleet_reports: Dict[int, dict] = field(default_factory=dict)
    empire_reports: Dict[int, dict] = field(default_factory=dict)

    # Temporary storage for fleet splits/merges during turn processing
    temporary_fleets: List['Fleet'] = field(default_factory=list)

    # Battle configuration
    battle_plans: Dict[str, dict] = field(default_factory=dict)
    battle_reports: List[dict] = field(default_factory=list)

    # Visible minefields
    visible_minefields: Dict[int, dict] = field(default_factory=dict)

    # Counters for key generation
    _fleet_counter: int = field(default=0, repr=False)
    _design_counter: int = field(default=0, repr=False)

    # Terraforming capabilities
    gravity_mod_capability: int = 0
    radiation_mod_capability: int = 0
    temperature_mod_capability: int = 0

    def get_next_fleet_key(self) -> int:
        """
        Get the next available fleet key.

        Key structure: bits 0-31 = counter, bits 32-39 = empire ID.

        Ported from EmpireData.cs GetNextFleetKey().
        """
        self._fleet_counter += 1
        return self._fleet_counter | (self.id << 32)

    def get_next_design_key(self) -> int:
        """
        Get the next available design key.

        Key structure: bits 0-31 = counter, bits 32-39 = empire ID.

        Ported from EmpireData.cs GetNextDesignKey().
        """
        self._design_counter += 1
        return self._design_counter | (self.id << 32)

    def add_or_update_fleet(self, fleet: 'Fleet'):
        """
        Add or update a fleet in the owned fleets dictionary.

        Ported from EmpireData.cs AddOrUpdateFleet().
        """
        self.owned_fleets[fleet.key] = fleet

    def has_trait(self, trait_code: str) -> bool:
        """Check if empire's race has a specific trait."""
        if self.race is None:
            return False
        return self.race.has_trait(trait_code)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "turn_year": self.turn_year,
            "turn_submitted": self.turn_submitted,
            "last_turn_submitted": self.last_turn_submitted,
            "research_budget": self.research_budget,
            "research_levels": self.research_levels.to_dict(),
            "research_topics": self.research_topics.to_dict(),
            "gravity_mod_capability": self.gravity_mod_capability,
            "radiation_mod_capability": self.radiation_mod_capability,
            "temperature_mod_capability": self.temperature_mod_capability,
            "_fleet_counter": self._fleet_counter,
            "_design_counter": self._design_counter
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'EmpireData':
        """Deserialize from dictionary."""
        empire = cls(
            id=data.get("id", 0),
            turn_year=data.get("turn_year", STARTING_YEAR),
            turn_submitted=data.get("turn_submitted", False),
            last_turn_submitted=data.get("last_turn_submitted", 0),
            research_budget=data.get("research_budget", 10),
            gravity_mod_capability=data.get("gravity_mod_capability", 0),
            radiation_mod_capability=data.get("radiation_mod_capability", 0),
            temperature_mod_capability=data.get("temperature_mod_capability", 0)
        )
        empire._fleet_counter = data.get("_fleet_counter", 0)
        empire._design_counter = data.get("_design_counter", 0)

        if "research_levels" in data:
            empire.research_levels = TechLevel.from_dict(data["research_levels"])
        if "research_topics" in data:
            empire.research_topics = TechLevel.from_dict(data["research_topics"])

        return empire
