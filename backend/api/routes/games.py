"""
Game management API routes.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
import uuid

router = APIRouter(prefix="/api/games", tags=["games"])

# In-memory game storage (would be database in production)
games: Dict[str, dict] = {}


class GameCreate(BaseModel):
    """Request model for creating a game."""
    name: str
    player_count: int = 2
    universe_size: str = "medium"  # small, medium, large, huge


class GameResponse(BaseModel):
    """Response model for game data."""
    id: str
    name: str
    player_count: int
    universe_size: str
    turn: int
    status: str


@router.post("/", response_model=GameResponse)
async def create_game(game: GameCreate) -> GameResponse:
    """Create a new game."""
    game_id = str(uuid.uuid4())
    game_data = {
        "id": game_id,
        "name": game.name,
        "player_count": game.player_count,
        "universe_size": game.universe_size,
        "turn": 0,
        "status": "setup",
        "stars": {},
        "fleets": {},
        "empires": {}
    }
    games[game_id] = game_data
    return GameResponse(**{k: v for k, v in game_data.items() if k in GameResponse.model_fields})


@router.get("/", response_model=List[GameResponse])
async def list_games() -> List[GameResponse]:
    """List all games."""
    return [
        GameResponse(**{k: v for k, v in g.items() if k in GameResponse.model_fields})
        for g in games.values()
    ]


@router.get("/{game_id}", response_model=GameResponse)
async def get_game(game_id: str) -> GameResponse:
    """Get a specific game."""
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    game_data = games[game_id]
    return GameResponse(**{k: v for k, v in game_data.items() if k in GameResponse.model_fields})


@router.delete("/{game_id}")
async def delete_game(game_id: str) -> dict:
    """Delete a game."""
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    del games[game_id]
    return {"message": "Game deleted"}


@router.post("/{game_id}/turn/generate")
async def generate_turn(game_id: str) -> dict:
    """Generate a new turn."""
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    games[game_id]["turn"] += 1
    return {"turn": games[game_id]["turn"]}
