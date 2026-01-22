"""
Stars Nova Web - First Step (Mine Laying)
Ported from ServerState/TurnSteps/FirstStep.cs (108 lines)

Manages mine laying and minefield decay at the start of turn processing.
"""

from typing import List, TYPE_CHECKING

from .base import ITurnStep
from ...core.commands.base import Message
from ...core.globals import MINEFIELD_SNAP_TO_GRID_SIZE
from ...core.waypoints.waypoint import WaypointTask, get_task_type

if TYPE_CHECKING:
    from ..server_data import ServerData, Minefield


class FirstStep(ITurnStep):
    """
    First turn step - handles mine laying and minefield decay.

    Minefields decay 1% each year. Fields of less than 10 mines are removed.

    Ported from FirstStep.cs.
    """

    def process(self, server_state: 'ServerData') -> List[Message]:
        """
        Process mine laying and decay.

        Args:
            server_state: Current game state.

        Returns:
            List of messages generated.
        """
        from ..server_data import Minefield
        from ...core.waypoints.waypoint import WaypointTask

        messages: List[Message] = []

        # Process fleets with LayMines task at waypoint 0
        for fleet in server_state.iterate_all_fleets():
            if len(fleet.waypoints) == 0:
                continue

            waypoint_zero = fleet.waypoints[0]

            # Check if task is LayMinesTask
            task_type = get_task_type(waypoint_zero.task)
            if task_type != WaypointTask.LAY_MINES:
                continue

            # Process each mine type (standard, heavy, speed bump)
            for mine_type in range(3):
                mine_count = 0
                if mine_type == 0:
                    mine_count = getattr(fleet, 'number_of_mines', 0)
                elif mine_type == 1:
                    mine_count = getattr(fleet, 'number_of_heavy_mines', 0)
                elif mine_type == 2:
                    mine_count = getattr(fleet, 'number_of_speed_bump_mines', 0)

                if mine_count <= 0:
                    continue

                # Calculate minefield key based on position grid
                grid_x = int(fleet.position.x / MINEFIELD_SNAP_TO_GRID_SIZE)
                grid_y = int(fleet.position.y / MINEFIELD_SNAP_TO_GRID_SIZE)
                key = (
                    grid_x * 0x10000000 +
                    grid_y +
                    fleet.owner * 0x40000000000000 +
                    mine_type * 0x4000000
                )

                # Check if minefield exists at this location
                if key in server_state.all_minefields:
                    minefield = server_state.all_minefields[key]
                    minefield.number_of_mines += mine_count
                    messages.append(Message(
                        audience=fleet.owner,
                        text=f"{fleet.name} has increased a {minefield.mine_descriptor} "
                             f"minefield by {mine_count} mines.",
                        message_type="Increase Minefield",
                        fleet_key=fleet.key
                    ))
                else:
                    # Create new minefield
                    new_field = Minefield(
                        key=key,
                        owner=fleet.owner,
                        position_x=fleet.position.x,
                        position_y=fleet.position.y,
                        number_of_mines=mine_count,
                        mine_type=mine_type
                    )
                    server_state.all_minefields[key] = new_field
                    messages.append(Message(
                        audience=fleet.owner,
                        text=f"{fleet.name} has created a {new_field.mine_descriptor} "
                             f"minefield with {mine_count} mines.",
                        message_type="New Minefield",
                        fleet_key=fleet.key
                    ))

        # Decay all minefields (1% per year)
        deleted_keys: List[int] = []
        for key, minefield in server_state.all_minefields.items():
            minefield.number_of_mines -= minefield.number_of_mines // 100
            if minefield.number_of_mines <= 10:
                deleted_keys.append(key)

        # Remove depleted minefields
        for key in deleted_keys:
            del server_state.all_minefields[key]

        return messages
