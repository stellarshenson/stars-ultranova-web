"""
Stars Nova Web - Server Module
Turn processing and game state management.
"""

from .server_data import ServerData
from .turn_generator import TurnGenerator

__all__ = [
    "ServerData",
    "TurnGenerator"
]
