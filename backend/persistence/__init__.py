"""
Stars Nova Web - Persistence Layer

SQLite database for game state persistence.
"""

from .database import Database
from .game_repository import GameRepository

__all__ = [
    'Database',
    'GameRepository',
]
