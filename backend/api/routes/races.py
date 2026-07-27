"""
Race design API routes.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict

from ...services.game_manager import _race_from_wizard
from ...services.race_points import calculate_advantage_points

router = APIRouter(prefix="/api/races", tags=["races"])


class RaceValidateResponse(BaseModel):
    """Response model for race validation."""
    points: int
    legal: bool
    leftover_points: int
    breakdown: Dict[str, int]


@router.post("/validate", response_model=RaceValidateResponse)
async def validate_race(race: dict) -> RaceValidateResponse:
    """
    Score a race wizard payload against the advantage-point budget.

    Returns the remaining points (negative = over budget), whether the
    race is legal (points >= 0, the C# RaceDesigner Finish_Click gate,
    RaceDesigner.cs:1712-1719), the leftover points granted at game
    start (clamped 0-50, Race.cs:215-221), and the running raw point
    total after each calculator step (RaceAdvantagePointCalculator.cs).
    """
    try:
        core_race = _race_from_wizard(race)
    except ValueError as e:
        # Invalid custom icon upload (non-image or oversized data URI)
        raise HTTPException(status_code=422, detail=str(e))
    breakdown: Dict[str, int] = {}
    points = calculate_advantage_points(core_race, breakdown)
    return RaceValidateResponse(
        points=points,
        legal=points >= 0,
        # clamp(points, 0, 50) - Race.cs GetLeftoverAdvantagePoints
        leftover_points=max(0, min(50, points)),
        breakdown=breakdown,
    )
