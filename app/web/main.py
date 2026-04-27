"""FastAPI application for the Next.js frontend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.web.api.routes import backtest, dashboard, optimize, settings, strategies

app = FastAPI(
    title="PySide6 Freqtrade Web API",
    description="Web API for the Next.js Freqtrade frontend",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "web-api"}


app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])
app.include_router(strategies.router, prefix="/api", tags=["strategies"])
app.include_router(settings.router, prefix="/api", tags=["settings"])
app.include_router(backtest.router, prefix="/api", tags=["backtest"])
app.include_router(optimize.router, prefix="/api", tags=["optimize"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
