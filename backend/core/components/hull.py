"""
Stars Nova Web - Hull
Ported from Common/Components/Hull.cs

Hull component property defining ship structure and module slots.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from .hull_module import HullModule


@dataclass
class Hull:
    """
    Hull component property with module slots for fitting components.

    Each hull defines:
    - Base stats (fuel, cargo, armor)
    - Module slots for fitting other components
    - Special capabilities (dock, refuel, heal)

    Ported from Hull.cs.
    """
    modules: List[HullModule] = field(default_factory=list)
    fuel_capacity: int = 0
    dock_capacity: int = 0
    base_cargo: int = 0
    ar_max_pop: int = 0  # Artificial Reality max population
    armor_strength: int = 0
    battle_initiative: int = 0
    heals_others_percent: int = 0

    @property
    def is_starbase(self) -> bool:
        """
        Determine if this is a starbase hull.

        Starbases have 0 fuel capacity (they don't move).
        """
        return self.fuel_capacity == 0

    @property
    def can_refuel(self) -> bool:
        """
        Determine if this starbase can refuel ships.

        Must be a starbase with dock capacity.
        """
        return self.fuel_capacity == 0 and self.dock_capacity > 0

    def clone(self) -> 'Hull':
        """Create a deep copy of this hull."""
        return Hull(
            modules=[m.clone() for m in self.modules],
            fuel_capacity=self.fuel_capacity,
            dock_capacity=self.dock_capacity,
            base_cargo=self.base_cargo,
            ar_max_pop=self.ar_max_pop,
            armor_strength=self.armor_strength,
            battle_initiative=self.battle_initiative,
            heals_others_percent=self.heals_others_percent
        )

    def get_module_by_cell(self, cell_number: int) -> Optional[HullModule]:
        """Get a module by its cell number."""
        for module in self.modules:
            if module.cell_number == cell_number:
                return module
        return None

    def get_modules_by_type(self, component_type: str) -> List[HullModule]:
        """Get all modules that accept a given component type."""
        return [m for m in self.modules if m.component_type == component_type]

    def clear_all_modules(self):
        """Remove all allocated components from all modules."""
        for module in self.modules:
            module.empty()

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "fuel_capacity": self.fuel_capacity,
            "dock_capacity": self.dock_capacity,
            "base_cargo": self.base_cargo,
            "ar_max_pop": self.ar_max_pop,
            "armor_strength": self.armor_strength,
            "battle_initiative": self.battle_initiative,
            "heals_others_percent": self.heals_others_percent,
            "modules": [m.to_dict() for m in self.modules]
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Hull':
        """Deserialize from dictionary."""
        hull = cls(
            fuel_capacity=data.get("fuel_capacity", 0),
            dock_capacity=data.get("dock_capacity", 0),
            base_cargo=data.get("base_cargo", 0),
            ar_max_pop=data.get("ar_max_pop", 0),
            armor_strength=data.get("armor_strength", 0),
            battle_initiative=data.get("battle_initiative", 0),
            heals_others_percent=data.get("heals_others_percent", 0),
            modules=[]
        )
        for module_data in data.get("modules", []):
            hull.modules.append(HullModule.from_dict(module_data))
        return hull

    # Operator overloads - hulls don't add or scale in Stars!
    def add(self, other: 'Hull'):
        """Hulls don't add - no-op."""
        pass

    def scale(self, scalar: int):
        """Hulls don't scale - no-op."""
        pass
