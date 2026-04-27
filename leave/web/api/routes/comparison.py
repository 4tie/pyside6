"""API endpoints for backtest run comparison.

Provides endpoints to compare two backtest runs and identify improvements.
"""
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends

from app.core.backtests.results_index import IndexStore
from app.core.backtests.results_store import RunStore
from app.core.services.comparison_service import ComparisonService
from app.core.services.pattern_database import PatternDatabase
from app.core.services.pattern_engine import PatternEngine
from app.core.services.settings_service import SettingsService
from app.web.dependencies import SettingsServiceDep
from app.web.models import ComparisonResponse

router = APIRouter()


@router.get("/comparison", response_model=ComparisonResponse)
async def compare_runs(
    settings: SettingsServiceDep,
    run_a_id: str = Query(..., description="First run ID (baseline)"),
    run_b_id: str = Query(..., description="Second run ID (candidate)"),
    detailed: bool = Query(False, description="Include pattern detection and full metrics"),
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
    # run_dir is relative to backtest_results_dir and already includes strategy path
    run_a_dir = backtest_results_dir / run_a_entry.get("run_dir", "")
    run_b_dir = backtest_results_dir / run_b_entry.get("run_dir", "")
    
    try:
        results_a = RunStore.load_run(run_a_dir)
        results_b = RunStore.load_run(run_b_dir)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=404, detail=f"Failed to load run data: {str(e)}")
    
    # Perform comparison
    if detailed:
        # Detect patterns if detailed mode
        patterns_a = []
        patterns_b = []
        if PatternDatabase.is_loaded():
            patterns_a = [d.pattern_id for d in PatternEngine.detect(results_a.summary, PatternDatabase.get_all())]
            patterns_b = [d.pattern_id for d in PatternEngine.detect(results_b.summary, PatternDatabase.get_all())]
        
        comparison = ComparisonService.compare_enhanced(
            results_a.summary,
            results_b.summary,
            patterns_a=patterns_a,
            patterns_b=patterns_b,
        )
    else:
        comparison = ComparisonService.compare(results_a.summary, results_b.summary)
    
    return ComparisonResponse(
        run_a_id=run_a_id,
        run_b_id=run_b_id,
        profit_diff=comparison.profit_diff,
        winrate_diff=comparison.winrate_diff,
        drawdown_diff=comparison.drawdown_diff,
        verdict=comparison.verdict,
        score_a=comparison.score_a,
        score_b=comparison.score_b,
        score_diff=comparison.score_diff,
        score_pct_change=(comparison.score_diff / abs(comparison.score_a) * 100) if comparison.score_a != 0 else 0.0,
        sharpe_diff=comparison.sharpe_diff,
        sortino_diff=comparison.sortino_diff,
        calmar_diff=comparison.calmar_diff,
        profit_factor_diff=comparison.profit_factor_diff,
        trade_frequency_diff=comparison.trade_frequency_diff,
        avg_duration_diff=comparison.avg_duration_diff,
        expectancy_diff=comparison.expectancy_diff,
        patterns_a=comparison.patterns_a,
        patterns_b=comparison.patterns_b,
        patterns_diff=list(set(comparison.patterns_b) - set(comparison.patterns_a)),
        confidence_score=comparison.confidence_score,
        confidence_reason=comparison.confidence_reason,
        is_statistically_significant=comparison.is_statistically_significant,
        metric_scores=comparison.metric_scores,
        recommendations=comparison.recommendations,
    )


