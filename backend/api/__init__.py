"""
Stars Nova Web - API Module

REST and WebSocket endpoints for the game.
"""

from .websocket import connection_manager, handle_websocket, notify_turn_generated

__all__ = [
    'connection_manager',
    'handle_websocket',
    'notify_turn_generated',
]
