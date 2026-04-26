"""Dashboard summary endpoints for the redesigned web UI."""
from typing import Any

from fastapi import APIRouter

from app.web.api.route_utils import (
    backtest_results_dir,
    iter_index_runs,
    load_run_index,
    run_response_from_entry,
)
from app.web.dependencies import SettingsServiceDep

router = APIRouter()


def _latest_first(run: dict[str, Any]) -> str:
    return str(run.get("saved_at") or run.get("backtest_end") or "")


@router.get("/dashboard/summary")
async def dashboard_summary(settings: SettingsServiceDep) -> dict[str, Any]:
    """Return backend-owned aggregate metrics for the dashboard."""
    if backtest_results_dir(settings, required=False) is None:
        return {
            "metrics": {
                "total_runs": 0,
                "total_strategies": 0,
                "best_profit_pct": 0.0,
                "best_win_rate_pct": 0.0,
                "min_drawdown_pct": 0.0,
                "total_trades": 0,
                "latest_run_date": "",
            },
            "recent_runs": [],
            "strategies": [],
        }

    index = load_run_index(settings)
    strategy_names = sorted(index.get("strategies", {}).keys())
    runs = sorted(iter_index_runs(index), key=_latest_first, reverse=True)

    profits = [float(run.get("profit_total_pct") or 0.0) for run in runs]
    win_rates = [float(run.get("win_rate_pct") or 0.0) for run in runs]
    drawdowns = [float(run.get("max_drawdown_pct") or 0.0) for run in runs]

    metrics = {
        "total_runs": len(runs),
        "total_strategies": len(strategy_names),
        "best_profit_pct": max(profits) if profits else 0.0,
        "best_win_rate_pct": max(win_rates) if win_rates else 0.0,
        "min_drawdown_pct": min(drawdowns) if drawdowns else 0.0,
        "total_trades": sum(int(run.get("trades_count") or 0) for run in runs),
        "latest_run_date": runs[0].get("saved_at", "") if runs else "",
    }

    return {
        "metrics": metrics,
        "recent_runs": [run_response_from_entry(run).model_dump(mode="json") for run in runs[:12]],
        "strategies": strategy_names,
    }
