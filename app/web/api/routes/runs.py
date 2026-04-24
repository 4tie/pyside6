"""API endpoints for backtest run management.

Provides endpoints to list, retrieve, create, and delete backtest runs.
"""
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends
from pydantic import BaseModel

from app.core.backtests.results_index import IndexStore
from app.core.backtests.results_store import RunStore
from app.core.services.backtest_service import BacktestService
from app.core.services.settings_service import SettingsService
from app.web.dependencies import (
    SettingsServiceDep,
    BacktestServiceDep,
)
from app.web.models import (
    BacktestRequest,
    RunResponse,
    RunDetailResponse,
)

router = APIRouter()


@router.get("/runs", response_model=List[RunResponse])
async def list_runs(
    settings: SettingsServiceDep,
    strategy: Optional[str] = Query(None, description="Filter by strategy name"),
) -> List[RunResponse]:
    """List all backtest runs, optionally filtered by strategy."""
    app_settings = settings.load_settings()
    if not app_settings.user_data_path:
        return []
    
    backtest_results_dir = Path(app_settings.user_data_path) / "backtest_results"
    
    if strategy:
        runs = IndexStore.get_strategy_runs(str(backtest_results_dir), strategy)
    else:
        index = IndexStore.load(str(backtest_results_dir))
        runs = []
        for strat_name, strat_data in index.get("strategies", {}).items():
            runs.extend(strat_data.get("runs", []))
    
    return [
        RunResponse(
            run_id=r.get("run_id", ""),
            strategy=r.get("strategy", ""),
            timeframe=r.get("timeframe", ""),
            pairs=r.get("pairs", []),
            timerange=r.get("timerange", ""),
            backtest_start=r.get("backtest_start", ""),
            backtest_end=r.get("backtest_end", ""),
            saved_at=r.get("saved_at", ""),
            profit_total_pct=r.get("profit_total_pct", 0.0),
            profit_total_abs=r.get("profit_total_abs", 0.0),
            starting_balance=r.get("starting_balance", 0.0),
            final_balance=r.get("final_balance", 0.0),
            max_drawdown_pct=r.get("max_drawdown_pct", 0.0),
            max_drawdown_abs=r.get("max_drawdown_abs", 0.0),
            trades_count=r.get("trades_count", 0),
            wins=r.get("wins", 0),
            losses=r.get("losses", 0),
            win_rate_pct=r.get("win_rate_pct", 0.0),
            sharpe=r.get("sharpe"),
            sortino=r.get("sortino"),
            calmar=r.get("calmar"),
            profit_factor=r.get("profit_factor", 0.0),
            expectancy=r.get("expectancy", 0.0),
            run_dir=r.get("run_dir", ""),
        )
        for r in runs
    ]


@router.get("/runs/{run_id}", response_model=RunDetailResponse)
async def get_run(
    run_id: str,
    settings: SettingsServiceDep,
) -> RunDetailResponse:
    """Get detailed information for a specific run."""
    app_settings = settings.load_settings()
    if not app_settings.user_data_path:
        raise HTTPException(status_code=404, detail="User data path not configured")
    
    backtest_results_dir = Path(app_settings.user_data_path) / "backtest_results"
    
    # Find the run in the index
    index = IndexStore.load(str(backtest_results_dir))
    run_entry = None
    for strat_data in index.get("strategies", {}).values():
        for run in strat_data.get("runs", []):
            if run.get("run_id") == run_id:
                run_entry = run
                break
        if run_entry:
            break
    
    if not run_entry:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    # Load full run data
    # run_dir is relative to backtest_results_dir and already includes strategy path
    run_dir = backtest_results_dir / run_entry.get("run_dir", "")
    try:
        results = RunStore.load_run(run_dir)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=404, detail=f"Failed to load run data: {str(e)}")
    
    # Load params if available
    params_file = run_dir / "params.json"
    params = {}
    if params_file.exists():
        import json
        params = json.loads(params_file.read_text(encoding="utf-8"))
    
    return RunDetailResponse(
        run_id=run_entry.get("run_id", ""),
        strategy=run_entry.get("strategy", ""),
        timeframe=run_entry.get("timeframe", ""),
        pairs=run_entry.get("pairs", []),
        timerange=run_entry.get("timerange", ""),
        backtest_start=run_entry.get("backtest_start", ""),
        backtest_end=run_entry.get("backtest_end", ""),
        saved_at=run_entry.get("saved_at", ""),
        profit_total_pct=run_entry.get("profit_total_pct", 0.0),
        profit_total_abs=run_entry.get("profit_total_abs", 0.0),
        starting_balance=run_entry.get("starting_balance", 0.0),
        final_balance=run_entry.get("final_balance", 0.0),
        max_drawdown_pct=run_entry.get("max_drawdown_pct", 0.0),
        max_drawdown_abs=run_entry.get("max_drawdown_abs", 0.0),
        trades_count=run_entry.get("trades_count", 0),
        wins=run_entry.get("wins", 0),
        losses=run_entry.get("losses", 0),
        win_rate_pct=run_entry.get("win_rate_pct", 0.0),
        sharpe=run_entry.get("sharpe"),
        sortino=run_entry.get("sortino"),
        calmar=run_entry.get("calmar"),
        profit_factor=run_entry.get("profit_factor", 0.0),
        expectancy=run_entry.get("expectancy", 0.0),
        run_dir=run_entry.get("run_dir", ""),
        trades=[
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
        params=params,
    )


@router.post("/runs")
async def create_run(
    request: BacktestRequest,
    background_tasks: BackgroundTasks,
    settings: SettingsServiceDep,
    backtest_service: BacktestServiceDep,
) -> dict:
    """Start a new backtest run asynchronously.
    
    Returns the run_id immediately; the backtest runs in the background.
    """
    # Build the backtest command
    command = backtest_service.build_command(
        strategy_name=request.strategy,
        timeframe=request.timeframe,
        timerange=request.timerange,
        pairs=request.pairs,
        max_open_trades=request.max_open_trades,
        dry_run_wallet=request.dry_run_wallet,
    )
    
    # For now, return a placeholder response
    # In a full implementation, this would:
    # 1. Execute the backtest command in the background
    # 2. Return a run_id for tracking
    
    return {
        "status": "queued",
        "message": "Backtest execution will be implemented with ProcessService integration",
        "command": str(command.args),
    }


@router.delete("/runs/{run_id}")
async def delete_run(
    run_id: str,
    settings: SettingsServiceDep,
) -> dict:
    """Delete a specific run."""
    app_settings = settings.load_settings()
    if not app_settings.user_data_path:
        raise HTTPException(status_code=404, detail="User data path not configured")
    
    backtest_results_dir = Path(app_settings.user_data_path) / "backtest_results"
    
    # Find the run in the index
    index = IndexStore.load(str(backtest_results_dir))
    run_entry = None
    strategy_name = None
    for strat_name, strat_data in index.get("strategies", {}).items():
        for run in strat_data.get("runs", []):
            if run.get("run_id") == run_id:
                run_entry = run
                strategy_name = strat_name
                break
        if run_entry:
            break
    
    if not run_entry:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    # Delete the run directory
    # run_dir is relative to backtest_results_dir and already includes strategy path
    run_dir = backtest_results_dir / run_entry.get("run_dir", "")
    if run_dir.exists():
        import shutil
        shutil.rmtree(run_dir)
    
    # Rebuild the index
    IndexStore.rebuild(str(backtest_results_dir))
    
    return {"status": "deleted", "run_id": run_id}
