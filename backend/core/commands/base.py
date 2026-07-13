"""
Stars Nova Web - Command Base Classes
Ported from Common/Commands/ICommand.cs

Command pattern for player actions that modify game state.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..data_structures.empire_data import EmpireData


class CommandMode(Enum):
    """
    Mode of command operation.

    Ported from ICommand.cs CommandMode enum.
    """
    ADD = "Add"
    EDIT = "Edit"
    DELETE = "Delete"
    INSERT = "Insert"
    # Web addition (no C# equivalent): queue reorder as a single
    # server-side move. C# reorders via two Edit commands carrying full
    # client-side orders (ProductionDialog.cs:365-406, QueueList.cs:113-132)
    MOVE = "Move"


@dataclass
class Message:
    """
    Message returned from command validation/execution.

    Ported from Message.cs (simplified).
    """
    audience: int = 0  # Empire ID or -1 for everyone
    text: str = ""
    message_type: str = ""
    fleet_key: int = 0

    def __init__(self, audience: int = 0, text: str = "",
                 message_type: str = "", fleet_key: int = 0):
        self.audience = audience
        self.text = text
        self.message_type = message_type
        self.fleet_key = fleet_key

    def __str__(self) -> str:
        return self.text

    def to_dict(self) -> dict:
        return {
            "audience": self.audience,
            "text": self.text,
            "type": self.message_type,
            "fleet_key": self.fleet_key,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Message':
        return cls(
            audience=data.get("audience", 0),
            text=data.get("text", ""),
            message_type=data.get("type", ""),
            fleet_key=data.get("fleet_key", 0),
        )


class Command(ABC):
    """
    Base class for all player commands.

    Implements the ICommand interface from C#.
    Commands represent player orders that are applied to game state
    during turn processing.

    Ported from ICommand.cs.
    """

    @abstractmethod
    def is_valid(self, empire: 'EmpireData') -> tuple[bool, Optional[Message]]:
        """
        Validate command against empire state.

        Args:
            empire: The empire data to validate against

        Returns:
            Tuple of (is_valid, optional_message)
        """
        pass

    @abstractmethod
    def apply_to_state(self, empire: 'EmpireData') -> Optional[Message]:
        """
        Apply command to empire state.

        Args:
            empire: The empire data to modify

        Returns:
            Optional message (errors or info)
        """
        pass

    @abstractmethod
    def to_dict(self) -> dict:
        """Serialize command to dictionary."""
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict) -> 'Command':
        """Deserialize command from dictionary."""
        pass
