"""diagnosis_service.py — Stateless service for backtest diagnostic analysis.

Analyzes pair performance and summary statistics to identify improvement
opportunities and performance issues. Returns a list of DiagnosisSuggestion
objects for each fired rule.
"""
from __future__ import annotations

from typing import List

from app.core.backtests.results_models import PairAnalysis, BacktestSummary
from app.core.models.analysis_models import DiagnosisSuggestion
from app.core.utils.app_logger import get_logger

_log = get_logger("services.diagnosis")


class DiagnosisService:
    """Stateless service for diagnostic rule evaluation.

    Evaluates five independent diagnostic rules against pair analysis
    and summary data. All methods are static — no instance state is held.
    """

    @staticmethod
    def diagnose(
        pair_analysis: PairAnalysis, summary: BacktestSummary
    ) -> List[DiagnosisSuggestion]:
        """Evaluate diagnostic rules and return all that fire.

        Implements five independent rules that can fire simultaneously:
        1. entry_too_aggressive: win_rate < 40% suggests entry logic is loose.
        2. stoploss_too_loose: max_drawdown > 15% suggests stop-loss is too wide.
        3. overfitting_risk: profit concentration > 50% on single pair.
        4. insufficient_trades: total_trades < 50 provides weak signal.
        5. negative_expectancy: avg_profit < 0 means strategy is losing money.

        Args:
            pair_analysis: PairAnalysis output from PairAnalysisService.
            summary: BacktestSummary with aggregate statistics.

        Returns:
            List of DiagnosisSuggestion objects for each rule that fired.
            Empty list if no rules match.
        """
        suggestions: List[DiagnosisSuggestion] = []

        # Rule 1: entry_too_aggressive
        if summary.win_rate < 40.0:
            _log.debug("diagnose: entry_too_aggressive fired (win_rate=%0.1f%%)", summary.win_rate)
            suggestions.append(
                DiagnosisSuggestion(
                    rule_id="entry_too_aggressive",
                    message=(
                        f"Entry logic may be too aggressive (win rate {summary.win_rate:.1f}% < 40%). "
                        "Consider tightening entry filters or using more conservative indicators."
                    ),
                    severity="critical",
                )
            )

        # Rule 2: stoploss_too_loose
        if summary.max_drawdown > 15.0:
            _log.debug("diagnose: stoploss_too_loose fired (max_drawdown=%0.1f%%)", summary.max_drawdown)
            suggestions.append(
                DiagnosisSuggestion(
                    rule_id="stoploss_too_loose",
                    message=(
                        f"Stop-loss may be too loose (max drawdown {summary.max_drawdown:.1f}% > 15%). "
                        "Reducing max drawdown tolerance can limit per-trade losses."
                    ),
                    severity="critical",
                )
            )

        # Rule 3: overfitting_risk
        max_profit_share = (
            max((pm.profit_share for pm in pair_analysis.pair_metrics), default=0.0)
            if pair_analysis.pair_metrics
            else 0.0
        )
        if max_profit_share > 0.50:
            _log.debug("diagnose: overfitting_risk fired (max_profit_share=%0.2f)", max_profit_share)
            suggestions.append(
                DiagnosisSuggestion(
                    rule_id="overfitting_risk",
                    message=(
                        f"Profit concentration is high ({max_profit_share * 100:.1f}% on one pair > 50%). "
                        "Strategy may be overfit to a specific pair. Diversify across more pairs."
                    ),
                    severity="warning",
                )
            )

        # Rule 4: insufficient_trades
        if summary.total_trades < 50:
            _log.debug("diagnose: insufficient_trades fired (total_trades=%d)", summary.total_trades)
            suggestions.append(
                DiagnosisSuggestion(
                    rule_id="insufficient_trades",
                    message=(
                        f"Sample size is small ({summary.total_trades} trades < 50). "
                        "Results may not be statistically significant. Run on larger date range."
                    ),
                    severity="warning",
                )
            )

        # Rule 5: negative_expectancy
        if summary.avg_profit < 0.0:
            _log.debug("diagnose: negative_expectancy fired (avg_profit=%0.3f%%)", summary.avg_profit)
            suggestions.append(
                DiagnosisSuggestion(
                    rule_id="negative_expectancy",
                    message=(
                        f"Strategy has negative expectancy (avg profit {summary.avg_profit:.3f}% < 0). "
                        "Expected value per trade is negative. Strategy needs fundamental revision."
                    ),
                    severity="critical",
                )
            )

        _log.debug("diagnose: %d rules fired", len(suggestions))
        return suggestions
