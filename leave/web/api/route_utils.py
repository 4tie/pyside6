"""Shared helpers for FastAPI route modules.

These helpers keep path resolution, run-index access, and response shaping in
one place so route handlers do not each rebuild the same settings logic.
"""
from pathlib import Path
from typing import Any, Iterable

from fastapi import HTTPException

from app.core.backtests.results_index import IndexStore
from app.core.backtests.results_store import RunStore
from app.core.parsing.json_parser import parse_json_file
from app.core.services.settings_service import SettingsService
from app.web.models import RunDetailResponse, RunResponse


def app_settings(settings: SettingsService):
    """Load current application settings through the shared settings service."""
    return settings.load_settings()


def user_data_path(settings: SettingsService, *, required: bool = True) -> Path | None:
    """Return the configured user_data path, optionally raising when missing."""
    configured = app_settings(settings).user_data_path
    if not configured:
        if required:
            raise HTTPException(status_code=404, detail="User data path not configured")
        return None
    return Path(configured)


def backtest_results_dir(settings: SettingsService, *, required: bool = True) -> Path | None:
    """Return the configured backtest_results directory."""
    base = user_data_path(settings, required=required)
    return base / "backtest_results" if base else None


def load_run_index(settings: SettingsService) -> dict[str, Any]:
    """Load the global backtest run index."""
    results_dir = backtest_results_dir(settings)
    return IndexStore.load(str(results_dir))


def iter_index_runs(index: dict[str, Any]) -> Iterable[dict[str, Any]]:
    """Yield every run entry from a global index payload."""
    for strategy_data in index.get("strategies", {}).values():
        yield from strategy_data.get("runs", [])


def find_run_entry(settings: SettingsService, run_id: str, strategy: str | None = None) -> dict[str, Any]:
    """Find a run entry by id, optionally constrained to one strategy."""
    index = load_run_index(settings)
    for run in iter_index_runs(index):
        if run.get("run_id") != run_id:
            continue
        if strategy is not None and run.get("strategy") != strategy:
            continue
        return run
    if strategy:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found in strategy {strategy}")
    raise HTTPException(status_code=404, detail=f"Run {run_id} not found")


def run_response_from_entry(run: dict[str, Any]) -> RunResponse:
    """Build the public run response model from an index entry."""
    return RunResponse(
        run_id=run.get("run_id", ""),
        strategy=run.get("strategy", ""),
        timeframe=run.get("timeframe", ""),
        pairs=run.get("pairs", []),
        timerange=run.get("timerange", ""),
        backtest_start=run.get("backtest_start", ""),
        backtest_end=run.get("backtest_end", ""),
        saved_at=run.get("saved_at", ""),
        profit_total_pct=run.get("profit_total_pct", 0.0),
        profit_total_abs=run.get("profit_total_abs", 0.0),
        starting_balance=run.get("starting_balance", 0.0),
        final_balance=run.get("final_balance", 0.0),
        max_drawdown_pct=run.get("max_drawdown_pct", 0.0),
        max_drawdown_abs=run.get("max_drawdown_abs", 0.0),
        trades_count=run.get("trades_count", 0),
        wins=run.get("wins", 0),
        losses=run.get("losses", 0),
        win_rate_pct=run.get("win_rate_pct", 0.0),
        sharpe=run.get("sharpe"),
        sortino=run.get("sortino"),
        calmar=run.get("calmar"),
        profit_factor=run.get("profit_factor", 0.0),
        expectancy=run.get("expectancy", 0.0),
        run_dir=run.get("run_dir", ""),
    )


def load_run_detail(settings: SettingsService, run_id: str, strategy: str | None = None) -> RunDetailResponse:
    """Load full run data and build the public detail response."""
    run_entry = find_run_entry(settings, run_id, strategy)
    results_dir = backtest_results_dir(settings)
    run_dir = results_dir / run_entry.get("run_dir", "")

    try:
        results = RunStore.load_run(run_dir)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=f"Failed to load run data: {exc}") from exc

    params_file = run_dir / "params.json"
    params = parse_json_file(params_file) if params_file.exists() else {}

    response = run_response_from_entry(run_entry).model_dump()
    response["trades"] = [
        {
            "pair": trade.pair,
            "profit_abs": trade.profit_abs,
            "profit": trade.profit,
            "open_date": trade.open_date,
            "close_date": trade.close_date,
            "exit_reason": trade.exit_reason,
        }
        for trade in results.trades
    ]
    response["params"] = params
    return RunDetailResponse(**response)
