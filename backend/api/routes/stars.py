"""
Star system API routes.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional

router = APIRouter(prefix="/api/games/{game_id}/stars", tags=["stars"])


class StarResponse(BaseModel):
    """Response model for star data."""
    name: str
    position_x: int
    position_y: int
    colonists: int
    factories: int
    mines: int
    gravity: int
    temperature: int
    radiation: int
    owner: Optional[int] = None


@router.get("/", response_model=List[StarResponse])
async def list_stars(game_id: str) -> List[StarResponse]:
    """List all stars in a game."""
    # Stub - would load from game state
    return []


@router.get("/{star_name}", response_model=StarResponse)
async def get_star(game_id: str, star_name: str) -> StarResponse:
    """Get a specific star."""
    # Stub - would load from game state
    raise HTTPException(status_code=404, detail="Star not found")
