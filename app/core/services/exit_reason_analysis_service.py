"""
exit_reason_analysis_service.py — Service for analyzing exit reasons from trades.

Provides analysis of trade exit patterns and generates actionable suggestions.
"""
from __future__ import annotations

from typing import List, Optional

from app.core.models.backtest_models import BacktestTrade
from app.core.models.exit_reason_models import (
    ExitReasonAnalysis,
    ExitReasonStats,
    ExitReasonSuggestion,
)
from app.core.utils.app_logger import get_logger

_log = get_logger("services.exit_reason_analysis")


class ExitReasonAnalysisService:
    """Stateless service for analyzing trade exit reasons.

    All methods are static — no instance state is required.
    """

    @staticmethod
    def analyze(trades: List[BacktestTrade]) -> ExitReasonAnalysis:
        """Analyze exit reasons from a list of trades.

        Args:
            trades: List of BacktestTrade objects (closed trades only).

        Returns:
            ExitReasonAnalysis with statistics and detected patterns.
        """
        # Filter to closed trades only
        closed_trades = [t for t in trades if not t.is_open and t.close_date]

        if not closed_trades:
            _log.debug("No closed trades to analyze")
            return ExitReasonAnalysis(total_trades=0)

        # Group trades by exit reason
        reason_groups: dict = {}
        for trade in closed_trades:
            reason = trade.exit_reason or "unknown"
            if reason not in reason_groups:
                reason_groups[reason] = []
            reason_groups[reason].append(trade)

        # Calculate stats for each reason
        total_trades = len(closed_trades)
        reason_stats: dict = {}

        for reason, reason_trades in reason_groups.items():
            wins = sum(1 for t in reason_trades if t.profit > 0)
            losses = sum(1 for t in reason_trades if t.profit < 0)
            total_profit = sum(t.profit for t in reason_trades)
            avg_profit = total_profit / len(reason_trades) if reason_trades else 0.0
            avg_duration = (
                sum(t.duration for t in reason_trades) / len(reason_trades)
                if reason_trades
                else 0.0
            )
            win_rate = (wins / len(reason_trades) * 100) if reason_trades else 0.0
            frequency = (len(reason_trades) / total_trades * 100) if total_trades else 0.0

            reason_stats[reason] = ExitReasonStats(
                reason=reason,
                count=len(reason_trades),
                win_count=wins,
                loss_count=losses,
                total_profit_pct=total_profit,
                avg_profit_pct=avg_profit,
                avg_duration_min=avg_duration,
                win_rate_pct=win_rate,
                frequency_pct=frequency,
            )

        # Find dominant reason
        dominant_reason = max(
            reason_stats.keys(),
            key=lambda r: reason_stats[r].count,
            default="",
        )

        # Identify problematic patterns
        problematic_reasons = []
        suggestions = []

        analysis = ExitReasonAnalysis(
            total_trades=total_trades,
            reason_stats=reason_stats,
            dominant_reason=dominant_reason,
            problematic_reasons=problematic_reasons,
            suggestions=suggestions,
        )

        # Detect patterns and generate suggestions
        suggestions_list = ExitReasonAnalysisService._detect_patterns(analysis)
        analysis.suggestions = [s.suggestion for s in suggestions_list]
        analysis.problematic_reasons = [s.affected_reason for s in suggestions_list]

        _log.debug(
            "Analyzed %d trades: %d unique exit reasons, %d problematic patterns detected",
            total_trades,
            len(reason_stats),
            len(suggestions_list),
        )

        return analysis

    @staticmethod
    def _detect_patterns(analysis: ExitReasonAnalysis) -> List[ExitReasonSuggestion]:
        """Detect problematic patterns and generate suggestions.

        Args:
            analysis: ExitReasonAnalysis to evaluate.

        Returns:
            List of ExitReasonSuggestion objects.
        """
        suggestions: List[ExitReasonSuggestion] = []

        # Pattern 1: High stoploss rate with negative expectancy
        stoploss_stats = analysis.reason_stats.get("stoploss")
        if stoploss_stats and stoploss_stats.frequency_pct > 40.0:
            if stoploss_stats.total_profit_pct < 0:
                suggestions.append(
                    ExitReasonSuggestion(
                        issue=f"High stoploss rate ({stoploss_stats.frequency_pct:.1f}%) with negative returns",
                        affected_reason="stoploss",
                        suggestion="Tighten stoploss to reduce per-trade loss exposure",
                        expected_improvement="Lower drawdown and smaller individual losses",
                        confidence=0.75,
                    )
                )
            else:
                # High stoploss rate but positive returns - might be working as intended
                suggestions.append(
                    ExitReasonSuggestion(
                        issue=f"High stoploss rate ({stoploss_stats.frequency_pct:.1f}%) but positive returns",
                        affected_reason="stoploss",
                        suggestion="Review if stoploss is cutting winners too early",
                        expected_improvement="Better balance between risk control and profit capture",
                        confidence=0.5,
                    )
                )

        # Pattern 2: ROI dominance with low profit factor
        roi_stats = analysis.reason_stats.get("roi")
        if roi_stats and roi_stats.frequency_pct > 50.0:
            if roi_stats.total_profit_pct < 0:
                suggestions.append(
                    ExitReasonSuggestion(
                        issue="ROI exits dominate but overall returns are negative",
                        affected_reason="roi",
                        suggestion="Widen ROI targets to capture larger moves",
                        expected_improvement="Better profit capture on winning trades",
                        confidence=0.7,
                    )
                )
            elif roi_stats.win_rate_pct < 45.0:
                suggestions.append(
                    ExitReasonSuggestion(
                        issue="ROI exits have low win rate despite dominance",
                        affected_reason="roi",
                        suggestion="Tighten ROI targets or review entry timing",
                        expected_improvement="Higher win rate with more achievable targets",
                        confidence=0.6,
                    )
                )

        # Pattern 3: Signal exits with poor performance
        signal_stats = analysis.reason_stats.get("signal")
        if signal_stats and signal_stats.win_rate_pct < 40.0:
            suggestions.append(
                ExitReasonSuggestion(
                    issue=f"Signal exits have poor win rate ({signal_stats.win_rate_pct:.1f}%)",
                    affected_reason="signal",
                    suggestion="Add entry confirmation filter or improve exit signal logic",
                    expected_improvement="Better entry quality and exit timing",
                    confidence=0.65,
                )
            )

        # Pattern 4: Trailing stop underperformance
        trailing_stats = analysis.reason_stats.get("trailing_stop")
        if trailing_stats:
            if trailing_stats.avg_profit_pct < 0:
                suggestions.append(
                    ExitReasonSuggestion(
                        issue="Trailing stop exits are losing money on average",
                        affected_reason="trailing_stop",
                        suggestion="Adjust trailing stop distance or activation threshold",
                        expected_improvement="Better profit protection without premature exits",
                        confidence=0.6,
                    )
                )

        # Pattern 5: Force exits indicating problems
        force_stats = analysis.reason_stats.get("force_exit")
        emergency_stats = analysis.reason_stats.get("emergency_exit")
        total_forced = (force_stats.count if force_stats else 0) + (
            emergency_stats.count if emergency_stats else 0
        )
        if total_forced > 0:
            forced_pct = (total_forced / analysis.total_trades * 100) if analysis.total_trades else 0
            if forced_pct > 5.0:
                suggestions.append(
                    ExitReasonSuggestion(
                        issue=f"High rate of forced/emergency exits ({forced_pct:.1f}%)",
                        affected_reason="force_exit",
                        suggestion="Reduce position size or add volatility filter",
                        expected_improvement="Fewer forced liquidations and better risk control",
                        confidence=0.7,
                    )
                )

        # Pattern 6: Exit timing mismatch (winners exit too fast, losers too slow)
        if roi_stats and stoploss_stats:
            roi_avg_duration = roi_stats.avg_duration_min
            stoploss_avg_duration = stoploss_stats.avg_duration_min

            if roi_avg_duration > 0 and stoploss_avg_duration > roi_avg_duration * 1.5:
                suggestions.append(
                    ExitReasonSuggestion(
                        issue="Losers (stoploss) last much longer than winners (ROI)",
                        affected_reason="timing_mismatch",
                        suggestion="Implement asymmetric exit rules or time-based stop",
                        expected_improvement="Faster exit from losing trades",
                        confidence=0.6,
                    )
                )

        # Pattern 7: Unknown/unexpected exit reasons
        known_reasons = {"roi", "stoploss", "trailing_stop", "signal", "force_exit", "emergency_exit"}
        for reason in analysis.reason_stats:
            if reason not in known_reasons and reason != "unknown":
                stats = analysis.reason_stats[reason]
                if stats.frequency_pct > 5.0:
                    suggestions.append(
                        ExitReasonSuggestion(
                            issue=f"Unusual exit reason '{reason}' accounts for {stats.frequency_pct:.1f}% of trades",
                            affected_reason=reason,
                            suggestion="Review strategy logic for unexpected exit conditions",
                            expected_improvement="More predictable and controlled exits",
                            confidence=0.5,
                        )
                    )

        return suggestions

    @staticmethod
    def get_exit_reason_summary(analysis: ExitReasonAnalysis) -> str:
        """Generate a human-readable summary of exit reason analysis.

        Args:
            analysis: ExitReasonAnalysis to summarize.

        Returns:
            Human-readable summary string.
        """
        if analysis.total_trades == 0:
            return "No trades to analyze."

        lines = [
            f"Exit Analysis: {analysis.total_trades} trades",
            f"Dominant: {analysis.dominant_reason} ({analysis.reason_stats.get(analysis.dominant_reason, ExitReasonStats('')).frequency_pct:.1f}%)",
        ]

        if analysis.has_high_stoploss_rate:
            lines.append("⚠ High stoploss rate detected")

        if analysis.has_roi_dominance:
            lines.append("⚠ ROI exits dominate but underperform")

        if analysis.suggestions:
            lines.append(f"Suggestions: {len(analysis.suggestions)}")

        return " | ".join(lines)
