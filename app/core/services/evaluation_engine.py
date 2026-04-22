"""
evaluation_engine.py — Pure function evaluation engine.

Part of the 4-layer diagnostic architecture.
Evaluates improvement between old and new metrics.
"""
from __future__ import annotations

from typing import Dict

from app.core.backtests.results_models import BacktestSummary

# Minimum trades required for stability
MIN_TRADES = 30


class EvaluationEngine:
    """Pure function evaluation engine.
    
    Evaluates whether new metrics represent actual improvement.
    """

    @staticmethod
    def evaluate(old_metrics: BacktestSummary, new_metrics: BacktestSummary) -> Dict:
        """Evaluate improvement between old and new metrics.
        
        Pure function: input → output only.
        
        Args:
            old_metrics: Previous backtest metrics
            new_metrics: New backtest metrics
            
        Returns:
            Dict with:
                - improved: bool (True if improvement detected)
                - score_diff: float (difference in multi-objective score)
        """
        # Simple multi-objective score
        old_score = (
            (old_metrics.profit_pct or 0) * 0.4 +
            (old_metrics.sharpe_ratio or 0) * 0.3 -
            (old_metrics.max_drawdown or 0) * 0.2 +
            (old_metrics.win_rate or 0) * 0.1
        )
        
        new_score = (
            (new_metrics.profit_pct or 0) * 0.4 +
            (new_metrics.sharpe_ratio or 0) * 0.3 -
            (new_metrics.max_drawdown or 0) * 0.2 +
            (new_metrics.win_rate or 0) * 0.1
        )
        
        # Binary improvement check with stability and sharpe guard
        # Prevents fake improvements (small profit gain but sharpe drops significantly)
        improved = (
            (new_metrics.profit_pct or 0) > (old_metrics.profit_pct or 0) and
            (new_metrics.max_drawdown or 0) <= (old_metrics.max_drawdown or 0) * 1.1 and
            (new_metrics.sharpe_ratio or 0) >= (old_metrics.sharpe_ratio or 0) * 0.9 and
            (new_metrics.total_trades or 0) > MIN_TRADES
        )
        
        return {
            "improved": improved,
            "score_diff": new_score - old_score
        }
    
    @staticmethod
    def calculate_score(metrics: BacktestSummary) -> float:
        """Calculate multi-objective score for metrics.
        
        Args:
            metrics: Backtest metrics
            
        Returns:
            Score value
        """
        return (
            (metrics.profit_pct or 0) * 0.4 +
            (metrics.sharpe_ratio or 0) * 0.3 -
            (metrics.max_drawdown or 0) * 0.2 +
            (metrics.win_rate or 0) * 0.1
        )
