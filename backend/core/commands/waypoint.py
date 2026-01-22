"""
Stars Nova Web - Waypoint Command
Ported from Common/Commands/WaypointCommand.cs (380 lines)

Command for adding, editing, deleting fleet waypoints.
"""

from dataclasses import dataclass, field
from typing import Optional, List, TYPE_CHECKING

from .base import Command, CommandMode, Message
from ..waypoints.waypoint import Waypoint

if TYPE_CHECKING:
    from ..data_structures.empire_data import EmpireData
    from ..game_objects.fleet import Fleet


@dataclass
class WaypointCommand(Command):
    """
    Command to modify fleet waypoints.

    Supports Add, Edit, Delete, Insert operations on a fleet's
    waypoint list.

    Ported from WaypointCommand.cs.
    """
    waypoint: Optional[Waypoint] = None
    index: int = 0
    mode: CommandMode = CommandMode.ADD
    fleet_key: int = 0
    messages: List[Message] = field(default_factory=list)

    def __init__(self, mode: CommandMode = CommandMode.ADD,
                 waypoint: Optional[Waypoint] = None,
                 fleet_key: int = 0,
                 index: int = 0):
        """
        Initialize waypoint command.

        Args:
            mode: Command mode (Add, Edit, Delete, Insert)
            waypoint: Waypoint to add/edit (None for Delete)
            fleet_key: Key of fleet to modify
            index: Waypoint index for Edit/Delete/Insert
        """
        self.mode = mode
        self.waypoint = waypoint
        self.fleet_key = fleet_key
        self.index = index
        self.messages = []

    def is_valid(self, empire: 'EmpireData') -> tuple[bool, Optional[Message]]:
        """
        Validate the waypoint command.

        Checks that the fleet belongs to the empire.

        Ported from WaypointCommand.cs IsValid().
        """
        if self.fleet_key not in empire.owned_fleets:
            msg = Message(
                audience=empire.id,
                text="Trying to add a Waypoint for a Fleet that you do not own",
                message_type="Invalid Command"
            )
            return False, msg
        return True, None

    def apply_to_state(self, empire: 'EmpireData') -> Optional[Message]:
        """
        Apply waypoint command to empire state.

        Modifies the fleet's waypoint list based on command mode.

        Ported from WaypointCommand.cs ApplyToState().
        """
        fleet = empire.owned_fleets.get(self.fleet_key)
        if fleet is None:
            return Message(
                audience=empire.id,
                text=f"Fleet {self.fleet_key} not found",
                message_type="Error"
            )

        if self.mode == CommandMode.ADD:
            fleet.waypoints.append(self.waypoint)
            return None

        elif self.mode == CommandMode.INSERT:
            if self.index <= len(fleet.waypoints):
                fleet.waypoints.insert(self.index, self.waypoint)
            else:
                fleet.waypoints.append(self.waypoint)
            return None

        elif self.mode == CommandMode.DELETE:
            if self.index < len(fleet.waypoints):
                fleet.waypoints.pop(self.index)
            else:
                return Message(
                    audience=empire.id,
                    text=f"Waypoint index {self.index} out of range",
                    message_type="Invalid Command",
                    fleet_key=self.fleet_key
                )
            return None

        elif self.mode == CommandMode.EDIT:
            # Edit removes then inserts at same index
            if self.index < len(fleet.waypoints):
                fleet.waypoints.pop(self.index)
            if self.index < len(fleet.waypoints):
                fleet.waypoints.insert(self.index, self.waypoint)
            else:
                fleet.waypoints.append(self.waypoint)
            return None

        return None

    def _is_waypoint_zero_command(self, waypoint: Waypoint, fleet: 'Fleet') -> bool:
        """
        Check if waypoint is at the fleet's current location.

        Waypoint zero commands execute immediately (splits, cargo).

        Ported from WaypointCommand.cs isWaypointZeroCommand().
        """
        if not fleet.waypoints:
            return True

        the_index = -1
        for i, wp in enumerate(fleet.waypoints):
            if wp is waypoint:
                the_index = i
                break

        if the_index < 0:
            return False

        destination = fleet.waypoints[0].destination
        pos = fleet.waypoints[0].position

        for i in range(the_index + 1):
            wp = fleet.waypoints[i]
            if wp.destination != destination and wp.position != pos:
                return False

        return True

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        result = {
            "type": "Waypoint",
            "mode": self.mode.value,
            "fleet_key": self.fleet_key,
            "index": self.index
        }
        if self.waypoint:
            result["waypoint"] = self.waypoint.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict) -> 'WaypointCommand':
        """Deserialize from dictionary."""
        mode = CommandMode(data.get("mode", "Add"))
        waypoint = None
        if "waypoint" in data:
            waypoint = Waypoint.from_dict(data["waypoint"])
        return cls(
            mode=mode,
            waypoint=waypoint,
            fleet_key=data.get("fleet_key", 0),
            index=data.get("index", 0)
        )
