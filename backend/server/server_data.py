"""
Stars Nova Web - Server Data
Ported from ServerState/Persistence/ServerData.cs (623 lines)

Central game state container for server-side processing.
Holds all persistent data across turn generation.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Iterator, TYPE_CHECKING

from ..core.globals import STARTING_YEAR, NOBODY

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

    # Cached density grid for fast lookups
    _grid: Optional[List[List[float]]] = field(default=None, repr=False)
    _grid_resolution: int = 20  # Grid cell size in light years

    def get_density_at(self, x: float, y: float) -> float:
        """
        Get nebula density at a specific position.

        Returns value from 0.0 (no nebula) to 1.0 (dense nebula core).
        Uses cached grid for performance.
        """
        if self._grid is None:
            self._build_grid()

        # Convert world position to grid cell
        grid_x = int(x / self._grid_resolution)
        grid_y = int(y / self._grid_resolution)

        # Bounds check
        if self._grid and 0 <= grid_y < len(self._grid):
            row = self._grid[grid_y]
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
        """Build cached density grid from regions."""
        import math

        cols = max(1, self.universe_width // self._grid_resolution + 1)
        rows = max(1, self.universe_height // self._grid_resolution + 1)

        self._grid = [[0.0 for _ in range(cols)] for _ in range(rows)]

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

    def invalidate_cache(self) -> None:
        """Invalidate the cached grid (call after modifying regions)."""
        self._grid = None

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

    # Messages generated this turn
    all_messages: List['Message'] = field(default_factory=list)

    # Game state flags
    game_in_progress: bool = False
    use_ron_battle_engine: bool = True

    # Current turn year
    turn_year: int = STARTING_YEAR

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
        self.turn_year = STARTING_YEAR
        self.state_path_name = None
        self._star_position_cache = None

    def to_dict(self) -> dict:
        """Serialize to dictionary for persistence."""
        return {
            "game_in_progress": self.game_in_progress,
            "use_ron_battle_engine": self.use_ron_battle_engine,
            "turn_year": self.turn_year,
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
                    "mine_type": v.mine_type
                }
                for k, v in self.all_minefields.items()
            }
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ServerData':
        """Deserialize from dictionary."""
        server = cls(
            game_in_progress=data.get("game_in_progress", False),
            use_ron_battle_engine=data.get("use_ron_battle_engine", True),
            turn_year=data.get("turn_year", STARTING_YEAR),
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
                mine_type=v.get("mine_type", 0)
            )

        return server
