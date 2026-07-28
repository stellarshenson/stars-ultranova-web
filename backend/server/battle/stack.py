"""
Stars Nova Web - Stack
Ported from Common/GameObjects/Stack.cs

Battle stack - a specialized fleet containing a single ship token for combat.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, TYPE_CHECKING

from ...core.data_structures import NovaPoint, Resources, Cargo
from ...core.components.ship_role import ShipRole, infer_battle_role
from ...core.game_objects import Fleet, ShipToken

if TYPE_CHECKING:
    from ...core.game_objects import Star
    from ...core.components import ShipDesign


@dataclass
class StackToken:
    """
    Token for battle stack with mutable shields/armor.

    ShipToken in Fleet has cached design values. StackToken adds
    mutable battle state (shields, armor remaining).
    """
    key: int = 0
    design_key: int = 0
    design_name: str = ""
    quantity: int = 0
    shields: float = 0.0  # Current shields (mutable during battle)
    armor: float = 0.0  # Current armor (mutable during battle)
    # Armour the stack entered the battle with, so the "Half Armour"
    # withdrawal threshold has a baseline to compare against
    initial_armor: float = 0.0

    # Cached design values
    mass: int = 0
    has_weapons: bool = False
    is_starbase: bool = False
    is_bomber: bool = False
    battle_speed: float = 0.5
    # Battle role of the design (ship_role.py cascade); cached so a
    # deserialized report stack still names its class
    battle_role: str = ""

    # Design reference (optional - for weapon access)
    design: Optional['ShipDesign'] = None

    @classmethod
    def from_ship_token(cls, token: ShipToken, design: Optional['ShipDesign'] = None) -> 'StackToken':
        """Create from ShipToken."""
        st = cls()
        st.key = token.design_key
        st.design_key = token.design_key
        st.design_name = token.design_name
        st.quantity = token.quantity
        st.shields = float(token.shields * token.quantity)  # Total shields
        st.armor = float(token.armor * token.quantity)  # Total armor
        st.initial_armor = st.armor
        st.mass = token.mass
        st.has_weapons = token.has_weapons
        st.is_starbase = token.is_starbase
        st.is_bomber = token.is_bomber
        st.design = design
        if design:
            st.battle_speed = design.battle_speed
            st.battle_role = getattr(design, 'battle_role', "")
        return st

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "design_key": self.design_key,
            "design_name": self.design_name,
            "quantity": self.quantity,
            "shields": self.shields,
            "armor": self.armor,
            "mass": self.mass,
            "battle_role": str(self.battle_role),
        }


@dataclass
class Stack:
    """
    A specialized fleet used in the battle engine.

    Contains only one ShipToken and holds the key of the parent Fleet.
    Ported from Stack.cs (259 lines).
    """
    # Core attributes
    key: int = 0
    owner: int = 0
    name: str = ""
    position: NovaPoint = field(default_factory=lambda: NovaPoint(0, 0))
    battle_plan: str = "Default"

    # Parent fleet reference
    parent_key: int = 0

    # Ship token (single design in this stack)
    token: Optional[StackToken] = None

    # Battle state
    target: Optional['Stack'] = None
    target_list: List['Stack'] = field(default_factory=list)
    # Plan tier that matched each target, keyed by target stack key.
    # The engine used to compute and discard it; the battle report now
    # carries it so a replay can explain every targeting choice
    target_priorities: Dict[int, int] = field(default_factory=dict)
    velocity_vector: Optional[NovaPoint] = None
    in_orbit: Optional['Star'] = None

    # Tactic state (battle-local, canonical Stars! disengage rules;
    # C# absent - BattleEngine.cs:603 TODO admits fleeing is
    # unimplemented). damage_taken drives "Disengage if Challenged";
    # a stack that completes DISENGAGE_MOVES flee moves has left the
    # battle (disengaged) and neither fires nor is targeted.
    damage_taken: bool = False
    flee_rounds: int = 0
    disengaged: bool = False
    # True when the hostile side outnumbers this stack's own side in
    # armed ships at the start of the battle, which is what the
    # "Outnumbered" withdrawal threshold tests
    outnumbered: bool = False

    # Cargo
    cargo: Cargo = field(default_factory=Cargo)

    @classmethod
    def from_fleet(
        cls,
        fleet: Fleet,
        stack_id: int,
        token: ShipToken,
        design: Optional['ShipDesign'] = None
    ) -> 'Stack':
        """
        Create a Stack from a Fleet and a specific token.

        Args:
            fleet: Parent fleet
            stack_id: Unique battle engine ID
            token: Ship token for this stack
            design: Optional ShipDesign for weapon access
        """
        stack = cls()
        stack.key = (fleet.owner << 32) | stack_id
        stack.owner = fleet.owner
        stack.parent_key = fleet.key
        stack.name = f"Stack #{stack_id:X}"
        # The engagement override wins for this battle only; turn
        # generation clears it unconditionally afterwards, so the
        # fleet always reverts to its standing plan
        stack.battle_plan = (getattr(fleet, 'engagement_plan', "")
                             or fleet.battle_plan)
        stack.position = NovaPoint(fleet.position.x, fleet.position.y)
        # Note: Fleet has in_orbit_name (string), Stack has in_orbit (Star)
        # Leave as None - battle engine resolves orbit separately
        stack.token = StackToken.from_ship_token(token, design)
        stack.cargo = Cargo(
            ironium=fleet.cargo.ironium,
            boranium=fleet.cargo.boranium,
            germanium=fleet.cargo.germanium,
            colonists_in_kilotons=fleet.cargo.colonists_in_kilotons
        )
        return stack

    @classmethod
    def copy(cls, other: 'Stack') -> 'Stack':
        """Create a copy of a Stack for battle reports."""
        stack = cls()
        stack.key = other.key
        stack.owner = other.owner
        stack.parent_key = other.parent_key
        stack.name = other.name
        stack.battle_plan = other.battle_plan
        stack.position = NovaPoint(other.position.x, other.position.y)
        stack.in_orbit = other.in_orbit
        stack.target = other.target
        stack.target_list = list(other.target_list)
        stack.target_priorities = dict(other.target_priorities)
        stack.damage_taken = other.damage_taken
        stack.flee_rounds = other.flee_rounds
        stack.disengaged = other.disengaged
        stack.outnumbered = other.outnumbered
        if other.velocity_vector:
            stack.velocity_vector = NovaPoint(
                other.velocity_vector.x, other.velocity_vector.y
            )
        # Copy token with current damage state
        if other.token:
            stack.token = StackToken()
            stack.token.key = other.token.key
            stack.token.design_key = other.token.design_key
            stack.token.design_name = other.token.design_name
            stack.token.quantity = other.token.quantity
            stack.token.shields = other.token.shields
            stack.token.armor = other.token.armor
            stack.token.initial_armor = other.token.initial_armor
            stack.token.mass = other.token.mass
            stack.token.has_weapons = other.token.has_weapons
            stack.token.is_starbase = other.token.is_starbase
            stack.token.is_bomber = other.token.is_bomber
            stack.token.battle_speed = other.token.battle_speed
            stack.token.battle_role = other.token.battle_role
            stack.token.design = other.token.design
        stack.cargo = Cargo(
            ironium=other.cargo.ironium,
            boranium=other.cargo.boranium,
            germanium=other.cargo.germanium,
            colonists_in_kilotons=other.cargo.colonists_in_kilotons
        )
        return stack

    @property
    def battle_speed(self) -> float:
        """Return this stack's battle speed from the design."""
        if self.token:
            return self.token.battle_speed
        return 0.5

    @property
    def defenses(self) -> float:
        """Return current defense capability (armor + shields)."""
        if self.token:
            return self.token.armor + self.token.shields
        return 0.0

    @property
    def is_destroyed(self) -> bool:
        """Check if stack has been destroyed."""
        return (
            self.token is None or
            self.token.quantity <= 0 or
            self.token.armor <= 0
        )

    @property
    def is_armed(self) -> bool:
        """Check if stack has weapons."""
        if self.token:
            return self.token.has_weapons
        return False

    @property
    def is_starbase(self) -> bool:
        """Check if stack is a starbase."""
        if self.token:
            return self.token.is_starbase
        return False

    @property
    def battle_role(self) -> str:
        """
        The battle role this stack's design falls into.

        Prefers the value cached when the stack was built; a stack
        rebuilt from an older save has none, so the cascade re-runs on
        the token's own capability flags.
        """
        if self.token is None:
            return ShipRole.SUPPORT
        if self.token.battle_role:
            return self.token.battle_role
        design = self.token.design
        return infer_battle_role(
            is_starbase=self.token.is_starbase,
            is_bomber=self.token.is_bomber,
            has_weapons=self.token.has_weapons,
            power_rating=int(getattr(design, 'power_rating', 0) or 0),
            can_refuel=bool(getattr(design, 'can_refuel', False)),
            can_colonize=bool(getattr(design, 'can_colonize', False)),
            heals_others_percent=int(
                getattr(design, 'heals_others_percent', 0) or 0),
            cargo_capacity=int(getattr(design, 'cargo_capacity', 0) or 0),
        )

    @property
    def has_bombers(self) -> bool:
        """Check if stack has bombers."""
        if self.token:
            return self.token.is_bomber
        return False

    @property
    def mass(self) -> int:
        """Total mass of the stack."""
        if self.token:
            return self.token.mass * self.token.quantity
        return 0

    @property
    def total_cost(self) -> Resources:
        """Total cost of all ships in stack."""
        # Without full design, estimate from mass
        if self.token:
            mass = self.token.mass * self.token.quantity
            return Resources(
                ironium=mass // 3,
                boranium=mass // 3,
                germanium=mass // 3,
                energy=mass
            )
        return Resources()

    @property
    def total_armor_strength(self) -> float:
        """Total armor across all ships."""
        if self.token:
            return self.token.armor
        return 0.0

    @property
    def total_shield_strength(self) -> float:
        """Total shields across all ships."""
        if self.token:
            return self.token.shields
        return 0.0

    @property
    def composition(self) -> Dict[int, StackToken]:
        """Return composition dict compatible with Fleet interface."""
        if self.token:
            return {self.token.key: self.token}
        return {}

    def distance_to(self, other: 'Stack') -> float:
        """Distance to another stack."""
        return self.position.distance_to(other.position)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "key": self.key,
            "owner": self.owner,
            "parent_key": self.parent_key,
            "name": self.name,
            "battle_plan": self.battle_plan,
            "position": self.position.to_dict(),
            "token": self.token.to_dict() if self.token else None,
            "cargo": self.cargo.to_dict(),
            "battle_role": str(self.battle_role),
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Stack':
        """Deserialize from dictionary."""
        stack = cls()
        stack.key = data.get("key", 0)
        stack.owner = data.get("owner", 0)
        stack.parent_key = data.get("parent_key", 0)
        stack.name = data.get("name", "")
        stack.battle_plan = data.get("battle_plan", "Default")

        pos_data = data.get("position", {})
        stack.position = NovaPoint.from_dict(pos_data) if pos_data else NovaPoint(0, 0)

        token_data = data.get("token")
        if token_data:
            st = StackToken()
            st.key = token_data.get("key", 0)
            st.design_key = token_data.get("design_key", 0)
            st.design_name = token_data.get("design_name", "")
            st.quantity = token_data.get("quantity", 0)
            st.shields = token_data.get("shields", 0.0)
            st.armor = token_data.get("armor", 0.0)
            st.mass = token_data.get("mass", 0)
            st.battle_role = token_data.get("battle_role", "")
            stack.token = st

        cargo_data = data.get("cargo", {})
        stack.cargo = Cargo.from_dict(cargo_data) if cargo_data else Cargo()

        return stack
