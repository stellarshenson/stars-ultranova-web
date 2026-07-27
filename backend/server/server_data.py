"""
Stars Nova Web - Server Data
Ported from ServerState/Persistence/ServerData.cs (623 lines)

Central game state container for server-side processing.
Holds all persistent data across turn generation.
"""

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Iterator, TYPE_CHECKING

from ..core.globals import (
    STARTING_YEAR, NOBODY, STORM_SHAPE_POINTS, STORM_SHAPE_AMPLITUDE
)

if TYPE_CHECKING:
    from ..core.data_structures import EmpireData
    from ..core.game_objects.star import Star
    from ..core.game_objects.fleet import Fleet
    from ..core.race.race import Race
    from ..core.commands.base import Command, Message


@dataclass
class PlayerSettings:
    """
    Settings for a player in the game.

    Ported from PlayerSettings in ServerData.cs.
    """
    player_number: int = 0
    race_name: str = ""
    ai_program: str = "Human"  # "Human", "Default AI", or AI program name


@dataclass
class EnabledValue:
    """
    Checkbox-plus-number pair used by the victory condition targets.

    Ported from Common/DataStructures/EnabledValue.cs:43-47
    (IsChecked / NumericValue).
    """
    enabled: bool = False
    value: int = 0

    def to_dict(self) -> dict:
        return {"enabled": self.enabled, "value": self.value}

    @classmethod
    def from_dict(cls, data: dict) -> 'EnabledValue':
        return cls(
            enabled=bool(data.get("enabled", False)),
            value=int(data.get("value", 0))
        )


@dataclass
class VictorySettings:
    """
    Victory condition settings for a game.

    Ported from the victory-conditions block of GameSettings
    (Common/Files/GameSettings.cs:49-58, the compiled copy;
    Common/DataStructures/GameSettings.cs:62-71 is a stale duplicate
    with identical defaults). Eight EnabledValue targets
    (number_of_fields is a sub-option of tech_levels) plus two ints.
    """
    planets_owned: EnabledValue = field(
        default_factory=lambda: EnabledValue(True, 60))
    tech_levels: EnabledValue = field(
        default_factory=lambda: EnabledValue(False, 22))
    number_of_fields: EnabledValue = field(
        default_factory=lambda: EnabledValue(False, 4))
    total_score: EnabledValue = field(
        default_factory=lambda: EnabledValue(False, 1000))
    second_place_score: EnabledValue = field(
        default_factory=lambda: EnabledValue(False, 0))
    production_capacity: EnabledValue = field(
        default_factory=lambda: EnabledValue(False, 1000))
    capital_ships: EnabledValue = field(
        default_factory=lambda: EnabledValue(False, 100))
    highest_score: EnabledValue = field(
        default_factory=lambda: EnabledValue(False, 100))
    targets_to_meet: int = 1
    minimum_game_time: int = 50

    _TARGET_FIELDS = (
        "planets_owned", "tech_levels", "number_of_fields",
        "total_score", "second_place_score", "production_capacity",
        "capital_ships", "highest_score"
    )

    def to_dict(self) -> dict:
        result = {
            name: getattr(self, name).to_dict()
            for name in self._TARGET_FIELDS
        }
        result["targets_to_meet"] = self.targets_to_meet
        result["minimum_game_time"] = self.minimum_game_time
        return result

    @classmethod
    def from_dict(cls, data: dict) -> 'VictorySettings':
        """Build from a (possibly partial) dict; missing keys keep
        the C# defaults."""
        settings = cls()
        for name in cls._TARGET_FIELDS:
            if name in data:
                setattr(settings, name, EnabledValue.from_dict(data[name]))
        if "targets_to_meet" in data:
            settings.targets_to_meet = int(data["targets_to_meet"])
        if "minimum_game_time" in data:
            settings.minimum_game_time = int(data["minimum_game_time"])
        return settings


