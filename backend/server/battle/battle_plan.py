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


# Tactic strings, exactly as in the C# BattlePlans dialog
# (BattlePlans.Designer.cs:168-174). BattleEngine.cs never consumes
# Tactic (its line 603 TODO admits fleeing is unimplemented); the Ron
# engine honors these per canonical Stars! rules.
TACTICS = [
    "Disengage",
    "Disengage if Challenged",
    "Maximise Damage",
    "Maximise Damage Ratio",
    "Maximise Net Damage",
    "Minimise Damage to Self",
]

# Attack-who strings, exactly as in the C# dialog
# (BattlePlans.Designer.cs:147-150). "Enemies and Neutrals" exists in
# the dialog but BattleEngine.cs:479-493 never checks it - honored here
# per canonical Stars! rules.
ATTACK_OPTIONS = [
    "Enemies",
    "Enemies and Neutrals",
    "Everyone",
]

# Display labels for the web dialog's five target tiers. The C# dialog
# offers a different 7-string list ("Any", "Armed Ships", "Bombers",
# "Freighters", "None", "Starbase", "Unarmed Ships",
# BattlePlans.Designer.cs:131-138) tied to the 2-tier string model
# (BattlePlan.cs:37-45); the web port keeps the later stars-nova trunk
# 5-tier Victims model the Ron engine consumes.
VICTIMS_LABELS = {
    Victims.STARBASE: "Starbase",
    Victims.BOMBER: "Bomber",
    Victims.CAPITAL_SHIP: "Capital Ship",
    Victims.ESCORT: "Escort",
    Victims.ARMED_SHIP: "Armed Ship",
    Victims.ANY_SHIP: "Any Ship",
    Victims.SUPPORT_SHIP: "Support Ship",
}

# Canonical Stars! cap of 14 battle plans per player (C# absent - the
# Nova dialog never implemented plan editing, BattlePlans.Designer.cs
# newPlan/modifyPlan buttons are disabled)
MAX_BATTLE_PLANS = 14


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
