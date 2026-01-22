"""
Stars Nova Web - FastAPI Application Entry Point

A web port of the Stars! Nova 4X strategy game.
"""
import logging
from fastapi import FastAPI, WebSocket, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from typing import Optional

from .config import settings
from .api.routes import games_router, stars_router, fleets_router, designs_router
from .api.websocket import handle_websocket

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Web port of Stars! Nova 4X strategy game"
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)


# Exception handlers
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle validation errors."""
    logger.warning(f"Validation error: {exc}")
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc), "type": "validation_error"}
    )


@app.exception_handler(KeyError)
async def key_error_handler(request: Request, exc: KeyError):
    """Handle missing key errors."""
    logger.warning(f"Key error: {exc}")
    return JSONResponse(
        status_code=404,
        content={"detail": f"Resource not found: {exc}", "type": "not_found"}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors."""
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "type": "internal_error"}
    )

# Include API routers
app.include_router(games_router)
app.include_router(stars_router)
app.include_router(fleets_router)
app.include_router(designs_router)

# Static files for frontend
frontend_path = Path(__file__).parent.parent / settings.frontend_dir
if settings.static_files and frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")


@app.get("/")
async def root():
    """Serve the main page or API info."""
    index_path = frontend_path / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {
        "name": settings.app_name,
        "version": settings.version,
        "docs": "/docs",
        "api": "/api/games"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.websocket("/ws/games/{game_id}")
async def websocket_game(websocket: WebSocket, game_id: str, empire_id: Optional[int] = None):
    """
    WebSocket endpoint for real-time game updates.

    Args:
        websocket: WebSocket connection.
        game_id: Game to connect to.
        empire_id: Optional empire filter for private messages.
    """
    await handle_websocket(websocket, game_id, empire_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload
    )
