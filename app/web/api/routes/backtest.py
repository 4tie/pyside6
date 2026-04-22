"""API endpoints for backtest and download-data operations.

Provides endpoints to run backtests, download data, manage pairs, and persist configuration.
"""
import json
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends

from app.core.services.backtest_service import BacktestService
from app.core.services.download_data_service import DownloadDataService
from app.core.services.settings_service import SettingsService
from app.web.dependencies import (
    SettingsServiceDep,
    BacktestServiceDep,
)
from app.web.models import (
    BacktestRequest,
    DownloadDataRequest,
    DownloadDataResponse,
    PairsResponse,
    FavoritesRequest,
    FavoritesResponse,
    BacktestConfigRequest,
    BacktestConfigResponse,
)

router = APIRouter()

# Common trading pairs from Binance
COMMON_PAIRS = [
    "BTC/USDT",
    "ETH/USDT",
    "BNB/USDT",
    "ADA/USDT",
    "XRP/USDT",
    "SOL/USDT",
    "DOGE/USDT",
    "DOT/USDT",
    "MATIC/USDT",
    "AVAX/USDT",
    "LINK/USDT",
    "UNI/USDT",
    "LTC/USDT",
    "ATOM/USDT",
    "NEAR/USDT",
]


@router.post("/download-data", response_model=DownloadDataResponse)
async def download_data(
    request: DownloadDataRequest,
    settings: SettingsServiceDep,
    background_tasks: BackgroundTasks,
) -> DownloadDataResponse:
    """Start download-data command with --prepend flag."""
    app_settings = settings.load_settings()
    if not app_settings.user_data_path:
        raise HTTPException(status_code=404, detail="User data path not configured")
    
    download_service = DownloadDataService(settings)
    command = download_service.build_command(
        timeframe=request.timeframe,
        timerange=request.timerange,
        pairs=request.pairs,
    )
    
    # For now, return a placeholder response
    # Full implementation would use ProcessService to execute the command
    return DownloadDataResponse(
        success=True,
        message=f"Download data command would be executed for timeframe={request.timeframe}",
        task_id="placeholder-task-id",
    )


@router.get("/pairs", response_model=PairsResponse)
async def get_pairs(settings: SettingsServiceDep) -> PairsResponse:
    """Get available trading pairs and favorites."""
    app_settings = settings.load_settings()
    if not app_settings.user_data_path:
        return PairsResponse(pairs=COMMON_PAIRS, favorites=[])
    
    # Load favorites from data folder
    favorites_file = Path(app_settings.user_data_path) / "favorites.json"
    favorites = []
    if favorites_file.exists():
        try:
            with open(favorites_file, "r") as f:
                data = json.load(f)
                favorites = data.get("favorites", [])
        except Exception:
            pass
    
    return PairsResponse(pairs=COMMON_PAIRS, favorites=favorites)


@router.post("/favorites", response_model=FavoritesResponse)
async def save_favorites(
    request: FavoritesRequest,
    settings: SettingsServiceDep,
) -> FavoritesResponse:
    """Save favorite pairs."""
    app_settings = settings.load_settings()
    if not app_settings.user_data_path:
        raise HTTPException(status_code=404, detail="User data path not configured")
    
    favorites_file = Path(app_settings.user_data_path) / "favorites.json"
    favorites_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(favorites_file, "w") as f:
        json.dump({"favorites": request.favorites}, f, indent=2)
    
    return FavoritesResponse(favorites=request.favorites)


@router.post("/backtest-config", response_model=BacktestConfigResponse)
async def save_backtest_config(
    request: BacktestConfigRequest,
    settings: SettingsServiceDep,
) -> BacktestConfigResponse:
    """Save backtest form configuration."""
    app_settings = settings.load_settings()
    if not app_settings.user_data_path:
        raise HTTPException(status_code=404, detail="User data path not configured")
    
    config_file = Path(app_settings.user_data_path) / "backtest_config.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    
    config = {
        "strategy": request.strategy,
        "timeframe": request.timeframe,
        "pairs": request.pairs or [],
        "timerange": request.timerange,
        "max_open_trades": request.max_open_trades,
        "dry_run_wallet": request.dry_run_wallet,
    }
    
    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)
    
    return BacktestConfigResponse(
        strategy=request.strategy,
        timeframe=request.timeframe,
        pairs=request.pairs or [],
        timerange=request.timerange,
        max_open_trades=request.max_open_trades,
        dry_run_wallet=request.dry_run_wallet,
    )


@router.get("/backtest-config", response_model=BacktestConfigResponse)
async def get_backtest_config(settings: SettingsServiceDep) -> BacktestConfigResponse:
    """Load backtest form configuration."""
    app_settings = settings.load_settings()
    if not app_settings.user_data_path:
        return BacktestConfigResponse()
    
    config_file = Path(app_settings.user_data_path) / "backtest_config.json"
    if not config_file.exists():
        return BacktestConfigResponse()
    
    try:
        with open(config_file, "r") as f:
            data = json.load(f)
        return BacktestConfigResponse(
            strategy=data.get("strategy"),
            timeframe=data.get("timeframe"),
            pairs=data.get("pairs", []),
            timerange=data.get("timerange"),
            max_open_trades=data.get("max_open_trades"),
            dry_run_wallet=data.get("dry_run_wallet"),
        )
    except Exception:
        return BacktestConfigResponse()
