"""
Item base class for most game items.
Port of: Common/GameObjects/Item.cs
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

from ..globals import NOBODY


class ItemType(IntEnum):
    """Lists all possible item Types."""
    # Port of: Common/GameObjects/ItemType.cs
    NONE = 0
    DEFENSE = 1
    PLANETARY_INSTALLATIONS = 2
    HULL = 3
    ENGINE = 4
    MECHANICAL = 5
    ELECTRICAL = 6
    SCANNER = 7
    TERRAFORMING = 8
    ORBITAL = 9
    GATE = 10
    MINING_ROBOT = 11
    MINE_LAYER = 12
    SHIELD = 13
    ARMOR = 14
    BOMB = 15
    WEAPON = 16
    BEAM_WEAPONS = 17
    TORPEDOES = 18
    SHIP = 19
    STARBASE = 20
    FLEET = 21
    STAR = 22
    STAR_INTEL = 23
    FLEET_INTEL = 24
    SALVAGE = 25

    def to_description(self) -> str:
        """Return human-readable description."""
        descriptions = {
            ItemType.PLANETARY_INSTALLATIONS: "Planetary Installations",
            ItemType.MINING_ROBOT: "Mining Robot",
            ItemType.MINE_LAYER: "Mine Layer",
            ItemType.BEAM_WEAPONS: "Beam Weapons",
            ItemType.STAR_INTEL: "Star Report",
            ItemType.FLEET_INTEL: "Fleet Report",
        }
        return descriptions.get(self, self.name.replace("_", " ").title())


# Key manipulation constants
# Port of: Common/GameObjects/KeyExtensions.cs
_ID_MASK = 0x00000000FFFFFFFF
_OWNER_MASK = 0x000000FF00000000


def key_owner(key: int) -> int:
    """Extract owner ID from key (bits 25-32)."""
    return (key & _OWNER_MASK) >> 32


def key_id(key: int) -> int:
    """Extract item ID from key (bits 33-64)."""
    return key & _ID_MASK


def key_set_owner(key: int, owner: int) -> int:
    """Set owner ID in key."""
    if owner > 0xFF or owner < 0:
        raise ValueError("OwnerId out of range")
    key &= _ID_MASK
    key |= owner << 32
    return key


def key_set_id(key: int, item_id: int) -> int:
    """Set item ID in key."""
    if item_id > _ID_MASK or item_id < 0:
        raise ValueError("ItemId out of range")
    key &= _OWNER_MASK
    key |= item_id
    return key


@dataclass
class Item:
    """
    Base class for most game items.

    Key structure (64-bit):
    - Bit 1: Sign (negative values reserved for special flags)
    - Bits 2-24: Reserved
    - Bits 25-32: Empire/Owner ID
    - Bits 33-64: Item ID (client-generated, unique per empire)

    Port of: Common/GameObjects/Item.cs
    """
    name: Optional[str] = None
    item_type: ItemType = ItemType.NONE
    _key: int = field(default=NOBODY, repr=False)

    @property
    def key(self) -> int:
        """Game-wide unique key."""
        return self._key

    @key.setter
    def key(self, value: int) -> None:
        """Set the key (must be non-negative)."""
        if value < 0:
            raise ValueError("Key must be non-negative")
        self._key = value

    @property
    def owner(self) -> int:
        """Owner empire ID (bits 25-32 of key)."""
        # Port of: Item.cs lines 84-89
        return key_owner(self._key)

    @owner.setter
    def owner(self, value: int) -> None:
        """Set owner empire ID."""
        self._key = key_set_owner(self._key, value)

    @property
    def id(self) -> int:
        """Item ID within owner's empire (bits 33-64 of key)."""
        # Port of: Item.cs lines 101-106
        return key_id(self._key)

    @id.setter
    def id(self, value: int) -> None:
        """Set item ID."""
        self._key = key_set_id(self._key, value)

    def copy(self) -> Item:
        """Create a copy of this Item."""
        return Item(
            name=self.name,
            item_type=self.item_type,
            _key=self._key
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "key": hex(self._key),
            "name": self.name,
            "type": self.item_type.name
        }

    @classmethod
    def from_dict(cls, data: dict) -> Item:
        """Create Item from dictionary."""
        item = cls()
        if "key" in data:
            key_str = data["key"]
            item._key = int(key_str, 16) if isinstance(key_str, str) else key_str
        item.name = data.get("name")
        if "type" in data:
            item.item_type = ItemType[data["type"]]
        return item
