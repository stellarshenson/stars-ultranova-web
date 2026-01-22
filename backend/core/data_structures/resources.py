"""
Resource class representing minerals and energy.
Port of: Common/DataStructures/Resources.cs
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Union
import math


class ResourceType(IntEnum):
    """Types of resources in the game."""
    IRONIUM = 0
    BORANIUM = 1
    GERMANIUM = 2
    ENERGY = 3
    COLONISTS_IN_KILOTONS = 4
    SILICOXIUM = 5


@dataclass
class Resources:
    """
    Resource class which represents the resources needed to construct a game item.
    Individual resource values are either kT (minerals on hand) or percent (mineral concentrations).

    Port of: Common/DataStructures/Resources.cs
    """
    ironium: int = 0
    boranium: int = 0
    germanium: int = 0
    energy: int = 0
    silicoxium: int = 0

    @classmethod
    def from_ibge(cls, i: int, b: int, g: int, e: int) -> Resources:
        """Create Resources with Ironium, Boranium, Germanium, Energy."""
        return cls(ironium=i, boranium=b, germanium=g, energy=e, silicoxium=0)

    def copy(self) -> Resources:
        """Create a copy of this Resources object."""
        return Resources(
            ironium=self.ironium,
            boranium=self.boranium,
            germanium=self.germanium,
            energy=self.energy,
            silicoxium=self.silicoxium
        )

    @property
    def mass(self) -> int:
        """Return the mass of a resource set (Energy does not contribute to mass)."""
        # Port of: Resources.cs line 285-288
        return self.ironium + self.boranium + self.germanium + self.silicoxium

    def __ge__(self, other: Resources) -> bool:
        """See if a resource set is greater than or equal to another."""
        # Port of: Resources.cs lines 93-101
        return (
            self.ironium >= other.ironium and
            self.boranium >= other.boranium and
            self.germanium >= other.germanium and
            self.energy >= other.energy
        )

    def __le__(self, other: Resources) -> bool:
        """See if a resource set is less than or equal to another."""
        # Port of: Resources.cs lines 202-205
        return other >= self

    def __eq__(self, other: object) -> bool:
        """Check if this is equal to another Resources object."""
        # Port of: Resources.cs lines 152-169
        if other is None:
            return False
        if not isinstance(other, Resources):
            return False
        return (
            self.ironium == other.ironium and
            self.boranium == other.boranium and
            self.germanium == other.germanium and
            self.energy == other.energy
        )

    def __hash__(self) -> int:
        """Generate a hash from the commodities."""
        # Port of: Resources.cs lines 194-197
        return self.ironium ^ self.boranium ^ self.germanium ^ self.energy

    def __sub__(self, other: Resources) -> Resources:
        """Subtract one resource set from another."""
        # Port of: Resources.cs lines 210-220
        return Resources(
            ironium=self.ironium - other.ironium,
            boranium=self.boranium - other.boranium,
            germanium=self.germanium - other.germanium,
            energy=self.energy - other.energy,
            silicoxium=self.silicoxium - other.silicoxium
        )

    def __add__(self, other: Resources) -> Resources:
        """Add a resource set to another."""
        # Port of: Resources.cs lines 225-235
        return Resources(
            ironium=self.ironium + other.ironium,
            boranium=self.boranium + other.boranium,
            germanium=self.germanium + other.germanium,
            energy=self.energy + other.energy,
            silicoxium=self.silicoxium + other.silicoxium
        )

    def __mul__(self, other: Union[int, float]) -> Resources:
        """Multiply resources by a scalar."""
        # Port of: Resources.cs lines 237-247 (int) and 265-275 (double)
        if isinstance(other, int):
            return Resources(
                ironium=self.ironium * other,
                boranium=self.boranium * other,
                germanium=self.germanium * other,
                energy=self.energy * other,
                silicoxium=self.silicoxium * other
            )
        else:
            # Rounding can cause one more resource to be consumed than we have
            return Resources(
                ironium=int(math.ceil(self.ironium * other)),
                boranium=int(math.ceil(self.boranium * other)),
                germanium=int(math.ceil(self.germanium * other)),
                energy=int(math.ceil(self.energy * other)),
                silicoxium=int(math.ceil(self.silicoxium * other))
            )

    def __rmul__(self, other: Union[int, float]) -> Resources:
        """Right multiply for scalar * resources."""
        # Port of: Resources.cs lines 259-262, 277-280
        return self * other

    def __truediv__(self, other: Resources) -> float:
        """
        Divide resources by another resource set.
        Returns the minimum ratio across all resource types.
        """
        # Port of: Resources.cs lines 248-258
        i = self.ironium / max(0.1, other.ironium)
        b = self.boranium / max(0.1, other.boranium)
        g = self.germanium / max(0.1, other.germanium)
        e = self.energy / max(0.1, other.energy)
        return min(i, b, g, e)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "ironium": self.ironium,
            "boranium": self.boranium,
            "germanium": self.germanium,
            "energy": self.energy,
            "silicoxium": self.silicoxium
        }

    @classmethod
    def from_dict(cls, data: dict) -> Resources:
        """Create Resources from dictionary."""
        return cls(
            ironium=data.get("ironium", 0),
            boranium=data.get("boranium", 0),
            germanium=data.get("germanium", 0),
            energy=data.get("energy", 0),
            silicoxium=data.get("silicoxium", 0)
        )
