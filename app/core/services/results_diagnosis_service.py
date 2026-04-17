"""
results_diagnosis_service.py — Stateless rule-based diagnosis of backtest results.
"""
from typing import List

from app.core.backtests.results_models import BacktestSummary
from app.core.models.improve_models import DiagnosedIssue
from app.core.utils.app_logger import get_logger

_log = get_logger("services.results_diagnosis")

# Threshold constants
STOPLOSS_TOO_WIDE: float = 20.0
TRADES_TOO_LOW: int = 30
WEAK_WIN_RATE: float = 45.0
DRAWDOWN_HIGH: float = 30.0
POOR_PAIR_CONCENTRATION: int = 3


class ResultsDiagnosisService:
    """Stateless service that evaluates rule-based heuristics on a BacktestSummary.

    All methods are static — no instance state is required.
    """

    @staticmethod
    def diagnose(summary: BacktestSummary) -> List[DiagnosedIssue]:
        """Evaluate all diagnosis rules against a backtest summary.

        Args:
            summary: Aggregate statistics from a completed backtest run.

        Returns:
            A list of DiagnosedIssue objects for every rule whose condition is met.
            Returns an empty list when no issues are detected.
        """
        issues: List[DiagnosedIssue] = []

        if summary.max_drawdown > STOPLOSS_TOO_WIDE:
            issues.append(DiagnosedIssue(
                issue_id="stoploss_too_wide",
                description=(
                    f"Max drawdown {summary.max_drawdown:.2f}% exceeds {STOPLOSS_TOO_WIDE}% — "
                    "stoploss may be set too wide, allowing large individual losses."
                ),
            ))

        if summary.total_trades < TRADES_TOO_LOW:
            issues.append(DiagnosedIssue(
                issue_id="trades_too_low",
                description=(
                    f"Only {summary.total_trades} trades recorded (threshold: {TRADES_TOO_LOW}) — "
                    "too few trades to draw statistically reliable conclusions."
                ),
            ))

        if summary.win_rate < WEAK_WIN_RATE:
            issues.append(DiagnosedIssue(
                issue_id="weak_win_rate",
                description=(
                    f"Win rate {summary.win_rate:.2f}% is below {WEAK_WIN_RATE}% — "
                    "the strategy wins less than half its trades."
                ),
            ))

        if summary.max_drawdown > DRAWDOWN_HIGH:
            issues.append(DiagnosedIssue(
                issue_id="drawdown_high",
                description=(
                    f"Max drawdown {summary.max_drawdown:.2f}% exceeds {DRAWDOWN_HIGH}% — "
                    "portfolio risk is high; consider reducing position size or open trades."
                ),
            ))

        if len(summary.pairlist) < POOR_PAIR_CONCENTRATION:
            issues.append(DiagnosedIssue(
                issue_id="poor_pair_concentration",
                description=(
                    f"Only {len(summary.pairlist)} pair(s) in pairlist (threshold: {POOR_PAIR_CONCENTRATION}) — "
                    "low diversification increases concentration risk."
                ),
            ))

        if summary.total_profit < 0.0:
            issues.append(DiagnosedIssue(
                issue_id="negative_profit",
                description=(
                    f"Total profit {summary.total_profit:.4f}% is negative — "
                    "the strategy lost money over the backtest period."
                ),
            ))

        _log.debug("Diagnosed %d issue(s) for strategy '%s'", len(issues), summary.strategy)
        return issues
