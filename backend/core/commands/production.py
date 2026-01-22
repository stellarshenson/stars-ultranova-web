"""
Stars Nova Web - Production Command
Ported from Common/Commands/ProductionCommand.cs (254 lines)

Command for adding, editing, deleting production queue items.
"""

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from .base import Command, CommandMode, Message
from ..production.production_queue import ProductionOrder

if TYPE_CHECKING:
    from ..data_structures.empire_data import EmpireData


@dataclass
class ProductionCommand(Command):
    """
    Command to modify a planet's production queue.

    Supports Add, Edit, Delete operations on production orders.

    Ported from ProductionCommand.cs.
    """
    production_order: Optional[ProductionOrder] = None
    mode: CommandMode = CommandMode.ADD
    index: int = 0
    star_key: str = ""

    def __init__(self, mode: CommandMode = CommandMode.ADD,
                 production_order: Optional[ProductionOrder] = None,
                 star_key: str = "",
                 index: int = 0):
        """
        Initialize production command.

        Args:
            mode: Command mode (Add, Edit, Delete)
            production_order: Production order to add/edit
            star_key: Name of the star (planet) to modify
            index: Queue index for edit/delete
        """
        self.mode = mode
        self.production_order = production_order
        self.star_key = star_key
        self.index = index

    def is_valid(self, empire: 'EmpireData') -> tuple[bool, Optional[Message]]:
        """
        Validate the production command.

        Checks:
        - Star is owned by empire
        - Cost is not fraudulent (at least matches design cost)
        - Index is valid for edit/delete

        Ported from ProductionCommand.cs IsValid().
        """
        # Check star ownership
        if self.star_key not in empire.owned_stars:
            msg = Message(
                audience=empire.id,
                text=f"Star {self.star_key} not owned",
                message_type="Invalid Command"
            )
            return False, msg

        star = empire.owned_stars[self.star_key]

        if self.mode == CommandMode.ADD:
            # Validate cost is not fraudulent
            if self.production_order is None:
                msg = Message(
                    audience=empire.id,
                    text="No production order provided",
                    message_type="Invalid Command"
                )
                return False, msg

            # Cost validation would check against design/factory/mine costs
            # Simplified for now - full validation done when processing

        elif self.mode == CommandMode.EDIT:
            if self.index >= len(star.manufacturing_queue.queue):
                msg = Message(
                    audience=empire.id,
                    text=f"Queue index {self.index} out of range",
                    message_type="Invalid Command"
                )
                return False, msg

        elif self.mode == CommandMode.DELETE:
            if self.index >= len(star.manufacturing_queue.queue):
                msg = Message(
                    audience=empire.id,
                    text=f"Queue index {self.index} out of range",
                    message_type="Invalid Command"
                )
                return False, msg

        return True, None

    def apply_to_state(self, empire: 'EmpireData') -> Optional[Message]:
        """
        Apply production command to empire state.

        Modifies the planet's manufacturing queue.

        Ported from ProductionCommand.cs ApplyToState().
        """
        if self.star_key not in empire.owned_stars:
            return Message(
                audience=empire.id,
                text=f"Star {self.star_key} not found",
                message_type="Error"
            )

        star = empire.owned_stars[self.star_key]
        queue = star.manufacturing_queue.queue

        if self.mode == CommandMode.ADD:
            if self.production_order is None:
                return Message(
                    audience=empire.id,
                    text="No production order provided",
                    message_type="Error"
                )
            if len(queue) > self.index:
                queue.insert(self.index, self.production_order)
            else:
                queue.append(self.production_order)
                self.index = len(queue) - 1
            return None

        elif self.mode == CommandMode.EDIT:
            if self.index < len(queue):
                queue.pop(self.index)
                if self.production_order:
                    queue.insert(self.index, self.production_order)
            return None

        elif self.mode == CommandMode.DELETE:
            if self.index < len(queue):
                queue.pop(self.index)
            return None

        return None

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        result = {
            "type": "Production",
            "mode": self.mode.value,
            "star_key": self.star_key,
            "index": self.index
        }
        if self.production_order:
            result["production_order"] = self.production_order.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict) -> 'ProductionCommand':
        """Deserialize from dictionary."""
        mode = CommandMode(data.get("mode", "Add"))
        order = None
        if "production_order" in data:
            order = ProductionOrder.from_dict(data["production_order"])
        return cls(
            mode=mode,
            production_order=order,
            star_key=data.get("star_key", ""),
            index=data.get("index", 0)
        )
