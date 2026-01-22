"""
Waypoint and waypoint task classes.
Port of: Common/Waypoints/Waypoint.cs and related task files
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional, TYPE_CHECKING

from ..data_structures import NovaPoint, Cargo

if TYPE_CHECKING:
    from ..game_objects import Mappable


class CargoMode(IntEnum):
    """Mode for cargo transfer tasks."""
    LOAD = 0
    UNLOAD = 1
    SET = 2


class WaypointTask(ABC):
    """Base class for waypoint tasks."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Task name for serialization."""
        pass

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {"type": self.name}

    @classmethod
    def from_dict(cls, data: dict) -> WaypointTask:
        """Create task from dictionary."""
        task_type = data.get("type", "NoTask")
        if task_type == "CargoTask":
            return CargoTask.from_dict(data)
        elif task_type == "ColoniseTask":
            return ColoniseTask.from_dict(data)
        elif task_type == "LayMinesTask":
            return LayMinesTask.from_dict(data)
        elif task_type == "InvadeTask":
            return InvadeTask.from_dict(data)
        elif task_type == "ScrapTask":
            return ScrapTask.from_dict(data)
        return NoTask()


@dataclass
class NoTask(WaypointTask):
    """No task - just travel to waypoint."""

    @property
    def name(self) -> str:
        return "NoTask"


@dataclass
class CargoTask(WaypointTask):
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

    def to_dict(self) -> dict:
        return {
            "type": self.name,
            "mode": self.mode.name,
            "amount": self.amount.to_dict(),
            "target_name": self.target_name
        }

    @classmethod
    def from_dict(cls, data: dict) -> CargoTask:
        task = cls()
        if "mode" in data:
            task.mode = CargoMode[data["mode"]]
        if "amount" in data:
            task.amount = Cargo.from_dict(data["amount"])
        task.target_name = data.get("target_name")
        return task


@dataclass
class ColoniseTask(WaypointTask):
    """
    Colonization task.
    Port of: Common/Waypoints/ColoniseTask.cs
    """

    @property
    def name(self) -> str:
        return "ColoniseTask"

    @classmethod
    def from_dict(cls, data: dict) -> ColoniseTask:
        return cls()


@dataclass
class LayMinesTask(WaypointTask):
    """
    Mine laying task.
    Port of: Common/Waypoints/LayMinesTask.cs
    """
    years: int = 1

    @property
    def name(self) -> str:
        return "LayMinesTask"

    def to_dict(self) -> dict:
        return {"type": self.name, "years": self.years}

    @classmethod
    def from_dict(cls, data: dict) -> LayMinesTask:
        return cls(years=data.get("years", 1))


@dataclass
class InvadeTask(WaypointTask):
    """
    Invasion task.
    Port of: Common/Waypoints/InvadeTask.cs
    """

    @property
    def name(self) -> str:
        return "InvadeTask"

    @classmethod
    def from_dict(cls, data: dict) -> InvadeTask:
        return cls()


@dataclass
class ScrapTask(WaypointTask):
    """
    Scrap fleet task.
    Port of: Common/Waypoints/ScrapTask.cs (implied)
    """

    @property
    def name(self) -> str:
        return "ScrapTask"

    @classmethod
    def from_dict(cls, data: dict) -> ScrapTask:
        return cls()


@dataclass
class Waypoint:
    """
    Waypoints have a position, destination description, speed, and task.

    Port of: Common/Waypoints/Waypoint.cs
    """
    position: NovaPoint = field(default_factory=NovaPoint)
    warp_factor: int = 6
    destination: str = ""
    task: WaypointTask = field(default_factory=NoTask)

    def copy(self) -> Waypoint:
        """Create a copy of this waypoint (without task)."""
        # Port of: Waypoint.cs lines 81-86
        return Waypoint(
            position=self.position.copy(),
            warp_factor=self.warp_factor,
            destination=self.destination,
            task=NoTask()
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "position": self.position.to_dict(),
            "warp_factor": self.warp_factor,
            "destination": self.destination,
            "task": self.task.to_dict()
        }

    @classmethod
    def from_dict(cls, data: dict) -> Waypoint:
        """Create Waypoint from dictionary."""
        wp = cls()
        if "position" in data:
            wp.position = NovaPoint.from_dict(data["position"])
        wp.warp_factor = data.get("warp_factor", 6)
        wp.destination = data.get("destination", "")
        if "task" in data:
            wp.task = WaypointTask.from_dict(data["task"])
        return wp
