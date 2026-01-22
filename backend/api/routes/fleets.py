"""
Fleet API routes.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional

router = APIRouter(prefix="/api/games/{game_id}/fleets", tags=["fleets"])


class WaypointModel(BaseModel):
    """Model for waypoint data."""
    position_x: int
    position_y: int
    warp_factor: int
    destination: str
    task_type: str = "NoTask"


class FleetResponse(BaseModel):
    """Response model for fleet data."""
    key: str
    name: str
    position_x: int
    position_y: int
    owner: int
    fuel_available: float
    cargo_mass: int
    waypoints: List[WaypointModel]


@router.get("/", response_model=List[FleetResponse])
async def list_fleets(game_id: str) -> List[FleetResponse]:
    """List all fleets in a game."""
    # Stub - would load from game state
    return []


@router.get("/{fleet_key}", response_model=FleetResponse)
async def get_fleet(game_id: str, fleet_key: str) -> FleetResponse:
    """Get a specific fleet."""
    # Stub - would load from game state
    raise HTTPException(status_code=404, detail="Fleet not found")


@router.get("/{fleet_key}/waypoints", response_model=List[WaypointModel])
async def get_fleet_waypoints(game_id: str, fleet_key: str) -> List[WaypointModel]:
    """Get waypoints for a fleet."""
    # Stub - would load from game state
    return []


@router.put("/{fleet_key}/waypoints")
async def update_fleet_waypoints(
    game_id: str, fleet_key: str, waypoints: List[WaypointModel]
) -> dict:
    """Update waypoints for a fleet."""
    # Stub - would update game state
    return {"message": "Waypoints updated"}
