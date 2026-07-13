"""
Stars Nova Web - Relation Command

No C# command exists for player relations: the WinForms dialog mutates
EmpireIntel.Relation client-side (PlayerRelations.cs:104-120) and the
edit only rides inside the full EmpireData XML of the orders file
(Common/Files/Orders.cs:53,174), which the C# server-side OrderReader
never merges back (OrderReader.cs:114-144 parses only research/
waypoint/design/production/renamefleet). This command is the web
transport for the same client edit.
"""

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from .base import Command, Message

if TYPE_CHECKING:
    from ..data_structures.empire_data import EmpireData


# PlayerRelation enum names (EmpireData.cs:34-39); serialized as the
# name string, matching EmpireIntel XML (EmpireIntel.cs:75-77,115)
VALID_RELATIONS = ("Enemy", "Neutral", "Friend")


@dataclass
class RelationCommand(Command):
    """
    Command to set the empire's relation toward another empire.

    Mirrors PlayerRelations.cs RelationChanged (lines 104-120): writes
    empire_reports[target].relation immediately.
    """
    target_empire_id: int = 0
    relation: str = "Enemy"

    def is_valid(self, empire: 'EmpireData') -> tuple[bool, Optional[Message]]:
        """Validate the relation change."""
        if self.relation not in VALID_RELATIONS:
            msg = Message(
                audience=empire.id,
                text=f"{self.relation} is not a valid player relation",
                message_type="Invalid Command"
            )
            return False, msg

        if (self.target_empire_id == empire.id
                or self.target_empire_id not in empire.empire_reports):
            msg = Message(
                audience=empire.id,
                text=f"Unknown empire {self.target_empire_id}",
                message_type="Invalid Command"
            )
            return False, msg

        # Benign no-op when nothing changes (pattern: ResearchCommand)
        current = empire.empire_reports[self.target_empire_id].get(
            "relation", "Enemy")
        if current == self.relation:
            return False, None

        return True, None

    def apply_to_state(self, empire: 'EmpireData') -> Optional[Message]:
        """Apply the relation change to the acting empire's intel."""
        empire.empire_reports[self.target_empire_id]["relation"] = \
            self.relation
        return None

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "type": "Relation",
            "target_empire_id": self.target_empire_id,
            "relation": self.relation,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'RelationCommand':
        """Deserialize from dictionary."""
        return cls(
            target_empire_id=data.get("target_empire_id", 0),
            relation=data.get("relation", "Enemy"),
        )
