"""Dashboard summary endpoints."""

from app.web.api.route_utils import (
    backtest_results_dir,
    latest_runs,
    load_run_index,
    run_response_from_entry,
)
from app.web.dependencies import SettingsServiceDep
from app.web.models import DashboardSummary

from fastapi import APIRouter

router = APIRouter()


@router.get("/dashboard/summary", response_model=DashboardSummary)
async def dashboard_summary(settings: SettingsServiceDep) -> DashboardSummary:
    if backtest_results_dir(settings, required=False) is None:
        return DashboardSummary()

    index = load_run_index(settings)
    strategy_names = sorted(index.get("strategies", {}).keys())
    runs = latest_runs(settings)
    profits = [float(run.get("profit_total_pct") or 0.0) for run in runs]
    win_rates = [float(run.get("win_rate_pct") or 0.0) for run in runs]
    drawdowns = [float(run.get("max_drawdown_pct") or 0.0) for run in runs]

    return DashboardSummary(
        metrics={
            "total_runs": len(runs),
            "total_strategies": len(strategy_names),
            "best_profit_pct": max(profits) if profits else 0.0,
            "best_win_rate_pct": max(win_rates) if win_rates else 0.0,
            "min_drawdown_pct": min(drawdowns) if drawdowns else 0.0,
            "total_trades": sum(int(run.get("trades_count") or 0) for run in runs),
            "latest_run_date": runs[0].get("saved_at", "") if runs else "",
        },
        recent_runs=[run_response_from_entry(run) for run in runs[:12]],
        strategies=strategy_names,
    )
