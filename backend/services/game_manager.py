"""
Stars Nova Web - Game Manager

Central service for game lifecycle management.
"""

import json
from typing import Dict, List, Optional, Any

from ..persistence.database import Database, get_database
from ..persistence.game_repository import GameRepository
from ..server.server_data import ServerData
from ..server.turn_generator import TurnGenerator
from ..core.data_structures.empire_data import EmpireData
from ..core.game_objects.star import Star
from ..core.game_objects.fleet import Fleet
from ..core.commands.base import Command
from .galaxy_generator import GalaxyGenerator


class GameManager:
    """
    Central service for game lifecycle management.

    Handles game creation, loading, saving, turn generation,
    and command processing.
    """

    def __init__(self, db_path: str = "stars_nova.db"):
        """
        Initialize game manager.

        Args:
            db_path: Path to SQLite database.
        """
        self.db = get_database(db_path)
        self.repository = GameRepository(self.db)

        # In-memory cache of loaded games
        self._game_cache: Dict[str, ServerData] = {}

    # =========================================================================
    # Game Lifecycle
    # =========================================================================

    def create_game(
        self,
        name: str,
        player_count: int = 2,
        universe_size: str = "medium",
        seed: Optional[int] = None
    ) -> dict:
        """
        Create a new game.

        Args:
            name: Game name.
            player_count: Number of players.
            universe_size: Universe size (tiny/small/medium/large/huge).
            seed: Random seed for galaxy generation.

        Returns:
            Game metadata dict.
        """
        # Create game record
        game_record = self.repository.create_game(name, player_count, universe_size)
        game_id = game_record["id"]

        # Generate galaxy
        generator = GalaxyGenerator(seed)
        server_data = generator.generate(player_count, universe_size)

        # Save game state
        self._save_game_state(game_id, server_data)

        # Update status to active
        self.repository.update_game(game_id, status="active")

        # Cache the game
        self._game_cache[game_id] = server_data

        return {
            **game_record,
            "status": "active",
            "turn": server_data.turn_year,
        }

    def get_game(self, game_id: str) -> Optional[dict]:
        """
        Get game metadata.

        Args:
            game_id: Game identifier.

        Returns:
            Game metadata or None.
        """
        game_record = self.repository.get_game(game_id)
        if not game_record:
            return None

        # Get turn year from state
        server_data = self._load_game_state(game_id)
        if server_data:
            game_record["turn"] = server_data.turn_year
        else:
            game_record["turn"] = 0

        return game_record

    def list_games(self) -> List[dict]:
        """
        List all games.

        Returns:
            List of game metadata dicts.
        """
        games = self.repository.list_games()

        # Add turn info from cached states
        for game in games:
            if game["id"] in self._game_cache:
                game["turn"] = self._game_cache[game["id"]].turn_year
            else:
                # Check persisted state
                state_dict = self.repository.load_game_state(game["id"])
                if state_dict:
                    game["turn"] = state_dict.get("turn_year", 0)
                else:
                    game["turn"] = 0

        return games

    def delete_game(self, game_id: str) -> bool:
        """
        Delete a game.

        Args:
            game_id: Game identifier.

        Returns:
            True if deleted.
        """
        # Remove from cache
        if game_id in self._game_cache:
            del self._game_cache[game_id]

        return self.repository.delete_game(game_id)

    # =========================================================================
    # Turn Processing
    # =========================================================================

    def generate_turn(self, game_id: str) -> dict:
        """
        Generate next turn for a game.

        Args:
            game_id: Game identifier.

        Returns:
            Turn generation result.
        """
        server_data = self._load_game_state(game_id)
        if not server_data:
            return {"error": "Game not found"}

        # Load pending commands
        commands = self.repository.get_commands(game_id, server_data.turn_year)
        for cmd_record in commands:
            cmd_dict = json.loads(cmd_record["command_json"])
            empire_id = cmd_record["empire_id"]
            # Commands would be deserialized and added to server_data.all_commands
            # This is simplified - full implementation would parse command types

        # Run turn generator
        turn_generator = TurnGenerator(server_data)
        messages = turn_generator.generate()

        # Clear processed commands
        self.repository.clear_commands(game_id, server_data.turn_year - 1)

        # Save updated state
        self._save_game_state(game_id, server_data)

        return {
            "turn": server_data.turn_year,
            "messages": [str(m) for m in messages],
        }

    # =========================================================================
    # Game State Access
    # =========================================================================

    def get_stars(self, game_id: str) -> List[dict]:
        """
        Get all stars for a game.

        Args:
            game_id: Game identifier.

        Returns:
            List of star data dicts.
        """
        server_data = self._load_game_state(game_id)
        if not server_data:
            return []

        return [
            self._star_to_dict(star)
            for star in server_data.all_stars.values()
        ]

    def get_star(self, game_id: str, star_name: str) -> Optional[dict]:
        """
        Get specific star.

        Args:
            game_id: Game identifier.
            star_name: Star name.

        Returns:
            Star data or None.
        """
        server_data = self._load_game_state(game_id)
        if not server_data:
            return None

        star = server_data.all_stars.get(star_name)
        if not star:
            return None

        return self._star_to_dict(star)

    def get_nebula_field(self, game_id: str) -> Optional[dict]:
        """
        Get nebula density field for a game.

        Args:
            game_id: Game identifier.

        Returns:
            Nebula field data or None.
        """
        server_data = self._load_game_state(game_id)
        if not server_data:
            return None

        if not server_data.nebula_field:
            return {"regions": [], "universe_width": 600, "universe_height": 600}

        return server_data.nebula_field.to_dict()

    def get_fleets(self, game_id: str, empire_id: Optional[int] = None) -> List[dict]:
        """
        Get fleets for a game.

        Args:
            game_id: Game identifier.
            empire_id: Optional empire filter.

        Returns:
            List of fleet data dicts.
        """
        server_data = self._load_game_state(game_id)
        if not server_data:
            return []

        fleets = []
        for fleet in server_data.iterate_all_fleets():
            if empire_id is None or fleet.owner == empire_id:
                fleets.append(self._fleet_to_dict(fleet))

        return fleets

    def get_fleet(self, game_id: str, fleet_key: int) -> Optional[dict]:
        """
        Get specific fleet.

        Args:
            game_id: Game identifier.
            fleet_key: Fleet key.

        Returns:
            Fleet data or None.
        """
        server_data = self._load_game_state(game_id)
        if not server_data:
            return None

        for fleet in server_data.iterate_all_fleets():
            if fleet.key == fleet_key:
                return self._fleet_to_dict(fleet)

        return None

    def get_empire(self, game_id: str, empire_id: int) -> Optional[dict]:
        """
        Get empire data.

        Args:
            game_id: Game identifier.
            empire_id: Empire ID.

        Returns:
            Empire data or None.
        """
        server_data = self._load_game_state(game_id)
        if not server_data:
            return None

        empire = server_data.all_empires.get(empire_id)
        if not empire:
            return None

        return {
            "id": empire_id,
            "race_name": empire.race_name,
            "turn_year": empire.turn_year,
            "star_count": len(empire.owned_stars),
            "fleet_count": len(empire.owned_fleets),
            "design_count": len(empire.designs),
        }

    def get_empires(self, game_id: str) -> List[dict]:
        """
        Get all empires for a game.

        Args:
            game_id: Game identifier.

        Returns:
            List of empire summaries.
        """
        server_data = self._load_game_state(game_id)
        if not server_data:
            return []

        return [
            {
                "id": empire_id,
                "race_name": empire.race_name,
                "turn_year": empire.turn_year,
                "star_count": len(empire.owned_stars),
                "fleet_count": len(empire.owned_fleets),
            }
            for empire_id, empire in server_data.all_empires.items()
        ]

    # =========================================================================
    # Command Submission
    # =========================================================================

    def submit_command(
        self,
        game_id: str,
        empire_id: int,
        command_type: str,
        command_data: dict
    ) -> dict:
        """
        Submit a player command.

        Args:
            game_id: Game identifier.
            empire_id: Empire submitting command.
            command_type: Type of command.
            command_data: Command parameters.

        Returns:
            Submission result.
        """
        server_data = self._load_game_state(game_id)
        if not server_data:
            return {"error": "Game not found"}

        # Validate empire exists
        if empire_id not in server_data.all_empires:
            return {"error": "Empire not found"}

        # Save command for processing
        command_id = self.repository.save_command(
            game_id,
            empire_id,
            server_data.turn_year,
            command_type,
            command_data
        )

        return {
            "command_id": command_id,
            "turn_year": server_data.turn_year,
            "status": "queued"
        }

    # =========================================================================
    # Waypoint Management
    # =========================================================================

    def get_fleet_waypoints(self, game_id: str, fleet_key: int) -> List[dict]:
        """
        Get waypoints for a fleet.

        Args:
            game_id: Game identifier.
            fleet_key: Fleet key.

        Returns:
            List of waypoint dicts.
        """
        server_data = self._load_game_state(game_id)
        if not server_data:
            return []

        for fleet in server_data.iterate_all_fleets():
            if fleet.key == fleet_key:
                return [
                    {
                        "position_x": wp.position.x,
                        "position_y": wp.position.y,
                        "warp_factor": wp.warp_factor,
                        "destination": wp.destination or "",
                        "task_type": str(wp.task.__class__.__name__) if wp.task else "NoTask",
                    }
                    for wp in fleet.waypoints
                ]

        return []

    def update_fleet_waypoints(
        self,
        game_id: str,
        fleet_key: int,
        waypoints: List[dict]
    ) -> dict:
        """
        Update waypoints for a fleet.

        This creates a waypoint command for the empire.

        Args:
            game_id: Game identifier.
            fleet_key: Fleet key.
            waypoints: New waypoint data.

        Returns:
            Update result.
        """
        server_data = self._load_game_state(game_id)
        if not server_data:
            return {"error": "Game not found"}

        # Find fleet and its owner
        target_fleet = None
        for fleet in server_data.iterate_all_fleets():
            if fleet.key == fleet_key:
                target_fleet = fleet
                break

        if not target_fleet:
            return {"error": "Fleet not found"}

        # Submit as waypoint command
        return self.submit_command(
            game_id,
            target_fleet.owner,
            "waypoint",
            {
                "fleet_key": fleet_key,
                "waypoints": waypoints,
            }
        )

    # =========================================================================
    # Internal Methods
    # =========================================================================

    def _load_game_state(self, game_id: str) -> Optional[ServerData]:
        """Load game state from cache or database."""
        # Check cache first
        if game_id in self._game_cache:
            return self._game_cache[game_id]

        # Load from database
        state_dict = self.repository.load_game_state(game_id)
        if not state_dict:
            return None

        # Deserialize
        server_data = self._deserialize_state(state_dict)

        # Cache it
        self._game_cache[game_id] = server_data

        return server_data

    def _save_game_state(self, game_id: str, server_data: ServerData) -> None:
        """Save game state to database."""
        state_dict = self._serialize_state(server_data)
        self.repository.save_game_state(game_id, state_dict)

        # Update star cache
        stars = [
            {
                "name": star.name,
                "position_x": star.position.x,
                "position_y": star.position.y,
                "owner": star.owner,
                "colonists": star.colonists,
            }
            for star in server_data.all_stars.values()
        ]
        self.repository.save_stars(game_id, stars)

        # Update cache
        self._game_cache[game_id] = server_data

    def _serialize_state(self, server_data: ServerData) -> dict:
        """Serialize ServerData to dict."""
        state = server_data.to_dict()

        # Add stars
        state["all_stars"] = {
            name: self._star_to_dict(star)
            for name, star in server_data.all_stars.items()
        }

        # Add empires
        state["all_empires"] = {}
        for empire_id, empire in server_data.all_empires.items():
            state["all_empires"][str(empire_id)] = {
                "id": empire.id,
                "race_name": empire.race_name,
                "turn_year": empire.turn_year,
                "research_budget": empire.research_budget,
                "owned_stars": list(empire.owned_stars.keys()),
                "owned_fleets": {
                    str(k): self._fleet_to_dict(f)
                    for k, f in empire.owned_fleets.items()
                },
            }

        # Add races
        state["all_races"] = {
            name: {
                "name": race.name,
                "plural_name": race.plural_name,
                "growth_rate": race.growth_rate,
            }
            for name, race in server_data.all_races.items()
        }

        return state

    def _deserialize_state(self, state_dict: dict) -> ServerData:
        """Deserialize dict to ServerData."""
        server_data = ServerData.from_dict(state_dict)

        # Restore stars
        for name, star_dict in state_dict.get("all_stars", {}).items():
            star = Star()
            star.name = star_dict.get("name", name)
            star.position.x = star_dict.get("position_x", 0)
            star.position.y = star_dict.get("position_y", 0)
            star.owner = star_dict.get("owner")
            star.colonists = star_dict.get("colonists", 0)
            star.factories = star_dict.get("factories", 0)
            star.mines = star_dict.get("mines", 0)
            star.gravity = star_dict.get("gravity", 50)
            star.temperature = star_dict.get("temperature", 50)
            star.radiation = star_dict.get("radiation", 50)
            star.ironium_concentration = star_dict.get("ironium_concentration", 50)
            star.boranium_concentration = star_dict.get("boranium_concentration", 50)
            star.germanium_concentration = star_dict.get("germanium_concentration", 50)
            # Star classification for visual rendering
            star.spectral_class = star_dict.get("spectral_class", "G")
            star.luminosity_class = star_dict.get("luminosity_class", "V")
            star.star_temperature = star_dict.get("star_temperature", 5778)
            star.star_radius = star_dict.get("star_radius", 1.0)
            server_data.all_stars[name] = star

        # Restore empires (simplified - full implementation would restore all fields)
        for empire_id_str, empire_dict in state_dict.get("all_empires", {}).items():
            empire_id = int(empire_id_str)
            empire = EmpireData()
            empire.id = empire_id
            empire.race_name = empire_dict.get("race_name", "")
            empire.turn_year = empire_dict.get("turn_year", server_data.turn_year)
            empire.research_budget = empire_dict.get("research_budget", 15)

            # Restore owned stars references
            for star_name in empire_dict.get("owned_stars", []):
                if star_name in server_data.all_stars:
                    empire.owned_stars[star_name] = server_data.all_stars[star_name]

            # Restore fleets
            for fleet_key_str, fleet_dict in empire_dict.get("owned_fleets", {}).items():
                fleet = self._dict_to_fleet(fleet_dict)
                empire.owned_fleets[fleet.key] = fleet

            server_data.all_empires[empire_id] = empire

        return server_data

    def _star_to_dict(self, star: Star) -> dict:
        """Convert Star to API response dict."""
        return {
            "name": star.name,
            "position_x": star.position.x,
            "position_y": star.position.y,
            "owner": star.owner,
            "colonists": star.colonists,
            "factories": star.factories,
            "mines": star.mines,
            "gravity": star.gravity,
            "temperature": star.temperature,
            "radiation": star.radiation,
            "ironium_concentration": star.ironium_concentration,
            "boranium_concentration": star.boranium_concentration,
            "germanium_concentration": star.germanium_concentration,
            # Star classification for visual rendering
            "spectral_class": getattr(star, 'spectral_class', 'G'),
            "luminosity_class": getattr(star, 'luminosity_class', 'V'),
            "star_temperature": getattr(star, 'star_temperature', 5778),
            "star_radius": getattr(star, 'star_radius', 1.0),
        }

    def _fleet_to_dict(self, fleet: Fleet) -> dict:
        """Convert Fleet to API response dict."""
        return {
            "key": fleet.key,
            "name": fleet.name,
            "owner": fleet.owner,
            "position_x": fleet.position.x,
            "position_y": fleet.position.y,
            "fuel_available": fleet.fuel_available,
            "cargo_mass": fleet.cargo.mass,
            "in_orbit": fleet.in_orbit_name,
            "token_count": len(fleet.tokens),
            "waypoint_count": len(fleet.waypoints),
        }

    def _dict_to_fleet(self, data: dict) -> Fleet:
        """Convert dict to Fleet."""
        from ..core.data_structures import NovaPoint

        fleet = Fleet()
        fleet._key = data.get("key", 0)
        fleet.name = data.get("name", "")
        fleet.position = NovaPoint(
            data.get("position_x", 0),
            data.get("position_y", 0)
        )
        fleet.fuel_available = data.get("fuel_available", 0)
        fleet.in_orbit_name = data.get("in_orbit")

        return fleet


# Global game manager instance
_game_manager: Optional[GameManager] = None


def get_game_manager(db_path: str = "stars_nova.db") -> GameManager:
    """
    Get or create global game manager instance.

    Args:
        db_path: Path to SQLite database.

    Returns:
        GameManager instance.
    """
    global _game_manager
    if _game_manager is None:
        _game_manager = GameManager(db_path)
    return _game_manager
