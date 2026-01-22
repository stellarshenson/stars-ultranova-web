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
            if len(fleet.composition) == 0:
                destroyed_fleets.append(fleet.key)

        # Remove destroyed fleets from all empires
        for key in destroyed_fleets:
            for empire in self.all_empires.values():
                if key in empire.owned_fleets:
                    del empire.owned_fleets[key]
                if key in empire.fleet_reports:
                    del empire.fleet_reports[key]

        # Remove destroyed starbases
        destroyed_stations: List[str] = []
        for star in self.all_stars.values():
            if star.starbase is not None:
                if len(star.starbase.composition) == 0:
                    destroyed_stations.append(star.name)

        for name in destroyed_stations:
            self.all_stars[name].starbase = None

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
