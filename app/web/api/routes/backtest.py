"""Backtest, pair, data download, and latest-result endpoints."""

from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.core.parsing.json_parser import parse_json_file, write_json_file_atomic
from app.core.services.process_service import ProcessService
from app.web.api.route_utils import (
    backtest_results_dir,
    latest_runs,
    load_run_detail,
)
from app.web.dependencies import (
    BacktestServiceDep,
    DownloadDataServiceDep,
    ProcessOutputBusDep,
    ProcessServiceDep,
    SettingsServiceDep,
)
from app.web.models import (
    BacktestConfigRequest,
    BacktestConfigResponse,
    BacktestRequest,
    DataAvailabilityResponse,
    DownloadDataRequest,
    DownloadDataResponse,
    FavoritesRequest,
    FavoritesResponse,
    PairsResponse,
)

router = APIRouter()

_backtest_status: dict[str, Optional[str]] = {
    "status": "idle",
    "run_id": None,
    "message": "",
}
_current_run_id: Optional[str] = None

COMMON_PAIRS = [
    "BTC/USDT",
    "ETH/USDT",
    "BNB/USDT",
    "SOL/USDT",
    "XRP/USDT",
    "ADA/USDT",
    "DOGE/USDT",
    "DOT/USDT",
    "AVAX/USDT",
    "LINK/USDT",
    "LTC/USDT",
    "ATOM/USDT",
    "NEAR/USDT",
    "OP/USDT",
    "GMT/USDT",
    "HOME/USDT",
    "HOLO/USDT",
    "SANTOS/USDT",
    "LUNA/USDT",
]


def _set_status(status: str, run_id: Optional[str] = None, message: str = "") -> None:
    _backtest_status.update({"status": status, "run_id": run_id, "message": message})


def _favorites_file(user_data_dir: Path) -> Path:
    return user_data_dir / "favorites.json"


def _load_favorites(user_data_dir: Path) -> list[str]:
    path = _favorites_file(user_data_dir)
    if not path.exists():
        return []
    try:
        data = parse_json_file(path)
    except Exception:
        return []
    return list(data.get("favorites") or [])


def _pair_file(user_data_dir: Path, pair: str, timeframe: str) -> Path:
    filename = f"{pair.replace('/', '_').replace(':', '_')}-{timeframe}.json"
    return user_data_dir / "data" / "binance" / filename


def _pair_categories(pairs: list[str]) -> dict[str, list[str]]:
    majors = {"BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT", "ADA/USDT"}
    tier_1 = [pair for pair in pairs if pair in majors]
    other = [pair for pair in pairs if pair not in majors]
    categories: dict[str, list[str]] = {}
    if tier_1:
        categories["Tier 1: Major cryptocurrencies"] = tier_1
    if other:
        categories["Other USDT pairs"] = other
    return categories


@router.get("/pairs", response_model=PairsResponse)
async def get_pairs(settings: SettingsServiceDep) -> PairsResponse:
    app_settings = settings.load_settings()
    if not app_settings.user_data_path:
        pairs = COMMON_PAIRS
        return PairsResponse(categories=_pair_categories(pairs), all_pairs=pairs, favorites=[])

    user_data_dir = Path(app_settings.user_data_path).expanduser()
    discovered = {
        path.name.rsplit("-", 1)[0].replace("_", "/")
        for path in (user_data_dir / "data" / "binance").glob("*.json")
    }
    pairs = sorted(set(COMMON_PAIRS) | discovered, key=lambda pair: (not pair.endswith("/USDT"), pair))
    return PairsResponse(
        categories=_pair_categories(pairs),
        all_pairs=pairs,
        favorites=_load_favorites(user_data_dir),
    )


