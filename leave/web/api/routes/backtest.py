"""API endpoints for backtest and download-data operations.

Provides endpoints to run backtests, download data, manage pairs, and persist configuration.
"""
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends

from app.core.services.backtest_service import BacktestService
from app.core.services.download_data_service import DownloadDataService
from app.core.services.settings_service import SettingsService
from leave.web.dependencies import (
    SettingsServiceDep,
    BacktestServiceDep,
    ProcessServiceDep,
    ProcessOutputBusDep,
)
from app.core.services.process_service import ProcessService
from app.core.parsing.json_parser import parse_json_file, write_json_file_atomic, ParseError
from leave.web.models import (
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

# Simple in-memory status tracking for polling fallback
_backtest_status = {"status": "idle", "run_id": None, "message": ""}
_current_run_id: Optional[str] = None

def update_backtest_status(status: str, run_id: str = None, message: str = ""):
    """Update backtest status for polling."""
    _backtest_status["status"] = status
    _backtest_status["run_id"] = run_id
    _backtest_status["message"] = message

def set_current_run_id(run_id: Optional[str]):
    """Set the current running backtest run ID."""
    global _current_run_id
    _current_run_id = run_id

def get_current_run_id() -> Optional[str]:
    """Get the current running backtest run ID."""
    return _current_run_id

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
    bus: ProcessOutputBusDep,
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
            prepend=request.prepend,
            erase=request.erase,
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
    full_command = command.as_list()

    # Execute command in background
    def execute_download():
        try:
            process_service.execute_command(
                command=full_command,
                on_output=bus.push_line,
                on_error=bus.push_line,
                on_finished=bus.push_finished,
                working_directory=command.cwd,
                env=env
            )
        except FileNotFoundError:
            pass
        except Exception:
            pass

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
            data = parse_json_file(favorites_file)
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
    
    write_json_file_atomic(favorites_file, {"favorites": request.favorites})
    
    return FavoritesResponse(favorites=request.favorites)


@router.post("/backtest/execute")
async def execute_backtest(
    request: BacktestRequest,
    settings: SettingsServiceDep,
    backtest_service: BacktestServiceDep,
    process_service: ProcessServiceDep,
    bus: ProcessOutputBusDep,
    background_tasks: BackgroundTasks,
) -> dict:
    """Execute a backtest command and return run_id for redirect."""
    try:
        # Reset status at start
        update_backtest_status("idle", message="Starting backtest...")
        
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
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to build command: {str(e)}")
        
        # Build environment with venv
        env = ProcessService.build_environment(app_settings.venv_path)
        full_command = command.as_list()

        def on_finished(exit_code: int):
            set_current_run_id(None)
            if exit_code == 0:
                # Use shared service method to parse and save results
                run_id = backtest_service.parse_and_save_latest_results(
                    export_dir=Path(command.export_dir),
                    strategy_name=request.strategy,
                )
                if run_id:
                    update_backtest_status("complete", run_id, "Backtest completed successfully")
                else:
                    update_backtest_status("error", message="Failed to parse or save results")
            else:
                update_backtest_status("error", message=f"Process exited with code: {exit_code}")
        
        # Generate a run_id for tracking
        from uuid import uuid4
        run_id = str(uuid4())[:8]
        set_current_run_id(run_id)
        
        # Execute command in background
        def execute_backtest_task():
            update_backtest_status("running", run_id, "Backtest in progress...")
            try:
                process_service.execute_command(
                    command=full_command,
                    on_output=bus.push_line,
                    on_error=bus.push_line,
                    on_finished=on_finished,
                    working_directory=command.cwd,
                    env=env
                )
            except FileNotFoundError as e:
                set_current_run_id(None)
                update_backtest_status("error", message=f"Freqtrade not found: {str(e)}")
            except Exception as e:
                set_current_run_id(None)
                update_backtest_status("error", message=f"Backtest execution failed: {str(e)}")
        
        background_tasks.add_task(execute_backtest_task)
        
        return {
            "status": "started",
            "message": "Backtest execution started",
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = f"{str(e)}\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=f"Backtest start failed: {error_detail}")


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
    
    write_json_file_atomic(config_file, config)
    
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
        data = parse_json_file(config_file)
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


@router.get("/backtest/status")
async def get_backtest_status() -> dict:
    """Get current backtest status for polling fallback."""
    return _backtest_status


@router.post("/backtest/stop")
async def stop_backtest(
    process_service: ProcessServiceDep,
) -> dict:
    """Stop the currently running backtest."""
    current_run_id = get_current_run_id()
    if not current_run_id:
        raise HTTPException(status_code=400, detail="No backtest is currently running")
    
    try:
        process_service.stop_process()
        set_current_run_id(None)
        update_backtest_status("stopped", message="Backtest stopped by user")
        return {"status": "stopped", "message": "Backtest stopped successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop backtest: {str(e)}")
