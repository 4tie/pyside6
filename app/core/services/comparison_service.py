"""comparison_service.py — Stateless service for comparing two backtest runs.

Compares two BacktestSummary objects and produces a RunComparison DTO
with profit/winrate/drawdown diffs and a verdict string.
"""
from __future__ import annotations

from app.core.backtests.results_models import BacktestSummary, RunComparison
from app.core.utils.app_logger import get_logger

_log = get_logger("services.comparison")


class ComparisonService:
    """Stateless service for run comparison.

    Computes deltas between two backtest runs and derives a verdict
    (improved/degraded/neutral). All methods are static.
    """

    @staticmethod
    def compare(run_a: BacktestSummary, run_b: BacktestSummary) -> RunComparison:
        """Compare two backtest runs, computing deltas relative to run_a.

        Computes three metrics and a verdict:
        - profit_diff = run_b.total_profit - run_a.total_profit
        - winrate_diff = run_b.win_rate - run_a.win_rate
        - drawdown_diff = run_b.max_drawdown - run_a.max_drawdown (positive = worse)

        Verdict logic (checked in order):
        1. If profit_diff > 0 AND winrate_diff > 0 AND drawdown_diff <= 0 → "improved"
        2. Else if profit_diff < 0 OR winrate_diff < 0 OR drawdown_diff > 0 → "degraded"
        3. Else → "neutral"

        Args:
            run_a: Baseline run (reference).
            run_b: Candidate run (comparison target).

        Returns:
            RunComparison with computed diffs and verdict.
        """
        profit_diff = run_b.total_profit - run_a.total_profit
        winrate_diff = run_b.win_rate - run_a.win_rate
        drawdown_diff = run_b.max_drawdown - run_a.max_drawdown

        # Verdict logic
        if profit_diff > 0 and winrate_diff > 0 and drawdown_diff <= 0:
            verdict = "improved"
        elif profit_diff < 0 or winrate_diff < 0 or drawdown_diff > 0:
            verdict = "degraded"
        else:
            verdict = "neutral"

        _log.debug(
            "compare: profit_diff=%0.3f, winrate_diff=%0.1f%%, drawdown_diff=%0.1f%%, verdict=%s",
            profit_diff,
            winrate_diff,
            drawdown_diff,
            verdict,
        )

        return RunComparison(
            profit_diff=profit_diff,
            winrate_diff=winrate_diff,
            drawdown_diff=drawdown_diff,
            verdict=verdict,
        )
