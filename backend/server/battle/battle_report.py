"""
Stars Nova Web - Battle Report
Ported from Common/DataStructures/BattleReport.cs

Container for battle results and replay data.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, TYPE_CHECKING

from .battle_step import (
    BattleStep,
    BattleStepMovement,
    BattleStepTarget,
    BattleStepWeapons,
    BattleStepDestroy,
)

if TYPE_CHECKING:
    from .stack import Stack


@dataclass
class BattleReport:
    """
    Container for battle results and replay data.

    Ported from BattleReport.cs (203 lines).
    """
    location: Optional[str] = None
    space_size: int = 0
    grid_size: int = 1
    year: int = 0
    steps: List[BattleStep] = field(default_factory=list)
    stacks: Dict[int, 'Stack'] = field(default_factory=dict)
    losses: Dict[int, int] = field(default_factory=dict)  # empire_id -> loss_count

    @property
    def key(self) -> str:
        """Unique key for this battle report."""
        if self.location is None:
            return ""
        return f"{self.year}{self.location}"

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        # Serialize steps based on their type
        steps_data = []
        for step in self.steps:
            steps_data.append(step.to_dict())

        # Serialize stacks
        stacks_data = {}
        for key, stack in self.stacks.items():
            stacks_data[str(key)] = stack.to_dict()

        return {
            "location": self.location,
            "space_size": self.space_size,
            "grid_size": self.grid_size,
            "year": self.year,
            "steps": steps_data,
            "stacks": stacks_data,
            "losses": {str(k): v for k, v in self.losses.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'BattleReport':
        """Deserialize from dictionary."""
        report = cls()
        report.location = data.get("location")
        report.space_size = data.get("space_size", 0)
        report.grid_size = data.get("grid_size", 1)
        report.year = data.get("year", 0)

        # Deserialize steps
        for step_data in data.get("steps", []):
            step_type = step_data.get("type", "Base")
            if step_type == "Movement":
                report.steps.append(BattleStepMovement.from_dict(step_data))
            elif step_type == "Target":
                report.steps.append(BattleStepTarget.from_dict(step_data))
            elif step_type == "Weapons":
                report.steps.append(BattleStepWeapons.from_dict(step_data))
            elif step_type == "Destroy":
                report.steps.append(BattleStepDestroy.from_dict(step_data))
            else:
                report.steps.append(BattleStep.from_dict(step_data))

        # Stacks will need to be deserialized separately with proper Stack class
        # For now store raw data
        report.losses = {int(k): v for k, v in data.get("losses", {}).items()}

        return report
