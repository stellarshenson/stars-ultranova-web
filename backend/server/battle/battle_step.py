"""
Stars Nova Web - Battle Step Classes
Ported from Common/DataStructures/BattleStep*.cs

Battle step classes for recording combat events.
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

from ...core.data_structures import NovaPoint


class TokenDefence(IntEnum):
    """Type of defense being targeted."""
    SHIELDS = 0
    ARMOR = 1


@dataclass
class BattleStep:
    """
    Base class for battle step events.

    Ported from BattleStep.cs.
    """
    step_type: str = "Base"

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {"type": self.step_type}

    @classmethod
    def from_dict(cls, data: dict) -> 'BattleStep':
        """Deserialize from dictionary."""
        return cls(step_type=data.get("type", "Base"))


@dataclass
class BattleStepMovement(BattleStep):
    """
    Records a stack movement during battle.

    Ported from BattleStepMovement.cs.
    """
    step_type: str = field(default="Movement", init=False)
    stack_key: int = 0
    position: NovaPoint = field(default_factory=lambda: NovaPoint(0, 0))

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "type": self.step_type,
            "stack_key": self.stack_key,
            "position": self.position.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'BattleStepMovement':
        """Deserialize from dictionary."""
        step = cls()
        step.stack_key = data.get("stack_key", 0)
        pos_data = data.get("position", {})
        step.position = NovaPoint.from_dict(pos_data) if pos_data else NovaPoint(0, 0)
        return step


@dataclass
class BattleStepTarget(BattleStep):
    """
    Records target selection during battle.

    Ported from BattleStepTarget.cs.
    """
    step_type: str = field(default="Target", init=False)
    stack_key: int = 0
    target_key: int = 0
    percent_to_fire: int = 100

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "type": self.step_type,
            "stack_key": self.stack_key,
            "target_key": self.target_key,
            "percent_to_fire": self.percent_to_fire,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'BattleStepTarget':
        """Deserialize from dictionary."""
        step = cls()
        step.stack_key = data.get("stack_key", 0)
        step.target_key = data.get("target_key", 0)
        step.percent_to_fire = data.get("percent_to_fire", 100)
        return step


@dataclass
class WeaponTarget:
    """Target information for weapon fire."""
    stack_key: int = 0
    target_key: int = 0

    def to_dict(self) -> dict:
        return {"stack_key": self.stack_key, "target_key": self.target_key}

    @classmethod
    def from_dict(cls, data: dict) -> 'WeaponTarget':
        return cls(
            stack_key=data.get("stack_key", 0),
            target_key=data.get("target_key", 0)
        )


@dataclass
class BattleStepWeapons(BattleStep):
    """
    Records weapon fire during battle.

    Ported from BattleStepWeapons.cs.
    """
    step_type: str = field(default="Weapons", init=False)
    weapon_target: WeaponTarget = field(default_factory=WeaponTarget)
    damage: float = 0.0
    targeting: TokenDefence = TokenDefence.SHIELDS

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "type": self.step_type,
            "weapon_target": self.weapon_target.to_dict(),
            "damage": self.damage,
            "targeting": self.targeting.value,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'BattleStepWeapons':
        """Deserialize from dictionary."""
        step = cls()
        wt_data = data.get("weapon_target", {})
        step.weapon_target = WeaponTarget.from_dict(wt_data) if wt_data else WeaponTarget()
        step.damage = data.get("damage", 0.0)
        step.targeting = TokenDefence(data.get("targeting", 0))
        return step


@dataclass
class BattleStepDestroy(BattleStep):
    """
    Records stack destruction during battle.

    Ported from BattleStepDestroy.cs.
    """
    step_type: str = field(default="Destroy", init=False)
    stack_key: int = 0

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "type": self.step_type,
            "stack_key": self.stack_key,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'BattleStepDestroy':
        """Deserialize from dictionary."""
        step = cls()
        step.stack_key = data.get("stack_key", 0)
        return step
