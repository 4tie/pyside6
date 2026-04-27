"""API endpoints for backtest and download-data operations.

Provides endpoints to run backtests, download data, manage pairs, and persist configuration.
"""
import re
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

# Hardcoded trading pairs - organized by category
TRADING_PAIRS_CATEGORIZED = {
    "Tier 1: Major cryptocurrencies": [
        "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT",
        "ADA/USDT", "DOGE/USDT", "AVAX/USDT", "DOT/USDT", "LINK/USDT",
    ],
    "Tier 2: Established altcoins": [
        "MATIC/USDT", "UNI/USDT", "LTC/USDT", "ATOM/USDT", "NEAR/USDT",
        "PEPE/USDT", "SHIB/USDT", "FET/USDT", "INJ/USDT", "OP/USDT",
        "AR/USDT", "APT/USDT", "SUI/USDT", "SEI/USDT", "TIA/USDT",
        "WLD/USDT", "GMX/USDT", "GRT/USDT", "ENS/USDT", "AAVE/USDT",
        "MKR/USDT", "YFI/USDT", "CRV/USDT", "SNX/USDT", "COMP/USDT",
    ],
    "Tier 3: Mid-cap gems": [
        "THETA/USDT", "MANA/USDT", "SAND/USDT", "AXS/USDT", "GALA/USDT",
        "IMX/USDT", "APE/USDT", "STX/USDT", "ROSE/USDT", "ALGO/USDT",
        "VET/USDT", "ICP/USDT", "FIL/USDT", "XTZ/USDT", "EOS/USDT",
        "TRX/USDT", "XLM/USDT", "BCH/USDT", "ETC/USDT", "FTM/USDT",
    ],
    "Tier 4: Emerging tokens": [
        "QNT/USDT", "ZIL/USDT", "CELO/USDT", "FLOW/USDT", "HBAR/USDT",
        "IOTA/USDT", "WAVES/USDT", "KSM/USDT", "BAT/USDT", "LRC/USDT",
        "RNDR/USDT", "MASK/USDT", "COTI/USDT", "NMR/USDT", "CELR/USDT",
    ],
}

TRADING_PAIRS = [pair for category in TRADING_PAIRS_CATEGORIZED.values() for pair in category]


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


@router.get("/check-data")
async def check_data_availability(
    pairs: List[str],
    timeframe: str,
    settings: SettingsServiceDep,
    timerange: str | None = None,
) -> dict:
    """Check if data exists for selected pairs and timeframe."""
    app_settings = settings.load_settings()
    if not app_settings.user_data_path:
        raise HTTPException(status_code=404, detail="User data path not configured")
    
    if not app_settings.venv_path:
        raise HTTPException(
            status_code=400,
            detail="Virtual environment not configured. Please configure the venv path in settings to check data availability."
        )
    
    download_service = DownloadDataService(settings)
    
    try:
        command = download_service.build_command(
            timeframe=timeframe,
            timerange=timerange,
            pairs=pairs,
            prepend=False,
            erase=False,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Configuration file not found: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(e)}")
    
    # Build environment with venv
    env = ProcessService.build_environment(app_settings.venv_path)
    
    # Use freqtrade list-data command to check availability
    # We'll modify the command to use list-data instead of download-data
    from app.core.services.command_builder import CommandBuilder
    
    try:
        # Build list-data command
        list_data_cmd = CommandBuilder(
            command="freqtrade",
            args=[
                "list-data",
                "--user-data-dir", str(command.cwd),
                "--timeframe", timeframe,
            ]
        )
        
        if timerange:
            list_data_cmd.add_arg("--timerange", timerange)
        
        if pairs:
            list_data_cmd.add_arg("--pairs", ",".join(pairs))
        
        full_command = list_data_cmd.as_list()
        
        # Execute command synchronously to get output
        import subprocess
        result = subprocess.run(
            full_command,
            capture_output=True,
            text=True,
            env=env,
            cwd=command.cwd,
        )
        
        if result.returncode != 0:
            # If command fails, assume data is missing
            return {
                "available": False,
                "missing_pairs": pairs,
                "message": "Data check failed - data may be missing",
            }
        
        # Parse output to determine which pairs have data
        available_pairs = set()
        if result.stdout:
            # Parse the output - freqtrade list-data shows available data
            for pair in pairs:
                if pair in result.stdout:
                    available_pairs.add(pair)
        
        missing_pairs = [p for p in pairs if p not in available_pairs]
        
        return {
            "available": len(missing_pairs) == 0,
            "available_pairs": list(available_pairs),
            "missing_pairs": missing_pairs,
            "message": f"Data available for {len(available_pairs)} pairs, missing for {len(missing_pairs)} pairs",
        }
    except Exception as e:
        # On error, assume data is missing
        return {
            "available": False,
            "missing_pairs": pairs,
            "message": f"Failed to check data availability: {str(e)}",
        }


