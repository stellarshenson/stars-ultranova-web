"""Waypoint task serialization round-trip (DEF-26)."""
import pytest

from backend.core.waypoints.waypoint import (
    TASK_COMMAND_NAMES,
    Waypoint,
    WaypointTask,
    get_task_type,
)


@pytest.mark.parametrize("task_enum", list(WaypointTask))
def test_enum_task_survives_round_trip(task_enum):
    """A waypoint holding a bare enum must not lose its task across a save.

    to_dict used to emit the enum's own name ("LAY_MINES"), which from_dict
    normalizes to "lay_mines" - matching no branch and degrading the order
    to NoTask. Serializing through TASK_COMMAND_NAMES keeps it addressable.
    """
    wp = Waypoint(position_x=1.0, position_y=2.0, task=task_enum)
    restored = Waypoint.from_dict(wp.to_dict())
    assert get_task_type(restored.task) == task_enum


def test_enum_task_serializes_to_command_vocabulary():
    wp = Waypoint(task=WaypointTask.LAY_MINES)
    assert wp.to_dict()["task"]["type"] == TASK_COMMAND_NAMES[WaypointTask.LAY_MINES]
    assert wp.to_dict()["task"]["type"] == "LayMines"
