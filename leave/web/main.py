"""FastAPI application for the web-based front-end.

Provides REST API endpoints for the web-based UI.
Serves static files from app/web/static/ for the browser-based UI.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Import route handlers
from leave.web.api.routes import (
    backtest,
    comparison,
    dashboard,
    diagnosis,
    diff,
    input_holder,
    loop,
    optimize,
    optimizer,
    process,
    runs,
    settings,
    shared_inputs,
    strategies,
)

# Create FastAPI app
app = FastAPI(
    title="PySide6 Freqtrade Web API",
    description="Web API for Freqtrade backtesting and strategy optimization",
    version="1.0.0",
)

# Configure CORS (local desktop app context - allow all origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for serving the web UI
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir), html=True), name="static")
else:
    # Create static directory if it doesn't exist yet
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir), html=True), name="static")

react_dist_dir = Path(__file__).parent.parent / "re_web" / "dist"
react_assets_dir = react_dist_dir / "assets"
if react_assets_dir.exists():
    app.mount("/app/assets", StaticFiles(directory=str(react_assets_dir)), name="re_web_assets")


def _no_cache_file_response(path: Path) -> FileResponse:
    return FileResponse(
        str(path),
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/")
async def root():
    """Root route serves the React build when present, otherwise legacy dashboard."""
    react_index_path = react_dist_dir / "index.html"
    if react_index_path.exists():
        return _no_cache_file_response(react_index_path)

    dashboard_path = static_dir / "pages" / "dashboard" / "index.html"
    if dashboard_path.exists():
        return _no_cache_file_response(dashboard_path)
    return {"error": "Dashboard not found"}


@app.get("/app/{full_path:path}")
async def react_spa(full_path: str):
    """Serve the React SPA entry for client-side routes."""
    react_index_path = react_dist_dir / "index.html"
    if react_index_path.exists():
        return _no_cache_file_response(react_index_path)
    return {"error": "React app build not found", "path": full_path}


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "web-api"}


# Register route handlers
app.include_router(runs.router, prefix="/api", tags=["runs"])
app.include_router(strategies.router, prefix="/api", tags=["strategies"])
app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])
app.include_router(diagnosis.router, prefix="/api", tags=["diagnosis"])
app.include_router(comparison.router, prefix="/api", tags=["comparison"])
app.include_router(settings.router, prefix="/api", tags=["settings"])
app.include_router(loop.router, prefix="/api", tags=["loop"])
app.include_router(diff.router, prefix="/api", tags=["diff"])
app.include_router(backtest.router, prefix="/api", tags=["backtest"])
app.include_router(optimize.router, prefix="/api", tags=["optimize"])
app.include_router(process.router, prefix="/api", tags=["process"])
app.include_router(optimizer.router, prefix="/api", tags=["optimizer"])
app.include_router(input_holder.router, prefix="/api", tags=["optimizer-config"])
app.include_router(shared_inputs.router, prefix="/api", tags=["shared-inputs"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
