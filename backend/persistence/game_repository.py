"""
Stars Nova Web - Game Repository

Data access layer for game persistence.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .database import Database


class GameRepository:
    """
    Repository for game CRUD operations.

    Handles game metadata, state serialization, and command storage.
    """

    def __init__(self, database: Database):
        """
        Initialize repository.

        Args:
            database: Database instance.
        """
        self.db = database

    # =========================================================================
    # Game CRUD
    # =========================================================================

    def create_game(
        self,
        name: str,
        player_count: int = 2,
        universe_size: str = "medium"
    ) -> dict:
        """
        Create a new game record.

        Args:
            name: Game name.
            player_count: Number of players.
            universe_size: Size of universe (small/medium/large/huge).

        Returns:
            Created game record.
        """
        game_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO games (id, name, player_count, universe_size, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'setup', ?, ?)
            """, (game_id, name, player_count, universe_size, now, now))
            conn.commit()

        return {
            "id": game_id,
            "name": name,
            "player_count": player_count,
            "universe_size": universe_size,
            "status": "setup",
            "created_at": now,
            "updated_at": now
        }

    def get_game(self, game_id: str) -> Optional[dict]:
        """
        Get game by ID.

        Args:
            game_id: Game identifier.

        Returns:
            Game record or None.
        """
        return self.db.fetch_one(
            "SELECT * FROM games WHERE id = ?",
            (game_id,)
        )

    def list_games(self) -> List[dict]:
        """
        List all games.

        Returns:
            List of game records.
        """
        return self.db.fetch_all(
            "SELECT * FROM games ORDER BY updated_at DESC"
        )

    def update_game(self, game_id: str, **updates) -> Optional[dict]:
        """
        Update game record.

        Args:
            game_id: Game identifier.
            **updates: Fields to update.

        Returns:
            Updated game record or None.
        """
        if not updates:
            return self.get_game(game_id)

        updates["updated_at"] = datetime.now(timezone.utc).isoformat()

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [game_id]

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE games SET {set_clause} WHERE id = ?",
                values
            )
            conn.commit()

        return self.get_game(game_id)

    def delete_game(self, game_id: str) -> bool:
        """
        Delete game and all related data.

        Args:
            game_id: Game identifier.

        Returns:
            True if deleted, False if not found.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM games WHERE id = ?", (game_id,))
            conn.commit()
            return cursor.rowcount > 0

    # =========================================================================
    # Game State
    # =========================================================================

    def save_game_state(self, game_id: str, state_dict: dict) -> None:
        """
        Save serialized game state.

        Args:
            game_id: Game identifier.
            state_dict: Serialized ServerData as dict.
        """
        state_json = json.dumps(state_dict)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO game_states (game_id, state_json)
                VALUES (?, ?)
            """, (game_id, state_json))
            conn.commit()

        # Update game's updated_at timestamp
        self.update_game(game_id)

    def load_game_state(self, game_id: str) -> Optional[dict]:
        """
        Load game state.

        Args:
            game_id: Game identifier.

        Returns:
            Deserialized state dict or None.
        """
        result = self.db.fetch_one(
            "SELECT state_json FROM game_states WHERE game_id = ?",
            (game_id,)
        )
        if result:
            return json.loads(result["state_json"])
        return None

    # =========================================================================
    # Star Cache (for quick lookups)
    # =========================================================================

    def save_stars(self, game_id: str, stars: List[dict]) -> None:
        """
        Save star data for quick lookups.

        Args:
            game_id: Game identifier.
            stars: List of star dicts with name, position, owner, colonists.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Clear existing stars for game
            cursor.execute("DELETE FROM stars WHERE game_id = ?", (game_id,))

            # Insert new stars
            for star in stars:
                cursor.execute("""
                    INSERT INTO stars (game_id, name, position_x, position_y, owner, colonists)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    game_id,
                    star.get("name", ""),
                    star.get("position_x", 0),
                    star.get("position_y", 0),
                    star.get("owner"),
                    star.get("colonists", 0)
                ))

            conn.commit()

    def get_stars(self, game_id: str) -> List[dict]:
        """
        Get all stars for a game.

        Args:
            game_id: Game identifier.

        Returns:
            List of star records.
        """
        return self.db.fetch_all(
            "SELECT * FROM stars WHERE game_id = ?",
            (game_id,)
        )

    def get_star(self, game_id: str, star_name: str) -> Optional[dict]:
        """
        Get specific star.

        Args:
            game_id: Game identifier.
            star_name: Star name.

        Returns:
            Star record or None.
        """
        return self.db.fetch_one(
            "SELECT * FROM stars WHERE game_id = ? AND name = ?",
            (game_id, star_name)
        )

    # =========================================================================
    # Empire Data
    # =========================================================================

    def save_empire(self, game_id: str, empire_id: int, race_name: str, empire_dict: dict) -> None:
        """
        Save empire data.

        Args:
            game_id: Game identifier.
            empire_id: Empire ID.
            race_name: Race name.
            empire_dict: Serialized EmpireData.
        """
        empire_json = json.dumps(empire_dict)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO empires (game_id, empire_id, race_name, empire_json)
                VALUES (?, ?, ?, ?)
            """, (game_id, empire_id, race_name, empire_json))
            conn.commit()

    def load_empire(self, game_id: str, empire_id: int) -> Optional[dict]:
        """
        Load empire data.

        Args:
            game_id: Game identifier.
            empire_id: Empire ID.

        Returns:
            Deserialized empire dict or None.
        """
        result = self.db.fetch_one(
            "SELECT empire_json FROM empires WHERE game_id = ? AND empire_id = ?",
            (game_id, empire_id)
        )
        if result:
            return json.loads(result["empire_json"])
        return None

    def get_empires(self, game_id: str) -> List[dict]:
        """
        Get all empires for a game.

        Args:
            game_id: Game identifier.

        Returns:
            List of empire summary records.
        """
        return self.db.fetch_all(
            "SELECT game_id, empire_id, race_name FROM empires WHERE game_id = ?",
            (game_id,)
        )

    # =========================================================================
    # Commands
    # =========================================================================

    def save_command(
        self,
        game_id: str,
        empire_id: int,
        turn_year: int,
        command_type: str,
        command_dict: dict
    ) -> int:
        """
        Save a player command.

        Args:
            game_id: Game identifier.
            empire_id: Empire ID.
            turn_year: Turn when command was submitted.
            command_type: Type of command.
            command_dict: Serialized command.

        Returns:
            Command ID.
        """
        command_json = json.dumps(command_dict)
        now = datetime.now(timezone.utc).isoformat()

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO commands (game_id, empire_id, turn_year, command_type, command_json, submitted_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (game_id, empire_id, turn_year, command_type, command_json, now))
            conn.commit()
            return cursor.lastrowid

    def get_commands(
        self,
        game_id: str,
        turn_year: int,
        empire_id: Optional[int] = None
    ) -> List[dict]:
        """
        Get commands for a turn.

        Args:
            game_id: Game identifier.
            turn_year: Turn year.
            empire_id: Optional empire filter.

        Returns:
            List of command records.
        """
        if empire_id is not None:
            return self.db.fetch_all("""
                SELECT * FROM commands
                WHERE game_id = ? AND turn_year = ? AND empire_id = ?
                ORDER BY submitted_at
            """, (game_id, turn_year, empire_id))
        else:
            return self.db.fetch_all("""
                SELECT * FROM commands
                WHERE game_id = ? AND turn_year = ?
                ORDER BY empire_id, submitted_at
            """, (game_id, turn_year))

    def clear_commands(self, game_id: str, turn_year: int) -> int:
        """
        Clear commands for a turn (after processing).

        Args:
            game_id: Game identifier.
            turn_year: Turn year.

        Returns:
            Number of commands deleted.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM commands
                WHERE game_id = ? AND turn_year = ?
            """, (game_id, turn_year))
            conn.commit()
            return cursor.rowcount
