"""
Stars Nova Web - Design Command
Ported from Common/Commands/DesignCommand.cs (242 lines)

Command for adding, editing, deleting ship designs.
"""

from dataclasses import dataclass
from typing import Optional, List, TYPE_CHECKING

from .base import Command, CommandMode, Message
from ..components.ship_design import ShipDesign

if TYPE_CHECKING:
    from ..data_structures.empire_data import EmpireData
    from ..game_objects.fleet import Fleet


@dataclass
class DesignCommand(Command):
    """
    Command to modify ship designs.

    Supports Add, Edit (toggle obsolete), Delete operations.

    Ported from DesignCommand.cs.
    """
    design: Optional[ShipDesign] = None
    mode: CommandMode = CommandMode.ADD

    def __init__(self, mode: CommandMode = CommandMode.ADD,
                 design: Optional[ShipDesign] = None,
                 design_key: int = 0):
        """
        Initialize design command.

        Args:
            mode: Command mode (Add, Edit, Delete)
            design: Ship design (full design for Add, key-only for Delete/Edit)
            design_key: Design key (used when design is None)
        """
        self.mode = mode
        if design is not None:
            self.design = design
        else:
            # Create minimal design with just key for delete/edit
            self.design = ShipDesign()
            self.design.key = design_key

    def is_valid(self, empire: 'EmpireData') -> tuple[bool, Optional[Message]]:
        """
        Validate the design command.

        Ported from DesignCommand.cs IsValid().
        """
        if self.design is None:
            msg = Message(
                audience=empire.id,
                text="No design provided",
                message_type="Invalid Command"
            )
            return False, msg

        if self.mode == CommandMode.ADD:
            if self.design.key in empire.designs:
                msg = Message(
                    audience=empire.id,
                    text=f"Can't re-add same design: {self.design.name}",
                    message_type="Invalid Command"
                )
                return False, msg

        elif self.mode == CommandMode.DELETE:
            if self.design.key not in empire.designs:
                msg = Message(
                    audience=empire.id,
                    text=f"Can't delete non-existent design: {self.design.name}",
                    message_type="Invalid Command"
                )
                return False, msg

        elif self.mode == CommandMode.EDIT:
            # Edit toggles obsolete flag - design must exist
            if self.design.key not in empire.designs:
                msg = Message(
                    audience=empire.id,
                    text=f"Can't edit non-existent design: {self.design.name}",
                    message_type="Invalid Command"
                )
                return False, msg

        return True, None

    def apply_to_state(self, empire: 'EmpireData') -> Optional[Message]:
        """
        Apply design command to empire state.

        Ported from DesignCommand.cs ApplyToState().
        """
        if self.design is None:
            return Message(
                audience=empire.id,
                text="No design provided",
                message_type="Error"
            )

        if self.mode == CommandMode.ADD:
            self.design.update()
            empire.designs[self.design.key] = self.design
            return None

        elif self.mode == CommandMode.DELETE:
            if self.design.key in empire.designs:
                del empire.designs[self.design.key]
                self._update_fleet_compositions(empire)
            return None

        elif self.mode == CommandMode.EDIT:
            # Edit toggles the obsolete flag
            if self.design.key in empire.designs:
                old_design = empire.designs[self.design.key]
                old_design.obsolete = not old_design.obsolete
            return None

        return None

    def _update_fleet_compositions(self, empire: 'EmpireData'):
        """
        Remove ships of deleted design from fleets.

        If a fleet becomes empty, it is also removed.

        Ported from DesignCommand.cs UpdateFleetCompositions().
        """
        if self.design is None:
            return

        design_key = self.design.key
        fleets_to_remove = []

        for fleet_key, fleet in empire.owned_fleets.items():
            tokens_to_remove = []

            for token_key, token in fleet.composition.items():
                if token.design.key == design_key:
                    tokens_to_remove.append(token_key)

            for token_key in tokens_to_remove:
                del fleet.composition[token_key]

            if len(fleet.composition) == 0:
                fleets_to_remove.append(fleet_key)

        for fleet_key in fleets_to_remove:
            del empire.owned_fleets[fleet_key]
            if fleet_key in empire.fleet_reports:
                del empire.fleet_reports[fleet_key]

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        result = {
            "type": "Design",
            "mode": self.mode.value
        }
        if self.mode in [CommandMode.DELETE, CommandMode.EDIT]:
            # Only need key for delete/edit
            result["key"] = self.design.key if self.design else 0
        else:
            # Full design for add
            result["design"] = self.design.to_dict() if self.design else None
        return result

    @classmethod
    def from_dict(cls, data: dict) -> 'DesignCommand':
        """Deserialize from dictionary."""
        mode = CommandMode(data.get("mode", "Add"))

        if mode in [CommandMode.DELETE, CommandMode.EDIT]:
            return cls(mode=mode, design_key=data.get("key", 0))
        else:
            design_data = data.get("design")
            design = ShipDesign.from_dict(design_data) if design_data else None
            return cls(mode=mode, design=design)
