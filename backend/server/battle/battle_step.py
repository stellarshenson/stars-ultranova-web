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
    # Why the stack moved the way it did, when the engine has a reason
    # worth reporting - today only the Salvo then Close commitment
    # ("closing for the kill - ..."), so a commander sees WHY a fleet
    # stopped holding range. Same justification as priority and
    # target_role on BattleStepTarget. Web-only (C# absent)
    motive: str = ""

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "type": self.step_type,
            "stack_key": self.stack_key,
            "position": self.position.to_dict(),
            "motive": self.motive,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'BattleStepMovement':
        """Deserialize from dictionary."""
        step = cls()
        step.stack_key = data.get("stack_key", 0)
        pos_data = data.get("position", {})
        step.position = NovaPoint.from_dict(pos_data) if pos_data else NovaPoint(0, 0)
        step.motive = data.get("motive", "")
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
    # Why this target was picked: the plan tier that matched
    # (RonBattleEngine._get_priority, 7 = primary down to 3 = quinary;
    # 0 for the C#-exact engine, which has no tiers) and the role the
    # tier matched. Web-only - the C# BattleStepTarget carries neither
    priority: int = 0
    target_role: str = ""

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "type": self.step_type,
            "stack_key": self.stack_key,
            "target_key": self.target_key,
            "percent_to_fire": self.percent_to_fire,
            "priority": self.priority,
            "target_role": str(self.target_role),
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'BattleStepTarget':
        """Deserialize from dictionary."""
        step = cls()
        step.stack_key = data.get("stack_key", 0)
        step.target_key = data.get("target_key", 0)
        step.percent_to_fire = data.get("percent_to_fire", 100)
        step.priority = data.get("priority", 0)
        step.target_role = data.get("target_role", "")
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
class BattleStepWithdraw(BattleStep):
    """
    Records a stack completing its disengagement and leaving the board.

    Web-only step (C# absent - BattleEngine.cs:603 TODO admits fleeing
    is unimplemented, so no C# step class exists). Without it a
    withdrawal only showed as movement steps that silently stop.
    """
    step_type: str = field(default="Withdraw", init=False)
    stack_key: int = 0

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "type": self.step_type,
            "stack_key": self.stack_key,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'BattleStepWithdraw':
        """Deserialize from dictionary."""
        step = cls()
        step.stack_key = data.get("stack_key", 0)
        return step


@dataclass
class BattleStepBoard(BattleStep):
    """
    Records a boarding attempt and how it went.

    Web-only step (C# absent - the Nova reference has no boarding).
    `chance` is the odds the attempt was resolved at, so a replay
    explains a lost gamble rather than only reporting it.
    """
    step_type: str = field(default="Board", init=False)
    stack_key: int = 0
    target_key: int = 0
    chance: float = 0.0
    success: bool = False
    design_name: str = ""

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "type": self.step_type,
            "stack_key": self.stack_key,
            "target_key": self.target_key,
            "chance": self.chance,
            "success": self.success,
            "design_name": self.design_name,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'BattleStepBoard':
        """Deserialize from dictionary."""
        step = cls()
        step.stack_key = data.get("stack_key", 0)
        step.target_key = data.get("target_key", 0)
        step.chance = data.get("chance", 0.0)
        step.success = data.get("success", False)
        step.design_name = data.get("design_name", "")
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
