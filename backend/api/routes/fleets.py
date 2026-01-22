"""
Fleet API routes.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional

from ...services.game_manager import get_game_manager

router = APIRouter(prefix="/api/games/{game_id}/fleets", tags=["fleets"])


class WaypointModel(BaseModel):
    """Model for waypoint data."""
    position_x: int
    position_y: int
    warp_factor: int = 6
    destination: str = ""
    task_type: str = "NoTask"


class FleetResponse(BaseModel):
    """Response model for fleet data."""
    key: int
    name: str
    owner: int
    position_x: int
    position_y: int
    fuel_available: float = 0
    cargo_mass: int = 0
    in_orbit: Optional[str] = None
    token_count: int = 0
    waypoint_count: int = 0


class FleetSummary(BaseModel):
    """Summary model for fleet list."""
    key: int
    name: str
    owner: int
    position_x: int
    position_y: int


@router.get("/", response_model=List[FleetSummary])
async def list_fleets(game_id: str, empire_id: Optional[int] = None) -> List[FleetSummary]:
    """
    List all fleets in a game.

    Args:
        game_id: Game identifier.
        empire_id: Optional filter by empire.
    """
    manager = get_game_manager()
    fleets = manager.get_fleets(game_id, empire_id)
    if not fleets and not manager.get_game(game_id):
        raise HTTPException(status_code=404, detail="Game not found")
    return [
        FleetSummary(
            key=f["key"],
            name=f["name"],
            owner=f["owner"],
            position_x=f["position_x"],
            position_y=f["position_y"]
        )
        for f in fleets
    ]


@router.get("/{fleet_key}", response_model=FleetResponse)
async def get_fleet(game_id: str, fleet_key: int) -> FleetResponse:
    """Get a specific fleet."""
    manager = get_game_manager()
    fleet = manager.get_fleet(game_id, fleet_key)
    if not fleet:
        raise HTTPException(status_code=404, detail="Fleet not found")
    return FleetResponse(
        key=fleet["key"],
        name=fleet["name"],
        owner=fleet["owner"],
        position_x=fleet["position_x"],
        position_y=fleet["position_y"],
        fuel_available=fleet.get("fuel_available", 0),
        cargo_mass=fleet.get("cargo_mass", 0),
        in_orbit=fleet.get("in_orbit"),
        token_count=fleet.get("token_count", 0),
        waypoint_count=fleet.get("waypoint_count", 0)
    )


@router.get("/{fleet_key}/waypoints", response_model=List[WaypointModel])
async def get_fleet_waypoints(game_id: str, fleet_key: int) -> List[WaypointModel]:
    """Get waypoints for a fleet."""
    manager = get_game_manager()
    waypoints = manager.get_fleet_waypoints(game_id, fleet_key)
    if not waypoints:
        # Check if fleet exists
        if not manager.get_fleet(game_id, fleet_key):
            raise HTTPException(status_code=404, detail="Fleet not found")
    return [
        WaypointModel(
            position_x=wp["position_x"],
            position_y=wp["position_y"],
            warp_factor=wp.get("warp_factor", 6),
            destination=wp.get("destination", ""),
            task_type=wp.get("task_type", "NoTask")
        )
        for wp in waypoints
    ]


@router.put("/{fleet_key}/waypoints")
async def update_fleet_waypoints(
    game_id: str,
    fleet_key: int,
    waypoints: List[WaypointModel]
) -> dict:
    """Update waypoints for a fleet."""
    manager = get_game_manager()
    result = manager.update_fleet_waypoints(
        game_id,
        fleet_key,
        [wp.model_dump() for wp in waypoints]
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return {"message": "Waypoints queued for update", **result}