@router.post("/comparison/batch")
async def compare_multiple_runs(
    settings: SettingsServiceDep,
    run_ids: List[str],
    baseline_id: Optional[str] = None,
    detailed: bool = Query(False, description="Include pattern detection and full metrics"),
) -> List[ComparisonResponse]:
    """Compare multiple runs against a baseline or each other.
    
    If baseline_id is provided, compares each run against the baseline.
    If no baseline_id, compares all runs against the first run in the list.
    
    Returns results sorted by score improvement (highest first).
    """
    app_settings = settings.load_settings()
    if not app_settings.user_data_path:
        raise HTTPException(status_code=404, detail="User data path not configured")
    
    if len(run_ids) < 2:
        raise HTTPException(status_code=400, detail="At least 2 run IDs required")
    
    backtest_results_dir = Path(app_settings.user_data_path) / "backtest_results"
    
    # Determine baseline
    baseline = baseline_id or run_ids[0]
    candidates = [r for r in run_ids if r != baseline]
    
    # Load baseline run
    def load_run_entry(run_id: str) -> Optional[dict]:
        index = IndexStore.load(str(backtest_results_dir))
        for strat_data in index.get("strategies", {}).values():
            for run in strat_data.get("runs", []):
                if run.get("run_id") == run_id:
                    return run
        return None
    
    baseline_entry = load_run_entry(baseline)
    if not baseline_entry:
        raise HTTPException(status_code=404, detail=f"Baseline run {baseline} not found")
    
    # run_dir is relative to backtest_results_dir and already includes strategy path
    baseline_dir = backtest_results_dir / baseline_entry.get("run_dir", "")
    try:
        baseline_results = RunStore.load_run(baseline_dir)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=404, detail=f"Failed to load baseline: {str(e)}")
    
    # Detect patterns for baseline if detailed
    baseline_patterns = []
    if detailed and PatternDatabase.is_loaded():
        baseline_patterns = [d.pattern_id for d in PatternEngine.detect(baseline_results.summary, PatternDatabase.get_all())]
    
    # Compare each candidate
    comparisons = []
    for run_id in candidates:
        run_entry = load_run_entry(run_id)
        if not run_entry:
            continue  # Skip missing runs
        
        # run_dir is relative to backtest_results_dir and already includes strategy path
        run_dir = backtest_results_dir / run_entry.get("run_dir", "")
        try:
            run_results = RunStore.load_run(run_dir)
        except (FileNotFoundError, ValueError):
            continue  # Skip failed loads
        
        # Detect patterns for candidate if detailed
        run_patterns = []
        if detailed and PatternDatabase.is_loaded():
            run_patterns = [d.pattern_id for d in PatternEngine.detect(run_results.summary, PatternDatabase.get_all())]
        
        # Perform comparison
        if detailed:
            comparison = ComparisonService.compare_enhanced(
                baseline_results.summary,
                run_results.summary,
                patterns_a=baseline_patterns,
                patterns_b=run_patterns,
            )
        else:
            comparison = ComparisonService.compare(baseline_results.summary, run_results.summary)
        
        comparisons.append(ComparisonResponse(
            run_a_id=baseline,
            run_b_id=run_id,
            profit_diff=comparison.profit_diff,
            winrate_diff=comparison.winrate_diff,
            drawdown_diff=comparison.drawdown_diff,
            verdict=comparison.verdict,
            score_a=comparison.score_a,
            score_b=comparison.score_b,
            score_diff=comparison.score_diff,
            score_pct_change=(comparison.score_diff / abs(comparison.score_a) * 100) if comparison.score_a != 0 else 0.0,
            sharpe_diff=comparison.sharpe_diff,
            sortino_diff=comparison.sortino_diff,
            calmar_diff=comparison.calmar_diff,
            profit_factor_diff=comparison.profit_factor_diff,
            trade_frequency_diff=comparison.trade_frequency_diff,
            avg_duration_diff=comparison.avg_duration_diff,
            expectancy_diff=comparison.expectancy_diff,
            patterns_a=comparison.patterns_a,
            patterns_b=comparison.patterns_b,
            patterns_diff=list(set(comparison.patterns_b) - set(comparison.patterns_a)),
            confidence_score=comparison.confidence_score,
            confidence_reason=comparison.confidence_reason,
            is_statistically_significant=comparison.is_statistically_significant,
            metric_scores=comparison.metric_scores,
            recommendations=comparison.recommendations,
        ))
    
    # Sort by score improvement (highest first)
    comparisons.sort(key=lambda x: x.score_diff, reverse=True)
    
    return comparisons
