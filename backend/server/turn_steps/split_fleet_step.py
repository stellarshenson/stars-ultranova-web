"""
Stars Nova Web - Split Fleet Step
Ported from ServerState/TurnSteps/SplitFleetStep.cs (118 lines)

Processes fleet split/merge operations and cargo transfers at waypoint zero.
"""

from typing import List, TYPE_CHECKING

from .base import ITurnStep
from ...core.commands.base import Message
from ...core.waypoints.waypoint import WaypointTask, WaypointTaskBase, get_task_type, NoTaskObj, Waypoint

if TYPE_CHECKING:
    from ..server_data import ServerData


class SplitFleetStep(ITurnStep):
    """
    Split/merge fleet turn step.

    The CargoTask and SplitMergeTask commands were pre-processed in sequence
    but not removed (during ParseCommands) to keep indices aligned between
    server and client. This step removes the already processed waypoints.

    Pre-existing waypoint zero tasks are also executed here.

    Ported from SplitFleetStep.cs.
    """

    def process(self, server_state: 'ServerData') -> List[Message]:
        """
        Process split/merge and cargo transfer cleanup.

        Args:
            server_state: Current game state.

        Returns:
            List of messages generated.
        """
        messages: List[Message] = []

        for fleet in server_state.iterate_all_fleets():
            if len(fleet.waypoints) == 0:
                continue

            # Store original waypoint zero for restoration if needed
            original_waypoint = fleet.waypoints[0].copy() if hasattr(fleet.waypoints[0], 'copy') else fleet.waypoints[0]
            waypoint_zero_destination = fleet.waypoints[0].destination

            index = 0
            while index < len(fleet.waypoints) and fleet.waypoints[index].destination == waypoint_zero_destination:
                current_task = get_task_type(fleet.waypoints[index].task)

                if current_task == WaypointTask.SPLIT_MERGE:
                    # Remove waypoints that have already been processed
                    fleet.waypoints.pop(index)
                    # Don't increment index since we removed an element

                elif current_task == WaypointTask.TRANSFER_CARGO:
                    # Check if cargo task is "spent" (amount is 0)
                    cargo_amount = getattr(fleet.waypoints[index], 'cargo_amount', None)
                    if cargo_amount is not None and cargo_amount.mass == 0:
                        # Remove spent waypoints
                        fleet.waypoints.pop(index)
                    else:
                        # Process and remove waypoint zero cargo tasks
                        # This block handles pre-existing cargo tasks
                        cargo_target = getattr(fleet.waypoints[index], 'cargo_target', None)

                        if cargo_target is not None:
                            sender = server_state.all_empires.get(fleet.owner)
                            if sender is not None:
                                # Perform cargo transfer
                                message = self._perform_cargo_transfer(
                                    fleet, cargo_target, sender
                                )
                                if message is not None:
                                    messages.append(message)

                        fleet.waypoints.pop(index)
                else:
                    index += 1

            # Stars! always has at least a NoTask waypoint for current position
            if len(fleet.waypoints) == 0:
                from ...core.waypoints.waypoint import Waypoint
                restored_waypoint = Waypoint(
                    position_x=fleet.position.x,
                    position_y=fleet.position.y,
                    destination=original_waypoint.destination if hasattr(original_waypoint, 'destination') else "",
                    task=WaypointTask.NO_TASK
                )
                fleet.waypoints.append(restored_waypoint)

        # Cleanup empty fleets
        server_state.cleanup_fleets()

        return messages

    def _perform_cargo_transfer(self, fleet, target, sender) -> Message:
        """
        Perform cargo transfer between fleet and target.

        Args:
            fleet: Source fleet.
            target: Target (star or fleet).
            sender: Sending empire.

        Returns:
            Message describing the transfer, or None.
        """
        # Simplified cargo transfer - actual implementation would be more complex
        # based on the cargo task parameters
        return None
