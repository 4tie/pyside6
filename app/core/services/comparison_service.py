"""comparison_service.py — Stateless service for backtest run comparison.

Compares two BacktestSummary objects and returns a RunComparison with diffs
and a verdict indicating whether the candidate run improved, degraded, or
remained neutral relative to the baseline.
"""

from __future__ import annotations

from app.core.backtests.results_models import BacktestSummary, RunComparison
from app.core.utils.app_logger import get_logger

_log = get_logger("services.comparison")


class ComparisonService:
    """Stateless service that compares two backtest runs.

    All methods are static — no instance state is held.
    """

    @staticmethod
    def compare(run_a: BacktestSummary, run_b: BacktestSummary) -> RunComparison:
        """Compute a RunComparison between two backtest summaries.

        run_b is treated as the candidate; run_a as the baseline.
        Diffs are computed as run_b - run_a.

        Verdict logic (evaluated in order, first match wins):
        1. profit_diff > 0.0 AND drawdown_diff <= 0.0 → "improved"
        2. profit_diff < 0.0 OR drawdown_diff > 5.0 → "degraded"
        3. Otherwise → "neutral"

        Args:
            run_a: Baseline BacktestSummary.
            run_b: Candidate BacktestSummary.

        Returns:
            RunComparison with diffs and verdict.
        """
        profit_diff = run_b.total_profit - run_a.total_profit
        winrate_diff = run_b.win_rate - run_a.win_rate
        drawdown_diff = run_b.max_drawdown - run_a.max_drawdown

        # Verdict logic
        if profit_diff > 0.0 and drawdown_diff <= 0.0:
            verdict = "improved"
        elif profit_diff < 0.0 or drawdown_diff > 5.0:
            verdict = "degraded"
        else:
            verdict = "neutral"

        _log.debug(
            "compare: profit_diff=%0.2f, winrate_diff=%0.2f, drawdown_diff=%0.2f, verdict=%s",
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
