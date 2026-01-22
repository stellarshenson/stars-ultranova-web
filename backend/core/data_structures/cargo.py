"""
Cargo class for ship cargo holds.
Port of: Common/DataStructures/Cargo.cs
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict

from .resources import Resources, ResourceType
from ..globals import COLONISTS_PER_KILOTON


@dataclass
class Cargo:
    """
    Cargo that may be carried by a ship (if it has a cargo pod).

    Port of: Common/DataStructures/Cargo.cs
    """
    ironium: int = 0
    boranium: int = 0
    germanium: int = 0
    colonists_in_kilotons: int = 0
    silicoxium: int = 0

    @classmethod
    def from_minerals(
        cls,
        ironium: int = 0,
        boranium: int = 0,
        germanium: int = 0,
        colonists_in_kilotons: int = 0,
        silicoxium: int = 0
    ) -> Cargo:
        """Create cargo with specified minerals."""
        return cls(
            ironium=ironium,
            boranium=boranium,
            germanium=germanium,
            colonists_in_kilotons=colonists_in_kilotons,
            silicoxium=silicoxium
        )

    def copy(self) -> Cargo:
        """Create a copy of this Cargo object."""
        return Cargo(
            ironium=self.ironium,
            boranium=self.boranium,
            germanium=self.germanium,
            colonists_in_kilotons=self.colonists_in_kilotons,
            silicoxium=self.silicoxium
        )

    @property
    def colonist_numbers(self) -> int:
        """Gets the amount of actual Colonists in the cargo."""
        # Port of: Cargo.cs lines 139-145
        return self.colonists_in_kilotons * COLONISTS_PER_KILOTON

    @property
    def mass(self) -> int:
        """Get the Mass of the cargo."""
        # Port of: Cargo.cs lines 150-153
        return (
            self.ironium + self.boranium + self.germanium +
            self.colonists_in_kilotons + self.silicoxium
        )

    def __getitem__(self, resource_type: ResourceType) -> int:
        """Array-like access to commodities via ResourceType."""
        # Port of: Cargo.cs lines 158-172
        if resource_type == ResourceType.IRONIUM:
            return self.ironium
        elif resource_type == ResourceType.BORANIUM:
            return self.boranium
        elif resource_type == ResourceType.GERMANIUM:
            return self.germanium
        elif resource_type == ResourceType.COLONISTS_IN_KILOTONS:
            return self.colonists_in_kilotons
        elif resource_type == ResourceType.SILICOXIUM:
            return self.silicoxium
        return 0

    def __setitem__(self, resource_type: ResourceType, value: int) -> None:
        """Array-like assignment via ResourceType."""
        if resource_type == ResourceType.IRONIUM:
            self.ironium = value
        elif resource_type == ResourceType.BORANIUM:
            self.boranium = value
        elif resource_type == ResourceType.GERMANIUM:
            self.germanium = value
        elif resource_type == ResourceType.COLONISTS_IN_KILOTONS:
            self.colonists_in_kilotons = value
        elif resource_type == ResourceType.SILICOXIUM:
            self.silicoxium = value

    def scale(self, scalar: float) -> Cargo:
        """
        Scale cargo by a factor (for splitting cargo or calculating salvage).
        Scalar is clamped to [0, 1].
        """
        # Port of: Cargo.cs lines 214-225
        if scalar > 1:
            scalar = 1
        if scalar < 0:
            scalar = 0
        return Cargo(
            ironium=int(self.ironium * scalar),
            boranium=int(self.boranium * scalar),
            germanium=int(self.germanium * scalar),
            colonists_in_kilotons=int(self.colonists_in_kilotons * scalar),
            silicoxium=int(self.silicoxium * scalar)
        )

    @staticmethod
    def min(left: Cargo, right: Cargo) -> Cargo:
        """Return cargo with minimum of each resource from left and right."""
        # Port of: Cargo.cs lines 277-287
        return Cargo(
            ironium=min(left.ironium, right.ironium),
            boranium=min(left.boranium, right.boranium),
            germanium=min(left.germanium, right.germanium),
            colonists_in_kilotons=min(left.colonists_in_kilotons, right.colonists_in_kilotons),
            silicoxium=min(left.silicoxium, right.silicoxium)
        )

    def add(self, other: Cargo) -> None:
        """Add cargo from another Cargo object (mutates self)."""
        # Port of: Cargo.cs lines 288-295
        self.ironium += other.ironium
        self.boranium += other.boranium
        self.germanium += other.germanium
        self.colonists_in_kilotons += other.colonists_in_kilotons
        self.silicoxium += other.silicoxium

    def remove(self, other: Cargo) -> None:
        """Remove cargo (mutates self)."""
        # Port of: Cargo.cs lines 297-304
        self.ironium -= other.ironium
        self.boranium -= other.boranium
        self.germanium -= other.germanium
        self.colonists_in_kilotons -= other.colonists_in_kilotons
        self.silicoxium -= other.silicoxium

    def clear(self) -> None:
        """Clears all cargo."""
        # Port of: Cargo.cs lines 309-316
        self.ironium = 0
        self.boranium = 0
        self.germanium = 0
        self.colonists_in_kilotons = 0
        self.silicoxium = 0

    def to_resource(self) -> Resources:
        """Returns a Resource object containing the cargo (Colonists excluded)."""
        # Port of: Cargo.cs lines 322-325
        return Resources(
            ironium=self.ironium,
            boranium=self.boranium,
            germanium=self.germanium,
            energy=0,
            silicoxium=self.silicoxium
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "ironium": self.ironium,
            "boranium": self.boranium,
            "germanium": self.germanium,
            "colonists_in_kilotons": self.colonists_in_kilotons,
            "silicoxium": self.silicoxium
        }

    @classmethod
    def from_dict(cls, data: dict) -> Cargo:
        """Create Cargo from dictionary."""
        return cls(
            ironium=data.get("ironium", 0),
            boranium=data.get("boranium", 0),
            germanium=data.get("germanium", 0),
            colonists_in_kilotons=data.get("colonists_in_kilotons", 0),
            silicoxium=data.get("silicoxium", 0)
        )

    def __str__(self) -> str:
        """String representation matching C# CargoTypeConverter."""
        # Port of: Cargo.cs lines 348-356
        return f"{self.ironium},{self.boranium},{self.germanium},{self.colonists_in_kilotons},{self.silicoxium}"
