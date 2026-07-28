"""
Stars Nova Web - FastAPI Application Entry Point

A web port of the Stars! Nova 4X strategy game.
"""
import logging
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pathlib import Path

from .config import settings
from .api.routes import (games_router, stars_router, fleets_router,
                         designs_router, races_router)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI application
# root_path is used for proxy support (e.g., JupyterHub proxy at /proxy/9800)
app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Web port of Stars! Nova 4X strategy game",
    root_path=settings.root_path
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
app.include_router(races_router)

# Static files for frontend
frontend_path = Path(__file__).parent.parent / settings.frontend_dir
if settings.static_files and frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")


@app.get("/")
async def root(request: Request):
    """Serve the main page or API info.

    The page locates its own base URL client-side from the address the
    browser used (see the inline script in index.html), so no proxy
    headers or server-side prefix configuration are needed.
    """
    index_path = frontend_path / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text())
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        proxy_headers=True,
        forwarded_allow_ips="*"
    )
