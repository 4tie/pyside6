"""API endpoints for the Strategy Optimizer (new composite scoring optimizer).

Provides endpoints for session-based strategy optimization with trial execution,
composite scoring, and real-time updates via SSE.
"""
import asyncio
import json
from typing import AsyncGenerator, Optional, List, Dict, Any
from pathlib import Path

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.models.optimizer_models import (
    SessionConfig,
    OptimizerSession,
    TrialRecord,
    BestPointer,
    ParamDef,
    OptimizerPreferences,
)
from app.core.services.optimizer_session_service import StrategyOptimizerService
from app.core.services.optimizer_store import OptimizerStore
from app.core.services.settings_service import SettingsService
from app.core.services.backtest_service import BacktestService
from app.web.dependencies import (
    SettingsServiceDep,
    BacktestServiceDep,
)

router = APIRouter()

# Store active sessions and their event queues
_active_sessions: Dict[str, asyncio.Queue] = {}


class CreateSessionRequest(BaseModel):
    """Request to create a new optimizer session."""
    strategy_name: str
    strategy_class: str
    pairs: List[str]
    timeframe: str = "5m"
    timerange: Optional[str] = None
    dry_run_wallet: float = 80.0
    max_open_trades: int = 2
    total_trials: int = 50
    score_metric: str = "composite"
    score_mode: str = "composite"
    target_min_trades: int = 100
    target_profit_pct: float = 50.0
    max_drawdown_limit: float = 25.0
    target_romad: float = 2.0
    param_defs: List[Dict[str, Any]] = []


class CreateSessionResponse(BaseModel):
    """Response after creating a session."""
    session_id: str
    status: str


class StrategyParamsResponse(BaseModel):
    """Response with strategy parameter definitions."""
    strategy_class: str
    timeframe: str
    params: List[Dict[str, Any]]


class TrialListResponse(BaseModel):
    """Response with list of trials."""
    trials: List[Dict[str, Any]]
    total: int


class SetBestRequest(BaseModel):
    """Request to set a trial as best."""
    trial_number: int


class ApplyTrialRequest(BaseModel):
    """Request to apply a trial."""
    new_strategy_name: Optional[str] = None


def get_optimizer_service(settings: SettingsService, backtest: BacktestService) -> StrategyOptimizerService:
    """Get or create optimizer service instance."""
    return StrategyOptimizerService(
        settings_service=settings,
        backtest_service=backtest,
    )


@router.get("/optimizer/strategies")
async def list_strategies(
    backtest: BacktestServiceDep,
) -> List[str]:
    """List available strategies for optimization."""
    try:
        return backtest.get_available_strategies()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list strategies: {str(e)}")


@router.get("/optimizer/strategy-params")
async def get_strategy_params(
    strategy: str,
    settings: SettingsServiceDep,
) -> StrategyParamsResponse:
    """Get parameter definitions for a strategy."""
    from app.core.parsing.strategy_py_parser import parse_strategy_py
    
    app_settings = settings.load_settings()
    if not app_settings.user_data_path:
        raise HTTPException(status_code=404, detail="User data path not configured")
    
    strategy_path = Path(app_settings.user_data_path) / "strategies" / f"{strategy}.py"
    if not strategy_path.exists():
        raise HTTPException(status_code=404, detail=f"Strategy {strategy} not found")
    
    try:
        params = parse_strategy_py(strategy_path)
        param_list = []
        for name, p in {**params.buy_params, **params.sell_params}.items():
            param_list.append({
                "name": name,
                "param_type": p.param_type.value,
                "default": p.default,
                "low": p.low,
                "high": p.high,
                "categories": p.categories,
                "space": p.space,
                "enabled": p.enabled,
            })
        return StrategyParamsResponse(
            strategy_class=params.strategy_class,
            timeframe=params.timeframe,
            params=param_list,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse strategy: {str(e)}")


@router.post("/optimizer/sessions", response_model=CreateSessionResponse)
async def create_session(
    request: CreateSessionRequest,
    settings: SettingsServiceDep,
    backtest: BacktestServiceDep,
) -> CreateSessionResponse:
    """Create a new optimizer session."""
    app_settings = settings.load_settings()
    if not app_settings.user_data_path:
        raise HTTPException(status_code=404, detail="User data path not configured")
    
    if not app_settings.venv_path:
        raise HTTPException(status_code=400, detail="Virtual environment not configured")
    
    # Convert param_defs from dict to ParamDef objects
    param_defs = [ParamDef(**p) for p in request.param_defs]
    
    config = SessionConfig(
        strategy_name=request.strategy_name,
        strategy_class=request.strategy_class,
        pairs=request.pairs,
        timeframe=request.timeframe,
        timerange=request.timerange,
        dry_run_wallet=request.dry_run_wallet,
        max_open_trades=request.max_open_trades,
        total_trials=request.total_trials,
        score_metric=request.score_metric,
        score_mode=request.score_mode,
        target_min_trades=request.target_min_trades,
        target_profit_pct=request.target_profit_pct,
        max_drawdown_limit=request.max_drawdown_limit,
        target_romad=request.target_romad,
        param_defs=param_defs,
    )
    
    service = get_optimizer_service(settings, backtest)
    session = service.create_session(config)
    
    # Create event queue for this session
    _active_sessions[session.session_id] = asyncio.Queue()
    
    return CreateSessionResponse(
        session_id=session.session_id,
        status=session.status.value,
    )


@router.get("/optimizer/sessions/{session_id}")
async def get_session(
    session_id: str,
    settings: SettingsServiceDep,
) -> Dict[str, Any]:
    """Get session details and status."""
    store = OptimizerStore(settings)
    session = store.load_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "session_id": session.session_id,
        "status": session.status.value,
        "trials_completed": session.trials_completed,
        "config": session.config.model_dump(),
        "best_pointer": session.best_pointer.model_dump() if session.best_pointer else None,
        "started_at": session.started_at,
        "finished_at": session.finished_at,
    }


