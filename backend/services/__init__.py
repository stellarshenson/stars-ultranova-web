"""
Stars Nova Web - Services Layer

Business logic services for game management.
"""

from .game_manager import GameManager
from .galaxy_generator import GalaxyGenerator

__all__ = [
    'GameManager',
    'GalaxyGenerator',
]
