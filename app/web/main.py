"""FastAPI application for the web-based front-end.

Provides REST API endpoints and WebSocket connections for real-time updates.
Serves static files from app/web/static/ for the browser-based UI.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Import route handlers
from app.web.api.routes import runs, strategies, diagnosis, comparison, settings, loop
from app.web.api.websocket import backtest, loop as loop_ws

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


@app.get("/")
async def root():
    """Root route redirects to dashboard."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/pages/dashboard/index.html")


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "web-api"}


# Register route handlers
app.include_router(runs.router, prefix="/api", tags=["runs"])
app.include_router(strategies.router, prefix="/api", tags=["strategies"])
app.include_router(diagnosis.router, prefix="/api", tags=["diagnosis"])
app.include_router(comparison.router, prefix="/api", tags=["comparison"])
app.include_router(settings.router, prefix="/api", tags=["settings"])
app.include_router(loop.router, prefix="/api", tags=["loop"])

# Register WebSocket handlers using decorator pattern
from app.web.api.websocket import backtest, loop as loop_ws

@app.websocket("/ws/backtest")
async def backtest_websocket(websocket):
    await backtest.websocket_endpoint(websocket)

@app.websocket("/ws/loop")
async def loop_websocket(websocket):
    await loop_ws.websocket_endpoint(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)
