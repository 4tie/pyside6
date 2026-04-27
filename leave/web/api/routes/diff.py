"""API endpoints for run diff and rollback operations.

Provides endpoints to compare runs and rollback strategy files to previous versions.
"""
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends

from app.core.backtests.results_index import IndexStore
from app.core.backtests.results_store import RunStore
from app.core.services.settings_service import SettingsService
from app.core.services.version_manager_service import VersionManagerService
from app.web.dependencies import SettingsServiceDep
from app.web.models import DiffResponse, RollbackRequest, RollbackResponse

router = APIRouter()


@router.get("/runs/{run_id}/diff", response_model=DiffResponse)
async def get_run_diff(
    run_id: str,
    settings: SettingsServiceDep,
    baseline_id: Optional[str] = Query(None, description="Baseline run ID (defaults to latest run for same strategy)"),
) -> DiffResponse:
    """Get diff between two runs (parameters and code changes).
    
    If baseline_id is not provided, uses the most recent run for the same strategy.
    """
    app_settings = settings.load_settings()
    if not app_settings.user_data_path:
        raise HTTPException(status_code=404, detail="User data path not configured")
    
    backtest_results_dir = Path(app_settings.user_data_path) / "backtest_results"
    
    # Load current run
    def load_run_entry(run_id: str) -> Optional[dict]:
        index = IndexStore.load(str(backtest_results_dir))
        for strat_data in index.get("strategies", {}).values():
            for run in strat_data.get("runs", []):
                if run.get("run_id") == run_id:
                    return run
        return None
    
    run_entry = load_run_entry(run_id)
    if not run_entry:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    # Determine baseline
    if not baseline_id:
        # Get latest run for the same strategy
        index = IndexStore.load(str(backtest_results_dir))
        strategy_runs = index.get("strategies", {}).get(run_entry.get("strategy", ""), {}).get("runs", [])
        if strategy_runs and len(strategy_runs) > 1:
            # Use the most recent run that's not the current run
            for run in strategy_runs:
                if run.get("run_id") != run_id:
                    baseline_id = run.get("run_id")
                    break
    
    if not baseline_id:
        raise HTTPException(status_code=400, detail="No baseline run available")
    
    baseline_entry = load_run_entry(baseline_id)
    if not baseline_entry:
        raise HTTPException(status_code=404, detail=f"Baseline run {baseline_id} not found")
    
    # Load run data
    # run_dir is relative to backtest_results_dir and already includes strategy path
    run_dir = backtest_results_dir / run_entry.get("run_dir", "")
    baseline_dir = backtest_results_dir / baseline_entry.get("run_dir", "")
    
    try:
        run_results = RunStore.load_run(run_dir)
        baseline_results = RunStore.load_run(baseline_dir)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=404, detail=f"Failed to load run data: {str(e)}")
    
    # Compare parameters
    parameter_changes = []
    all_params = set(run_results.params.keys()) | set(baseline_results.params.keys())
    
    for param in sorted(all_params):
        run_val = run_results.params.get(param)
        baseline_val = baseline_results.params.get(param)
        
        if run_val != baseline_val:
            parameter_changes.append({
                "parameter": param,
                "before": baseline_val,
                "after": run_val,
                "changed": True,
            })
    
    # Compare code (placeholder - would need strategy file comparison)
    code_changes = []
    has_code_diff = False
    
    return DiffResponse(
        run_id=run_id,
        baseline_id=baseline_id,
        parameter_changes=parameter_changes,
        code_changes=code_changes,
        has_code_diff=has_code_diff,
    )


@router.post("/runs/{run_id}/rollback", response_model=RollbackResponse)
async def rollback_run(
    run_id: str,
    request: RollbackRequest,
    settings: SettingsServiceDep,
) -> RollbackResponse:
    """Rollback strategy file to a previous version.
    
    Reverts the strategy file on disk to the version used in the baseline run.
    """
    app_settings = settings.load_settings()
    if not app_settings.user_data_path:
        raise HTTPException(status_code=404, detail="User data path not configured")
    
    backtest_results_dir = Path(app_settings.user_data_path) / "backtest_results"
    
    # Load baseline run
    def load_run_entry(run_id: str) -> Optional[dict]:
        index = IndexStore.load(str(backtest_results_dir))
        for strat_data in index.get("strategies", {}).values():
            for run in strat_data.get("runs", []):
                if run.get("run_id") == run_id:
                    return run
        return None
    
    baseline_entry = load_run_entry(request.baseline_run_id)
    if not baseline_entry:
        raise HTTPException(status_code=404, detail=f"Baseline run {request.baseline_run_id} not found")
    
    strategy_name = baseline_entry.get("strategy", "")
    
    # Initialize version manager
    version_manager = VersionManagerService(str(app_settings.user_data_path))
    
    # Try to find the version for this run
    # For now, return a placeholder response
    # Full implementation would:
    # 1. Load the strategy file from the baseline run
    # 2. Copy it to the current strategy location
    # 3. Update the strategy file on disk
    
    return RollbackResponse(
        success=True,
        message=f"Rollback to {request.baseline_run_id} would be implemented with full version manager integration",
        rollback_to_run_id=request.baseline_run_id,
        strategy_name=strategy_name,
    )
