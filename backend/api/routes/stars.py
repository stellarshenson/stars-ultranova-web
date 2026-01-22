"""
Star system API routes.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional

from ...services.game_manager import get_game_manager

router = APIRouter(prefix="/api/games/{game_id}/stars", tags=["stars"])


class StarResponse(BaseModel):
    """Response model for star data."""
    name: str
    position_x: int
    position_y: int
    owner: Optional[int] = None
    colonists: int = 0
    factories: int = 0
    mines: int = 0
    gravity: int = 50
    temperature: int = 50
    radiation: int = 50
    ironium_concentration: int = 0
    boranium_concentration: int = 0
    germanium_concentration: int = 0


class StarSummary(BaseModel):
    """Summary model for star list."""
    name: str
    position_x: int
    position_y: int
    owner: Optional[int] = None
    colonists: int = 0


@router.get("/", response_model=List[StarSummary])
async def list_stars(game_id: str) -> List[StarSummary]:
    """List all stars in a game."""
    manager = get_game_manager()
    stars = manager.get_stars(game_id)
    if not stars and not manager.get_game(game_id):
        raise HTTPException(status_code=404, detail="Game not found")
    return [
        StarSummary(
            name=s["name"],
            position_x=s["position_x"],
            position_y=s["position_y"],
            owner=s.get("owner"),
            colonists=s.get("colonists", 0)
        )
        for s in stars
    ]


@router.get("/{star_name}", response_model=StarResponse)
async def get_star(game_id: str, star_name: str) -> StarResponse:
    """Get a specific star."""
    manager = get_game_manager()
    star = manager.get_star(game_id, star_name)
    if not star:
        raise HTTPException(status_code=404, detail="Star not found")
    return StarResponse(
        name=star["name"],
        position_x=star["position_x"],
        position_y=star["position_y"],
        owner=star.get("owner"),
        colonists=star.get("colonists", 0),
        factories=star.get("factories", 0),
        mines=star.get("mines", 0),
        gravity=star.get("gravity", 50),
        temperature=star.get("temperature", 50),
        radiation=star.get("radiation", 50),
        ironium_concentration=star.get("ironium_concentration", 0),
        boranium_concentration=star.get("boranium_concentration", 0),
        germanium_concentration=star.get("germanium_concentration", 0)
    )