@router.get("/pairs")
async def get_pairs(settings: SettingsServiceDep) -> dict:
    """Get available trading pairs and favorites, grouped by category."""
    app_settings = settings.load_settings()

    # Load favorites from data folder
    favorites = []
    if app_settings.user_data_path:
        favorites_file = Path(app_settings.user_data_path) / "favorites.json"
        if favorites_file.exists():
            try:
                data = parse_json_file(favorites_file)
                favorites = data.get("favorites", [])
                # Filter favorites to only include valid pairs from our hardcoded list
                favorites = [f for f in favorites if f in TRADING_PAIRS]
            except Exception:
                pass

    return {
        "categories": TRADING_PAIRS_CATEGORIZED,
        "all_pairs": TRADING_PAIRS,
        "favorites": favorites,
    }


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
            # Clean up pairs: remove leading slashes, ensure BASE/QUOTE format
            cleaned_pairs = []
            if request.pairs:
                for pair in request.pairs:
                    if not pair or not isinstance(pair, str):
                        continue
                    # Remove leading slash and ensure valid format
                    clean_pair = pair.lstrip('/')
                    # Only include if it matches BASE/QUOTE format
                    if re.match(r'^[A-Z][A-Z0-9]*\/[A-Z][A-Z0-9]*$', clean_pair):
                        cleaned_pairs.append(clean_pair)

            command = backtest_service.build_command(
                strategy_name=request.strategy,
                timeframe=request.timeframe,
                timerange=request.timerange,
                pairs=cleaned_pairs,
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


@router.get("/latest-run")
async def get_latest_backtest_run(settings: SettingsServiceDep) -> dict:
    """Get the most recent backtest run with full details."""
    app_settings = settings.load_settings()
    if not app_settings.user_data_path:
        raise HTTPException(status_code=404, detail="User data path not configured")

    from leave.web.api.route_utils import backtest_results_dir, load_run_index, iter_index_runs
    from app.core.indexing.run_store import RunStore
    from app.core.parsing.json_parser import parse_json_file

    backtest_dir = backtest_results_dir(settings, required=False)
    if not backtest_dir:
        return {
            "exists": False,
            "message": "No backtest results directory configured",
        }

    try:
        index = load_run_index(settings)
        runs = list(iter_index_runs(index))
        
        if not runs:
            return {
                "exists": False,
                "message": "No backtest runs found",
            }

        # Sort by saved_at to get latest
        def _latest_first(run: dict) -> str:
            return str(run.get("saved_at") or run.get("backtest_end") or "")

        runs = sorted(runs, key=_latest_first, reverse=True)
        latest_run = runs[0]

        # Load full run data
        run_dir = backtest_dir / latest_run.get("run_dir", "")
        try:
            results = RunStore.load_run(run_dir)
        except (FileNotFoundError, ValueError):
            return {
                "exists": False,
                "message": "Failed to load latest run data",
            }

        # Load params if available
        params_file = run_dir / "params.json"
        params = {}
        if params_file.exists():
            params = parse_json_file(params_file)

        return {
            "exists": True,
            "run_id": latest_run.get("run_id", ""),
            "strategy": latest_run.get("strategy", ""),
            "timeframe": latest_run.get("timeframe", ""),
            "pairs": latest_run.get("pairs", []),
            "timerange": latest_run.get("timerange", ""),
            "backtest_start": latest_run.get("backtest_start", ""),
            "backtest_end": latest_run.get("backtest_end", ""),
            "saved_at": latest_run.get("saved_at", ""),
            "profit_total_pct": latest_run.get("profit_total_pct", 0.0),
            "profit_total_abs": latest_run.get("profit_total_abs", 0.0),
            "starting_balance": latest_run.get("starting_balance", 0.0),
            "final_balance": latest_run.get("final_balance", 0.0),
            "max_drawdown_pct": latest_run.get("max_drawdown_pct", 0.0),
            "max_drawdown_abs": latest_run.get("max_drawdown_abs", 0.0),
            "trades_count": latest_run.get("trades_count", 0),
            "wins": latest_run.get("wins", 0),
            "losses": latest_run.get("losses", 0),
            "win_rate_pct": latest_run.get("win_rate_pct", 0.0),
            "sharpe": latest_run.get("sharpe"),
            "sortino": latest_run.get("sortino"),
            "calmar": latest_run.get("calmar"),
            "profit_factor": latest_run.get("profit_factor", 0.0),
            "expectancy": latest_run.get("expectancy", 0.0),
            "run_dir": latest_run.get("run_dir", ""),
            "trades": [
                {
                    "pair": t.pair,
                    "profit_abs": t.profit_abs,
                    "profit": t.profit,
                    "open_date": t.open_date,
                    "close_date": t.close_date,
                    "exit_reason": t.exit_reason,
                }
                for t in results.trades
            ],
            "params": params,
        }
    except Exception as e:
        return {
            "exists": False,
            "message": f"Failed to load latest run: {str(e)}",
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
