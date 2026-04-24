"""diagnosis_service.py — Stateless service for backtest diagnostic analysis.

Analyzes pair performance and summary statistics to identify improvement
opportunities and performance issues. Returns a list of DiagnosisSuggestion
objects for each fired rule.
"""
from __future__ import annotations

from typing import List

from app.core.models.backtest_models import PairAnalysis, BacktestSummary
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
        1. entry_too_aggressive: win_rate < 30% suggests entry logic is loose.
        2. stoploss_too_loose: max_drawdown > 40% suggests stop-loss is too wide.
        3. overfitting_risk: profit concentration flag indicates single pair dominance.
        4. insufficient_trades: total_trades < 30 provides weak signal.
        5. negative_expectancy: 0 < profit_factor < 1 means strategy has negative expectancy.

        Args:
            pair_analysis: PairAnalysis output from PairAnalysisService.
            summary: BacktestSummary with aggregate statistics.

        Returns:
            List of DiagnosisSuggestion objects for each rule that fired.
            Empty list if no rules match.
        """
        suggestions: List[DiagnosisSuggestion] = []

        # Rule 1: entry_too_aggressive
        if summary.win_rate < 30.0:
            _log.debug("diagnose: entry_too_aggressive fired (win_rate=%0.1f%%)", summary.win_rate)
            suggestions.append(
                DiagnosisSuggestion(
                    rule_id="entry_too_aggressive",
                    message=(
                        f"Win rate is {summary.win_rate:.1f}% — entry conditions may be too aggressive."
                    ),
                    severity="critical",
                )
            )

        # Rule 2: stoploss_too_loose
        if summary.max_drawdown > 40.0:
            _log.debug("diagnose: stoploss_too_loose fired (max_drawdown=%0.1f%%)", summary.max_drawdown)
            suggestions.append(
                DiagnosisSuggestion(
                    rule_id="stoploss_too_loose",
                    message=(
                        f"Max drawdown is {summary.max_drawdown:.1f}% — stoploss may be too loose."
                    ),
                    severity="critical",
                )
            )

        # Rule 3: overfitting_risk
        if "profit_concentration" in pair_analysis.dominance_flags:
            _log.debug("diagnose: overfitting_risk fired (dominance_flags=%s)", pair_analysis.dominance_flags)
            suggestions.append(
                DiagnosisSuggestion(
                    rule_id="overfitting_risk",
                    message=(
                        "One pair dominates profit — strategy may be overfit to a single asset."
                    ),
                    severity="warning",
                )
            )

        # Rule 4: insufficient_trades
        if summary.total_trades < 30:
            _log.debug("diagnose: insufficient_trades fired (total_trades=%d)", summary.total_trades)
            suggestions.append(
                DiagnosisSuggestion(
                    rule_id="insufficient_trades",
                    message=(
                        f"Only {summary.total_trades} trades — results may not be statistically significant."
                    ),
                    severity="warning",
                )
            )

        # Rule 5: negative_expectancy
        if 0.0 < summary.profit_factor < 1.0:
            _log.debug("diagnose: negative_expectancy fired (profit_factor=%0.2f)", summary.profit_factor)
            suggestions.append(
                DiagnosisSuggestion(
                    rule_id="negative_expectancy",
                    message=(
                        f"Profit factor is {summary.profit_factor:.2f} — strategy has negative expectancy."
                    ),
                    severity="critical",
                )
            )

        _log.debug("diagnose: %d rules fired", len(suggestions))
        return suggestions
