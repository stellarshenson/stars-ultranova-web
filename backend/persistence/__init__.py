"""
Stars Nova Web - Persistence Layer

SQLite database for game state persistence.
"""

from .database import Database, get_database
from .game_repository import GameRepository

__all__ = [
    'Database',
    'get_database',
    'GameRepository',
]
