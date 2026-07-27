"""
Stars Nova Web - Ship Design
Ported from Common/Components/ShipDesign.cs (954 lines)

Ship design class aggregating hull and components.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, TYPE_CHECKING

from ..game_objects.item import Item, ItemType
from ..data_structures.resources import Resources
from ..globals import (
    BEAM_RATING_MULTIPLIER, CAPACITOR_MAXIMUM, MAX_CLOAK_PERCENT
)

if TYPE_CHECKING:
    from ..race.race import Race

from .hull import Hull
from .hull_module import HullModule
from .engine import Engine
from .component import Component, ComponentProperty


# Canonical Stars! cloaking curve. The C# reference is a stub: the
# design-level "Cloak" summary (probability-stacked percent,
# ShipDesign.cs:621 / ProbabilityProperty.cs:117-121) is never read by
# any game logic, and fleet detection ignores cloak entirely
# (ScanStep.cs:165). Cloaking devices are canonically rated in cloak
# UNITS per kT; Nova's components.xml stores each device's single-ship
# percent, so the inverse table recovers the unit rating.

def cloak_units_from_percent(pct: float) -> float:
    """
    Percent -> cloak units per kT (inverse of the canonical curve).

    The component catalog maxes at 85%, so three branches suffice:
    Stealth Cloak 35%->70u, Super-Stealth 55%->140u, Transport
    Cloaking 75%->300u, Ultra-Stealth 85%->540u.
    """
    if pct <= 50:
        return 2 * pct
    if pct <= 75:
        return 100 + 8 * (pct - 50)
    return 300 + 24 * (pct - 75)


def cloak_percent_from_units(units: float) -> float:
    """
    Cloak units per kT -> cloak percent (canonical piecewise curve).

    Anchors: 70->35, 140->55, 300->75, 540->85. Result capped at
    MAX_CLOAK_PERCENT (documented Stars! maximum of 98%).
    """
    if units <= 100:
        pct = units / 2.0
    elif units <= 300:
        pct = 50 + (units - 100) / 8.0
    elif units <= 612:
        pct = 75 + (units - 300) / 24.0
    elif units <= 1124:
        pct = 88 + (units - 612) / 64.0
    elif units <= 1892:
        pct = 96 + (units - 1124) / 256.0
    else:
        pct = 99.0
    return min(pct, MAX_CLOAK_PERCENT)


@dataclass
class Weapon:
    """Weapon summary for ship design."""
    power: int = 0
    range: int = 0
    initiative: int = 0
    accuracy: int = 0
    group: str = "standardBeam"

    @property
    def is_beam(self) -> bool:
        return self.group in ["standardBeam", "shieldSapper", "gatlingGun"]

    @property
    def is_missile(self) -> bool:
        return self.group in ["torpedo", "missile"]


@dataclass
class Bomb:
    """Bomb capability summary."""
    pop_kill: float = 0.0
    installations: int = 0
    minimum_kill: int = 0
    is_smart: bool = False

    def __add__(self, other: 'Bomb') -> 'Bomb':
        if self.is_smart != other.is_smart:
            return self
        return Bomb(
            pop_kill=self.pop_kill + other.pop_kill,
            installations=self.installations + other.installations,
            minimum_kill=max(self.minimum_kill, other.minimum_kill),
            is_smart=self.is_smart
        )


@dataclass
class MineLayer:
    """Mine layer capability summary."""
    STANDARD_HIT_CHANCE = 0.003
    HEAVY_HIT_CHANCE = 0.01
    SPEED_TRAP_HIT_CHANCE = 0.035

    layer_rate: int = 0
    hit_chance: float = 0.003
    safe_warp: int = 0

    def __add__(self, other: 'MineLayer') -> 'MineLayer':
        return MineLayer(
            layer_rate=self.layer_rate + other.layer_rate,
            hit_chance=self.hit_chance,
            safe_warp=min(self.safe_warp, other.safe_warp) if self.safe_warp > 0 else other.safe_warp
        )


@dataclass
class ShipDesign(Item):
    """
    Ship design aggregating hull and fitted components.

    The design calculates combined stats from all components:
    mass, cost, armor, shields, weapons, scanners, etc.

    Ported from ShipDesign.cs.
    """
    # The hull component (contains Hull property with modules)
    blueprint: Optional[Component] = None
    obsolete: bool = False
    icon_source: str = ""

    # Aggregated summary - recalculated by update()
    _summary_mass: int = field(default=0, repr=False)
    _summary_cost: Resources = field(default_factory=Resources, repr=False)
    _summary_properties: Dict[str, Any] = field(default_factory=dict, repr=False)

    # Weapons can't be simply summed - each fires at its own initiative
    weapons: List[Weapon] = field(default_factory=list)

    # Bombs separated by type
    conventional_bombs: Bomb = field(default_factory=lambda: Bomb(is_smart=False))
    smart_bombs: Bomb = field(default_factory=lambda: Bomb(is_smart=True))

    # Mine layers by type
    standard_mines: MineLayer = field(default_factory=lambda: MineLayer(hit_chance=MineLayer.STANDARD_HIT_CHANCE))
    heavy_mines: MineLayer = field(default_factory=lambda: MineLayer(hit_chance=MineLayer.HEAVY_HIT_CHANCE))
    speed_bump_mines: MineLayer = field(default_factory=lambda: MineLayer(hit_chance=MineLayer.SPEED_TRAP_HIT_CHANCE))

    # Cached values
    _needs_update: bool = field(default=True, repr=False)

    def __post_init__(self):
        self.item_type = ItemType.SHIP

    @property
    def hull(self) -> Optional[Hull]:
        """Get the Hull property from the blueprint."""
        if self.blueprint is None:
            return None
        hull_prop = self.blueprint.get_property("Hull")
        if hull_prop is None:
            return None
        # Convert ComponentProperty to Hull if needed
        if isinstance(hull_prop, Hull):
            return hull_prop
        # Reconstruct Hull from property values
        hull = Hull.from_dict(hull_prop.values)

        # Allocated components serialize by name only (HullModule.to_dict);
        # re-resolve them against the component catalog so aggregation
        # in update() sees real Component objects
        module_dicts = hull_prop.values.get("modules", [])
        if module_dicts:
            from .component_loader import get_component_loader
            loader = get_component_loader()
            for module, m_data in zip(hull.modules, module_dicts):
                name = m_data.get("allocated_component")
                if name and loader.is_loaded:
                    module.allocated_component = loader.get_component(name)
        return hull

    @property
    def mass(self) -> int:
        """Total mass of the design (no cargo)."""
        self._ensure_updated()
        return self._summary_mass

    @property
    def cost(self) -> Resources:
        """Total resource cost to build."""
        self._ensure_updated()
        return self._summary_cost

    @property
    def shield(self) -> int:
        """Total shield value."""
        self._ensure_updated()
        return self._get_int_property("Shield")

    @property
    def armor(self) -> int:
        """Total armor value."""
        self._ensure_updated()
        return self._get_int_property("Armor")

    @property
    def fuel_capacity(self) -> int:
        """Total fuel capacity."""
        self._ensure_updated()
        fuel = self._summary_properties.get("Fuel")
        if fuel and isinstance(fuel, dict):
            return fuel.get("Capacity", 0)
        return 0

    @property
    def cargo_capacity(self) -> int:
        """Total cargo capacity."""
        self._ensure_updated()
        return self._get_int_property("Cargo")

    @property
    def dock_capacity(self) -> int:
        """Dock capacity (starbases only)."""
        hull = self.hull
        return hull.dock_capacity if hull else 0

    @property
    def engine(self) -> Optional[Engine]:
        """Get the fitted engine."""
        self._ensure_updated()
        engine_data = self._summary_properties.get("Engine")
        if engine_data and isinstance(engine_data, dict):
            return Engine.from_dict(engine_data)
        return None

    @property
    def free_warp_speed(self) -> int:
        """Max speed at 0 fuel consumption."""
        engine = self.engine
        return engine.free_warp_speed if engine else 0

    @property
    def battle_speed(self) -> float:
        """
        Calculate battle movement speed.

        Formula from manual:
        Movement = (Ideal_Speed - 4) / 4 - (weight / 70 / 4 / Number_of_Engines)
                   + (Maneuvering_Jets / 4) + (Overthrusters / 2)

        Speed clamped to [0.5, 2.5] in 0.25 increments.
        """
        if self.is_starbase:
            return 0.0

        self._ensure_updated()
        engine = self.engine
        if engine is None:
            return 0.5

        speed = (engine.optimal_speed - 4.0) / 4.0
        num_engines = self.number_of_engines
        if num_engines > 0:
            speed -= self._summary_mass / 70.0 / 4.0 / num_engines

        # Add battle movement bonuses
        battle_move = self._summary_properties.get("Battle Movement")
        if battle_move and isinstance(battle_move, dict):
            speed += battle_move.get("Value", 0.0)

        # Clamp to [0.5, 2.5]
        speed = max(0.5, min(2.5, speed))
        # Round to 0.25 increments
        speed = round(speed * 4.0) / 4.0
        return speed

    @property
    def number_of_engines(self) -> int:
        """Count of engines fitted."""
        hull = self.hull
        if hull is None:
            return 0
        for module in hull.modules:
            if module.allocated_component and module.allocated_component.item_type == ItemType.ENGINE:
                return module.component_count
        return 0

    @property
    def is_starbase(self) -> bool:
        """Check if this is a starbase design."""
        hull = self.hull
        return hull.is_starbase if hull else False

    @property
    def can_refuel(self) -> bool:
        """Check if design can refuel other ships."""
        hull = self.hull
        if hull is None:
            return False
        if hull.can_refuel:
            return True
        fuel = self._summary_properties.get("Fuel")
        if fuel and isinstance(fuel, dict):
            return fuel.get("Generation", 0) > 0
        return False

    @property
    def can_scan(self) -> bool:
        """Check if design has scanners."""
        self._ensure_updated()
        return "Scanner" in self._summary_properties

    @property
    def normal_scan(self) -> int:
        """Normal scanner range."""
        self._ensure_updated()
        scanner = self._summary_properties.get("Scanner")
        if scanner and isinstance(scanner, dict):
            return scanner.get("NormalScan", 0)
        return 0

    @property
    def penetrating_scan(self) -> int:
        """Penetrating scanner range."""
        self._ensure_updated()
        scanner = self._summary_properties.get("Scanner")
        if scanner and isinstance(scanner, dict):
            return scanner.get("PenetratingScan", 0)
        return 0

    @property
    def initiative(self) -> int:
        """Battle initiative (hull + computers)."""
        self._ensure_updated()
        initiative = 0
        hull = self.hull
        if hull:
            initiative += hull.battle_initiative
        computer = self._summary_properties.get("Computer")
        if computer and isinstance(computer, dict):
            initiative += computer.get("Initiative", 0)
        return initiative

    @property
    def jamming(self) -> float:
        """Stacked Jammer percent (torpedo hit chance x (1 - this/100))."""
        self._ensure_updated()
        prop = self._summary_properties.get("Jammer")
        if prop is None:
            return 0.0
        return float(prop.get("Value", 0))

    @property
    def battle_computer_accuracy(self) -> float:
        """Stacked Computer accuracy percent (cuts torpedo miss chance)."""
        self._ensure_updated()
        prop = self._summary_properties.get("Computer")
        if prop is None:
            return 0.0
        return float(prop.get("Accuracy", 0))

    @property
    def capacitor(self) -> float:
        """Stacked Capacitor percent (beam damage x (1 + this/100))."""
        self._ensure_updated()
        prop = self._summary_properties.get("Capacitor")
        if prop is None:
            return 0.0
        return float(prop.get("Value", 0))

    @property
    def beam_deflector(self) -> float:
        """Stacked Beam Deflector percent (beam damage x (1 - this/100))."""
        self._ensure_updated()
        prop = self._summary_properties.get("Beam Deflector")
        if prop is None:
            return 0.0
        return float(prop.get("Value", 0))

    @property
    def can_colonize(self) -> bool:
        """Check if design can colonize planets."""
        self._ensure_updated()
        return "Colonizer" in self._summary_properties

    @property
    def gate(self) -> Optional[dict]:
        """Fitted stargate values ({SafeHullMass, SafeRange}) or None."""
        self._ensure_updated()
        return self._summary_properties.get("Gate")

    @property
    def mass_driver(self) -> int:
        """Aggregated mass driver warp rating (0 = no driver)."""
        self._ensure_updated()
        return self._get_int_property("Mass Driver")

    @property
    def has_weapons(self) -> bool:
        """Check if design has weapons."""
        self._ensure_updated()
        return len(self.weapons) > 0

    @property
    def orbital_adjuster(self) -> int:
        """Summed Orbital Adjuster value (negative = Retro Bombs)."""
        self._ensure_updated()
        prop = self._summary_properties.get("Orbital Adjuster")
        if prop is None:
            return 0
        return prop.get("Value", 0)

    @property
    def cloak_units(self) -> int:
        """Cloak units per kT rating of one ship (canonical curve)."""
        self._ensure_updated()
        prop = self._summary_properties.get("Cloak")
        if prop is None:
            return 0
        return int(prop.get("Units", 0))

    @property
    def tachyon_detectors(self) -> int:
        """Number of Tachyon Detector devices fitted."""
        self._ensure_updated()
        prop = self._summary_properties.get("Tachyon Detector")
        if prop is None:
            return 0
        return prop.get("Count", 0)

    @property
    def storm_shield(self) -> float:
        """Best storm-shield protection fraction fitted (0.0 to 1.0).

        Web-only extension (galactic storm protection, user directive -
        no C# equivalent). The best tier aboard wins; storm shields
        never sum, so a component is never double-counted.
        """
        self._ensure_updated()
        prop = self._summary_properties.get("Storm Shield")
        if prop is None:
            return 0.0
        return float(prop.get("Value", 0.0))

    @property
    def has_armor_components(self) -> bool:
        """Whether any armor COMPONENT is mounted (web-only extension,
        galactic storm protection). The hull's inherent armor strength
        does not count - only fitted armor plates do."""
        hull = self.hull
        if hull is None:
            return False
        for module in hull.modules:
            comp = module.allocated_component
            if (comp is not None and module.component_count > 0
                    and comp.has_property("Armor")):
                return True
        return False

    @property
    def is_bomber(self) -> bool:
        """Check if design can bomb planets."""
        self._ensure_updated()
        # A negative Orbital Adjuster (Retro Bomb) must reach the
        # bombing step even without pop-kill bombs
        return (self.conventional_bombs.pop_kill > 0
                or self.smart_bombs.pop_kill > 0
                or self.orbital_adjuster < 0)

    @property
    def mine_count(self) -> int:
        """Standard mine laying rate."""
        self._ensure_updated()
        return self.standard_mines.layer_rate

    @property
    def mining_rate(self) -> int:
        """Remote mining rate (kT per mineral per year at 100%)."""
        self._ensure_updated()
        return self._get_int_property("Mining Robot")

    @property
    def power_rating(self) -> int:
        """Calculate weapon power rating for ship comparison."""
        self._ensure_updated()
        rating = 0.0
        for weapon in self.weapons:
            if weapon.is_beam:
                # Use beam rating multiplier table
                speed_idx = int(self.battle_speed * 4)
                range_idx = 3 - weapon.range
                if 0 <= speed_idx < len(BEAM_RATING_MULTIPLIER) and 0 <= range_idx < 4:
                    rating += BEAM_RATING_MULTIPLIER[speed_idx][range_idx] * weapon.power
            elif weapon.range > 5:
                rating += weapon.power
            else:
                rating += 1.5 * weapon.power
        return int(rating)

    def _ensure_updated(self):
        """Ensure summary is up to date."""
        if self._needs_update:
            self.update()

    def _get_int_property(self, key: str) -> int:
        """Get an integer property value."""
        prop = self._summary_properties.get(key)
        if prop is None:
            return 0
        if isinstance(prop, dict):
            return prop.get("Value", 0)
        return 0

    def update(self):
        """
        Recalculate aggregated design statistics.

        Scans all hull modules and sums up component properties.
        """
        self._needs_update = False
        self.weapons.clear()
        self._summary_properties.clear()
        self.standard_mines = MineLayer(hit_chance=MineLayer.STANDARD_HIT_CHANCE)
        self.heavy_mines = MineLayer(hit_chance=MineLayer.HEAVY_HIT_CHANCE)
        self.speed_bump_mines = MineLayer(hit_chance=MineLayer.SPEED_TRAP_HIT_CHANCE)
        self.conventional_bombs = Bomb(is_smart=False)
        self.smart_bombs = Bomb(is_smart=True)

        if self.blueprint is None:
            return

        hull = self.hull
        if hull is None:
            return

        # Start with hull's base properties
        self._summary_mass = self.blueprint.mass
        self._summary_cost = Resources(
            self.blueprint.cost.ironium,
            self.blueprint.cost.boranium,
            self.blueprint.cost.germanium,
            self.blueprint.cost.energy
        )

        # Add hull's inherent armor and cargo
        self._summary_properties["Armor"] = {"Value": hull.armor_strength}
        self._summary_properties["Cargo"] = {"Value": hull.base_cargo}
        self._summary_properties["Fuel"] = {"Capacity": hull.fuel_capacity, "Generation": 0}

        # Add components from all modules
        for module in hull.modules:
            if module.allocated_component is not None and module.component_count > 0:
                comp = module.allocated_component
                count = module.component_count

                # Add mass and cost
                self._summary_mass += comp.mass * count
                self._summary_cost = self._summary_cost + (comp.cost * count)

                # Process each property
                for prop_type, prop in comp.properties.items():
                    self._sum_property(prop_type, prop, count)

    def _sum_property(self, prop_type: str, prop: ComponentProperty, count: int):
        """
        Add a component property to the summary.

        Different property types have different aggregation rules.
        """
        values = prop.values

        # Properties that sum directly
        if prop_type in ["Armor", "Cargo", "Shield"]:
            value = values.get("Value", 0) * count
            if prop_type in self._summary_properties:
                self._summary_properties[prop_type]["Value"] += value
            else:
                self._summary_properties[prop_type] = {"Value": value}

        elif prop_type == "Fuel":
            capacity = values.get("Capacity", 0) * count
            generation = values.get("Generation", 0) * count
            if "Fuel" in self._summary_properties:
                self._summary_properties["Fuel"]["Capacity"] += capacity
                self._summary_properties["Fuel"]["Generation"] += generation
            else:
                self._summary_properties["Fuel"] = {"Capacity": capacity, "Generation": generation}

        elif prop_type == "Scanner":
            normal = values.get("NormalScan", 0)
            penetrating = values.get("PenetratingScan", 0)
            if "Scanner" in self._summary_properties:
                # Scanners use best value, not sum
                self._summary_properties["Scanner"]["NormalScan"] = max(
                    self._summary_properties["Scanner"]["NormalScan"], normal)
                self._summary_properties["Scanner"]["PenetratingScan"] = max(
                    self._summary_properties["Scanner"]["PenetratingScan"], penetrating)
            else:
                self._summary_properties["Scanner"] = {
                    "NormalScan": normal,
                    "PenetratingScan": penetrating
                }

        elif prop_type == "Computer":
            # Battle computers (ShipDesign.cs:622 -> Computer.cs):
            # Initiative sums; Accuracy stacks as independent
            # probabilities - per-slot scale (1-(1-a)^n)*100
            # (Computer.cs:129-136), cross-slot 100-(100-a1)(100-a2)/100
            # (Computer.cs:110-118). Canonical rule: each computer
            # multiplies the torpedo MISS chance by (1 - bonus). Note:
            # the C# operator+ computes the stacked accuracy but
            # returns op1 (Computer.cs:117 bug, keeping only the first
            # slot's values); we port the INTENDED math, not the bug.
            initiative = values.get("Initiative", 0) * count
            accuracy = values.get("Accuracy", 0)
            scaled = (1.0 - (1.0 - accuracy / 100.0) ** count) * 100.0
            if "Computer" in self._summary_properties:
                self._summary_properties["Computer"]["Initiative"] += initiative
                old = self._summary_properties["Computer"]["Accuracy"]
                self._summary_properties["Computer"]["Accuracy"] = \
                    100.0 - (100.0 - old) * (100.0 - scaled) / 100.0
            else:
                self._summary_properties["Computer"] = {
                    "Initiative": initiative,
                    "Accuracy": scaled
                }

        elif prop_type == "Jammer":
            # Jammers stack as independent probabilities
            # (ShipDesign.cs:626 -> ProbabilityProperty.cs:111-133):
            # per-slot (1-(1-v)^n)*100, cross-slot
            # 100-(100-v1)(100-v2)/100. Torpedo hit chance is
            # multiplied by (1 - this/100).
            value = values.get("Value", 0)
            scaled = (1.0 - (1.0 - value / 100.0) ** count) * 100.0
            if "Jammer" in self._summary_properties:
                old = self._summary_properties["Jammer"]["Value"]
                self._summary_properties["Jammer"]["Value"] = \
                    100.0 - (100.0 - old) * (100.0 - scaled) / 100.0
            else:
                self._summary_properties["Jammer"] = {"Value": scaled}

        elif prop_type == "Capacitor":
            # Capacitors stack geometrically (ShipDesign.cs:619 ->
            # Capacitor.cs:111-130): per-slot ((1+v)^n - 1)*100,
            # cross-slot ((100+v1)(100+v2))/100 - 100. Every C#
            # constructor clamps to Maximum=250 (Capacitor.cs:41,58,67)
            # so each step clamps - beam multiplier caps at x3.5.
            value = values.get("Value", 0)
            scaled = min(((1.0 + value / 100.0) ** count - 1.0) * 100.0,
                         CAPACITOR_MAXIMUM)
            if "Capacitor" in self._summary_properties:
                old = self._summary_properties["Capacitor"]["Value"]
                scaled = min((100.0 + old) * (100.0 + scaled) / 100.0 - 100.0,
                             CAPACITOR_MAXIMUM)
            self._summary_properties["Capacitor"] = {"Value": scaled}

        elif prop_type == "Beam Deflector":
            # Probability stacking like Jammer. DEVIATION from C#:
            # SumProperty has no "Beam Deflector" case
            # (ShipDesign.cs:613-701) and the BeamDeflectors getter
            # reads the never-written key "Deflector"
            # (ShipDesign.cs:334-346), so C# deflectors are doubly
            # dead. Canonical Stars! rule is beam damage x (1-0.1)^n,
            # which probability stacking of the catalog's 10% values
            # reproduces exactly (2 deflectors -> 19% -> 0.81 = 0.9^2).
            value = values.get("Value", 0)
            scaled = (1.0 - (1.0 - value / 100.0) ** count) * 100.0
            if "Beam Deflector" in self._summary_properties:
                old = self._summary_properties["Beam Deflector"]["Value"]
                self._summary_properties["Beam Deflector"]["Value"] = \
                    100.0 - (100.0 - old) * (100.0 - scaled) / 100.0
            else:
                self._summary_properties["Beam Deflector"] = {"Value": scaled}

        elif prop_type == "Weapon":
            weapon = Weapon(
                power=values.get("Power", 0) * count,
                range=values.get("Range", 0),
                initiative=values.get("Initiative", 0),
                accuracy=values.get("Accuracy", 0),
                group=values.get("Group", "standardBeam")
            )
            self.weapons.append(weapon)

        elif prop_type == "Bomb":
            bomb = Bomb(
                pop_kill=values.get("PopKill", 0) * count,
                installations=values.get("Installations", 0) * count,
                minimum_kill=values.get("MinimumKill", 0),
                is_smart=values.get("IsSmart", False)
            )
            if bomb.is_smart:
                self.smart_bombs = self.smart_bombs + bomb
            else:
                self.conventional_bombs = self.conventional_bombs + bomb

        elif prop_type == "Mine Layer":
            hit_chance = values.get("HitChance", MineLayer.STANDARD_HIT_CHANCE)
            layer = MineLayer(
                layer_rate=values.get("LayerRate", 0) * count,
                hit_chance=hit_chance,
                safe_warp=values.get("SafeWarp", 0)
            )
            if abs(hit_chance - MineLayer.HEAVY_HIT_CHANCE) < 0.001:
                self.heavy_mines = self.heavy_mines + layer
            elif abs(hit_chance - MineLayer.SPEED_TRAP_HIT_CHANCE) < 0.001:
                self.speed_bump_mines = self.speed_bump_mines + layer
            else:
                self.standard_mines = self.standard_mines + layer

        elif prop_type == "Engine":
            # Only keep one engine type
            if "Engine" not in self._summary_properties:
                self._summary_properties["Engine"] = dict(values)

        elif prop_type in ["Colonizer", "Gate"]:
            # Keep one of each - first wins
            if prop_type not in self._summary_properties:
                self._summary_properties[prop_type] = dict(values)

        elif prop_type == "Orbital Adjuster":
            # Summable (ShipDesign.cs:628; IntegerProperty.Add sums),
            # so a stack of N Retro Bombs = adjuster value -N
            value = values.get("Value", 0) * count
            if "Orbital Adjuster" in self._summary_properties:
                self._summary_properties["Orbital Adjuster"]["Value"] += value
            else:
                self._summary_properties["Orbital Adjuster"] = {"Value": value}

        elif prop_type == "Battle Movement":
            value = values.get("Value", 0) * count
            if "Battle Movement" in self._summary_properties:
                self._summary_properties["Battle Movement"]["Value"] += value
            else:
                self._summary_properties["Battle Movement"] = {"Value": value}

        elif prop_type == "Mining Robot":
            # kT of EACH mineral mined per year at 100% concentration.
            # C# intended to sum this via SumProperty case "Robot"
            # (ShipDesign.cs:630), but Component.cs:362 stores the
            # property under the raw xml key "Mining Robot", so the C#
            # case never fires - dead code. We aggregate correctly
            # under the stored key (documented deviation). The Orbital
            # Adjuster has no "Mining Robot" property despite its
            # MiningRobot item type, so it contributes 0 here.
            value = values.get("Value", 0) * count
            if "Mining Robot" in self._summary_properties:
                self._summary_properties["Mining Robot"]["Value"] += value
            else:
                self._summary_properties["Mining Robot"] = {"Value": value}

        elif prop_type == "Cloak":
            # Cloak UNITS stack linearly across devices (canonical
            # Stars! rule: 2 Stealth Cloaks = 140u -> 55%). Documented
            # deviation from the C# probability stacking
            # (ShipDesign.cs:621, ProbabilityProperty.cs:117-121, which
            # would give 57.75%) - that summary was never consumed:
            # fleet detection ignores cloak (ScanStep.cs:165 stub)
            units = cloak_units_from_percent(values.get("Value", 0)) * count
            if "Cloak" in self._summary_properties:
                self._summary_properties["Cloak"]["Units"] += units
            else:
                self._summary_properties["Cloak"] = {"Units": units}

        elif prop_type == "Storm Shield":
            # Web-only extension (galactic storm protection, user
            # directive - no C# equivalent). The BEST tier aboard wins:
            # storm shields never sum, so no stack of low-tier
            # deflectors reaches immunity and no component is ever
            # double-counted.
            value = float(values.get("Value", 0.0))
            if "Storm Shield" in self._summary_properties:
                self._summary_properties["Storm Shield"]["Value"] = max(
                    self._summary_properties["Storm Shield"]["Value"], value)
            else:
                self._summary_properties["Storm Shield"] = {"Value": value}

        elif prop_type == "Mass Driver":
            # Driver warp rating (MassDriver.cs). C# never aggregates
            # this: SumProperty case "Driver" (ShipDesign.cs:624) is
            # dead because Component.cs:362 stores the raw xml key
            # "Mass Driver" - the same dead-key pattern as the "Mining
            # Robot" case above. We aggregate under the stored key.
            # Per-slot Scale (MassDriver.cs:132-139): the comment says
            # "+1 warp speed if more than one" but the code adds +1
            # for scalar >= 1 (a bug like Computer.cs:117); we port
            # the INTENDED math (+1 only for a stack of 2+).
            # Cross-slot Add (MassDriver.cs:113-123): equal ratings
            # give value + 1, else the better of the two wins.
            value = values.get("Value", 0)
            scaled = value + 1 if count >= 2 else value
            if "Mass Driver" in self._summary_properties:
                old = self._summary_properties["Mass Driver"]["Value"]
                self._summary_properties["Mass Driver"]["Value"] = \
                    old + 1 if old == scaled else max(old, scaled)
            else:
                self._summary_properties["Mass Driver"] = {"Value": scaled}

        elif prop_type == "Tachyon Detector":
            # Aggregate the device COUNT, not the XML value (5 =
            # percent effectiveness cut per detector, applied with
            # 4th-root damping at scan time). C# never aggregates this
            # property (no case in ShipDesign.cs SumProperty:615-646)
            if "Tachyon Detector" in self._summary_properties:
                self._summary_properties["Tachyon Detector"]["Count"] += count
            else:
                self._summary_properties["Tachyon Detector"] = {"Count": count}

        # Ignore Hull, Hull Affinity, Transport Ships Only in summary

    def fuel_consumption(self, warp: int, race: 'Race', cargo_mass: int = 0) -> float:
        """
        Calculate fuel consumption at given warp speed.

        Formula: ship_mass * efficiency * distance / 200
        With IFE trait: 15% reduction

        Args:
            warp: Warp speed (1-10)
            race: Race for trait checking
            cargo_mass: Additional cargo mass

        Returns:
            Fuel consumption in mg per year
        """
        if warp == 0:
            return 0.0

        engine = self.engine
        if engine is None:
            return 0.0  # Starbase

        fuel_factor = engine.get_fuel_consumption(warp)
        efficiency = fuel_factor / 100.0
        speed = warp * warp

        consumption = (self._summary_mass + cargo_mass) * efficiency * speed / 200.0

        # IFE trait reduces consumption by 15%
        if race and race.has_trait("IFE"):
            consumption *= 0.85

        # Subtract fuel generation
        fuel = self._summary_properties.get("Fuel")
        if fuel and isinstance(fuel, dict):
            consumption -= fuel.get("Generation", 0)

        return max(0.0, consumption)

    def clear_allocated(self):
        """Remove all allocated components, keeping hull."""
        hull = self.hull
        if hull:
            hull.clear_all_modules()
        self._needs_update = True

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        self._ensure_updated()
        return {
            "key": self.key,
            "name": self.name,
            "obsolete": self.obsolete,
            "icon_source": self.icon_source,
            "blueprint": self.blueprint.to_dict() if self.blueprint else None,
            "mass": self._summary_mass,
            "cost": self._summary_cost.to_dict(),
            "armor": self.armor,
            "shield": self.shield,
            "fuel_capacity": self.fuel_capacity,
            "cargo_capacity": self.cargo_capacity,
            "is_starbase": self.is_starbase
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ShipDesign':
        """Deserialize from dictionary."""
        design = cls(
            name=data.get("name", ""),
            obsolete=data.get("obsolete", False),
            icon_source=data.get("icon_source", "")
        )
        if "key" in data:
            design.key = data["key"]
        if data.get("blueprint"):
            design.blueprint = Component.from_dict(data["blueprint"])
        design._needs_update = True
        return design
