"""
Waypoint and waypoint task classes.
Port of: Common/Waypoints/Waypoint.cs and related task files
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional, Union, TYPE_CHECKING

from ..data_structures import NovaPoint, Cargo

if TYPE_CHECKING:
    from ..game_objects import Mappable


class CargoMode(IntEnum):
    """Mode for cargo transfer tasks."""
    LOAD = 0
    UNLOAD = 1
    SET = 2


class WaypointTask(IntEnum):
    """Enumeration of waypoint task types for quick comparison."""
    NO_TASK = 0
    TRANSFER_CARGO = 1
    COLONIZE = 2
    LAY_MINES = 3
    INVADE = 4
    SCRAP = 5
    SPLIT_MERGE = 6


class WaypointTaskBase(ABC):
    """Base class for waypoint task objects with parameters."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Task name for serialization."""
        pass

    @property
    @abstractmethod
    def task_type(self) -> WaypointTask:
        """Task type enum for quick comparison."""
        pass

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {"type": self.name}

    @classmethod
    def from_dict(cls, data: dict) -> 'WaypointTaskBase':
        """Create task from dictionary."""
        task_type = data.get("type", "NoTask")
        if task_type == "CargoTask":
            return CargoTaskObj.from_dict(data)
        elif task_type == "ColoniseTask":
            return ColoniseTaskObj.from_dict(data)
        elif task_type == "LayMinesTask":
            return LayMinesTaskObj.from_dict(data)
        elif task_type == "InvadeTask":
            return InvadeTaskObj.from_dict(data)
        elif task_type == "ScrapTask":
            return ScrapTaskObj.from_dict(data)
        elif task_type == "SplitMergeTask":
            return SplitMergeTaskObj.from_dict(data)
        return NoTaskObj()


@dataclass
class NoTaskObj(WaypointTaskBase):
    """No task - just travel to waypoint."""

    @property
    def name(self) -> str:
        return "NoTask"

    @property
    def task_type(self) -> WaypointTask:
        return WaypointTask.NO_TASK


# Backwards compatibility alias
NoTask = NoTaskObj


@dataclass
class CargoTaskObj(WaypointTaskBase):
    """
    Cargo transfer task.
    Port of: Common/Waypoints/CargoTask.cs
    """
    mode: CargoMode = CargoMode.LOAD
    amount: Cargo = field(default_factory=Cargo)
    target_name: Optional[str] = None

    @property
    def name(self) -> str:
        return "CargoTask"

    @property
    def task_type(self) -> WaypointTask:
        return WaypointTask.TRANSFER_CARGO

    def to_dict(self) -> dict:
        return {
            "type": self.name,
            "mode": self.mode.name,
            "amount": self.amount.to_dict(),
            "target_name": self.target_name
        }

    @classmethod
    def from_dict(cls, data: dict) -> CargoTaskObj:
        task = cls()
        if "mode" in data:
            task.mode = CargoMode[data["mode"]]
        if "amount" in data:
            task.amount = Cargo.from_dict(data["amount"])
        task.target_name = data.get("target_name")
        return task


# Backwards compatibility alias
CargoTask = CargoTaskObj


@dataclass
class ColoniseTaskObj(WaypointTaskBase):
    """
    Colonization task.
    Port of: Common/Waypoints/ColoniseTask.cs
    """

    @property
    def name(self) -> str:
        return "ColoniseTask"

    @property
    def task_type(self) -> WaypointTask:
        return WaypointTask.COLONIZE

    @classmethod
    def from_dict(cls, data: dict) -> ColoniseTaskObj:
        return cls()


# Backwards compatibility alias
ColoniseTask = ColoniseTaskObj


@dataclass
class LayMinesTaskObj(WaypointTaskBase):
    """
    Mine laying task.
    Port of: Common/Waypoints/LayMinesTask.cs
    """
    years: int = 1

    @property
    def name(self) -> str:
        return "LayMinesTask"

    @property
    def task_type(self) -> WaypointTask:
        return WaypointTask.LAY_MINES

    def to_dict(self) -> dict:
        return {"type": self.name, "years": self.years}

    @classmethod
    def from_dict(cls, data: dict) -> LayMinesTaskObj:
        return cls(years=data.get("years", 1))


