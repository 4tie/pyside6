"""comparison_service.py — Stateless service for backtest run comparison.

Compares two BacktestSummary objects and returns a RunComparison with diffs
and a verdict indicating whether the candidate run improved, degraded, or
remained neutral relative to the baseline.

Enhanced version includes:
- Multi-objective 4-layer scoring
- Risk-adjusted metrics (Sharpe, Sortino, Calmar)
- Statistical confidence scoring
- Pattern detection integration
- Actionable recommendations
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from app.core.models.backtest_models import BacktestSummary, RunComparison
from app.core.services.evaluation_engine import EvaluationEngine
from app.core.utils.app_logger import get_logger

_log = get_logger("services.comparison")

# Minimum trades for statistical significance
MIN_TRADES_SIGNIFICANCE = 30


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

    @staticmethod
    def compare_enhanced(
        run_a: BacktestSummary,
        run_b: BacktestSummary,
        patterns_a: Optional[List[str]] = None,
        patterns_b: Optional[List[str]] = None,
    ) -> RunComparison:
        """Enhanced comparison with multi-objective scoring and detailed analysis.

        Args:
            run_a: Baseline BacktestSummary.
            run_b: Candidate BacktestSummary.
            patterns_a: Pattern IDs affecting run A (optional).
            patterns_b: Pattern IDs affecting run B (optional).

        Returns:
            RunComparison with enhanced metrics and recommendations.
        """
        # Basic diffs (existing logic)
        profit_diff = run_b.total_profit - run_a.total_profit
        winrate_diff = run_b.win_rate - run_a.win_rate
        drawdown_diff = run_b.max_drawdown - run_a.max_drawdown

        # Multi-objective 4-layer scores
        score_a = EvaluationEngine.calculate_score(run_a)
        score_b = EvaluationEngine.calculate_score(run_b)
        score_diff = score_b - score_a
        score_pct_change = (score_diff / abs(score_a) * 100) if score_a != 0 else 0.0

        # Risk-adjusted metrics
        sharpe_diff = (run_b.sharpe_ratio or 0) - (run_a.sharpe_ratio or 0)
        sortino_diff = (run_b.sortino_ratio or 0) - (run_a.sortino_ratio or 0)
        calmar_diff = (run_b.calmar_ratio or 0) - (run_a.calmar_ratio or 0)
        profit_factor_diff = (run_b.profit_factor or 0) - (run_a.profit_factor or 0)

        # Trade quality analysis
        trade_frequency_diff = ComparisonService._calculate_trade_frequency_diff(run_a, run_b)
        avg_duration_diff = ComparisonService._calculate_avg_duration_diff(run_a, run_b)
        expectancy_diff = (run_b.expectancy or 0) - (run_a.expectancy or 0)

        # Enhanced verdict logic
        verdict = ComparisonService._determine_verdict(
            profit_diff, score_diff, drawdown_diff, sharpe_diff,
            run_a.total_trades, run_b.total_trades
        )

        # Confidence scoring
        confidence_score, confidence_reason, is_significant = ComparisonService._calculate_confidence(
            run_a, run_b, score_diff
        )

        # Per-metric scores
        metric_scores = ComparisonService._calculate_metric_scores(run_a, run_b)

        # Recommendations
        recommendations = ComparisonService._generate_recommendations(
            verdict, metric_scores, patterns_a or [], patterns_b or []
        )

        _log.debug(
            "compare_enhanced: score_diff=%0.4f, confidence=%0.2f, verdict=%s",
            score_diff, confidence_score, verdict
        )

        return RunComparison(
            profit_diff=profit_diff,
            winrate_diff=winrate_diff,
            drawdown_diff=drawdown_diff,
            verdict=verdict,
            score_a=score_a,
            score_b=score_b,
            score_diff=score_diff,
            sharpe_diff=sharpe_diff,
            sortino_diff=sortino_diff,
            calmar_diff=calmar_diff,
            profit_factor_diff=profit_factor_diff,
            trade_frequency_diff=trade_frequency_diff,
            avg_duration_diff=avg_duration_diff,
            expectancy_diff=expectancy_diff,
            patterns_a=patterns_a or [],
            patterns_b=patterns_b or [],
            confidence_score=confidence_score,
            confidence_reason=confidence_reason,
            is_statistically_significant=is_significant,
            metric_scores=metric_scores,
            recommendations=recommendations,
        )

    @staticmethod
    def _calculate_trade_frequency_diff(run_a: BacktestSummary, run_b: BacktestSummary) -> float:
        """Calculate difference in trade frequency (trades per day)."""
        # Estimate days from backtest period (if available)
        # Fallback: use trade count ratio
        if run_a.total_trades == 0:
            return 0.0
        return (run_b.total_trades - run_a.total_trades) / max(run_a.total_trades, 1)

    @staticmethod
    def _calculate_avg_duration_diff(run_a: BacktestSummary, run_b: BacktestSummary) -> float:
        """Calculate difference in average trade duration."""
        # If we had trade-level data, we'd calculate this properly
        # For now, return 0 as we don't have duration in summary
        return 0.0

    @staticmethod
    def _determine_verdict(
        profit_diff: float,
        score_diff: float,
        drawdown_diff: float,
        sharpe_diff: float,
        trades_a: int,
        trades_b: int,
    ) -> str:
        """Determine verdict using multi-objective scoring and risk metrics.

        Enhanced logic:
        1. Strong improvement: profit > 0 AND score > 0 AND drawdown <= 0
        2. Degraded: profit < 0 OR drawdown > 5 OR sharpe < -0.5
        3. Neutral: otherwise
        """
        # Strong improvement criteria
        if profit_diff > 0 and score_diff > 0 and drawdown_diff <= 0:
            return "improved"

        # Degradation criteria
        if profit_diff < 0 or drawdown_diff > 5.0 or sharpe_diff < -0.5:
            return "degraded"

        # Weak improvement (profit up but risk increased slightly)
        if profit_diff > 0 and score_diff > 0:
            return "improved"

        return "neutral"

    @staticmethod
    def _calculate_confidence(
        run_a: BacktestSummary,
        run_b: BacktestSummary,
        score_diff: float,
    ) -> Tuple[float, str, bool]:
        """Calculate confidence score and statistical significance.

        Returns:
            Tuple of (confidence_score, reason, is_significant)
        """
        factors = []
        reasons = []

        # Factor 1: Trade count (more trades = more confidence)
        min_trades = min(run_a.total_trades, run_b.total_trades)
        if min_trades >= MIN_TRADES_SIGNIFICANCE:
            factors.append(1.0)
            reasons.append("sufficient trades")
        elif min_trades >= 15:
            factors.append(0.6)
            reasons.append("moderate trade count")
        else:
            factors.append(0.3)
            reasons.append("low trade count")

        # Factor 2: Score magnitude (larger improvements = more confidence)
        if abs(score_diff) > 0.5:
            factors.append(1.0)
            reasons.append("large score change")
        elif abs(score_diff) > 0.2:
            factors.append(0.7)
            reasons.append("moderate score change")
        else:
            factors.append(0.4)
            reasons.append("small score change")

        # Factor 3: Consistency across metrics
        consistent_metrics = 0
        if (run_b.profit_pct or 0) > (run_a.profit_pct or 0):
            consistent_metrics += 1
        if (run_b.sharpe_ratio or 0) > (run_a.sharpe_ratio or 0):
            consistent_metrics += 1
        if (run_b.max_drawdown or 100) < (run_a.max_drawdown or 100):
            consistent_metrics += 1

        if consistent_metrics >= 2:
            factors.append(1.0)
            reasons.append("consistent metric improvements")
        elif consistent_metrics >= 1:
            factors.append(0.6)
            reasons.append("mixed metric changes")
        else:
            factors.append(0.3)
            reasons.append("conflicting metric changes")

        # Calculate final confidence
        confidence_score = sum(factors) / len(factors)
        confidence_reason = ", ".join(reasons)
        is_significant = min_trades >= MIN_TRADES_SIGNIFICANCE and confidence_score >= 0.6

        return confidence_score, confidence_reason, is_significant

    @staticmethod
    def _calculate_metric_scores(run_a: BacktestSummary, run_b: BacktestSummary) -> Dict[str, float]:
        """Calculate per-metric improvement scores (-1 to 1 scale).

        Positive = improvement, Negative = degradation, 0 = neutral.
        """
        scores = {}

        # Profit (normalized to -1 to 1)
        profit_a = run_a.profit_pct or 0
        profit_b = run_b.profit_pct or 0
        if profit_a != 0:
            scores["profit"] = max(-1, min(1, (profit_b - profit_a) / abs(profit_a)))
        else:
            scores["profit"] = 1.0 if profit_b > 0 else -1.0 if profit_b < 0 else 0.0

        # Sharpe ratio
        sharpe_a = run_a.sharpe_ratio or 0
        sharpe_b = run_b.sharpe_ratio or 0
        if sharpe_a != 0:
            scores["sharpe"] = max(-1, min(1, (sharpe_b - sharpe_a) / abs(sharpe_a)))
        else:
            scores["sharpe"] = 1.0 if sharpe_b > sharpe_a else -1.0 if sharpe_b < sharpe_a else 0.0

        # Drawdown (inverse - lower is better)
        dd_a = run_a.max_drawdown or 100
        dd_b = run_b.max_drawdown or 100
        if dd_a != 0:
            scores["drawdown"] = max(-1, min(1, (dd_a - dd_b) / dd_a))
        else:
            scores["drawdown"] = 0.0

        # Win rate
        wr_a = run_a.win_rate or 0
        wr_b = run_b.win_rate or 0
        scores["win_rate"] = max(-1, min(1, (wr_b - wr_a) / 100))

        # Expectancy
        exp_a = run_a.expectancy or 0
        exp_b = run_b.expectancy or 0
        if exp_a != 0:
            scores["expectancy"] = max(-1, min(1, (exp_b - exp_a) / abs(exp_a)))
        else:
            scores["expectancy"] = 1.0 if exp_b > 0 else -1.0 if exp_b < 0 else 0.0

        return scores

    @staticmethod
    def _generate_recommendations(
        verdict: str,
        metric_scores: Dict[str, float],
        patterns_a: List[str],
        patterns_b: List[str],
    ) -> List[str]:
        """Generate actionable recommendations based on comparison results."""
        recommendations = []

        if verdict == "improved":
            recommendations.append("Run B shows overall improvement over Run A.")

            # Identify best improvements
            best_metric = max(metric_scores.items(), key=lambda x: x[1])
            if best_metric[1] > 0.3:
                recommendations.append(f"Best improvement: {best_metric[0]} (+{best_metric[1]*100:.0f}%)")

        elif verdict == "degraded":
            recommendations.append("Run B shows degradation compared to Run A.")

            # Identify worst degradations
            worst_metric = min(metric_scores.items(), key=lambda x: x[1])
            if worst_metric[1] < -0.3:
                recommendations.append(f"Concern: {worst_metric[0]} degraded ({worst_metric[1]*100:.0f}%)")

            # Suggest fixes based on patterns
            if patterns_b:
                recommendations.append(f"Detected {len(patterns_b)} failure patterns - review diagnostics")

        else:
            recommendations.append("Run B is neutral compared to Run A.")

        # Pattern analysis
        new_patterns = set(patterns_b) - set(patterns_a)
        if new_patterns:
            recommendations.append(f"New patterns in Run B: {', '.join(list(new_patterns)[:3])}")

        return recommendations
