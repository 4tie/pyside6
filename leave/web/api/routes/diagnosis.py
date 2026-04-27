"""API endpoints for backtest diagnosis.

Provides endpoints to retrieve diagnostic analysis for backtest runs.
"""
from pathlib import Path
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Depends

from app.core.backtests.results_index import IndexStore
from app.core.backtests.results_store import RunStore
from app.core.services.diagnosis_service import DiagnosisService
from app.core.services.pair_analysis_service import PairAnalysisService
from app.core.services.settings_service import SettingsService
from leave.web.dependencies import SettingsServiceDep
from leave.web.models import DiagnosisResponse

router = APIRouter()


@router.get("/diagnosis/{run_id}", response_model=DiagnosisResponse)
async def get_diagnosis(
    run_id: str,
    settings: SettingsServiceDep,
) -> DiagnosisResponse:
    """Get diagnostic analysis for a specific run."""
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
    
    # Perform pair analysis
    pair_analysis = PairAnalysisService.analyse(results)
    
    # Perform diagnosis
    diagnosis = DiagnosisService.diagnose(pair_analysis, results.summary)
    
    return DiagnosisResponse(
        run_id=run_id,
        issues=[
            {
                "rule_id": d.rule_id,
                "message": d.message,
                "severity": d.severity,
            }
            for d in diagnosis
        ],
        suggestions=[
            {
                "rule_id": d.rule_id,
                "message": d.message,
                "severity": d.severity,
            }
            for d in diagnosis
        ],
    )
