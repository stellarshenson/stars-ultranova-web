"""
Stars Nova Web - Ship Specifications

Starting ship designs and the design/token factory.

The original game gives each empire a set of pre-built designs at game
start (Long Range Scout, Santa Maria colony ship, etc.). This module
defines those specs, a lightweight SimpleDesign record stored in
EmpireData.designs, and make_token() used both at galaxy generation and
by the production step when ships are built.
"""

from dataclasses import dataclass, field
from typing import Optional

from typing import List

from ..core.data_structures.resources import Resources
from ..core.game_objects.fleet import ShipToken
from ..core.components.ship_design import Weapon


@dataclass
class SimpleDesign:
    """
    A lightweight ship design carrying pre-aggregated stats.

    Duck-compatible with the fields production and fleet code read from
    a full ShipDesign (name, key, cost, is_starbase, ...).
    """
    key: int = 0
    name: str = ""
    cost: Resources = field(default_factory=Resources)
    mass: int = 0
    armor: int = 0
    shields: int = 0
    fuel_capacity: int = 0
    cargo_capacity: int = 0
    can_colonize: bool = False
    can_refuel: bool = False
    can_scan: bool = False
    is_starbase: bool = False
    is_bomber: bool = False
    has_weapons: bool = False
    free_warp_speed: int = 0
    optimal_speed: int = 6
    scan_range_normal: int = 0
    scan_range_penetrating: int = 0
    dock_capacity: int = 0
    obsolete: bool = False
    hull_name: str = ""
    battle_speed: float = 0.5
    initiative: int = 0
    weapons: List[Weapon] = field(default_factory=list)

    @property
    def power_rating(self) -> int:
        """Rough combat value used for battle targeting."""
        weapon_power = sum(w.power for w in self.weapons)
        return weapon_power * 10 + self.armor + self.shields

    @property
    def shield(self) -> int:
        """Alias used by battle code (ShipDesign uses 'shield')."""
        return self.shields

    def update(self) -> None:
        """Aggregates are static for SimpleDesign - nothing to recompute."""
        return

    def to_dict(self) -> dict:
        return {
            "design_class": "SimpleDesign",
            "key": hex(self.key),
            "name": self.name,
            "cost": self.cost.to_dict(),
            "mass": self.mass,
            "armor": self.armor,
            "shields": self.shields,
            "fuel_capacity": self.fuel_capacity,
            "cargo_capacity": self.cargo_capacity,
            "can_colonize": self.can_colonize,
            "can_refuel": self.can_refuel,
            "can_scan": self.can_scan,
            "is_starbase": self.is_starbase,
            "is_bomber": self.is_bomber,
            "has_weapons": self.has_weapons,
            "free_warp_speed": self.free_warp_speed,
            "optimal_speed": self.optimal_speed,
            "scan_range_normal": self.scan_range_normal,
            "scan_range_penetrating": self.scan_range_penetrating,
            "dock_capacity": self.dock_capacity,
            "obsolete": self.obsolete,
            "hull_name": self.hull_name,
            "battle_speed": self.battle_speed,
            "initiative": self.initiative,
            "weapons": [
                {"power": w.power, "range": w.range, "initiative": w.initiative,
                 "accuracy": w.accuracy, "group": w.group}
                for w in self.weapons
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'SimpleDesign':
        design = cls()
        key = data.get("key", 0)
        design.key = int(key, 16) if isinstance(key, str) else key
        design.name = data.get("name", "")
        if "cost" in data:
            design.cost = Resources.from_dict(data["cost"])
        design.mass = data.get("mass", 0)
        design.armor = data.get("armor", 0)
        design.shields = data.get("shields", 0)
        design.fuel_capacity = data.get("fuel_capacity", 0)
        design.cargo_capacity = data.get("cargo_capacity", 0)
        design.can_colonize = data.get("can_colonize", False)
        design.can_refuel = data.get("can_refuel", False)
        design.can_scan = data.get("can_scan", False)
        design.is_starbase = data.get("is_starbase", False)
        design.is_bomber = data.get("is_bomber", False)
        design.has_weapons = data.get("has_weapons", False)
        design.free_warp_speed = data.get("free_warp_speed", 0)
        design.optimal_speed = data.get("optimal_speed", 6)
        design.scan_range_normal = data.get("scan_range_normal", 0)
        design.scan_range_penetrating = data.get("scan_range_penetrating", 0)
        design.dock_capacity = data.get("dock_capacity", 0)
        design.obsolete = data.get("obsolete", False)
        design.hull_name = data.get("hull_name", "")
        design.battle_speed = data.get("battle_speed", 0.5)
        design.initiative = data.get("initiative", 0)
        design.weapons = [
            Weapon(power=w.get("power", 0), range=w.get("range", 0),
                   initiative=w.get("initiative", 0), accuracy=w.get("accuracy", 75),
                   group=w.get("group", "standardBeam"))
            for w in data.get("weapons", [])
        ]
        return design


# Starting design specs - stats follow the original game's starting ships
STARTING_DESIGN_SPECS = [
    {
        "name": "Long Range Scout",
        "hull_name": "Scout",
        "cost": {"ironium": 8, "boranium": 2, "germanium": 7, "energy": 22},
        "mass": 25,
        "armor": 20,
        "fuel_capacity": 300,
        "can_scan": True,
        "scan_range_normal": 66,
        "optimal_speed": 9,
    },
    {
        "name": "Santa Maria",
        "hull_name": "Colony Ship",
        "cost": {"ironium": 20, "boranium": 5, "germanium": 15, "energy": 30},
        "mass": 70,
        "armor": 20,
        "fuel_capacity": 200,
        "cargo_capacity": 25,
        "can_colonize": True,
        "optimal_speed": 6,
    },
    {
        "name": "Teamster",
        "hull_name": "Small Freighter",
        "cost": {"ironium": 15, "boranium": 2, "germanium": 10, "energy": 25},
        "mass": 60,
        "armor": 25,
        "fuel_capacity": 130,
        "cargo_capacity": 70,
        "optimal_speed": 6,
    },
    {
        "name": "Stalwart Defender",
        "hull_name": "Destroyer",
        "cost": {"ironium": 30, "boranium": 15, "germanium": 15, "energy": 60},
        "mass": 110,
        "armor": 200,
        "shields": 40,
        "fuel_capacity": 280,
        "has_weapons": True,
        "optimal_speed": 7,
        "battle_speed": 1.0,
        "initiative": 3,
        "weapons": [
            {"power": 16, "range": 3, "initiative": 9, "accuracy": 75, "group": "standardBeam"},
            {"power": 16, "range": 3, "initiative": 9, "accuracy": 75, "group": "standardBeam"},
        ],
    },
    {
        "name": "Starbase",
        "hull_name": "Space Station",
        "cost": {"ironium": 120, "boranium": 80, "germanium": 100, "energy": 400},
        "mass": 0,
        "armor": 500,
        "shields": 400,
        "is_starbase": True,
        "can_refuel": True,
        "has_weapons": True,
        "dock_capacity": 200,
        "optimal_speed": 0,
        "battle_speed": 0.0,
        "initiative": 10,
        "weapons": [
            {"power": 25, "range": 4, "initiative": 12, "accuracy": 75, "group": "standardBeam"},
            {"power": 25, "range": 4, "initiative": 12, "accuracy": 75, "group": "standardBeam"},
        ],
    },
]


def make_starting_designs(empire) -> None:
    """
    Register the starting ship designs on an empire.

    Args:
        empire: EmpireData to receive the designs.
    """
    for spec in STARTING_DESIGN_SPECS:
        design = _design_from_spec(spec)
        design.key = empire.get_next_design_key()
        empire.designs[design.key] = design


def _design_from_spec(spec: dict) -> SimpleDesign:
    """Build a SimpleDesign from a spec dict."""
    cost = spec.get("cost", {})
    return SimpleDesign(
        name=spec["name"],
        hull_name=spec.get("hull_name", ""),
        cost=Resources(
            ironium=cost.get("ironium", 0),
            boranium=cost.get("boranium", 0),
            germanium=cost.get("germanium", 0),
            energy=cost.get("energy", 0),
        ),
        mass=spec.get("mass", 0),
        armor=spec.get("armor", 0),
        shields=spec.get("shields", 0),
        fuel_capacity=spec.get("fuel_capacity", 0),
        cargo_capacity=spec.get("cargo_capacity", 0),
        can_colonize=spec.get("can_colonize", False),
        can_refuel=spec.get("can_refuel", False),
        can_scan=spec.get("can_scan", False),
        is_starbase=spec.get("is_starbase", False),
        has_weapons=spec.get("has_weapons", False),
        free_warp_speed=spec.get("free_warp_speed", 0),
        optimal_speed=spec.get("optimal_speed", 6),
        scan_range_normal=spec.get("scan_range_normal", 0),
        scan_range_penetrating=spec.get("scan_range_penetrating", 0),
        dock_capacity=spec.get("dock_capacity", 0),
        battle_speed=spec.get("battle_speed", 0.5),
        initiative=spec.get("initiative", 0),
        weapons=[
            Weapon(power=w.get("power", 0), range=w.get("range", 0),
                   initiative=w.get("initiative", 0), accuracy=w.get("accuracy", 75),
                   group=w.get("group", "standardBeam"))
            for w in spec.get("weapons", [])
        ],
    )


def find_design(empire, name: str):
    """Find an empire design by name."""
    for design in empire.designs.values():
        if design.name == name:
            return design
    return None


def make_token(design, quantity: int = 1) -> ShipToken:
    """
    Create a ShipToken from a design (SimpleDesign or ShipDesign).

    Reads pre-aggregated stats via getattr so both design flavours work.

    Args:
        design: Design to instantiate.
        quantity: Number of ships in the token.

    Returns:
        ShipToken with cached design stats.
    """
    token = ShipToken()
    token.design_key = design.key
    token.design_name = design.name
    token.quantity = quantity

    cost = getattr(design, 'cost', None)
    token.mass = getattr(design, 'mass', 0)
    token.armor = getattr(design, 'armor', 0) * quantity
    token.shields = getattr(design, 'shields', getattr(design, 'shield', 0)) * quantity
    token.fuel_capacity = getattr(design, 'fuel_capacity', 0)
    token.cargo_capacity = getattr(design, 'cargo_capacity', 0)
    token.can_colonize = getattr(design, 'can_colonize', False)
    token.can_refuel = getattr(design, 'can_refuel', False)
    token.can_scan = getattr(design, 'can_scan', False)
    token.is_starbase = getattr(design, 'is_starbase', False)
    token.is_bomber = getattr(design, 'is_bomber', False)
    token.has_weapons = getattr(design, 'has_weapons', False)
    token.free_warp_speed = getattr(design, 'free_warp_speed', 0)
    token.optimal_speed = getattr(design, 'optimal_speed', 6)
    # SimpleDesign caches scan_range_normal; ShipDesign exposes normal_scan
    token.scan_range_normal = getattr(
        design, 'scan_range_normal', None) or getattr(design, 'normal_scan', 0)
    token.scan_range_penetrating = getattr(
        design, 'scan_range_penetrating', None) or getattr(
        design, 'penetrating_scan', 0)
    token.dock_capacity = getattr(design, 'dock_capacity', 0)

    # Mine laying rates (ShipDesign aggregates MineLayer components)
    token.mine_count = getattr(design, 'mine_count', 0)
    heavy = getattr(design, 'heavy_mines', None)
    token.heavy_mine_count = heavy.layer_rate if heavy else 0
    bump = getattr(design, 'speed_bump_mines', None)
    token.speed_bump_mine_count = bump.layer_rate if bump else 0

    # Stargate (ShipDesign aggregates the Gate component; -1 = unlimited)
    gate = getattr(design, 'gate', None)
    if gate:
        token.has_gate = True
        token.gate_mass = int(gate.get("SafeHullMass", -1))
        token.gate_range = int(gate.get("SafeRange", -1))
    return token


def design_from_dict(data: dict):
    """
    Deserialize a design dict back to the right design class.

    SimpleDesign dicts carry design_class == "SimpleDesign"; anything
    else falls back to the full ShipDesign deserializer.
    """
    if data.get("design_class") == "SimpleDesign":
        return SimpleDesign.from_dict(data)
    from ..core.components.ship_design import ShipDesign
    return ShipDesign.from_dict(data)
