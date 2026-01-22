"""
Production queue and order classes.
Port of: Common/Production/ProductionQueue.cs, ProductionOrder.cs
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
from enum import IntEnum


class ProductionType(IntEnum):
    """Types of items that can be produced."""
    NONE = 0
    FACTORY = 1
    MINE = 2
    DEFENSE = 3
    SHIP = 4
    STARBASE = 5
    TERRAFORM = 6
    ALCHEMY = 7
    PACKET = 8


@dataclass
class ProductionOrder:
    """
    A single production order in the queue.

    Port of: Common/Production/ProductionOrder.cs
    """
    production_type: ProductionType = ProductionType.NONE
    quantity: int = 0
    design_key: Optional[int] = None  # For ships/starbases - reference to design
    name: str = ""
    # Partial completion tracking
    partial_resources_spent: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "production_type": self.production_type.name,
            "quantity": self.quantity,
            "design_key": hex(self.design_key) if self.design_key else None,
            "name": self.name,
            "partial_resources_spent": self.partial_resources_spent
        }

    @classmethod
    def from_dict(cls, data: dict) -> ProductionOrder:
        """Create ProductionOrder from dictionary."""
        order = cls()
        if "production_type" in data:
            order.production_type = ProductionType[data["production_type"]]
        order.quantity = data.get("quantity", 0)
        if data.get("design_key"):
            key_str = data["design_key"]
            order.design_key = int(key_str, 16) if isinstance(key_str, str) else key_str
        order.name = data.get("name", "")
        order.partial_resources_spent = data.get("partial_resources_spent", 0)
        return order


@dataclass
class ProductionQueue:
    """
    Production queue for a star system.

    Port of: Common/Production/ProductionQueue.cs
    """
    orders: List[ProductionOrder] = field(default_factory=list)

    def add(self, order: ProductionOrder) -> None:
        """Add an order to the queue."""
        self.orders.append(order)

    def remove(self, index: int) -> None:
        """Remove an order from the queue."""
        if 0 <= index < len(self.orders):
            del self.orders[index]

    def clear(self) -> None:
        """Clear all orders."""
        self.orders.clear()

    def __len__(self) -> int:
        return len(self.orders)

    def __getitem__(self, index: int) -> ProductionOrder:
        return self.orders[index]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "orders": [order.to_dict() for order in self.orders]
        }

    @classmethod
    def from_dict(cls, data: dict) -> ProductionQueue:
        """Create ProductionQueue from dictionary."""
        queue = cls()
        if "orders" in data:
            queue.orders = [ProductionOrder.from_dict(o) for o in data["orders"]]
        return queue
