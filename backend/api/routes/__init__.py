from .games import router as games_router
from .stars import router as stars_router
from .fleets import router as fleets_router

__all__ = ["games_router", "stars_router", "fleets_router"]
