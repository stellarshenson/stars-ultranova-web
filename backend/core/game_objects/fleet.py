"""
Fleet class - container for ships.
Port of: Common/GameObjects/Fleet.cs
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
import math

from .mappable import Mappable
from .item import ItemType
from ..data_structures import NovaPoint, Cargo, Resources
from ..waypoints import Waypoint, NoTask

if TYPE_CHECKING:
    from ..race import Race
    from .star import Star


class TravelStatus(IntEnum):
    """Fleet travel status."""
    ARRIVED = 0
    IN_TRANSIT = 1


@dataclass
class ShipToken:
    """
    A token representing ships of the same design in a fleet.

    Port of: Common/GameObjects/ShipToken.cs (simplified)
    """
    design_key: int = 0
    design_name: str = ""
    hull_name: str = ""
    quantity: int = 0
    damage_percent: float = 0.0

    # Cached design values (would normally come from ShipDesign)
    mass: int = 0
    fuel_capacity: int = 0
    cargo_capacity: int = 0
    armor: int = 0
    shields: int = 0
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
    mine_count: int = 0
    heavy_mine_count: int = 0
    speed_bump_mine_count: int = 0
    mining_rate: int = 0
    dock_capacity: int = 0
    heals_others_percent: int = 0

    # Cloak units per kT and Tachyon Detector count (canonical
    # cloaking rules; cached from the design like the fields above)
    cloak_units: int = 0
    tachyon_detectors: int = 0

    # Stargate (starbases with a Gate component); -1 means unlimited
    has_gate: bool = False
    gate_mass: int = 0
    gate_range: int = 0

    # Mass driver warp rating (starbases with Mass Driver components;
    # cached from the design like the fields above, 0 = no driver)
    mass_driver: int = 0

    # Storm protection sources (web-only extension, user directive -
    # galactic storm protection; cached from the design like the
    # fields above). storm_shield is the best Storm Shield component
    # tier fitted (protection fraction 0..1); has_armor_components is
    # True only for fitted armor plates, never the hull's base armor.
    storm_shield: float = 0.0
    has_armor_components: bool = False

    @property
    def key(self) -> int:
        """Return design key as the token key."""
        return self.design_key

    def storm_protection(self, race: Optional['Race'] = None) -> float:
        """
        Storm protection fraction for this token, in [0, 1].

        Web-only extension (galactic storm protection, user directive -
        no C# equivalent). Sources are ADDITIVE, then clamped at 1.0
        (total immunity); each source counts at most once:

        - Storm Shield components: the best tier's protection value
        - conventional shields: STORM_SHIELD_PROTECTION scaled by the
          token's shield coverage. Shields regenerate fully between
          battles and tokens carry no persistent shield depletion, so
          shields present -> full factor
        - armor components: STORM_ARMOR_PROTECTION (hull base armor
          grants nothing)
        - radiation-hardened race: STORM_RAD_RACE_PROTECTION fleet-wide
        """
        from ..globals import (
            STORM_SHIELD_PROTECTION, STORM_ARMOR_PROTECTION,
            STORM_RAD_RACE_PROTECTION
        )
        protection = self.storm_shield
        if self.shields > 0:
            protection += STORM_SHIELD_PROTECTION
        if self.has_armor_components:
            protection += STORM_ARMOR_PROTECTION
        if race is not None and race.is_radiation_hardened:
            protection += STORM_RAD_RACE_PROTECTION
        return max(0.0, min(1.0, protection))

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "design_key": hex(self.design_key),
            "design_name": self.design_name,
            "hull_name": self.hull_name,
            "quantity": self.quantity,
            "damage_percent": self.damage_percent,
            "mass": self.mass,
            "fuel_capacity": self.fuel_capacity,
            "cargo_capacity": self.cargo_capacity,
            "armor": self.armor,
            "shields": self.shields,
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
            "mine_count": self.mine_count,
            "heavy_mine_count": self.heavy_mine_count,
            "speed_bump_mine_count": self.speed_bump_mine_count,
            "mining_rate": self.mining_rate,
            "dock_capacity": self.dock_capacity,
            "heals_others_percent": self.heals_others_percent,
            "cloak_units": self.cloak_units,
            "tachyon_detectors": self.tachyon_detectors,
            "has_gate": self.has_gate,
            "gate_mass": self.gate_mass,
            "gate_range": self.gate_range,
            "mass_driver": self.mass_driver,
            "storm_shield": self.storm_shield,
            "has_armor_components": self.has_armor_components,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ShipToken:
        """Create ShipToken from dictionary."""
        token = cls()
        if "design_key" in data:
            key_str = data["design_key"]
            token.design_key = int(key_str, 16) if isinstance(key_str, str) else key_str
        token.design_name = data.get("design_name", "")
        token.hull_name = data.get("hull_name", "")
        token.quantity = data.get("quantity", 0)
        token.damage_percent = data.get("damage_percent", 0.0)
        token.mass = data.get("mass", 0)
        token.fuel_capacity = data.get("fuel_capacity", 0)
        token.cargo_capacity = data.get("cargo_capacity", 0)
        token.armor = data.get("armor", 0)
        token.shields = data.get("shields", 0)
        token.can_colonize = data.get("can_colonize", False)
        token.can_refuel = data.get("can_refuel", False)
        token.can_scan = data.get("can_scan", False)
        token.is_starbase = data.get("is_starbase", False)
        token.is_bomber = data.get("is_bomber", False)
        token.has_weapons = data.get("has_weapons", False)
        token.free_warp_speed = data.get("free_warp_speed", 0)
        token.optimal_speed = data.get("optimal_speed", 6)
        token.scan_range_normal = data.get("scan_range_normal", 0)
        token.scan_range_penetrating = data.get("scan_range_penetrating", 0)
        token.mine_count = data.get("mine_count", 0)
        token.heavy_mine_count = data.get("heavy_mine_count", 0)
        token.speed_bump_mine_count = data.get("speed_bump_mine_count", 0)
        token.mining_rate = data.get("mining_rate", 0)
        token.dock_capacity = data.get("dock_capacity", 0)
        token.heals_others_percent = data.get("heals_others_percent", 0)
        token.cloak_units = data.get("cloak_units", 0)
        token.tachyon_detectors = data.get("tachyon_detectors", 0)
        token.has_gate = data.get("has_gate", False)
        token.gate_mass = data.get("gate_mass", 0)
        token.gate_range = data.get("gate_range", 0)
        token.mass_driver = data.get("mass_driver", 0)
        token.storm_shield = data.get("storm_shield", 0.0)
        token.has_armor_components = data.get("has_armor_components", False)
        return token


def is_mineral_packet(fleet) -> bool:
    """
    True when the fleet is a mineral-packet pseudo-fleet.

    Canonical Stars! mass-driver rules, C# absent (no MineralPacket
    class exists in the reference). packet_warp is authoritative for
    packets flung by the fling_packet command; the name check keeps
    pre-wave-5 remnant packets in legacy saves recognized.
    """
    return getattr(fleet, 'packet_warp', 0) > 0 or \
        "Mineral Packet" in (fleet.name or "")


@dataclass
class Fleet(Mappable):
    """
    Fleet class. A fleet is a container for one or more ships.

    Port of: Common/GameObjects/Fleet.cs
    """
    # Ship tokens
    tokens: Dict[int, ShipToken] = field(default_factory=dict)

    # Waypoints
    waypoints: List[Waypoint] = field(default_factory=list)

    # Cargo
    cargo: Cargo = field(default_factory=Cargo)

    # Orbit and movement
    in_orbit_name: Optional[str] = None
    in_orbit: Optional['Star'] = field(default=None, repr=False)  # Runtime reference, not persisted
    bearing: float = 0.0
    cloaked: float = 0.0
    fuel_available: float = 0.0
    target_distance: float = 100.0
    battle_plan: str = "Default"
    max_population: int = 1000000  # For AR starbases
    turn_year: int = -1  # For salvage decay

    # Mineral packet pseudo-fleet fields (canonical Stars! mass-driver
    # rules, C# absent). packet_warp is the flight speed the packet
    # was flung at; packet_safe_warp is the flinging driver's rating
    # (overfling above it decays the packet in flight). Both 0 for
    # ordinary fleets, so legacy saves load unchanged.
    packet_warp: int = 0
    packet_safe_warp: int = 0

    def __post_init__(self):
        """Initialize fleet-specific defaults."""
        super().__post_init__()
        self.item_type = ItemType.FLEET

    # =========================================================================
    # Capacity Properties
    # Port of: Fleet.cs lines 96-500
    # =========================================================================

    @property
    def can_colonize(self) -> bool:
        """Check if any ship has colonization module."""
        # Port of: Fleet.cs lines 96-109
        return any(token.can_colonize for token in self.tokens.values())

    @property
    def can_refuel(self) -> bool:
        """Check if fleet can refuel."""
        # Port of: Fleet.cs lines 114-127
        return any(token.can_refuel for token in self.tokens.values())

    def can_scan(self, race: Race) -> bool:
        """Check if fleet can scan."""
        # Port of: Fleet.cs lines 132-144
        for token in self.tokens.values():
            if token.can_scan:
                return True
            # JOAT races with certain ship types get free scanning
            if race.has_trait("JOAT"):
                if any(s in self.name for s in ["Scout", "Frigate", "Destroyer"]):
                    return True
        return False

    @property
    def free_warp_speed(self) -> int:
        """Return free warp speed for fleet (minimum across all ships)."""
        # Port of: Fleet.cs lines 162-174
        if not self.tokens:
            return 0
        return min(token.free_warp_speed for token in self.tokens.values())

    @property
    def heals_others_percent(self) -> int:
        """Return healing capability (maximum across ships)."""
        # Port of: Fleet.cs lines 175-187
        if not self.tokens:
            return 0
        return max(token.heals_others_percent for token in self.tokens.values())

    @property
    def slowest_engine(self) -> int:
        """Return slowest optimal engine speed in fleet."""
        # Port of: Fleet.cs lines 202-215
        if not self.tokens:
            return 0
        speeds = [token.optimal_speed for token in self.tokens.values() if token.optimal_speed > 0]
        return min(speeds) if speeds else 0

    @property
    def has_bombers(self) -> bool:
        """Check if fleet has bombers."""
        # Port of: Fleet.cs lines 226-240
        return any(token.is_bomber for token in self.tokens.values())

    @property
    def is_armed(self) -> bool:
        """Check if fleet is armed."""
        # Port of: Fleet.cs lines 265-278
        return any(token.has_weapons for token in self.tokens.values())

    @property
    def is_starbase(self) -> bool:
        """Check if fleet is a starbase."""
        # Port of: Fleet.cs lines 283-296
        return any(token.is_starbase for token in self.tokens.values())

    @property
    def mass_driver(self) -> int:
        """Best mass driver warp rating aboard (0 = no driver).

        A starbase is a single token, so the max over tokens is exact
        for the receiving/flinging driver rating.
        """
        return max((token.mass_driver for token in self.tokens.values()),
                   default=0)

    @property
    def mass(self) -> int:
        """Return total mass of fleet including cargo."""
        # Port of: Fleet.cs lines 301-315
        total = sum(token.mass * token.quantity for token in self.tokens.values())
        total += self.cargo.mass
        return total

    @property
    def number_of_mines(self) -> int:
        """Return total mines fleet can lay."""
        # Port of: Fleet.cs lines 320-333
        return sum(token.mine_count for token in self.tokens.values())

    @property
    def number_of_heavy_mines(self) -> int:
        """Return total heavy mines fleet can lay."""
        # Port of: Fleet.cs lines 334-347
        return sum(token.heavy_mine_count for token in self.tokens.values())

    @property
    def number_of_speed_bump_mines(self) -> int:
        """Return total speed bump mines fleet can lay."""
        # Port of: Fleet.cs lines 348-361
        return sum(token.speed_bump_mine_count for token in self.tokens.values())

    @property
    def total_mining_rate(self) -> int:
        """Total remote mining rate (kT per mineral per year at 100%).

        No C# equivalent (remote mining is a stub in the reference);
        canonical Stars! rule: every robot on every ship mines, so the
        per-ship design rate multiplies by ship quantity.
        """
        return sum(token.mining_rate * token.quantity
                   for token in self.tokens.values())

    @property
    def speed(self) -> int:
        """Return current speed (from first waypoint)."""
        # Port of: Fleet.cs lines 409-426
        if not self.waypoints:
            return 0
        return self.waypoints[0].warp_factor

    @speed.setter
    def speed(self, value: int) -> None:
        """Set speed on first waypoint."""
        if self.waypoints:
            self.waypoints[0].warp_factor = value

    def storm_protection(self, race: Optional['Race'] = None) -> float:
        """
        Fleet storm protection in [0, 1]: the MINIMUM across tokens.

        Web-only extension (galactic storm protection, user directive -
        no C# equivalent). A convoy is only as protected as its weakest
        ship; 1.0 means total immunity to storm hull damage, warp
        mishaps and colonist attrition (scan dampening is environmental
        and never reduced).
        """
        if not self.tokens:
            return 0.0
        return min(token.storm_protection(race)
                   for token in self.tokens.values())

    @property
    def total_armor_strength(self) -> float:
        """Return total armor strength of fleet."""
        # Port of: Fleet.cs lines 432-438
        return sum(token.armor for token in self.tokens.values())

    @property
    def total_cargo_capacity(self) -> int:
        """Return total cargo capacity of fleet."""
        # Port of: Fleet.cs lines 443-449
        return sum(token.cargo_capacity * token.quantity for token in self.tokens.values())

    @property
    def total_cost(self) -> Resources:
        """Return total cost of fleet (stub - needs design costs)."""
        # Port of: Fleet.cs lines 454-467
        return Resources()  # Would sum design costs

    @property
    def total_dock_capacity(self) -> int:
        """Return total dock capacity."""
        # Port of: Fleet.cs lines 472-478
        return sum(token.dock_capacity for token in self.tokens.values())

    @property
    def total_fuel_capacity(self) -> int:
        """Return total fuel capacity of fleet."""
        # Port of: Fleet.cs lines 483-489
        return sum(token.fuel_capacity * token.quantity for token in self.tokens.values())

    @property
    def total_shield_strength(self) -> float:
        """Return total shield strength of fleet."""
        # Port of: Fleet.cs lines 494-500
        return sum(token.shields for token in self.tokens.values())

    # =========================================================================
    # Travel and Movement
    # Port of: Fleet.cs lines 597-807
    # =========================================================================

    def get_travel_status(self) -> TravelStatus:
        """Check if fleet has arrived at waypoint."""
        # Port of: Fleet.cs lines 597-608
        if not self.waypoints:
            return TravelStatus.ARRIVED
        target = self.waypoints[0]
        if self.position.distance_to_squared(target.position) < 2:
            return TravelStatus.ARRIVED
        return TravelStatus.IN_TRANSIT

    def calculate_interception_point(
        self,
        target_pos: NovaPoint,
        target_velocity: NovaPoint,
        interceptor_pos: NovaPoint,
        interceptor_speed: float
    ) -> Optional[NovaPoint]:
        """
        Calculate interception point for moving target.

        Port of: Fleet.cs lines 633-672
        """
        ox = target_pos.x - interceptor_pos.x
        oy = target_pos.y - interceptor_pos.y

        h1 = (target_velocity.x ** 2 + target_velocity.y ** 2 -
              interceptor_speed ** 2)
        h2 = ox * target_velocity.x + oy * target_velocity.y

        if h1 == 0:
            # Linear equation
            if h2 == 0:
                return None
            t = -(ox * ox + oy * oy) / (2 * h2)
        else:
            # Quadratic equation
            minus_p_half = -h2 / h1
            discriminant = minus_p_half ** 2 - (ox * ox + oy * oy) / h1

            if discriminant < 0:
                return None

            root = math.sqrt(discriminant)
            t1 = minus_p_half + root
            t2 = minus_p_half - root

            t_min = min(t1, t2)
            t_max = max(t1, t2)
            t = t_min if t_min > 0 else t_max

            if t < 0:
                return None

        return NovaPoint(
            x=int(target_pos.x + t * target_velocity.x),
            y=int(target_pos.y + t * target_velocity.y)
        )

    def move(
        self,
        available_time: float,
        race: Race,
        target_velocity: int = 0,
        target_velocity_vector: Optional[NovaPoint] = None
    ) -> Tuple[TravelStatus, float, List[str]]:
        """
        Move fleet towards first waypoint.

        Port of: Fleet.cs lines 683-807

        Returns:
            (TravelStatus, remaining_time, messages)
        """
        messages = []

        if self.get_travel_status() == TravelStatus.ARRIVED:
            return TravelStatus.ARRIVED, available_time, messages

        if not self.waypoints:
            return TravelStatus.ARRIVED, available_time, messages

        target = self.waypoints[0]
        self.in_orbit_name = None

        # Calculate target position (accounting for moving target)
        target_position = target.position.copy()
        if target_velocity != 0 and target_velocity_vector:
            one_years_travel = target_velocity_vector.battle_speed_vector(target_velocity)
            target_position = target_position + one_years_travel

        leg_distance = self._distance_to(self.position, target_position)

        warp_factor = target.warp_factor
        speed = warp_factor * warp_factor
        # Stars! 2.70j uses slightly faster speed for arrival check
        speed_stars = warp_factor * warp_factor + 1 - 1.0 / float(2**31)

        target_time = leg_distance / speed if speed > 0 else float('inf')
        target_time_stars = leg_distance / speed_stars if speed_stars > 0 else float('inf')

        fuel_consumption_rate = self.fuel_consumption(warp_factor, race)

        # Mineral packets don't consume fuel
        if is_mineral_packet(self):
            fuel_consumption_rate = 1.0 / float(2**31)

        # Warp 1 generates fuel
        if warp_factor == 1:
            fuel_consumption_rate = -1

        fuel_time = target_time
        if fuel_consumption_rate > 0:
            fuel_time = self.fuel_available / fuel_consumption_rate

        travel_time = target_time
        if fuel_time < 0:
            fuel_time = target_time

        arrived = TravelStatus.ARRIVED

        # Check if we can reach destination this turn
        if target_time_stars > available_time:
            travel_time = available_time
            arrived = TravelStatus.IN_TRANSIT

        if travel_time > fuel_time:
            travel_time = fuel_time
            arrived = TravelStatus.IN_TRANSIT

        # Update position
        if arrived == TravelStatus.ARRIVED:
            self.position = target.position.copy()
            target.warp_factor = 0
        else:
            travelled = speed * travel_time
            self.position = self._move_towards(
                self.position, target.position, travelled
            )
            leg_distance -= travelled
            target_time = leg_distance / speed if speed > 0 else float('inf')
            if fuel_consumption_rate > 0:
                fuel_time = self.fuel_available / fuel_consumption_rate
            else:
                fuel_time = float('inf')

        # Update fuel
        available_time -= travel_time
        fuel_used = int(fuel_consumption_rate * travel_time)

        if self.total_fuel_capacity / max(1, self.fuel_available) > 2 and fuel_used < 0:
            messages.append(
                f"Fleet {self.name} has generated {-fuel_used} mg of fuel."
            )

        self.fuel_available -= fuel_used

        # Check if out of fuel
        if (arrived == TravelStatus.IN_TRANSIT and
                target_time > fuel_time and
                fuel_consumption_rate > self.fuel_available):
            target.warp_factor = max(1, self.free_warp_speed)
            messages.append(
                f"Fleet {self.name} has run out of fuel. "
                f"Speed reduced to Warp {target.warp_factor}."
            )

        return arrived, available_time, messages

    def fuel_consumption(self, warp_factor: int, race: Race) -> float:
        """
        Calculate fuel consumption rate at given warp factor.

        Port of: Fleet.cs lines 817-839
        """
        if not self.tokens:
            return 0.0

        # Calculate cargo fullness
        if self.total_cargo_capacity == 0:
            cargo_fullness = 0.0
        else:
            cargo_fullness = self.cargo.mass / self.total_cargo_capacity

        # Sum fuel consumption from all ships (per year of travel).
        # Matches the movement model: mass * warp / 200 fuel per ly,
        # at warp^2 ly per year -> mass * warp^3 / 200 per year.
        total = 0.0
        for token in self.tokens.values():
            base_consumption = token.mass * token.quantity * (warp_factor ** 3) / 200.0
            cargo_factor = 1 + cargo_fullness * (token.cargo_capacity * token.quantity / max(1, token.mass * token.quantity))
            total += base_consumption * cargo_factor

        return total

    def fuel_consumption_when_full(self, warp_factor: int, race: Race) -> float:
        """
        Calculate fuel consumption if cargo was full.

        Port of: Fleet.cs lines 847-869
        """
        # Temporarily set cargo to full
        original_cargo = self.cargo.copy()
        if self.total_cargo_capacity > 0:
            # Fake full cargo
            full_cargo = Cargo()
            full_cargo.ironium = self.total_cargo_capacity // 4
            full_cargo.boranium = self.total_cargo_capacity // 4
            full_cargo.germanium = self.total_cargo_capacity // 4
            full_cargo.colonists_in_kilotons = self.total_cargo_capacity // 4
            self.cargo = full_cargo

        result = self.fuel_consumption(warp_factor, race)
        self.cargo = original_cargo
        return result

    def get_fuel_required(
        self, warp_factor: int, race: Race, dest: NovaPoint
    ) -> int:
        """
        Calculate fuel required to reach destination.

        Port of: Fleet.cs lines 943-948
        """
        consumption = self.fuel_consumption(warp_factor, race)
        dist_sq = (dest.x - self.position.x) ** 2 + (dest.y - self.position.y) ** 2
        time = dist_sq / (warp_factor ** 4) if warp_factor > 0 else 0
        return int(time * consumption)

    def max_distance(self, race: Race) -> float:
        """
        Calculate maximum distance fleet can travel.

        Port of: Fleet.cs lines 1084-1089
        """
        if self.slowest_engine == 0:
            return 0.0
        distance_per_year = self.slowest_engine ** 2
        fuel_per_year = self.fuel_consumption_when_full(self.slowest_engine, race)
        if fuel_per_year <= 0:
            return float('inf')
        return self.fuel_available / fuel_per_year * distance_per_year

    # =========================================================================
    # Helper Methods
    # =========================================================================

    @staticmethod
    def _distance_to(p1: NovaPoint, p2: NovaPoint) -> float:
        """Calculate distance between two points."""
        dx = p2.x - p1.x
        dy = p2.y - p1.y
        return math.sqrt(dx * dx + dy * dy)

    @staticmethod
    def _move_towards(start: NovaPoint, end: NovaPoint, distance: float) -> NovaPoint:
        """Move from start towards end by given distance."""
        total_dist = Fleet._distance_to(start, end)
        if total_dist == 0:
            return start.copy()
        ratio = min(1.0, distance / total_dist)
        return NovaPoint(
            x=int(start.x + (end.x - start.x) * ratio),
            y=int(start.y + (end.y - start.y) * ratio)
        )

    # =========================================================================
    # Serialization
    # =========================================================================

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        data = super().to_dict()
        data.update({
            "tokens": {hex(k): v.to_dict() for k, v in self.tokens.items()},
            "waypoints": [wp.to_dict() for wp in self.waypoints],
            "cargo": self.cargo.to_dict(),
            "in_orbit_name": self.in_orbit_name,
            "bearing": self.bearing,
            "cloaked": self.cloaked,
            "fuel_available": self.fuel_available,
            "target_distance": self.target_distance,
            "battle_plan": self.battle_plan,
            "max_population": self.max_population,
            "turn_year": self.turn_year,
            "packet_warp": self.packet_warp,
            "packet_safe_warp": self.packet_safe_warp
        })
        return data

    @classmethod
    def from_dict(cls, data: dict) -> Fleet:
        """Create Fleet from dictionary."""
        fleet = cls()

        # Item fields
        if "key" in data:
            key_str = data["key"]
            fleet._key = int(key_str, 16) if isinstance(key_str, str) else key_str
        fleet.name = data.get("name")
        if "type" in data:
            fleet.item_type = ItemType[data["type"]]

        # Mappable fields
        if "position" in data:
            fleet.position = NovaPoint.from_dict(data["position"])

        # Fleet-specific fields
        if "tokens" in data:
            for key_str, token_data in data["tokens"].items():
                key = int(key_str, 16) if isinstance(key_str, str) else int(key_str)
                fleet.tokens[key] = ShipToken.from_dict(token_data)

        if "waypoints" in data:
            fleet.waypoints = [Waypoint.from_dict(wp) for wp in data["waypoints"]]

        if "cargo" in data:
            fleet.cargo = Cargo.from_dict(data["cargo"])

        fleet.in_orbit_name = data.get("in_orbit_name")
        fleet.bearing = data.get("bearing", 0.0)
        fleet.cloaked = data.get("cloaked", 0.0)
        fleet.fuel_available = data.get("fuel_available", 0.0)
        fleet.target_distance = data.get("target_distance", 100.0)
        fleet.battle_plan = data.get("battle_plan", "Default")
        fleet.max_population = data.get("max_population", 1000000)
        fleet.turn_year = data.get("turn_year", -1)
        fleet.packet_warp = data.get("packet_warp", 0)
        fleet.packet_safe_warp = data.get("packet_safe_warp", 0)

        return fleet

    def __str__(self) -> str:
        """String representation."""
        return f"Fleet: {self.name}"
