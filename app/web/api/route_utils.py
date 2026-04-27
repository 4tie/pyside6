"""Shared helpers for web API routes."""

from pathlib import Path
from typing import Any, Iterable

from fastapi import HTTPException

from app.core.backtests.results_index import IndexStore
from app.core.backtests.results_store import RunStore
from app.core.parsing.json_parser import parse_json_file
from app.core.services.settings_service import SettingsService
from app.web.models import RunDetailResponse, RunResponse


def user_data_path(settings: SettingsService, *, required: bool = True) -> Path | None:
    configured = settings.load_settings().user_data_path
    if not configured:
        if required:
            raise HTTPException(status_code=404, detail="User data path not configured")
        return None
    return Path(configured).expanduser()


def backtest_results_dir(settings: SettingsService, *, required: bool = True) -> Path | None:
    base = user_data_path(settings, required=required)
    return base / "backtest_results" if base else None


def load_run_index(settings: SettingsService) -> dict[str, Any]:
    results_dir = backtest_results_dir(settings)
    return IndexStore.load(str(results_dir))


def iter_index_runs(index: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for strategy_data in index.get("strategies", {}).values():
        yield from strategy_data.get("runs", [])


def latest_runs(settings: SettingsService) -> list[dict[str, Any]]:
    if backtest_results_dir(settings, required=False) is None:
        return []
    runs = list(iter_index_runs(load_run_index(settings)))
    return sorted(
        runs,
        key=lambda run: str(run.get("saved_at") or run.get("backtest_end") or ""),
        reverse=True,
    )


def find_run_entry(settings: SettingsService, run_id: str) -> dict[str, Any]:
    for run in latest_runs(settings):
        if run.get("run_id") == run_id:
            return run
    raise HTTPException(status_code=404, detail=f"Run {run_id} not found")


def run_response_from_entry(run: dict[str, Any]) -> RunResponse:
    return RunResponse(
        run_id=run.get("run_id", ""),
        strategy=run.get("strategy", ""),
        timeframe=run.get("timeframe", ""),
        pairs=run.get("pairs", []),
        timerange=run.get("timerange", ""),
        backtest_start=run.get("backtest_start", ""),
        backtest_end=run.get("backtest_end", ""),
        saved_at=run.get("saved_at", ""),
        profit_total_pct=float(run.get("profit_total_pct") or 0.0),
        profit_total_abs=float(run.get("profit_total_abs") or 0.0),
        starting_balance=float(run.get("starting_balance") or 0.0),
        final_balance=float(run.get("final_balance") or 0.0),
        max_drawdown_pct=float(run.get("max_drawdown_pct") or 0.0),
        max_drawdown_abs=float(run.get("max_drawdown_abs") or 0.0),
        trades_count=int(run.get("trades_count") or 0),
        wins=int(run.get("wins") or 0),
        losses=int(run.get("losses") or 0),
        win_rate_pct=float(run.get("win_rate_pct") or 0.0),
        sharpe=run.get("sharpe"),
        sortino=run.get("sortino"),
        calmar=run.get("calmar"),
        profit_factor=float(run.get("profit_factor") or 0.0),
        expectancy=float(run.get("expectancy") or 0.0),
        run_dir=run.get("run_dir", ""),
    )


def load_run_detail(settings: SettingsService, run_id: str) -> RunDetailResponse:
    run_entry = find_run_entry(settings, run_id)
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
