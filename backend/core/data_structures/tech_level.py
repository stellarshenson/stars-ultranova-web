"""
Stars Nova Web - Tech Level
Ported from Common/DataStructures/TechLevel.cs

Technology level requirements for components.
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, Iterator


class ResearchField(IntEnum):
    """Enumeration of different fields of technical research."""
    BIOTECHNOLOGY = 0
    ELECTRONICS = 1
    ENERGY = 2
    PROPULSION = 3
    WEAPONS = 4
    CONSTRUCTION = 5


# String keys used in XML serialization
RESEARCH_KEYS = [
    "Biotechnology", "Electronics", "Energy",
    "Propulsion", "Weapons", "Construction"
]


@dataclass
class TechLevel:
    """
    Class defining the set of technology levels required to access a component.

    Ported from TechLevel.cs.
    """
    levels: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize all tech levels to 0 if not provided."""
        for key in RESEARCH_KEYS:
            if key not in self.levels:
                self.levels[key] = 0

    @classmethod
    def from_values(cls, biotechnology: int = 0, electronics: int = 0,
                    energy: int = 0, propulsion: int = 0,
                    weapons: int = 0, construction: int = 0) -> 'TechLevel':
        """Create TechLevel with specific values."""
        return cls(levels={
            "Biotechnology": biotechnology,
            "Electronics": electronics,
            "Energy": energy,
            "Propulsion": propulsion,
            "Weapons": weapons,
            "Construction": construction
        })

    @classmethod
    def from_level(cls, level: int) -> 'TechLevel':
        """Create TechLevel with all fields set to same value."""
        return cls(levels={key: level for key in RESEARCH_KEYS})

    def __getitem__(self, index: ResearchField) -> int:
        """Get tech level by research field enum."""
        return self.levels[RESEARCH_KEYS[index.value]]

    def __setitem__(self, index: ResearchField, value: int):
        """Set tech level by research field enum."""
        self.levels[RESEARCH_KEYS[index.value]] = value

    def __iter__(self) -> Iterator[int]:
        """Allow foreach iteration over tech levels."""
        for key in RESEARCH_KEYS:
            yield self.levels[key]

    def __ge__(self, other: 'TechLevel') -> bool:
        """Return true if self >= other for all fields."""
        for key in RESEARCH_KEYS:
            if self.levels.get(key, 0) < other.levels.get(key, 0):
                return False
        return True

    def __gt__(self, other: 'TechLevel') -> bool:
        """Return true if self >= other for all fields and > for at least one."""
        return not (self <= other)

    def __lt__(self, other: 'TechLevel') -> bool:
        """Return true if self < other in any field."""
        for key in RESEARCH_KEYS:
            if self.levels.get(key, 0) < other.levels.get(key, 0):
                return True
        return False

    def __le__(self, other: 'TechLevel') -> bool:
        """Return true if self < other in any field or self == other."""
        for key in RESEARCH_KEYS:
            if self.levels.get(key, 0) <= other.levels.get(key, 0):
                return True
        return self.levels == other.levels

    def zero(self):
        """Set all levels to zero."""
        for key in RESEARCH_KEYS:
            self.levels[key] = 0

    def clone(self) -> 'TechLevel':
        """Create a copy of this TechLevel."""
        return TechLevel(levels=dict(self.levels))

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {"levels": dict(self.levels)}

    @classmethod
    def from_dict(cls, data: dict) -> 'TechLevel':
        """Deserialize from dictionary."""
        return cls(levels=dict(data.get("levels", {})))

    def __str__(self) -> str:
        """String representation showing non-zero levels."""
        non_zero = [f"{k}: {v}" for k, v in self.levels.items() if v > 0]
        return ", ".join(non_zero) if non_zero else "None"
