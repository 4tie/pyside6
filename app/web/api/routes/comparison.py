"""API endpoints for backtest run comparison.

Provides endpoints to compare two backtest runs and identify improvements.
"""
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.core.backtests.results_index import IndexStore
from app.core.backtests.results_store import RunStore
from app.core.services.comparison_service import ComparisonService
from app.core.services.settings_service import SettingsService
from app.web.dependencies import SettingsServiceDep
from app.web.models import ComparisonResponse

router = APIRouter()


@router.get("/comparison", response_model=ComparisonResponse)
async def compare_runs(
    run_a_id: str = Query(..., description="First run ID (baseline)"),
    run_b_id: str = Query(..., description="Second run ID (candidate)"),
    settings: SettingsServiceDep = Depends(),
) -> ComparisonResponse:
    """Compare two backtest runs and return the comparison result."""
    app_settings = settings.load_settings()
    if not app_settings.user_data_path:
        raise HTTPException(status_code=404, detail="User data path not configured")
    
    backtest_results_dir = Path(app_settings.user_data_path) / "backtest_results"
    
    # Load both runs
    def load_run_entry(run_id: str) -> Optional[dict]:
        index = IndexStore.load(str(backtest_results_dir))
        for strat_data in index.get("strategies", {}).values():
            for run in strat_data.get("runs", []):
                if run.get("run_id") == run_id:
                    return run
        return None
    
    run_a_entry = load_run_entry(run_a_id)
    run_b_entry = load_run_entry(run_b_id)
    
    if not run_a_entry:
        raise HTTPException(status_code=404, detail=f"Run {run_a_id} not found")
    if not run_b_entry:
        raise HTTPException(status_code=404, detail=f"Run {run_b_id} not found")
    
    # Load full run data
    run_a_dir = backtest_results_dir / run_a_entry.get("strategy", "") / run_a_entry.get("run_dir", "")
    run_b_dir = backtest_results_dir / run_b_entry.get("strategy", "") / run_b_entry.get("run_dir", "")
    
    try:
        results_a = RunStore.load_run(run_a_dir)
        results_b = RunStore.load_run(run_b_dir)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=404, detail=f"Failed to load run data: {str(e)}")
    
    # Perform comparison
    comparison = ComparisonService.compare(results_a.summary, results_b.summary)
    
    return ComparisonResponse(
        run_a_id=run_a_id,
        run_b_id=run_b_id,
        profit_diff=comparison.profit_diff,
        winrate_diff=comparison.winrate_diff,
        drawdown_diff=comparison.drawdown_diff,
        verdict=comparison.verdict,
    )