@router.post("/optimizer/sessions/{session_id}/start")
async def start_session(
    session_id: str,
    settings: SettingsServiceDep,
    backtest: BacktestServiceDep,
    background_tasks: BackgroundTasks,
) -> Dict[str, str]:
    """Start an optimizer session."""
    service = get_optimizer_service(settings, backtest)
    store = OptimizerStore(settings)
    
    session = store.load_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session.status.value in ["running", "completed"]:
        raise HTTPException(status_code=400, detail=f"Session is already {session.status.value}")
    
    # Define callbacks that push to the event queue
    async def on_trial_start(trial_number: int, params: dict):
        queue = _active_sessions.get(session_id)
        if queue:
            await queue.put({
                "type": "trial_start",
                "trial_number": trial_number,
                "params": params,
            })
    
    async def on_trial_complete(record: TrialRecord):
        queue = _active_sessions.get(session_id)
        if queue:
            await queue.put({
                "type": "trial_complete",
                "trial": record.model_dump(),
            })
    
    async def on_session_complete(session: OptimizerSession):
        queue = _active_sessions.get(session_id)
        if queue:
            await queue.put({
                "type": "session_complete",
                "session": session.model_dump(),
            })
    
    async def on_log_line(line: str):
        queue = _active_sessions.get(session_id)
        if queue:
            await queue.put({
                "type": "log",
                "line": line,
            })
    
    def run_in_thread():
        service.run_session_async(
            session,
            on_trial_start=lambda n, p: asyncio.run_coroutine_threadsafe(
                on_trial_start(n, p), asyncio.get_event_loop()
            ),
            on_trial_complete=lambda r: asyncio.run_coroutine_threadsafe(
                on_trial_complete(r), asyncio.get_event_loop()
            ),
            on_session_complete=lambda s: asyncio.run_coroutine_threadsafe(
                on_session_complete(s), asyncio.get_event_loop()
            ),
            on_log_line=lambda l: asyncio.run_coroutine_threadsafe(
                on_log_line(l), asyncio.get_event_loop()
            ),
        )
    
    background_tasks.add_task(run_in_thread)
    
    return {"status": "started", "session_id": session_id}


@router.post("/optimizer/sessions/{session_id}/stop")
async def stop_session(
    session_id: str,
    settings: SettingsServiceDep,
    backtest: BacktestServiceDep,
) -> Dict[str, str]:
    """Stop a running optimizer session."""
    service = get_optimizer_service(settings, backtest)
    service.stop_session()
    
    return {"status": "stopped", "session_id": session_id}


@router.get("/optimizer/sessions/{session_id}/trials")
async def list_trials(
    session_id: str,
    settings: SettingsServiceDep,
) -> TrialListResponse:
    """List all trials for a session."""
    store = OptimizerStore(settings)
    session = store.load_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    trials = []
    for i in range(1, session.trials_completed + 1):
        trial = store.load_trial_record(session_id, i)
        if trial:
            trials.append(trial.model_dump())
    
    return TrialListResponse(trials=trials, total=len(trials))


