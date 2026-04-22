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
    ProcessServiceDep,
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
from app.web.api.websocket.backtest import manager

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
    process_service: ProcessServiceDep,
    background_tasks: BackgroundTasks,
) -> DownloadDataResponse:
    """Start download-data command with --prepend flag."""
    app_settings = settings.load_settings()
    if not app_settings.user_data_path:
        raise HTTPException(status_code=404, detail="User data path not configured. Please configure it in settings.")
    
    download_service = DownloadDataService(settings)
    
    try:
        command = download_service.build_command(
            timeframe=request.timeframe,
            timerange=request.timerange,
            pairs=request.pairs,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Configuration file not found: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(e)}")
    
    # Check if venv is configured
    if not app_settings.venv_path:
        raise HTTPException(
            status_code=400,
            detail="Virtual environment not configured. Please configure the venv path in settings to run freqtrade commands."
        )
    
    # Build environment with venv
    env = ProcessService.build_environment(app_settings.venv_path)
    
    import asyncio
    
    def stream_output(line: str):
        asyncio.create_task(manager.send_log(line))
    
    def stream_error(line: str):
        asyncio.create_task(manager.send_log(line))
    
    def on_finished(exit_code: int):
        if exit_code == 0:
            asyncio.create_task(manager.send_complete("", True))
        else:
            asyncio.create_task(manager.send_error("Download failed", f"Process exited with code: {exit_code}"))
    
    # Execute command in background
    def execute_download():
        try:
            process_service.execute_command(
                command=command.args,
                on_output=stream_output,
                on_error=stream_error,
                on_finished=on_finished,
                working_directory=command.cwd,
                env=env
            )
        except FileNotFoundError as e:
            asyncio.create_task(manager.send_error("Freqtrade not found", f"Could not execute freqtrade: {str(e)}. Please ensure freqtrade is installed in your virtual environment."))
        except Exception as e:
            asyncio.create_task(manager.send_error("Download failed", str(e)))
    
    background_tasks.add_task(execute_download)
    
    return DownloadDataResponse(
        success=True,
        message=f"Download data started for timeframe={request.timeframe}",
        task_id="download-task",
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


@router.post("/backtest/execute")
async def execute_backtest(
    request: BacktestRequest,
    settings: SettingsServiceDep,
    backtest_service: BacktestServiceDep,
    process_service: ProcessServiceDep,
    background_tasks: BackgroundTasks,
) -> dict:
    """Execute a backtest command and return run_id for redirect."""
    app_settings = settings.load_settings()
    if not app_settings.user_data_path:
        raise HTTPException(status_code=404, detail="User data path not configured. Please configure it in settings.")
    
    # Check if venv is configured
    if not app_settings.venv_path:
        raise HTTPException(
            status_code=400,
            detail="Virtual environment not configured. Please configure the venv path in settings to run freqtrade commands."
        )
    
    # Build the backtest command
    try:
        command = backtest_service.build_command(
            strategy_name=request.strategy,
            timeframe=request.timeframe,
            timerange=request.timerange,
            pairs=request.pairs,
            max_open_trades=request.max_open_trades,
            dry_run_wallet=request.dry_run_wallet,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Strategy or configuration file not found: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(e)}")
    
    # Build environment with venv
    env = ProcessService.build_environment(app_settings.venv_path)
    
    import asyncio
    from pathlib import Path
    from app.core.backtests.results_parser import parse_backtest_zip
    from app.core.backtests.results_store import RunStore
    from app.core.freqtrade.resolvers.config_resolver import resolve_config_file
    
    def stream_output(line: str):
        asyncio.create_task(manager.send_log(line))
    
    def stream_error(line: str):
        asyncio.create_task(manager.send_log(line))
    
    def on_finished(exit_code: int):
        if exit_code == 0:
            # Parse results and save to index
            try:
                export_dir = Path(command.export_dir)
                # Find the most recent zip file
                zips = sorted(export_dir.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
                if zips:
                    results = parse_backtest_zip(str(zips[0]))
                    if results:
                        # Save to index
                        config_path = None
                        try:
                            config_path = str(resolve_config_file(Path(app_settings.user_data_path), strategy_name=request.strategy))
                        except FileNotFoundError:
                            pass
                        
                        backtest_results_dir = Path(app_settings.user_data_path) / "backtest_results"
                        strategy_dir = backtest_results_dir / request.strategy
                        run_dir = RunStore.save(results, str(strategy_dir), config_path=config_path)
                        
                        # Get run_id from the saved run
                        run_id = run_dir.name
                        asyncio.create_task(manager.send_complete(run_id, True))
                        return
            except Exception as e:
                asyncio.create_task(manager.send_error("Failed to parse results", str(e)))
        else:
            asyncio.create_task(manager.send_error("Backtest failed", f"Process exited with code: {exit_code}"))
    
    # Execute command in background
    def execute_backtest_task():
        try:
            process_service.execute_command(
                command=command.args,
                on_output=stream_output,
                on_error=stream_error,
                on_finished=on_finished,
                working_directory=command.cwd,
                env=env
            )
        except FileNotFoundError as e:
            asyncio.create_task(manager.send_error("Freqtrade not found", f"Could not execute freqtrade: {str(e)}. Please ensure freqtrade is installed in your virtual environment."))
        except Exception as e:
            asyncio.create_task(manager.send_error("Backtest execution failed", str(e)))
    
    background_tasks.add_task(execute_backtest_task)
    
    return {
        "status": "started",
        "message": "Backtest execution started",
    }


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
