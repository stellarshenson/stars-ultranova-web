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
    # Doctrine stance shifts when this attack resolves inside the
    # round (battle_plan.STANCE_MODIFIERS). 0 for every attack under
    # the C#-exact engine and under a Balanced stance.
    initiative_bonus: int = 0

    @property
    def effective_initiative(self) -> int:
        """Weapon initiative after the stance shift."""
        if self.weapon is None:
            return 0
        return self.weapon.initiative + self.initiative_bonus

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
        source_design: 'ShipDesign',
        target_design: 'ShipDesign',
        base_accuracy: float
    ) -> float:
        """
        Torpedo/missile accuracy from computers vs jammers (0-1 scale).

        Canonical Stars! rule per project directive (C# consumption is
        a stub: BattleEngine.cs:920-929 TODO, :788 FIXME): the
        attacker's stacked battle computer accuracy cuts the MISS
        chance multiplicatively, the target's stacked jamming cuts the
        HIT chance multiplicatively. Because the design aggregates are
        probability-stacked this equals applying each computer as
        miss *= (1 - bonus) and each jammer as hit *= (1 - jam).

        Args:
            source_design: Attacking ship design (may be None)
            target_design: Target ship design (may be None)
            base_accuracy: Weapon base accuracy (0.0 to 1.0)

        Returns:
            Modified accuracy (0.0 to 1.0)
        """
        computer = getattr(source_design, 'battle_computer_accuracy', 0.0) \
            if source_design else 0.0
        jamming = getattr(target_design, 'jamming', 0.0) \
            if target_design else 0.0

        accuracy = 1.0 - (1.0 - base_accuracy) * (1.0 - computer / 100.0)
        accuracy = accuracy * (1.0 - jamming / 100.0)
        return accuracy

    def beam_power_modifier(
        self,
        source_design: 'ShipDesign',
        target_design: 'ShipDesign'
    ) -> float:
        """
        Beam damage multiplier from capacitors vs deflectors.

        damage = power * (1 + capacitor/100) * (1 - deflector/100).
        Canonical Stars! rule per project directive: C# consumption is
        a stub (BattleEngine.cs:880-908 returns weapon.Power; the
        commented intent at :888 subtracts instead of multiplying and
        is not ported). The capacitor aggregate is geometric-stacked
        and capped at 250; the deflector factor equals (0.9)^n for n
        catalog 10% Beam Deflectors because the design aggregate is
        probability-stacked.

        Args:
            source_design: Attacking ship design (may be None)
            target_design: Target ship design (may be None)

        Returns:
            Multiplier to apply to beam hit power
        """
        capacitor = getattr(source_design, 'capacitor', 0.0) \
            if source_design else 0.0
        deflector = getattr(target_design, 'beam_deflector', 0.0) \
            if target_design else 0.0

        return (1.0 + capacitor / 100.0) * (1.0 - deflector / 100.0)

    def __lt__(self, other: 'WeaponDetails') -> bool:
        """Compare by weapon initiative for sorting."""
        if self.weapon is None:
            return True
        if other.weapon is None:
            return False
        return self.effective_initiative < other.effective_initiative

    def __eq__(self, other: object) -> bool:
        """Equal comparison by initiative."""
        if not isinstance(other, WeaponDetails):
            return False
        if self.weapon is None or other.weapon is None:
            return self.weapon is None and other.weapon is None
        return self.effective_initiative == other.effective_initiative
