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
from ..core.components.boarding import (
    base_boarding_strength, is_boarding_specialist)
from ..core.components.engine import Engine
from ..core.components.ship_design import Weapon
from ..core.components.ship_role import ShipRole, battle_role_of


# Per-warp engine fuel tables (index 0 = warp 1, index 9 = warp 10;
# C# Engine.cs:34, consumed as table[warp - 1] per ShipDesign.cs:732).
# backend/data/components.xml is the single source for every table -
# nothing here duplicates the numbers. Its fuel-burning entries are the
# canonical references/original-game/components.xml values; the NEGATIVE
# entries on the ram-scoop engines listed in
# Engine.WEB_MOD_RAMSCOOP_ENGINES are a deliberate web mod marking free
# warps with fuel generation (C# stores 0 there). The old note about
# hardcoding to keep SimpleDesign loader-free no longer applies: the
# lookup below imports the loader lazily and memoizes, so a process
# parses the catalog at most once.
_FUEL_TABLE_CACHE: dict = {}


def engine_fuel_table(engine_name: str) -> List[int]:
    """
    Resolve an engine's per-warp fuel table from the component catalog.

    Args:
        engine_name: Component name, "" for no engine (starbase).

    Returns:
        A fresh 10-entry table; all zeros for no/unknown engine.
    """
    if not engine_name:
        return [0] * 10
    cached = _FUEL_TABLE_CACHE.get(engine_name)
    if cached is None:
        from .design_builder import ensure_components_loaded
        loader = ensure_components_loaded()
        component = loader.get_component(engine_name)
        prop = component.get_property("Engine") if component else None
        cached = list(prop.values["fuel_consumption"]) if prop else [0] * 10
        _FUEL_TABLE_CACHE[engine_name] = cached
    return list(cached)


_HULL_SLOT_CACHE: dict = {}


def hull_slot_counts(hull_name: str) -> tuple:
    """
    Resolve (module slots, Boarding-only troop bays) for a hull.

    Reads the component catalog so a SimpleDesign's boarding party is
    derived from the same hull data a full ShipDesign reads, with no
    duplicated per-hull table and nothing extra to persist.

    Args:
        hull_name: Hull component name, "" for an unknown hull.

    Returns:
        (total slots, troop bays); (0, 0) for an unknown hull.
    """
    if not hull_name:
        return (0, 0)
    cached = _HULL_SLOT_CACHE.get(hull_name)
    if cached is None:
        from ..core.components.boarding import TROOP_BAY_SLOT
        from .design_builder import ensure_components_loaded
        loader = ensure_components_loaded()
        component = loader.get_component(hull_name)
        prop = component.get_property("Hull") if component else None
        modules = prop.values.get("modules", []) if prop else []
        cached = (
            len(modules),
            sum(1 for m in modules
                if (m.get("component_type") or "").strip() == TROOP_BAY_SLOT),
        )
        _HULL_SLOT_CACHE[hull_name] = cached
    return cached