@router.post("/favorites", response_model=FavoritesResponse)
async def save_favorites(request: FavoritesRequest, settings: SettingsServiceDep) -> FavoritesResponse:
    app_settings = settings.load_settings()
    if not app_settings.user_data_path:
        raise HTTPException(status_code=404, detail="User data path not configured")

    user_data_dir = Path(app_settings.user_data_path).expanduser()
    path = _favorites_file(user_data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_file_atomic(path, {"favorites": request.favorites})
    return FavoritesResponse(favorites=request.favorites)


@router.get("/check-data", response_model=DataAvailabilityResponse)
async def check_data(
    settings: SettingsServiceDep,
    pairs: str = Query(""),
    timeframe: str = Query(...),
    timerange: Optional[str] = None,
) -> DataAvailabilityResponse:
    app_settings = settings.load_settings()
    selected = [pair.strip() for pair in pairs.split(",") if pair.strip()]
    if not app_settings.user_data_path:
        return DataAvailabilityResponse(
            available=False,
            available_pairs=[],
            missing_pairs=selected,
            message="User data path not configured",
        )

    user_data_dir = Path(app_settings.user_data_path).expanduser()
    available = [pair for pair in selected if _pair_file(user_data_dir, pair, timeframe).exists()]
    missing = [pair for pair in selected if pair not in available]
    return DataAvailabilityResponse(
        available=not missing,
        available_pairs=available,
        missing_pairs=missing,
        message="All selected data is available" if not missing else f"Missing data for {len(missing)} pair(s)",
    )


@router.post("/download-data", response_model=DownloadDataResponse)
async def download_data(
    request: DownloadDataRequest,
    settings: SettingsServiceDep,
    download_service: DownloadDataServiceDep,
    process_service: ProcessServiceDep,
    bus: ProcessOutputBusDep,
    background_tasks: BackgroundTasks,
) -> DownloadDataResponse:
    app_settings = settings.load_settings()
    if not app_settings.user_data_path:
        raise HTTPException(status_code=404, detail="User data path not configured")
    if not app_settings.venv_path:
        raise HTTPException(status_code=400, detail="Virtual environment not configured")

    try:
        command = download_service.build_command(
            timeframe=request.timeframe,
            timerange=request.timerange,
            pairs=request.pairs,
            prepend=request.prepend,
            erase=request.erase,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    env = ProcessService.build_environment(app_settings.venv_path)

    def execute_download() -> None:
        process_service.execute_command(
            command=command.as_list(),
            on_output=bus.push_line,
            on_error=bus.push_line,
            on_finished=bus.push_finished,
            working_directory=command.cwd,
            env=env,
        )

    background_tasks.add_task(execute_download)
    return DownloadDataResponse(
        success=True,
        message=f"Download data started for timeframe={request.timeframe}",
        task_id="download-task",
    )


@router.post("/backtest/execute")
async def execute_backtest(
    request: BacktestRequest,
    settings: SettingsServiceDep,
    backtest_service: BacktestServiceDep,
    process_service: ProcessServiceDep,
    bus: ProcessOutputBusDep,
    background_tasks: BackgroundTasks,
) -> dict:
    global _current_run_id
    app_settings = settings.load_settings()
    if not app_settings.user_data_path:
        raise HTTPException(status_code=404, detail="User data path not configured")
    if not app_settings.venv_path:
        raise HTTPException(status_code=400, detail="Virtual environment not configured")

    try:
        command = backtest_service.build_command(
            strategy_name=request.strategy,
            timeframe=request.timeframe,
            timerange=request.timerange,
            pairs=request.pairs,
            max_open_trades=request.max_open_trades,
            dry_run_wallet=request.dry_run_wallet,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    run_id = str(uuid4())[:8]
    _current_run_id = run_id
    _set_status("running", run_id, "Backtest in progress...")
    env = ProcessService.build_environment(app_settings.venv_path)

    def on_finished(exit_code: int) -> None:
        global _current_run_id
        _current_run_id = None
        if exit_code != 0:
            _set_status("error", None, f"Process exited with code {exit_code}")
            return
        saved_run_id = backtest_service.parse_and_save_latest_results(
            export_dir=Path(command.export_dir),
            strategy_name=request.strategy,
        )
        if saved_run_id:
            _set_status("complete", saved_run_id, "Backtest completed successfully")
        else:
            _set_status("error", None, "Backtest completed but results could not be saved")

    def execute_task() -> None:
        try:
            process_service.execute_command(
                command=command.as_list(),
                on_output=bus.push_line,
                on_error=bus.push_line,
                on_finished=on_finished,
                working_directory=command.cwd,
                env=env,
            )
        except Exception as exc:
            _set_status("error", None, f"Backtest execution failed: {exc}")

    background_tasks.add_task(execute_task)
    return {"status": "started", "message": "Backtest execution started"}


@router.get("/backtest/status")
async def get_backtest_status() -> dict:
    return _backtest_status


@router.post("/backtest/stop")
async def stop_backtest(process_service: ProcessServiceDep) -> dict:
    global _current_run_id
    if not _current_run_id:
        raise HTTPException(status_code=400, detail="No backtest is currently running")
    process_service.stop_process()
    _current_run_id = None
    _set_status("stopped", None, "Backtest stopped by user")
    return {"status": "stopped", "message": "Backtest stopped successfully"}


@router.post("/backtest-config", response_model=BacktestConfigResponse)
async def save_backtest_config(
    request: BacktestConfigRequest,
    settings: SettingsServiceDep,
) -> BacktestConfigResponse:
    app_settings = settings.load_settings()
    if not app_settings.user_data_path:
        raise HTTPException(status_code=404, detail="User data path not configured")

    path = Path(app_settings.user_data_path).expanduser() / "backtest_config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = request.model_dump(mode="json")
    write_json_file_atomic(path, payload)
    return BacktestConfigResponse(**payload)


@router.get("/backtest-config", response_model=BacktestConfigResponse)
async def get_backtest_config(settings: SettingsServiceDep) -> BacktestConfigResponse:
    app_settings = settings.load_settings()
    if not app_settings.user_data_path:
        return BacktestConfigResponse()

    path = Path(app_settings.user_data_path).expanduser() / "backtest_config.json"
    if not path.exists():
        return BacktestConfigResponse()
    try:
        return BacktestConfigResponse(**parse_json_file(path))
    except Exception:
        return BacktestConfigResponse()


@router.get("/latest-run")
async def latest_run(settings: SettingsServiceDep) -> dict:
    if backtest_results_dir(settings, required=False) is None:
        return {"exists": False, "message": "User data path not configured"}
    runs = latest_runs(settings)
    if not runs:
        return {"exists": False, "message": "No backtest runs found"}
    detail = load_run_detail(settings, runs[0].get("run_id", ""))
    payload = detail.model_dump(mode="json")
    payload["exists"] = True
    return payload
