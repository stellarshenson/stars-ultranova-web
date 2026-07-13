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


class FleetSummary(BaseModel):
    """Summary model for fleet list."""
    key: int
    name: str
    owner: int
    position_x: float
    position_y: float


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


@router.get("/{fleet_key}")
async def get_fleet(game_id: str, fleet_key: int) -> dict:
    """Get a specific fleet with full detail (tokens, cargo, waypoints)."""
    manager = get_game_manager()
    fleet = manager.get_fleet(game_id, fleet_key)
    if not fleet:
        raise HTTPException(status_code=404, detail="Fleet not found")
    return fleet


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
            position_x=int(wp["position_x"]),
            position_y=int(wp["position_y"]),
            warp_factor=wp.get("warp_factor", 6),
            destination=wp.get("destination", ""),
            task_type=wp.get("task_type", "NoTask")
        )
        for wp in waypoints
    ]


class FleetRename(BaseModel):
    """Request model for fleet rename."""
    empire_id: int
    name: str


@router.post("/{fleet_key}/rename")
async def rename_fleet(game_id: str, fleet_key: int, rename: FleetRename) -> dict:
    """Rename an owned fleet."""
    manager = get_game_manager()
    result = manager.rename_fleet(game_id, rename.empire_id, fleet_key, rename.name)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


class FleetSplit(BaseModel):
    """Request model for fleet split."""
    empire_id: int
    # {design_key (int or hex string): quantity to KEEP in this fleet}
    keep: Dict[str, int]


@router.post("/{fleet_key}/split")
async def split_fleet(game_id: str, fleet_key: int, split: FleetSplit) -> dict:
    """Split ships out of a fleet into a new fleet at the same location."""
    manager = get_game_manager()
    keep = {}
    for key, qty in split.keep.items():
        design_key = int(key, 16) if isinstance(key, str) and \
            key.startswith("0x") else int(key)
        keep[design_key] = qty
    result = manager.split_fleet(game_id, split.empire_id, fleet_key, keep)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


class FleetMerge(BaseModel):
    """Request model for fleet merge."""
    empire_id: int
    other_fleet_key: int


@router.post("/{fleet_key}/merge")
async def merge_fleets(game_id: str, fleet_key: int, merge: FleetMerge) -> dict:
    """Merge another fleet's ships into this fleet."""
    manager = get_game_manager()
    result = manager.merge_fleets(
        game_id, merge.empire_id, fleet_key, merge.other_fleet_key)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


class CargoTransfer(BaseModel):
    """Request model for cargo transfer between fleet and orbited star."""
    empire_id: int
    ironium: int = 0
    boranium: int = 0
    germanium: int = 0
    colonists: int = 0


@router.post("/{fleet_key}/cargo")
async def transfer_cargo(game_id: str, fleet_key: int, transfer: CargoTransfer) -> dict:
    """
    Transfer cargo between a fleet and the star it orbits.

    Positive values load star -> fleet; negative values unload.
    """
    manager = get_game_manager()
    result = manager.transfer_cargo(
        game_id,
        transfer.empire_id,
        fleet_key,
        {
            "ironium": transfer.ironium,
            "boranium": transfer.boranium,
            "germanium": transfer.germanium,
            "colonists": transfer.colonists,
        }
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
