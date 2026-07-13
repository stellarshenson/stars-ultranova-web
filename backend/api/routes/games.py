"""
Game management API routes.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional

from ...services.game_manager import get_game_manager

router = APIRouter(prefix="/api/games", tags=["games"])


class GameCreate(BaseModel):
    """Request model for creating a game."""
    name: str
    player_count: int = 2
    universe_size: str = "medium"  # tiny, small, medium, large, huge
    seed: Optional[int] = None
    race: Optional[dict] = None  # race wizard payload for the human player
    # Accelerated BBS play (GameSettings.cs:63): starting population
    # 100000 instead of 25000
    accelerated_start: bool = False
    # Victory condition settings (GameSettings.cs:49-58); partial dict
    # in the VictorySettings shape - missing keys keep the C# defaults
    victory: Optional[dict] = None


class GameResponse(BaseModel):
    """Response model for game data."""
    id: str
    name: str
    player_count: int
    universe_size: str
    turn: int
    status: str


class TurnResponse(BaseModel):
    """Response model for turn generation."""
    turn: int
    messages: List[dict]


class CommandSubmit(BaseModel):
    """Request model for command submission."""
    command_type: str
    command_data: dict


class CommandResponse(BaseModel):
    """Response model for command submission."""
    command_id: Optional[int] = None
    turn_year: int
    status: str
    error: Optional[str] = None


class EmpireResponse(BaseModel):
    """Response model for empire data."""
    id: int
    race_name: str
    star_count: int
    fleet_count: int


@router.post("/", response_model=GameResponse)
async def create_game(game: GameCreate) -> GameResponse:
    """Create a new game."""
    manager = get_game_manager()
    try:
        game_data = manager.create_game(
            name=game.name,
            player_count=game.player_count,
            universe_size=game.universe_size,
            seed=game.seed,
            race=game.race,
            accelerated_start=game.accelerated_start,
            victory=game.victory
        )
    except ValueError as e:
        # Over-budget race rejected (the web equivalent of the C# race
        # designer's Finish_Click gate, RaceDesigner.cs:1712-1719)
        raise HTTPException(status_code=422, detail=str(e))
    return GameResponse(
        id=game_data["id"],
        name=game_data["name"],
        player_count=game_data["player_count"],
        universe_size=game_data["universe_size"],
        turn=game_data.get("turn", 0),
        status=game_data["status"]
    )


@router.get("/", response_model=List[GameResponse])
async def list_games() -> List[GameResponse]:
    """List all games."""
    manager = get_game_manager()
    games = manager.list_games()
    return [
        GameResponse(
            id=g["id"],
            name=g["name"],
            player_count=g["player_count"],
            universe_size=g["universe_size"],
            turn=g.get("turn", 0),
            status=g["status"]
        )
        for g in games
    ]


@router.get("/{game_id}", response_model=GameResponse)
async def get_game(game_id: str) -> GameResponse:
    """Get a specific game."""
    manager = get_game_manager()
    game_data = manager.get_game(game_id)
    if not game_data:
        raise HTTPException(status_code=404, detail="Game not found")
    return GameResponse(
        id=game_data["id"],
        name=game_data["name"],
        player_count=game_data["player_count"],
        universe_size=game_data["universe_size"],
        turn=game_data.get("turn", 0),
        status=game_data["status"]
    )


@router.delete("/{game_id}")
async def delete_game(game_id: str) -> dict:
    """Delete a game."""
    manager = get_game_manager()
    if not manager.delete_game(game_id):
        raise HTTPException(status_code=404, detail="Game not found")
    return {"message": "Game deleted"}


@router.post("/{game_id}/turn/generate", response_model=TurnResponse)
async def generate_turn(game_id: str) -> TurnResponse:
    """Generate a new turn."""
    manager = get_game_manager()
    result = manager.generate_turn(game_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return TurnResponse(
        turn=result["turn"],
        messages=result.get("messages", [])
    )


@router.get("/{game_id}/empires", response_model=List[EmpireResponse])
async def list_empires(game_id: str) -> List[EmpireResponse]:
    """List all empires in a game."""
    manager = get_game_manager()
    empires = manager.get_empires(game_id)
    if not empires:
        # Check if game exists
        if not manager.get_game(game_id):
            raise HTTPException(status_code=404, detail="Game not found")
    return [
        EmpireResponse(
            id=e["id"],
            race_name=e["race_name"],
            star_count=e["star_count"],
            fleet_count=e["fleet_count"]
        )
        for e in empires
    ]


@router.get("/{game_id}/empires/{empire_id}")
async def get_empire(game_id: str, empire_id: int) -> dict:
    """Get specific empire data."""
    manager = get_game_manager()
    empire = manager.get_empire(game_id, empire_id)
    if not empire:
        raise HTTPException(status_code=404, detail="Empire not found")
    return empire


@router.get("/{game_id}/empires/{empire_id}/state")
async def get_player_state(game_id: str, empire_id: int) -> dict:
    """
    Get the full game state as seen by one empire (fog of war applied).

    This is the primary payload the game client renders from: owned
    stars in full detail, scanned stars via intel reports, own fleets
    with composition and orders, foreign fleet contacts, last turn's
    messages, research state, and ship designs.
    """
    manager = get_game_manager()
    state = manager.get_player_state(game_id, empire_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Game or empire not found")
    return state


@router.post("/{game_id}/empires/{empire_id}/commands", response_model=CommandResponse)
async def submit_command(game_id: str, empire_id: int, command: CommandSubmit) -> CommandResponse:
    """Submit a command for an empire."""
    manager = get_game_manager()
    result = manager.submit_command(
        game_id,
        empire_id,
        command.command_type,
        command.command_data
    )
    if "error" in result:
        return CommandResponse(
            turn_year=0,
            status="error",
            error=result["error"]
        )
    return CommandResponse(
        command_id=result.get("command_id"),
        turn_year=result["turn_year"],
        status=result["status"]
    )


@router.get("/{game_id}/empires/{empire_id}/battles")
async def get_battles(game_id: str, empire_id: int) -> List[dict]:
    """
    Get the empire's battle reports from the last generated turn.

    Each report carries the full battle timeline (movement, targeting,
    weapon fire, destruction steps) plus participating stacks and
    per-empire losses, for replay in the battle viewer.
    """
    manager = get_game_manager()
    battles = manager.get_battle_reports(game_id, empire_id)
    if battles is None:
        raise HTTPException(status_code=404, detail="Game or empire not found")
    return battles


@router.get("/{game_id}/nebulae")
async def get_nebulae(game_id: str) -> dict:
    """
    Get nebula field data for rendering and gameplay.

    Returns nebula regions with position, shape, and density.
    Density affects warp speed - higher density = slower travel.
    """
    manager = get_game_manager()
    nebula_data = manager.get_nebula_field(game_id)
    if nebula_data is None:
        raise HTTPException(status_code=404, detail="Game not found or no nebula data")
    return nebula_data