def _free_warp_from_table(fuel_table: List[int]) -> int:
    """
    Highest warp whose table entry is <= 0 (free travel).

    Delegates to Engine.free_warp_speed so the web <= 0 convention
    (C# Engine.cs lines 43-56 tests == 0) has one implementation.
    """
    return Engine(fuel_consumption=list(fuel_table)).free_warp_speed


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
    # Extra fleet repair percent granted by the hull (full ShipDesign
    # reads Hull.heals_others_percent from the blueprint)
    heals_others_percent: int = 0
    obsolete: bool = False
    hull_name: str = ""
    battle_speed: float = 0.5
    initiative: int = 0
    weapons: List[Weapon] = field(default_factory=list)
    # Mine laying rates (mines laid per year; full ShipDesign derives
    # these from MineLayer components)
    mine_count: int = 0
    speed_bump_mine_count: int = 0
    # Remote mining rate (kT per mineral per year at 100% concentration;
    # full ShipDesign derives this from Mining Robot components)
    mining_rate: int = 0
    # Cloak units per kT and Tachyon Detector count (full ShipDesign
    # derives these from Cloak / Tachyon Detector properties)
    cloak_units: int = 0
    tachyon_detectors: int = 0
    # Storm protection (web-only extension; full ShipDesign derives
    # these from Storm Shield / Armor component properties)
    storm_shield: float = 0.0
    has_armor_components: bool = False
    # Mass driver warp rating (full ShipDesign aggregates Mass Driver
    # components per MassDriver.cs semantics; 0 = no driver)
    mass_driver: int = 0
    # Mounted engine and its per-warp fuel table (index 0 = warp 1;
    # C# Engine.cs:34 / ShipDesign.cs:732). All zeros = no engine
    # (starbase)
    engine_name: str = ""
    fuel_table: List[int] = field(default_factory=lambda: [0] * 10)
    # Multiplier fitted boarding gear applies to this ship's own
    # boarding party (web-only extension; full ShipDesign aggregates
    # the Boarding component property). 1.0 = no gear fitted
    boarding_multiplier: float = 1.0

    @property
    def power_rating(self) -> int:
        """Rough combat value used for battle targeting."""
        weapon_power = sum(w.power for w in self.weapons)
        return weapon_power * 10 + self.armor + self.shields

    @property
    def shield(self) -> int:
        """Alias used by battle code (ShipDesign uses 'shield')."""
        return self.shields

    @property
    def base_boarding_strength(self) -> int:
        """
        The boarding party this hull musters with no gear fitted.

        Derived from the catalog hull the design names, so the value
        matches a full ShipDesign on the same hull and nothing has to
        be persisted or migrated (boarding.py).
        """
        slots, bays = hull_slot_counts(self.hull_name)
        return base_boarding_strength(slots, bays)

    @property
    def boarding_strength(self) -> float:
        """Boarding strength of ONE ship of this design."""
        return self.base_boarding_strength * self.boarding_multiplier

    @property
    def is_boarder(self) -> bool:
        """Whether fitted gear makes this a dedicated boarding ship."""
        return is_boarding_specialist(self.boarding_multiplier)

    @property
    def battle_role(self) -> ShipRole:
        """The single battle role this design falls into."""
        return battle_role_of(self)

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
            # Derived, not stored: from_dict re-infers it from the
            # capability fields, so old saves classify identically
            "battle_role": self.battle_role.value,
            "has_weapons": self.has_weapons,
            "free_warp_speed": self.free_warp_speed,
            "optimal_speed": self.optimal_speed,
            "scan_range_normal": self.scan_range_normal,
            "scan_range_penetrating": self.scan_range_penetrating,
            "dock_capacity": self.dock_capacity,
            "heals_others_percent": self.heals_others_percent,
            "obsolete": self.obsolete,
            "hull_name": self.hull_name,
            "battle_speed": self.battle_speed,
            "initiative": self.initiative,
            "mine_count": self.mine_count,
            "speed_bump_mine_count": self.speed_bump_mine_count,
            "mining_rate": self.mining_rate,
            "cloak_units": self.cloak_units,
            "tachyon_detectors": self.tachyon_detectors,
            "storm_shield": self.storm_shield,
            "has_armor_components": self.has_armor_components,
            "mass_driver": self.mass_driver,
            "engine_name": self.engine_name,
            "fuel_table": list(self.fuel_table),
            "boarding_multiplier": self.boarding_multiplier,
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
        design.heals_others_percent = data.get("heals_others_percent", 0)
        design.obsolete = data.get("obsolete", False)
        design.hull_name = data.get("hull_name", "")
        design.battle_speed = data.get("battle_speed", 0.5)
        design.initiative = data.get("initiative", 0)
        design.mine_count = data.get("mine_count", 0)
        design.speed_bump_mine_count = data.get("speed_bump_mine_count", 0)
        design.mining_rate = data.get("mining_rate", 0)
        design.cloak_units = data.get("cloak_units", 0)
        design.tachyon_detectors = data.get("tachyon_detectors", 0)
        design.storm_shield = data.get("storm_shield", 0.0)
        design.has_armor_components = data.get("has_armor_components", False)
        design.mass_driver = data.get("mass_driver", 0)
        design.engine_name = data.get("engine_name", "")
        design.fuel_table = list(data.get("fuel_table", [0] * 10))
        # Saves written before boarding existed carry no gear, so the
        # no-gear multiplier is the right default; the hull half of the
        # party is re-derived from hull_name and never persisted
        design.boarding_multiplier = data.get("boarding_multiplier", 1.0)
        design.weapons = [
            Weapon(power=w.get("power", 0), range=w.get("range", 0),
                   initiative=w.get("initiative", 0), accuracy=w.get("accuracy", 75),
                   group=w.get("group", "standardBeam"))
            for w in data.get("weapons", [])
        ]
        return design


