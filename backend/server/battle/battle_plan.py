"""
Stars Nova Web - Battle Plan
Ported from Common/DataStructures/BattlePlan.cs

Player-defined battle tactics and targeting priorities.
"""

from dataclasses import dataclass
from enum import IntEnum


class Victims(IntEnum):
    """
    Target priority types for battle plans.

    Ported from Global.Victims enum.
    """
    STARBASE = 0
    BOMBER = 1
    CAPITAL_SHIP = 2
    ESCORT = 3
    ARMED_SHIP = 4
    ANY_SHIP = 5
    SUPPORT_SHIP = 6


@dataclass
class BattlePlan:
    """
    Player-defined battle tactics and targeting priorities.

    Ported from BattlePlan.cs (139 lines).
    """
    name: str = "Default"
    primary_target: int = 0  # Victims enum value
    secondary_target: int = 1
    tertiary_target: int = 3
    quaternary_target: int = 5
    quinary_target: int = 6
    tactic: str = "Maximise Damage"
    attack: str = "Enemies"  # "Everyone", "Enemies", or specific
    target_id: int = 0  # Empire ID to target when attack is specific

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "primary_target": self.primary_target,
            "secondary_target": self.secondary_target,
            "tertiary_target": self.tertiary_target,
            "quaternary_target": self.quaternary_target,
            "quinary_target": self.quinary_target,
            "tactic": self.tactic,
            "attack": self.attack,
            "target_id": self.target_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'BattlePlan':
        """Deserialize from dictionary."""
        return cls(
            name=data.get("name", "Default"),
            primary_target=data.get("primary_target", 0),
            secondary_target=data.get("secondary_target", 1),
            tertiary_target=data.get("tertiary_target", 3),
            quaternary_target=data.get("quaternary_target", 5),
            quinary_target=data.get("quinary_target", 6),
            tactic=data.get("tactic", "Maximise Damage"),
            attack=data.get("attack", "Enemies"),
            target_id=data.get("target_id", 0),
        )
