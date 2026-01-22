"""
Mappable class - an object with a position in Nova.
Port of: Common/GameObjects/Mappable.cs
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from .item import Item, ItemType
from ..data_structures import NovaPoint


@dataclass
class Mappable(Item):
    """
    An object which has a position in Nova.

    Port of: Common/GameObjects/Mappable.cs
    """
    position: NovaPoint = field(default_factory=NovaPoint)

    def __post_init__(self):
        """Ensure position is a NovaPoint instance."""
        if self.position is None:
            self.position = NovaPoint()
        elif isinstance(self.position, dict):
            self.position = NovaPoint.from_dict(self.position)

    def copy(self) -> Mappable:
        """Create a copy of this Mappable."""
        # Port of: Mappable.cs lines 50-60
        return Mappable(
            name=self.name,
            item_type=self.item_type,
            _key=self._key,
            position=self.position.copy()
        )

    def distance_to(self, other: Mappable) -> float:
        """Calculate distance to another Mappable."""
        # Port of: Mappable.cs lines 135-138
        return self.position.distance_to(other.position)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        data = super().to_dict()
        data["position"] = self.position.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> Mappable:
        """Create Mappable from dictionary."""
        obj = cls()
        if "key" in data:
            key_str = data["key"]
            obj._key = int(key_str, 16) if isinstance(key_str, str) else key_str
        obj.name = data.get("name")
        if "type" in data:
            obj.item_type = ItemType[data["type"]]
        if "position" in data:
            obj.position = NovaPoint.from_dict(data["position"])
        return obj