@dataclass
class Minefield:
    """
    Minefield data structure.

    Ported from Minefield in Common.
    """
    key: int = 0
    owner: int = 0
    position_x: float = 0.0
    position_y: float = 0.0
    number_of_mines: int = 0
    mine_type: int = 0  # 0=standard, 1=heavy, 2=speed bump
    # SD remote detonation toggle. C# has no detonation code - the SD
    # trait text is PrimaryTraits.cs:58; canonical Stars! rule: while
    # set, a standard field detonates each year (see TurnGenerator
    # _detonate_minefields).
    detonate: bool = False

    @property
    def radius(self) -> float:
        """Calculate minefield radius from number of mines."""
        import math
        return math.sqrt(self.number_of_mines)

    @property
    def mine_descriptor(self) -> str:
        """Get human-readable mine type description."""
        if self.mine_type == 0:
            return "standard"
        elif self.mine_type == 1:
            return "heavy"
        elif self.mine_type == 2:
            return "speed bump"
        return "unknown"


@dataclass
class Wormhole:
    """
    A wormhole pair connecting two points in space.

    Wormholes existed in original Stars! but were never implemented
    in the Nova codebase; this follows the canonical behaviour:
    stable endpoint pairs that drift slowly over time, giving instant
    transit between the two ends.
    """
    key: int = 0
    name: str = ""
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 0.0
    y2: float = 0.0
    stability: float = 0.5  # 0..1, scales endpoint drift per turn

    def endpoints(self):
        """Both endpoints as (end_index, name, x, y) tuples."""
        return [
            (0, f"{self.name} (A)", self.x1, self.y1),
            (1, f"{self.name} (B)", self.x2, self.y2),
        ]

    def other_end(self, end_index: int):
        """Coordinates of the opposite end."""
        if end_index == 0:
            return self.x2, self.y2
        return self.x1, self.y1

    def drift(self, rng, universe_width: int, universe_height: int) -> None:
        """Jiggle both endpoints; less stable wormholes drift more."""
        magnitude = 1.0 + (1.0 - self.stability) * 3.0
        self.x1 = min(float(universe_width), max(
            0.0, self.x1 + rng.uniform(-magnitude, magnitude)))
        self.y1 = min(float(universe_height), max(
            0.0, self.y1 + rng.uniform(-magnitude, magnitude)))
        self.x2 = min(float(universe_width), max(
            0.0, self.x2 + rng.uniform(-magnitude, magnitude)))
        self.y2 = min(float(universe_height), max(
            0.0, self.y2 + rng.uniform(-magnitude, magnitude)))

    def to_dict(self) -> dict:
        return {
            'key': self.key, 'name': self.name,
            'x1': self.x1, 'y1': self.y1,
            'x2': self.x2, 'y2': self.y2,
            'stability': self.stability,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Wormhole':
        return cls(
            key=data.get('key', 0), name=data.get('name', ''),
            x1=data.get('x1', 0.0), y1=data.get('y1', 0.0),
            x2=data.get('x2', 0.0), y2=data.get('y2', 0.0),
            stability=data.get('stability', 0.5),
        )


@dataclass
class GalacticStorm:
    """
    A roaming galactic storm (web extension - not in original Stars!).

    Storms drift across the universe each turn. The perimeter is an
    irregular blob r(theta) = radius * (1 + amp * low-order sine
    harmonics), sampled at STORM_SHAPE_POINTS angles; the intensity is
    a radial field ramping from 0 at the blob boundary to the storm's
    intensity at the core (user directive 2026-07-13). Every gameplay
    effect scales with the LOCAL intensity at the affected position.
    """
    key: int = 0
    x: float = 0.0
    y: float = 0.0
    radius: float = 40.0      # base radius the blob deviates around
    velocity_x: float = 0.0   # ly per turn
    velocity_y: float = 0.0
    intensity: float = 0.5    # 0.0 to 1.0, peak intensity at the core
    # Blob boundary radii sampled at STORM_SHAPE_POINTS equal angles
    # starting at theta=0; empty means a plain circle of `radius`
    shape_radii: List[float] = field(default_factory=list)

    def generate_shape(self, rng: random.Random) -> None:
        """
        Sample the irregular blob perimeter from an RNG.

        r(theta) = radius * (1 + STORM_SHAPE_AMPLITUDE * mean of 2-4
        low-order sine harmonics with per-storm random phases),
        sampled at STORM_SHAPE_POINTS angles. Deterministic for a
        given RNG state (galaxy generation seeds it from the game
        seed; legacy loads from the storm key and radius).
        """
        harmonics = rng.randint(2, 4)
        phases = [rng.random() * 2 * math.pi for _ in range(harmonics)]
        self.shape_radii = []
        for i in range(STORM_SHAPE_POINTS):
            theta = 2 * math.pi * i / STORM_SHAPE_POINTS
            wave = sum(math.sin((k + 1) * theta + phases[k])
                       for k in range(harmonics)) / harmonics
            self.shape_radii.append(
                self.radius * (1.0 + STORM_SHAPE_AMPLITUDE * wave))

    def boundary_radius(self, theta: float) -> float:
        """Blob boundary radius along a bearing, linearly interpolating
        the sampled perimeter; circular fallback when no shape is
        set."""
        if not self.shape_radii:
            return self.radius
        n = len(self.shape_radii)
        t = (theta % (2 * math.pi)) / (2 * math.pi) * n
        i = int(t) % n
        frac = t - int(t)
        return (self.shape_radii[i] * (1.0 - frac)
                + self.shape_radii[(i + 1) % n] * frac)

    def contains(self, px: float, py: float) -> bool:
        """Check whether a position lies inside the storm blob."""
        dx, dy = px - self.x, py - self.y
        return math.hypot(dx, dy) <= self.boundary_radius(
            math.atan2(dy, dx))

    def get_intensity_at(self, px: float, py: float) -> float:
        """
        Local storm intensity at a position.

        The radial distance from the core is normalized by the blob
        boundary radius along that bearing (0 at core, 1 at boundary,
        >1 outside -> 0) and eased with a smoothstep ramp, so the
        intensity rises from 0 at the boundary to the storm's full
        intensity at the core (user directive 2026-07-13).
        """
        dx, dy = px - self.x, py - self.y
        boundary = self.boundary_radius(math.atan2(dy, dx))
        if boundary <= 0:
            return 0.0
        d = math.hypot(dx, dy) / boundary
        if d >= 1.0:
            return 0.0
        ease = 1.0 - d
        ramp = ease * ease * (3.0 - 2.0 * ease)  # smoothstep
        return self.intensity * ramp

    def drift(self, universe_width: int, universe_height: int) -> None:
        """Move the storm one turn, bouncing off universe edges. The
        blob polygon rides along with the center."""
        self.x += self.velocity_x
        self.y += self.velocity_y
        if self.x < 0 or self.x > universe_width:
            self.velocity_x = -self.velocity_x
            self.x = max(0.0, min(float(universe_width), self.x))
        if self.y < 0 or self.y > universe_height:
            self.velocity_y = -self.velocity_y
            self.y = max(0.0, min(float(universe_height), self.y))

    def to_dict(self) -> dict:
        return {
            'key': self.key, 'x': self.x, 'y': self.y,
            'radius': self.radius,
            'velocity_x': self.velocity_x, 'velocity_y': self.velocity_y,
            'intensity': self.intensity,
            'shape_radii': list(self.shape_radii),
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'GalacticStorm':
        storm = cls(
            key=data.get('key', 0),
            x=data.get('x', 0.0), y=data.get('y', 0.0),
            radius=data.get('radius', 40.0),
            velocity_x=data.get('velocity_x', 0.0),
            velocity_y=data.get('velocity_y', 0.0),
            intensity=data.get('intensity', 0.5),
        )
        radii = data.get('shape_radii')
        if radii:
            storm.shape_radii = [float(r) for r in radii]
        else:
            # Legacy save without a shape: regenerate one
            # deterministically from the stored key and radius
            storm.generate_shape(
                random.Random(storm.key * 1000003 + int(storm.radius)))
        return storm


@dataclass
class MysteryTrader:
    """
    The Mystery Trader: an untouchable neutral ship crossing the galaxy.

    Canonical Stars! Mystery Trader - the C# reference has only a TODO
    (GameInitialiser.cs:180 "Mystery Trader Items ... hidden
    technology"); built from canonical rules per user directive
    (acc-crit Mystery Trader section). Spawns on a galaxy edge, crosses
    in a straight line at warp 7-13 (velocity = heading * warp^2) and
    exits the far side. It belongs to no empire and is not a Fleet, so
    battles, minefields and storms never touch it by construction.
    """
    key: int = 0
    x: float = 0.0
    y: float = 0.0
    velocity_x: float = 0.0  # ly per turn (unit heading * warp^2)
    velocity_y: float = 0.0
    warp: int = 7
    # Per-empire gift ledger: empire_id -> {"total": unrewarded kT
    # balance, "fleet_key": last gifting fleet}. Gifts of different
    # empires accumulate and resolve independently.
    gifts: Dict[int, dict] = field(default_factory=dict)

    @property
    def name(self) -> str:
        """Stable unique name (keys never reuse - trader_counter)."""
        return f"Mystery Trader {self.key}"

    def move(self, universe_width: int, universe_height: int) -> bool:
        """Advance one turn along the straight-line course.

        Returns True when the trader has left the galaxy (spawn points
        sit exactly ON an edge with an inward velocity, so the first
        out-of-bounds step is the exit).
        """
        self.x += self.velocity_x
        self.y += self.velocity_y
        return (self.x < 0 or self.x > universe_width
                or self.y < 0 or self.y > universe_height)

    def to_dict(self) -> dict:
        return {
            'key': self.key, 'x': self.x, 'y': self.y,
            'velocity_x': self.velocity_x, 'velocity_y': self.velocity_y,
            'warp': self.warp,
            'gifts': {str(k): dict(v) for k, v in self.gifts.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'MysteryTrader':
        trader = cls(
            key=data.get('key', 0),
            x=data.get('x', 0.0), y=data.get('y', 0.0),
            velocity_x=data.get('velocity_x', 0.0),
            velocity_y=data.get('velocity_y', 0.0),
            warp=data.get('warp', 7),
        )
        for k, v in data.get('gifts', {}).items():
            trader.gifts[int(k)] = dict(v)
        return trader


@dataclass
class NebulaRegion:
    """
    A single nebula region with position, shape, and density.
    """
    x: float = 0.0
    y: float = 0.0
    radius_x: float = 50.0  # Semi-axis X (for elliptical shape)
    radius_y: float = 50.0  # Semi-axis Y
    rotation: float = 0.0   # Rotation in radians
    density: float = 0.5    # Peak density (0.0 to 1.0)
    nebula_type: str = "emission"  # emission, dark, planetary, etc.


@dataclass
class NebulaField:
    """
    Nebula density field for the galaxy.

    Stores nebula regions and provides density lookup for any position.
    Density affects warp speed: higher density = slower travel.
    """
    regions: List[NebulaRegion] = field(default_factory=list)
    universe_width: int = 600
    universe_height: int = 600

    # Cached density grids for fast lookups
    _grid: Optional[List[List[float]]] = field(default=None, repr=False)
    _dust_grid: Optional[List[List[float]]] = field(default=None, repr=False)
    _emission_grid: Optional[List[List[float]]] = field(default=None, repr=False)
    _grid_resolution: int = 20  # Grid cell size in light years

    def get_density_at(self, x: float, y: float) -> float:
        """
        Get nebula density at a specific position.

        Returns value from 0.0 (no nebula) to 1.0 (dense nebula core).
        Uses cached grid for performance.
        """
        if self._grid is None:
            self._build_grid()
        return self._sample_grid(self._grid, x, y)

    def get_dust_density_at(self, x: float, y: float) -> float:
        """
        Get dust (dark) nebula density at a specific position.

        Only dark/dust nebulae impede travel and dampen sensors;
        emission and filament nebulae are luminous gas without drag.
        """
        if self._dust_grid is None:
            self._build_grid()
        return self._sample_grid(self._dust_grid, x, y)

    def get_emission_density_at(self, x: float, y: float) -> float:
        """
        Get emission nebula density at a specific position.

        Emission glow washes out sensors (nebula glare, user directive
        2026-07-13) but never slows ships - see scan_step.py.
        """
        if self._emission_grid is None:
            self._build_grid()
        return self._sample_grid(self._emission_grid, x, y)

    def get_average_dust_density_along_path(
        self, x1: float, y1: float, x2: float, y2: float, samples: int = 10
    ) -> float:
        """Average dust density along a path (for warp speed penalty)."""
        if samples < 2:
            samples = 2
        total = 0.0
        for i in range(samples):
            t = i / (samples - 1)
            total += self.get_dust_density_at(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t)
        return total / samples

    def _sample_grid(self, grid: Optional[List[List[float]]],
                     x: float, y: float) -> float:
        """Look up a density grid at a world position."""
        # Convert world position to grid cell
        grid_x = int(x / self._grid_resolution)
        grid_y = int(y / self._grid_resolution)

        # Bounds check
        if grid and 0 <= grid_y < len(grid):
            row = grid[grid_y]
            if 0 <= grid_x < len(row):
                return row[grid_x]

        return 0.0

    def get_average_density_along_path(
        self, x1: float, y1: float, x2: float, y2: float, samples: int = 10
    ) -> float:
        """
        Get average nebula density along a path (for warp speed calculation).

        Args:
            x1, y1: Start position
            x2, y2: End position
            samples: Number of sample points along path

        Returns:
            Average density along the path (0.0 to 1.0)
        """
        if samples < 2:
            samples = 2

        total_density = 0.0
        for i in range(samples):
            t = i / (samples - 1)
            x = x1 + (x2 - x1) * t
            y = y1 + (y2 - y1) * t
            total_density += self.get_density_at(x, y)

        return total_density / samples

    def _build_grid(self) -> None:
        """Build cached density grids (all nebulae + dust-only) from regions."""
        import math

        cols = max(1, self.universe_width // self._grid_resolution + 1)
        rows = max(1, self.universe_height // self._grid_resolution + 1)

        self._grid = [[0.0 for _ in range(cols)] for _ in range(rows)]
        self._dust_grid = [[0.0 for _ in range(cols)] for _ in range(rows)]
        self._emission_grid = [[0.0 for _ in range(cols)] for _ in range(rows)]

        for region in self.regions:
            # Calculate bounding box for this region
            max_radius = max(region.radius_x, region.radius_y)
            min_gx = max(0, int((region.x - max_radius) / self._grid_resolution))
            max_gx = min(cols - 1, int((region.x + max_radius) / self._grid_resolution))
            min_gy = max(0, int((region.y - max_radius) / self._grid_resolution))
            max_gy = min(rows - 1, int((region.y + max_radius) / self._grid_resolution))

            cos_r = math.cos(-region.rotation)
            sin_r = math.sin(-region.rotation)

            for gy in range(min_gy, max_gy + 1):
                for gx in range(min_gx, max_gx + 1):
                    # World position of grid cell center
                    wx = (gx + 0.5) * self._grid_resolution
                    wy = (gy + 0.5) * self._grid_resolution

                    # Transform to region's local coordinate system
                    dx = wx - region.x
                    dy = wy - region.y
                    local_x = dx * cos_r - dy * sin_r
                    local_y = dx * sin_r + dy * cos_r

                    # Normalized distance (elliptical)
                    if region.radius_x > 0 and region.radius_y > 0:
                        norm_dist = math.sqrt(
                            (local_x / region.radius_x) ** 2 +
                            (local_y / region.radius_y) ** 2
                        )
                    else:
                        norm_dist = float('inf')

                    # Gaussian falloff
                    if norm_dist < 2.0:  # Only compute within 2 sigma
                        contribution = region.density * math.exp(-norm_dist ** 2)
                        # Additive blending, clamped to 1.0
                        self._grid[gy][gx] = min(1.0, self._grid[gy][gx] + contribution)
                        if region.nebula_type == 'dark':
                            self._dust_grid[gy][gx] = min(
                                1.0, self._dust_grid[gy][gx] + contribution
                            )
                        elif region.nebula_type == 'emission':
                            self._emission_grid[gy][gx] = min(
                                1.0, self._emission_grid[gy][gx] + contribution
                            )

    def invalidate_cache(self) -> None:
        """Invalidate the cached grids (call after modifying regions)."""
        self._grid = None
        self._dust_grid = None
        self._emission_grid = None

    def to_dict(self) -> dict:
        """Serialize to dictionary for persistence."""
        return {
            'regions': [
                {
                    'x': r.x, 'y': r.y,
                    'radius_x': r.radius_x, 'radius_y': r.radius_y,
                    'rotation': r.rotation, 'density': r.density,
                    'nebula_type': r.nebula_type
                }
                for r in self.regions
            ],
            'universe_width': self.universe_width,
            'universe_height': self.universe_height
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'NebulaField':
        """Deserialize from dictionary."""
        nebula_field = cls(
            universe_width=data.get('universe_width', 600),
            universe_height=data.get('universe_height', 600)
        )
        for r in data.get('regions', []):
            nebula_field.regions.append(NebulaRegion(
                x=r.get('x', 0),
                y=r.get('y', 0),
                radius_x=r.get('radius_x', 50),
                radius_y=r.get('radius_y', 50),
                rotation=r.get('rotation', 0),
                density=r.get('density', 0.5),
                nebula_type=r.get('nebula_type', 'emission')
            ))
        return nebula_field


@dataclass
class ServerData:
    """
    Server-side game state container.

    This holds all persistent data across multiple turn generations
    and provides utility methods for iterating and managing game objects.

    Ported from ServerData.cs.
    """
    # Command stacks per empire (empire_id -> stack of commands)
    all_commands: Dict[int, List['Command']] = field(default_factory=dict)

    # Player settings list
    all_players: List[PlayerSettings] = field(default_factory=list)

    # Tech level sums per player (for scoring)
    all_tech_levels: Dict[int, int] = field(default_factory=dict)

    # Empire data per player
    all_empires: Dict[int, 'EmpireData'] = field(default_factory=dict)

    # Race definitions
    all_races: Dict[str, 'Race'] = field(default_factory=dict)

    # All stars in the game (by name)
    all_stars: Dict[str, 'Star'] = field(default_factory=dict)

    # All minefields (by key)
    all_minefields: Dict[int, Minefield] = field(default_factory=dict)

    # Nebula density field (affects warp speed)
    nebula_field: Optional[NebulaField] = None

    # Roaming galactic storms (by key)
    all_storms: Dict[int, GalacticStorm] = field(default_factory=dict)

    # Wormhole pairs (by key)
    all_wormholes: Dict[int, Wormhole] = field(default_factory=dict)

    # Mystery traders currently crossing the galaxy (by key)
    all_traders: Dict[int, MysteryTrader] = field(default_factory=dict)

    # Persisted trader key source - never resets, departed keys are
    # never reused
    trader_counter: int = 0

    # "Mystery Trader" game-creation toggle (default on)
    mystery_trader_enabled: bool = True

    # Messages generated this turn
    all_messages: List['Message'] = field(default_factory=list)

    # Game state flags
    game_in_progress: bool = False
    use_ron_battle_engine: bool = True

    # Victory condition settings (GameSettings.cs:49-58)
    victory_settings: VictorySettings = field(default_factory=VictorySettings)

    # Winning empire id once victory has been declared (None = no
    # victor yet). Persisted so a declared victory survives a server
    # restart; the game stays playable (VictoryCheck.cs "doesn't mean
    # the end of a game")
    victor: Optional[int] = None

    # Current turn year
    turn_year: int = STARTING_YEAR

    # Seed the game was created with (None = unseeded). Web extension:
    # used to make turn generation reproducible (see GameManager.generate_turn)
    game_seed: Optional[int] = None

    # Game folder path (for file-based persistence)
    game_folder: Optional[str] = None
    state_path_name: Optional[str] = None

    # Cache for star position lookups
    _star_position_cache: Optional[Dict[str, 'Star']] = field(
        default=None, repr=False
    )

    def iterate_all_fleets(self) -> Iterator['Fleet']:
        """
        Iterate through all fleets in all empires.

        Ported from IterateAllFleets().

        Yields:
            All fleets from all empires.
        """
        for empire in self.all_empires.values():
            yield from empire.owned_fleets.values()

    def iterate_all_fleet_keys(self) -> Iterator[int]:
        """
        Iterate through all fleet keys in all empires.

        Ported from IterateAllFleetKeys().

        Yields:
            All fleet keys from all empires.
        """
        for empire in self.all_empires.values():
            yield from empire.owned_fleets.keys()

    def iterate_all_designs(self):
        """
        Iterate through all ship designs in all empires.

        Ported from IterateAllDesigns().

        Yields:
            All ship designs from all empires.
        """
        for empire in self.all_empires.values():
            yield from empire.designs.values()

    def iterate_all_mappables(self):
        """
        Iterate through all mappable objects (stars and fleets).

        Ported from IterateAllMappables().

        Yields:
            All stars and fleets.
        """
        yield from self.all_stars.values()
        for empire in self.all_empires.values():
            yield from empire.owned_fleets.values()

    def cleanup_fleets(self):
        """
        Remove fleets that no longer have ships.

        This needs to be done after each time the fleet list is processed,
        as fleets cannot be destroyed until the iterator completes.

        Ported from CleanupFleets().
        """
        # Find all fleets with no ships
        destroyed_fleets: List[int] = []

        for fleet in self.iterate_all_fleets():
            if len(fleet.tokens) == 0:
                destroyed_fleets.append(fleet.key)

        # Remove destroyed fleets from all empires
        for key in destroyed_fleets:
            for empire in self.all_empires.values():
                if key in empire.owned_fleets:
                    del empire.owned_fleets[key]
                if key in empire.fleet_reports:
                    del empire.fleet_reports[key]

        # Remove destroyed starbases
        # Note: Star has starbase_key (int) pointing to a fleet, not starbase object
        # Starbase cleanup is handled when the fleet is destroyed
        destroyed_stations: List[str] = []
        for star in self.all_stars.values():
            # Check if star has a starbase_key that references a destroyed fleet
            if hasattr(star, 'starbase_key') and star.starbase_key is not None:
                # Would need to look up fleet by key to check if destroyed
                # For now, starbases are cleaned up when fleet iteration finds empty fleet
                pass

        for name in destroyed_stations:
            self.all_stars[name].starbase_key = None

        # Handle salvage decay (salvage decays 30% per turn)
        for empire in self.all_empires.values():
            deleted_fleets: List[int] = []
            for fleet in empire.owned_fleets.values():
                if fleet.turn_year > 0 and fleet.name == "S A L V A G E":
                    fleet.cargo.ironium = int(fleet.cargo.ironium * 0.7)
                    fleet.cargo.boranium = int(fleet.cargo.boranium * 0.7)
                    fleet.cargo.germanium = int(fleet.cargo.germanium * 0.7)
                    if self.turn_year - fleet.turn_year > 3:
                        deleted_fleets.append(fleet.key)

            for key in deleted_fleets:
                if key in empire.owned_fleets:
                    del empire.owned_fleets[key]

    def set_fleet_orbit(self, fleet: 'Fleet'):
        """
        Check if fleet is orbiting a star and set the reference.

        Ported from SetFleetOrbit().

        Args:
            fleet: The fleet to check.
        """
        try:
            fleet.in_orbit = self.get_star_at_position(
                fleet.position.x, fleet.position.y
            )
        except (KeyError, AttributeError):
            fleet.in_orbit = None
        # Keep the persisted orbit name in sync with the runtime
        # reference (movement previously left in_orbit_name stale at
        # the departure star)
        fleet.in_orbit_name = fleet.in_orbit.name if fleet.in_orbit else None

    def get_star_at_position(self, x: float, y: float) -> Optional['Star']:
        """
        Get the star at a given position.

        Ported from GetStarAtPosition().

        Args:
            x: X coordinate.
            y: Y coordinate.

        Returns:
            Star at position, or None if no star found.
        """
        if self._star_position_cache is None:
            self._star_position_cache = {}
            for star in self.all_stars.values():
                key = f"{star.position.x:.0f},{star.position.y:.0f}"
                self._star_position_cache[key] = star

        key = f"{x:.0f},{y:.0f}"
        return self._star_position_cache.get(key)

    def clear(self):
        """
        Reset all values to defaults.

        Ported from Clear().
        """
        self.all_commands.clear()
        self.all_players.clear()
        self.all_tech_levels.clear()
        self.all_empires.clear()
        self.all_races.clear()
        self.all_stars.clear()
        self.all_minefields.clear()
        self.all_messages.clear()

        self.game_folder = None
        self.game_in_progress = False
        self.use_ron_battle_engine = True
        self.victory_settings = VictorySettings()
        self.victor = None
        self.turn_year = STARTING_YEAR
        self.state_path_name = None
        self._star_position_cache = None

    def to_dict(self) -> dict:
        """Serialize to dictionary for persistence."""
        return {
            "game_in_progress": self.game_in_progress,
            "use_ron_battle_engine": self.use_ron_battle_engine,
            "victory_settings": self.victory_settings.to_dict(),
            "victor": self.victor,
            "turn_year": self.turn_year,
            "game_seed": self.game_seed,
            "game_folder": self.game_folder,
            "state_path_name": self.state_path_name,
            "all_tech_levels": self.all_tech_levels,
            "all_players": [
                {
                    "player_number": p.player_number,
                    "race_name": p.race_name,
                    "ai_program": p.ai_program
                }
                for p in self.all_players
            ],
            "all_minefields": {
                str(k): {
                    "key": v.key,
                    "owner": v.owner,
                    "position_x": v.position_x,
                    "position_y": v.position_y,
                    "number_of_mines": v.number_of_mines,
                    "mine_type": v.mine_type,
                    "detonate": v.detonate
                }
                for k, v in self.all_minefields.items()
            },
            "all_storms": {
                str(k): v.to_dict() for k, v in self.all_storms.items()
            },
            "all_wormholes": {
                str(k): v.to_dict() for k, v in self.all_wormholes.items()
            },
            "all_traders": {
                str(k): v.to_dict() for k, v in self.all_traders.items()
            },
            "trader_counter": self.trader_counter,
            "mystery_trader_enabled": self.mystery_trader_enabled
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ServerData':
        """Deserialize from dictionary."""
        server = cls(
            game_in_progress=data.get("game_in_progress", False),
            use_ron_battle_engine=data.get("use_ron_battle_engine", True),
            victory_settings=VictorySettings.from_dict(
                data.get("victory_settings", {})),
            victor=data.get("victor"),
            turn_year=data.get("turn_year", STARTING_YEAR),
            game_seed=data.get("game_seed"),
            game_folder=data.get("game_folder"),
            state_path_name=data.get("state_path_name")
        )

        server.all_tech_levels = data.get("all_tech_levels", {})

        for p_data in data.get("all_players", []):
            server.all_players.append(PlayerSettings(
                player_number=p_data.get("player_number", 0),
                race_name=p_data.get("race_name", ""),
                ai_program=p_data.get("ai_program", "Human")
            ))

        for k, v in data.get("all_minefields", {}).items():
            server.all_minefields[int(k)] = Minefield(
                key=v.get("key", 0),
                owner=v.get("owner", 0),
                position_x=v.get("position_x", 0.0),
                position_y=v.get("position_y", 0.0),
                number_of_mines=v.get("number_of_mines", 0),
                mine_type=v.get("mine_type", 0),
                detonate=v.get("detonate", False)
            )

        for k, v in data.get("all_storms", {}).items():
            server.all_storms[int(k)] = GalacticStorm.from_dict(v)

        for k, v in data.get("all_wormholes", {}).items():
            server.all_wormholes[int(k)] = Wormhole.from_dict(v)

        # Pre-trader saves load cleanly with the defaults
        for k, v in data.get("all_traders", {}).items():
            server.all_traders[int(k)] = MysteryTrader.from_dict(v)
        server.trader_counter = data.get("trader_counter", 0)
        server.mystery_trader_enabled = data.get(
            "mystery_trader_enabled", True)

        return server
