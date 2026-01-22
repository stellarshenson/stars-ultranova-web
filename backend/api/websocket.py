"""
Stars Nova Web - WebSocket Handler

Real-time updates for game events.
"""

import json
import asyncio
from typing import Dict, Set, Optional
from fastapi import WebSocket, WebSocketDisconnect
from dataclasses import dataclass, field


@dataclass
class GameConnection:
    """Represents a WebSocket connection to a game."""
    websocket: WebSocket
    game_id: str
    empire_id: Optional[int] = None


class ConnectionManager:
    """
    Manages WebSocket connections for real-time updates.

    Supports broadcasting to all connections in a game,
    or to specific empire connections.
    """

    def __init__(self):
        """Initialize connection manager."""
        # game_id -> set of connections
        self._game_connections: Dict[str, Set[GameConnection]] = {}
        # Lock for thread safety
        self._lock = asyncio.Lock()

    async def connect(
        self,
        websocket: WebSocket,
        game_id: str,
        empire_id: Optional[int] = None
    ) -> GameConnection:
        """
        Accept and register a WebSocket connection.

        Args:
            websocket: WebSocket connection.
            game_id: Game to connect to.
            empire_id: Optional empire filter.

        Returns:
            GameConnection object.
        """
        await websocket.accept()

        connection = GameConnection(
            websocket=websocket,
            game_id=game_id,
            empire_id=empire_id
        )

        async with self._lock:
            if game_id not in self._game_connections:
                self._game_connections[game_id] = set()
            self._game_connections[game_id].add(connection)

        return connection

    async def disconnect(self, connection: GameConnection):
        """
        Remove a WebSocket connection.

        Args:
            connection: Connection to remove.
        """
        async with self._lock:
            if connection.game_id in self._game_connections:
                self._game_connections[connection.game_id].discard(connection)
                if not self._game_connections[connection.game_id]:
                    del self._game_connections[connection.game_id]

    async def broadcast_to_game(self, game_id: str, message: dict):
        """
        Broadcast message to all connections in a game.

        Args:
            game_id: Game identifier.
            message: Message to broadcast.
        """
        async with self._lock:
            connections = self._game_connections.get(game_id, set()).copy()

        for connection in connections:
            try:
                await connection.websocket.send_json(message)
            except Exception:
                # Connection may have closed
                await self.disconnect(connection)

    async def broadcast_to_empire(self, game_id: str, empire_id: int, message: dict):
        """
        Broadcast message to connections for a specific empire.

        Args:
            game_id: Game identifier.
            empire_id: Empire identifier.
            message: Message to broadcast.
        """
        async with self._lock:
            connections = self._game_connections.get(game_id, set()).copy()

        for connection in connections:
            if connection.empire_id == empire_id or connection.empire_id is None:
                try:
                    await connection.websocket.send_json(message)
                except Exception:
                    await self.disconnect(connection)

    async def send_personal(self, connection: GameConnection, message: dict):
        """
        Send message to a specific connection.

        Args:
            connection: Target connection.
            message: Message to send.
        """
        try:
            await connection.websocket.send_json(message)
        except Exception:
            await self.disconnect(connection)

    def get_game_connection_count(self, game_id: str) -> int:
        """
        Get number of connections for a game.

        Args:
            game_id: Game identifier.

        Returns:
            Connection count.
        """
        return len(self._game_connections.get(game_id, set()))


# Global connection manager
connection_manager = ConnectionManager()


# Event types for WebSocket messages
class GameEvent:
    """Constants for WebSocket event types."""
    TURN_GENERATED = "turn_generated"
    COMMAND_SUBMITTED = "command_submitted"
    PLAYER_JOINED = "player_joined"
    PLAYER_LEFT = "player_left"
    CHAT_MESSAGE = "chat_message"
    GAME_STARTED = "game_started"
    GAME_ENDED = "game_ended"


async def handle_websocket(
    websocket: WebSocket,
    game_id: str,
    empire_id: Optional[int] = None
):
    """
    Handle a WebSocket connection for a game.

    Args:
        websocket: WebSocket connection.
        game_id: Game to connect to.
        empire_id: Optional empire filter.
    """
    connection = await connection_manager.connect(websocket, game_id, empire_id)

    # Notify others of new connection
    await connection_manager.broadcast_to_game(
        game_id,
        {
            "event": GameEvent.PLAYER_JOINED,
            "empire_id": empire_id,
            "connection_count": connection_manager.get_game_connection_count(game_id)
        }
    )

    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_json()

            # Handle different message types
            message_type = data.get("type")

            if message_type == "chat":
                # Broadcast chat message to all in game
                await connection_manager.broadcast_to_game(
                    game_id,
                    {
                        "event": GameEvent.CHAT_MESSAGE,
                        "empire_id": empire_id,
                        "message": data.get("message", ""),
                    }
                )

            elif message_type == "ping":
                # Respond with pong
                await connection_manager.send_personal(
                    connection,
                    {"event": "pong", "timestamp": data.get("timestamp")}
                )

    except WebSocketDisconnect:
        await connection_manager.disconnect(connection)

        # Notify others of disconnection
        await connection_manager.broadcast_to_game(
            game_id,
            {
                "event": GameEvent.PLAYER_LEFT,
                "empire_id": empire_id,
                "connection_count": connection_manager.get_game_connection_count(game_id)
            }
        )


# Helper functions for notifying clients from API handlers

async def notify_turn_generated(game_id: str, turn_year: int, messages: list):
    """
    Notify all clients that a turn was generated.

    Args:
        game_id: Game identifier.
        turn_year: New turn year.
        messages: Turn generation messages.
    """
    await connection_manager.broadcast_to_game(
        game_id,
        {
            "event": GameEvent.TURN_GENERATED,
            "turn_year": turn_year,
            "messages": messages,
        }
    )


async def notify_command_submitted(game_id: str, empire_id: int, command_type: str):
    """
    Notify that a command was submitted.

    Args:
        game_id: Game identifier.
        empire_id: Empire that submitted.
        command_type: Type of command.
    """
    await connection_manager.broadcast_to_game(
        game_id,
        {
            "event": GameEvent.COMMAND_SUBMITTED,
            "empire_id": empire_id,
            "command_type": command_type,
        }
    )
