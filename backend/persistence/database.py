"""
Stars Nova Web - Database Connection

SQLite database management for game persistence.
"""

import sqlite3
import json
from pathlib import Path
from typing import Optional
from contextlib import contextmanager


class Database:
    """
    SQLite database connection manager.

    Provides connection pooling and schema initialization.
    """

    def __init__(self, db_path: str = "stars_nova.db"):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = db_path
        self._connection: Optional[sqlite3.Connection] = None
        self._init_schema()

    def _init_schema(self):
        """Initialize database schema if not exists."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Games table - stores game metadata
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS games (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    player_count INTEGER NOT NULL DEFAULT 2,
                    universe_size TEXT NOT NULL DEFAULT 'medium',
                    status TEXT NOT NULL DEFAULT 'setup',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Game state table - stores serialized ServerData
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS game_states (
                    game_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
                )
            """)

            # Stars table - for quick star queries without full deserialization
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stars (
                    game_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    position_x INTEGER NOT NULL,
                    position_y INTEGER NOT NULL,
                    owner INTEGER,
                    colonists INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (game_id, name),
                    FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
                )
            """)

            # Empires table - stores empire data per game
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS empires (
                    game_id TEXT NOT NULL,
                    empire_id INTEGER NOT NULL,
                    race_name TEXT NOT NULL,
                    empire_json TEXT NOT NULL,
                    PRIMARY KEY (game_id, empire_id),
                    FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
                )
            """)

            # Commands table - stores pending player commands
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS commands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id TEXT NOT NULL,
                    empire_id INTEGER NOT NULL,
                    turn_year INTEGER NOT NULL,
                    command_type TEXT NOT NULL,
                    command_json TEXT NOT NULL,
                    submitted_at TEXT NOT NULL,
                    FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
                )
            """)

            # Create index for faster lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_stars_game
                ON stars(game_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_commands_game_turn
                ON commands(game_id, turn_year)
            """)

            conn.commit()

    @contextmanager
    def get_connection(self):
        """
        Get database connection as context manager.

        Yields:
            SQLite connection with row factory set to dict.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """
        Execute a query and return cursor.

        Args:
            query: SQL query string.
            params: Query parameters.

        Returns:
            Cursor with results.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor

    def fetch_one(self, query: str, params: tuple = ()) -> Optional[dict]:
        """
        Execute query and fetch one result.

        Args:
            query: SQL query string.
            params: Query parameters.

        Returns:
            Dict result or None.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else None

    def fetch_all(self, query: str, params: tuple = ()) -> list:
        """
        Execute query and fetch all results.

        Args:
            query: SQL query string.
            params: Query parameters.

        Returns:
            List of dict results.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]


# Global database instance
_database: Optional[Database] = None


def get_database(db_path: str = "stars_nova.db") -> Database:
    """
    Get or create global database instance.

    Args:
        db_path: Path to SQLite database file.

    Returns:
        Database instance.
    """
    global _database
    if _database is None:
        _database = Database(db_path)
    return _database