# Backwards compatibility alias
LayMinesTask = LayMinesTaskObj


@dataclass
class InvadeTaskObj(WaypointTaskBase):
    """
    Invasion task.
    Port of: Common/Waypoints/InvadeTask.cs
    """

    @property
    def name(self) -> str:
        return "InvadeTask"

    @property
    def task_type(self) -> WaypointTask:
        return WaypointTask.INVADE

    @classmethod
    def from_dict(cls, data: dict) -> InvadeTaskObj:
        return cls()


# Backwards compatibility alias
InvadeTask = InvadeTaskObj


@dataclass
class ScrapTaskObj(WaypointTaskBase):
    """
    Scrap fleet task.
    Port of: Common/Waypoints/ScrapTask.cs (implied)
    """

    @property
    def name(self) -> str:
        return "ScrapTask"

    @property
    def task_type(self) -> WaypointTask:
        return WaypointTask.SCRAP

    @classmethod
    def from_dict(cls, data: dict) -> ScrapTaskObj:
        return cls()


# Backwards compatibility alias
ScrapTask = ScrapTaskObj


@dataclass
class SplitMergeTaskObj(WaypointTaskBase):
    """
    Split/merge fleet task.
    Port of: Common/Waypoints/SplitMergeTask.cs
    """

    @property
    def name(self) -> str:
        return "SplitMergeTask"

    @property
    def task_type(self) -> WaypointTask:
        return WaypointTask.SPLIT_MERGE

    @classmethod
    def from_dict(cls, data: dict) -> SplitMergeTaskObj:
        return cls()


# Backwards compatibility alias
SplitMergeTask = SplitMergeTaskObj


def get_task_type(task: Union[WaypointTask, WaypointTaskBase, None]) -> WaypointTask:
    """
    Get the WaypointTask enum value from a task.

    Handles both enum values and task objects.
    """
    if task is None:
        return WaypointTask.NO_TASK
    if isinstance(task, WaypointTask):
        return task
    if isinstance(task, WaypointTaskBase):
        return task.task_type
    return WaypointTask.NO_TASK


@dataclass
class Waypoint:
    """
    Waypoints have a position, destination description, speed, and task.

    Port of: Common/Waypoints/Waypoint.cs
    """
    position_x: float = 0.0
    position_y: float = 0.0
    warp_factor: int = 6
    destination: str = ""
    task: Union[WaypointTask, WaypointTaskBase] = field(default_factory=NoTaskObj)

    # Legacy support for position as NovaPoint
    _position: Optional[NovaPoint] = field(default=None, repr=False)

    @property
    def position(self) -> NovaPoint:
        """Get position as NovaPoint for backwards compatibility."""
        if self._position is None:
            self._position = NovaPoint(x=self.position_x, y=self.position_y)
        else:
            self._position.x = self.position_x
            self._position.y = self.position_y
        return self._position

    @position.setter
    def position(self, value: NovaPoint):
        """Set position from NovaPoint."""
        self.position_x = value.x
        self.position_y = value.y
        self._position = value

    def copy(self) -> Waypoint:
        """Create a copy of this waypoint (without task)."""
        # Port of: Waypoint.cs lines 81-86
        return Waypoint(
            position_x=self.position_x,
            position_y=self.position_y,
            warp_factor=self.warp_factor,
            destination=self.destination,
            task=NoTaskObj()
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        task_dict = {"type": "NoTask"}
        if isinstance(self.task, WaypointTask):
            task_dict = {"type": self.task.name}
        elif isinstance(self.task, WaypointTaskBase):
            task_dict = self.task.to_dict()

        return {
            "position_x": self.position_x,
            "position_y": self.position_y,
            "warp_factor": self.warp_factor,
            "destination": self.destination,
            "task": task_dict
        }

    @classmethod
    def from_dict(cls, data: dict) -> Waypoint:
        """Create Waypoint from dictionary."""
        wp = cls(
            position_x=data.get("position_x", data.get("position", {}).get("x", 0.0)),
            position_y=data.get("position_y", data.get("position", {}).get("y", 0.0)),
            warp_factor=data.get("warp_factor", 6),
            destination=data.get("destination", "")
        )
        if "task" in data:
            wp.task = WaypointTaskBase.from_dict(data["task"])
        return wp
