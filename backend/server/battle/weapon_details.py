"""
Stars Nova Web - Weapon Details
Ported from ServerState/WeaponDetails.cs

Weapon attack information sortable by initiative.
"""

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .stack import Stack
    from ...core.components import ShipDesign
    from ...core.components.component import Weapon


@dataclass
class TargetPercent:
    """Target and percentage of fire to allocate."""
    target: Optional['Stack'] = None
    percent_to_fire: int = 100


@dataclass
class WeaponDetails:
    """
    Weapon capability and target information.

    Sortable by weapon system initiative.
    Ported from WeaponDetails.cs (82 lines).
    """
    source_stack: Optional['Stack'] = None
    target_stack: TargetPercent = field(default_factory=TargetPercent)
    weapon: Optional['Weapon'] = None

    def beam_dispersal(self, distance_squared: float) -> float:
        """
        Calculate beam damage dispersal over distance.

        Returns percentage of damage (90% at max range, 100% at same location).
        """
        if self.weapon is None or self.weapon.range == 0:
            return 100.0
        max_range_squared = self.weapon.range * self.weapon.range
        return 100.0 - 10 * (distance_squared / max_range_squared)

    def beam_dispersal_ron(
        self, distance_squared: float, grid_scale_squared: float
    ) -> float:
        """
        Calculate beam damage dispersal for Ron battle engine.

        In Ron engine real distance = 1/gridScale of a grid step.
        """
        if self.weapon is None or self.weapon.range == 0:
            return 100.0
        max_range_squared = (
            self.weapon.range * self.weapon.range * grid_scale_squared
        )
        return 100.0 - 10 * (distance_squared / max_range_squared)

    def missile_accuracy(
        self,
        source: 'ShipDesign',
        target: 'ShipDesign',
        missile_base_accuracy: float
    ) -> float:
        """
        Calculate missile accuracy considering computers and jammers.

        Args:
            source: Attacking ship design
            target: Target ship design
            missile_base_accuracy: Base accuracy (0.0 to 1.0)

        Returns:
            Modified accuracy value
        """
        increase = 1.0
        decrease = 1.0

        # Check for computer bonus on source
        if source.summary and "Computer" in source.summary.properties:
            computer = source.summary.properties["Computer"]
            if hasattr(computer, 'accuracy'):
                increase = 1.0 + (computer.accuracy / 100.0)

        # Check for jammer penalty on target
        if target.summary and "Jammer" in target.summary.properties:
            jammer = target.summary.properties["Jammer"]
            if hasattr(jammer, 'value'):
                decrease = 1.0 - (jammer.value / 100.0)

        return missile_base_accuracy * increase * decrease

    def __lt__(self, other: 'WeaponDetails') -> bool:
        """Compare by weapon initiative for sorting."""
        if self.weapon is None:
            return True
        if other.weapon is None:
            return False
        return self.weapon.initiative < other.weapon.initiative

    def __eq__(self, other: object) -> bool:
        """Equal comparison by initiative."""
        if not isinstance(other, WeaponDetails):
            return False
        if self.weapon is None or other.weapon is None:
            return self.weapon is None and other.weapon is None
        return self.weapon.initiative == other.weapon.initiative