@router.get("/optimizer/sessions/{session_id}/trials/{trial_number}")
async def get_trial(
    session_id: str,
    trial_number: int,
    settings: SettingsServiceDep,
) -> Dict[str, Any]:
    """Get a specific trial record."""
    store = OptimizerStore(settings)
    trial = store.load_trial_record(session_id, trial_number)
    if not trial:
        raise HTTPException(status_code=404, detail="Trial not found")
    
    return trial.model_dump()


@router.post("/optimizer/sessions/{session_id}/best")
async def set_best_trial(
    session_id: str,
    request: SetBestRequest,
    settings: SettingsServiceDep,
    backtest: BacktestServiceDep,
) -> Dict[str, Any]:
    """Manually set a trial as the best."""
    service = get_optimizer_service(settings, backtest)
    
    try:
        service.set_best(session_id, request.trial_number)
        return {"success": True, "trial_number": request.trial_number}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/optimizer/sessions/{session_id}/export")
async def export_best(
    session_id: str,
    settings: SettingsServiceDep,
    backtest: BacktestServiceDep,
) -> Dict[str, Any]:
    """Export the best trial to the live strategy."""
    service = get_optimizer_service(settings, backtest)
    
    result = service.export_best(session_id)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error_message)
    
    return {
        "success": True,
        "live_json_path": result.live_json_path,
        "backup_path": result.backup_path,
    }


@router.post("/optimizer/sessions/{session_id}/trials/{trial_number}/apply")
async def apply_trial(
    session_id: str,
    trial_number: int,
    request: ApplyTrialRequest,
    settings: SettingsServiceDep,
    backtest: BacktestServiceDep,
) -> Dict[str, Any]:
    """Apply a trial to a strategy (existing or new)."""
    service = get_optimizer_service(settings, backtest)
    
    if request.new_strategy_name:
        result = service.apply_trial_as_new_strategy(
            session_id, trial_number, request.new_strategy_name
        )
    else:
        result = service.apply_trial_to_strategy(session_id, trial_number)
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error_message)
    
    return {
        "success": True,
        "strategy_py_path": result.strategy_py_path,
        "strategy_json_path": result.strategy_json_path,
        "backup_paths": result.backup_paths,
    }


@router.get("/optimizer/sessions/{session_id}/trials/{trial_number}/diff")
async def get_trial_diff(
    session_id: str,
    trial_number: int,
    settings: SettingsServiceDep,
    backtest: BacktestServiceDep,
) -> Dict[str, Any]:
    """Get the diff between live strategy and a trial."""
    service = get_optimizer_service(settings, backtest)
    
    diff = service.build_trial_diff(session_id, trial_number)
    if not diff.success:
        raise HTTPException(status_code=400, detail=diff.error_message)
    
    return {
        "success": True,
        "param_changes": [c.model_dump() for c in diff.param_changes],
        "strategy_diff": diff.strategy_diff,
        "live_strategy_path": diff.live_strategy_path,
        "trial_strategy_path": diff.trial_strategy_path,
    }


@router.get("/optimizer/sessions/{session_id}/stream")
async def stream_session_events(
    session_id: str,
) -> StreamingResponse:
    """Stream live session events via SSE."""
    async def event_generator() -> AsyncGenerator[str, None]:
        queue = _active_sessions.get(session_id)
        if not queue:
            # Create queue if not exists
            queue = asyncio.Queue()
            _active_sessions[session_id] = queue
        
        try:
            while True:
                # Wait for events with timeout
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield f"data: {json.dumps({'type': 'keepalive'})}\n\n"
        except asyncio.CancelledError:
            pass
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/optimizer/sessions")
async def list_sessions(
    settings: SettingsServiceDep,
) -> List[Dict[str, Any]]:
    """List all optimizer sessions."""
    store = OptimizerStore(settings)
    sessions = []
    
    sessions_dir = store.sessions_root()
    if sessions_dir.exists():
        for session_dir in sessions_dir.iterdir():
            if session_dir.is_dir():
                session = store.load_session(session_dir.name)
                if session:
                    sessions.append({
                        "session_id": session.session_id,
                        "strategy_name": session.config.strategy_name,
                        "status": session.status.value,
                        "trials_completed": session.trials_completed,
                        "started_at": session.started_at,
                    })
    
    return sessions
