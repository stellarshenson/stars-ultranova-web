"""
Stars Nova Web - Research Command
Ported from Common/Commands/ResearchCommand.cs (124 lines)

Command for changing research budget and topics.
"""

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from .base import Command, CommandMode, Message
from ..data_structures.tech_level import TechLevel

if TYPE_CHECKING:
    from ..data_structures.empire_data import EmpireData


@dataclass
class ResearchCommand(Command):
    """
    Command to modify empire research settings.

    Sets research budget (percentage) and topic priorities.

    Ported from ResearchCommand.cs.
    """
    budget: int = 10  # Percentage of resources to research (0-100)
    topics: TechLevel = None  # Priority weighting for each field

    def __init__(self, budget: int = 10, topics: Optional[TechLevel] = None):
        """
        Initialize research command.

        Args:
            budget: Research budget as percentage (0-100)
            topics: Tech level with priority weights for each field
        """
        self.budget = budget
        # Default: prioritize Energy research
        self.topics = topics if topics else TechLevel(levels={
            "Biotechnology": 0,
            "Electronics": 0,
            "Energy": 1,
            "Propulsion": 0,
            "Weapons": 0,
            "Construction": 0
        })

    def is_valid(self, empire: 'EmpireData') -> tuple[bool, Optional[Message]]:
        """
        Validate the research command.

        Checks budget is in valid range (0-100).
        Returns invalid if nothing changed.

        Ported from ResearchCommand.cs IsValid().
        """
        if self.budget < 0 or self.budget > 100:
            msg = Message(
                audience=empire.id,
                text=f"{self.budget}% is not a valid research percentage",
                message_type="Invalid Command"
            )
            return False, msg

        # Invalidate if nothing changed
        if (self.budget == empire.research_budget and
            self.topics == empire.research_topics):
            return False, None

        return True, None

    def apply_to_state(self, empire: 'EmpireData') -> Optional[Message]:
        """
        Apply research command to empire state.

        Updates research budget and topic priorities.

        Ported from ResearchCommand.cs ApplyToState().
        """
        empire.research_budget = self.budget
        empire.research_topics = self.topics
        return None

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "type": "Research",
            "budget": self.budget,
            "topics": self.topics.to_dict() if self.topics else {}
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ResearchCommand':
        """Deserialize from dictionary."""
        topics = None
        if "topics" in data:
            topics = TechLevel.from_dict(data["topics"])
        return cls(
            budget=data.get("budget", 10),
            topics=topics
        )
