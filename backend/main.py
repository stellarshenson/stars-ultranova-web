"""
Stars Nova Web - FastAPI Application Entry Point

A web port of the Stars! Nova 4X strategy game.
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from .config import config
from .api.routes import games_router, stars_router, fleets_router, designs_router

# Create FastAPI application
app = FastAPI(
    title=config.app_name,
    version=config.version,
    description="Web port of Stars! Nova 4X strategy game"
)

# Include API routers
app.include_router(games_router)
app.include_router(stars_router)
app.include_router(fleets_router)
app.include_router(designs_router)

# Static files for frontend
frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")


@app.get("/")
async def root():
    """Serve the main page or API info."""
    index_path = frontend_path / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {
        "name": config.app_name,
        "version": config.version,
        "docs": "/docs",
        "api": "/api/games"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.host, port=config.port)