# Starting design specs - stats follow the original game's starting
# ships. Every ship mounts Quick Jump 5 except the HE Spore Cloud
# (Settler's Delight) per StarMapInitialiser.cs:140-151; the starbase
# has no engine
STARTING_DESIGN_SPECS = [
    {
        "name": "Long Range Scout",
        "hull_name": "Scout",
        "engine": "Quick Jump 5",
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
        "engine": "Quick Jump 5",
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
        "engine": "Quick Jump 5",
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
        "engine": "Quick Jump 5",
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
    # Per-PRT starting extras below follow canonical Stars! rules; the
    # C# reference registers only colony ship / scout / starbase and
    # leaves the per-PRT fleets as comments (GameInitialiser.cs:192-248,
    # StarMapInitialiser.cs:259-302). Registered for every empire
    # (superset), as C# registers designs the race can build anyway.
    {
        # HE starting colonizer: Mini-Colony Ship hull with the
        # Settler's Delight engine (StarMapInitialiser.cs:143-151).
        # free_warp_speed derives from the engine table: warp 6
        "name": "Spore Cloud",
        "hull_name": "Mini-Colony Ship",
        "engine": "Settler's Delight",
        "cost": {"ironium": 12, "boranium": 3, "germanium": 9, "energy": 22},
        "mass": 32,
        "armor": 20,
        "fuel_capacity": 150,
        "cargo_capacity": 10,
        "can_colonize": True,
        "optimal_speed": 5,
    },
    {
        # Armed scout for HE and WM (X-Ray-class beam)
        "name": "Armed Probe",
        "hull_name": "Scout",
        "engine": "Quick Jump 5",
        "cost": {"ironium": 9, "boranium": 4, "germanium": 8, "energy": 26},
        "mass": 27,
        "armor": 20,
        "fuel_capacity": 300,
        "can_scan": True,
        "scan_range_normal": 66,
        "optimal_speed": 9,
        "has_weapons": True,
        "battle_speed": 1.0,
        "initiative": 1,
        "weapons": [
            {"power": 16, "range": 1, "initiative": 9, "accuracy": 75, "group": "standardBeam"},
        ],
    },
    {
        # PP shielded scout
        "name": "Shielded Scout",
        "hull_name": "Scout",
        "engine": "Quick Jump 5",
        "cost": {"ironium": 10, "boranium": 2, "germanium": 9, "energy": 26},
        "mass": 28,
        "armor": 20,
        "shields": 25,
        "fuel_capacity": 300,
        "can_scan": True,
        "scan_range_normal": 66,
        "optimal_speed": 9,
    },
    {
        # SD standard mine layer (Mine Dispenser 40)
        "name": "Little Hen",
        "hull_name": "Mini Mine Layer",
        "engine": "Quick Jump 5",
        "cost": {"ironium": 20, "boranium": 10, "germanium": 10, "energy": 40},
        "mass": 60,
        "armor": 60,
        "fuel_capacity": 400,
        "optimal_speed": 6,
        "mine_count": 40,
    },
    {
        # SD speed-trap mine layer (Speed Trap 20)
        "name": "Speed Turtle",
        "hull_name": "Mini Mine Layer",
        "engine": "Quick Jump 5",
        "cost": {"ironium": 20, "boranium": 10, "germanium": 10, "energy": 40},
        "mass": 60,
        "armor": 60,
        "fuel_capacity": 400,
        "optimal_speed": 6,
        "speed_bump_mine_count": 20,
    },
    {
        # IT starting privateer
        "name": "Swashbuckler",
        "hull_name": "Privateer",
        "engine": "Quick Jump 5",
        "cost": {"ironium": 38, "boranium": 2, "germanium": 22, "energy": 80},
        "mass": 150,
        "armor": 150,
        "fuel_capacity": 650,
        "cargo_capacity": 250,
        "optimal_speed": 6,
    },
    {
        # JOAT starting mini-miner (also the ARM midget-miner stand-in;
        # carries no robots, so it mines 0 until refitted)
        "name": "Cotton Picker",
        "hull_name": "Mini Miner",
        "engine": "Quick Jump 5",
        "cost": {"ironium": 25, "boranium": 0, "germanium": 6, "energy": 50},
        "mass": 80,
        "armor": 50,
        "fuel_capacity": 210,
        "optimal_speed": 6,
    },
    {
        # No mass_driver here: the PP starting warp-5 accelerator at
        # the home starbase (PrimaryTraits.cs:59 trait text) is out of
        # scope - drivers arrive via player starbase designs
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
    # Resolve the mounted engine's fuel table; free warp derives from
    # the table (Engine.cs:43-56 with the web <= 0 rule), overriding
    # any hand-set spec value
    engine_name = spec.get("engine", "")
    fuel_table = engine_fuel_table(engine_name)
    if engine_name:
        free_warp = _free_warp_from_table(fuel_table)
    else:
        free_warp = spec.get("free_warp_speed", 0)
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
        free_warp_speed=free_warp,
        engine_name=engine_name,
        fuel_table=fuel_table,
        optimal_speed=spec.get("optimal_speed", 6),
        scan_range_normal=spec.get("scan_range_normal", 0),
        scan_range_penetrating=spec.get("scan_range_penetrating", 0),
        dock_capacity=spec.get("dock_capacity", 0),
        battle_speed=spec.get("battle_speed", 0.5),
        initiative=spec.get("initiative", 0),
        mine_count=spec.get("mine_count", 0),
        speed_bump_mine_count=spec.get("speed_bump_mine_count", 0),
        cloak_units=spec.get("cloak_units", 0),
        tachyon_detectors=spec.get("tachyon_detectors", 0),
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
    # Hull blueprint name (SimpleDesign caches hull_name; ShipDesign
    # exposes it via blueprint.name) - drives the gate hull-size limit
    token.hull_name = getattr(design, 'hull_name', '') or (
        design.blueprint.name
        if getattr(design, 'blueprint', None) else '')
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

    # Per-warp engine fuel table (C# Engine.cs:34, consumed as
    # table[warp - 1] per ShipDesign.cs:732). Full ShipDesign exposes
    # the fitted Engine; SimpleDesign caches fuel_table directly.
    # All zeros = no engine (starbase) - burns nothing
    engine = getattr(design, 'engine', None)
    if engine is not None:
        token.fuel_table = list(engine.fuel_consumption)
    else:
        token.fuel_table = list(getattr(design, 'fuel_table', [0] * 10))
    # Fuel generated per year (web mod - ShipDesign.fuel_consumption
    # subtracts Fuel property "Generation"; no C# equivalent)
    token.fuel_generation = getattr(design, 'fuel_generation', 0)
    # SimpleDesign caches scan_range_normal; ShipDesign exposes normal_scan
    token.scan_range_normal = getattr(
        design, 'scan_range_normal', None) or getattr(design, 'normal_scan', 0)
    token.scan_range_penetrating = getattr(
        design, 'scan_range_penetrating', None) or getattr(
        design, 'penetrating_scan', 0)
    token.dock_capacity = getattr(design, 'dock_capacity', 0)
    # Repair-tender bonus (Hull.HealsOthersPercent: Fuel Transport 5,
    # Super-Fuel Xport 10) - Fleet.heals_others_percent takes the max
    # over tokens and TurnGenerator adds it to the repair rate
    token.heals_others_percent = getattr(design, 'heals_others_percent', 0)

    # Mine laying rates (ShipDesign aggregates MineLayer components)
    token.mine_count = getattr(design, 'mine_count', 0)
    # Remote mining rate per ship (ShipDesign aggregates Mining Robot
    # components; SimpleDesign caches the same field)
    token.mining_rate = getattr(design, 'mining_rate', 0)
    heavy = getattr(design, 'heavy_mines', None)
    token.heavy_mine_count = heavy.layer_rate if heavy else 0
    bump = getattr(design, 'speed_bump_mines', None)
    token.speed_bump_mine_count = bump.layer_rate if bump else getattr(
        design, 'speed_bump_mine_count', 0)

    # Cloak units per kT and Tachyon Detector count (canonical
    # cloaking rules; ShipDesign aggregates Cloak / Tachyon Detector
    # properties, SimpleDesign caches the same fields)
    token.cloak_units = getattr(design, 'cloak_units', 0)
    token.tachyon_detectors = getattr(design, 'tachyon_detectors', 0)

    # Boarding strength of one ship (web-only extension; hull-derived
    # party times fitted gear, backend/core/components/boarding.py).
    # Cached like the fields above so the battle engine can read it
    # from a token whose design object is missing
    token.boarding_strength = float(getattr(design, 'boarding_strength', 0.0))

    # Storm protection sources (web-only extension; ShipDesign
    # aggregates Storm Shield / Armor component properties)
    token.storm_shield = getattr(design, 'storm_shield', 0.0)
    token.has_armor_components = getattr(design, 'has_armor_components',
                                         False)

    # Mass driver warp rating (ShipDesign aggregates Mass Driver
    # components; SimpleDesign caches the same field)
    token.mass_driver = getattr(design, 'mass_driver', 0)

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
