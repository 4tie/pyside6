"""
results_diagnosis_service.py — Stateless rule-based diagnosis of backtest results.

Accepts a DiagnosisInput bundle and returns a DiagnosisBundle containing:
  - issues: legacy shallow DiagnosedIssue objects (eight rules)
  - structural: pattern-based StructuralDiagnosis objects (ten rules)
  - exit_reason_suggestions: suggestions from exit reason analysis
"""
from __future__ import annotations

from typing import List, Optional

from app.core.backtests.results_models import BacktestSummary
from app.core.models.diagnosis_models import DiagnosisBundle, DiagnosisInput, StructuralDiagnosis
from app.core.models.exit_reason_models import ExitReasonSuggestion
from app.core.models.improve_models import DiagnosedIssue
from app.core.utils.app_logger import get_logger

_log = get_logger("services.results_diagnosis")

# ---------------------------------------------------------------------------
# Threshold constants for legacy shallow rules
# ---------------------------------------------------------------------------
STOPLOSS_TOO_WIDE: float = 20.0
TRADES_TOO_LOW: int = 30
WEAK_WIN_RATE: float = 45.0
DRAWDOWN_HIGH: float = 30.0
POOR_PAIR_CONCENTRATION: int = 3
PROFIT_FACTOR_LOW: float = 1.0
EXPECTANCY_NEGATIVE: float = 0.0

# ---------------------------------------------------------------------------
# Minimum confidence thresholds by severity
# ---------------------------------------------------------------------------
_MIN_CONFIDENCE_CRITICAL: float = 0.6
_MIN_CONFIDENCE_MODERATE: float = 0.5
_MIN_CONFIDENCE_ADVISORY: float = 0.4


class ResultsDiagnosisService:
    """Stateless service that evaluates rule-based heuristics on a DiagnosisInput.

    All methods are static — no instance state is required.
    """

    @staticmethod
    def diagnose(input: DiagnosisInput) -> DiagnosisBundle:
        """Evaluate all diagnosis rules against a DiagnosisInput bundle.

        Args:
            input: DiagnosisInput containing in_sample summary and optional
                supplementary data (OOS summary, fold summaries, trade
                contributions, drawdown periods, ATR spike periods, exit_reason_analysis).

        Returns:
            DiagnosisBundle with:
              - issues: legacy DiagnosedIssue objects from eight shallow rules.
              - structural: StructuralDiagnosis objects from ten pattern rules.
              - exit_reason_suggestions: suggestions from exit reason analysis.
            All lists may be empty. None are ever None.
        """
        summary = input.in_sample
        issues = ResultsDiagnosisService._run_shallow_rules(summary)
        structural = ResultsDiagnosisService._run_structural_rules(input)
        exit_reason_suggestions = ResultsDiagnosisService._run_exit_reason_rules(input)

        _log.debug(
            "Diagnosed %d issue(s), %d structural pattern(s), %d exit suggestions for strategy '%s'",
            len(issues),
            len(structural),
            len(exit_reason_suggestions),
            summary.strategy,
        )
        return DiagnosisBundle(
            issues=issues,
            structural=structural,
            exit_reason_suggestions=exit_reason_suggestions,
        )

    # ------------------------------------------------------------------
    # Legacy shallow rules (eight rules)
    # ------------------------------------------------------------------

    @staticmethod
    def _run_shallow_rules(summary: BacktestSummary) -> List[DiagnosedIssue]:
        """Evaluate the eight legacy shallow rules against a BacktestSummary."""
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

        if 0.0 < summary.profit_factor < PROFIT_FACTOR_LOW:
            issues.append(DiagnosedIssue(
                issue_id="profit_factor_low",
                description=(
                    f"Profit factor {summary.profit_factor:.2f} is below 1.0 — "
                    "losses exceed gains over the backtest period."
                ),
            ))

        if summary.expectancy < EXPECTANCY_NEGATIVE:
            issues.append(DiagnosedIssue(
                issue_id="expectancy_negative",
                description=(
                    f"Expectancy {summary.expectancy:.4f} is negative — "
                    "the average trade loses money."
                ),
            ))

        return issues

    # ------------------------------------------------------------------
    # Structural pattern rules (ten rules)
    # ------------------------------------------------------------------

    @staticmethod
    def _run_structural_rules(input: DiagnosisInput) -> List[StructuralDiagnosis]:
        """Evaluate the ten structural pattern rules against a DiagnosisInput."""
        structural: List[StructuralDiagnosis] = []
        s = input.in_sample

        # Derived metrics
        avg_profit_per_trade = (
            s.total_profit / s.total_trades if s.total_trades > 0 else 0.0
        )
        # Approximate avg_win and avg_loss from win_rate and profit_factor
        # avg_win / avg_loss ≈ profit_factor * (1 - win_rate/100) / (win_rate/100)
        win_rate_frac = s.win_rate / 100.0 if s.win_rate else 0.0
        loss_rate_frac = 1.0 - win_rate_frac

        # ------------------------------------------------------------------
        # Rule 1: entries_too_loose_in_chop (critical)
        # Detection: high trade count, win_rate < 45%, avg_loss < 0.5%,
        #            avg_trade_duration short
        # ------------------------------------------------------------------
        if (
            s.total_trades > 100
            and s.win_rate < 45.0
            and s.trade_duration_avg < 120  # < 2 hours in minutes
        ):
            confidence = 0.7
            if confidence >= _MIN_CONFIDENCE_CRITICAL:
                structural.append(StructuralDiagnosis(
                    failure_pattern="entries_too_loose_in_chop",
                    evidence=(
                        f"{s.total_trades} trades, win_rate={s.win_rate:.1f}%, "
                        f"avg_duration={s.trade_duration_avg}min"
                    ),
                    root_cause="Entries fire in sideways/choppy conditions",
                    mutation_direction=(
                        "Tighten entry confirmation, add trend filter or "
                        "volatility regime filter"
                    ),
                    confidence=confidence,
                    severity="critical",
                ))

        # ------------------------------------------------------------------
        # Rule 2: entries_too_late_in_trend (moderate)
        # Detection: low trade count, high win rate but low total profit,
        #            avg_trade_duration long
        # ------------------------------------------------------------------
        if (
            s.total_trades < 30
            and s.win_rate > 55.0
            and s.total_profit < 5.0
            and s.trade_duration_avg > 480  # > 8 hours
        ):
            confidence = 0.6
            if confidence >= _MIN_CONFIDENCE_MODERATE:
                structural.append(StructuralDiagnosis(
                    failure_pattern="entries_too_late_in_trend",
                    evidence=(
                        f"{s.total_trades} trades, win_rate={s.win_rate:.1f}%, "
                        f"profit={s.total_profit:.2f}%, "
                        f"avg_duration={s.trade_duration_avg}min"
                    ),
                    root_cause=(
                        "Entries trigger after most of the move has occurred"
                    ),
                    mutation_direction=(
                        "Use earlier signal (lower timeframe confirmation, "
                        "reduce lag on indicator)"
                    ),
                    confidence=confidence,
                    severity="moderate",
                ))

        # ------------------------------------------------------------------
        # Rule 3: exits_cutting_winners_early (moderate)
        # Detection: win_rate > 60% but profit_factor < 1.3
        # ------------------------------------------------------------------
        if (
            s.win_rate > 60.0
            and 0.0 < s.profit_factor < 1.3
        ):
            confidence = 0.65
            if confidence >= _MIN_CONFIDENCE_MODERATE:
                structural.append(StructuralDiagnosis(
                    failure_pattern="exits_cutting_winners_early",
                    evidence=(
                        f"win_rate={s.win_rate:.1f}%, "
                        f"profit_factor={s.profit_factor:.2f}"
                    ),
                    root_cause=(
                        "ROI table or trailing stop exits too early"
                    ),
                    mutation_direction=(
                        "Widen ROI targets or increase trailing stop distance"
                    ),
                    confidence=confidence,
                    severity="moderate",
                ))

        # ------------------------------------------------------------------
        # Rule 4: losers_lasting_too_long (moderate)
        # Detection: low win rate, avg_trade_duration long (proxy for losers
        #            lasting longer than winners)
        # ------------------------------------------------------------------
        if (
            s.win_rate < 45.0
            and s.trade_duration_avg > 360  # > 6 hours
            and s.total_trades >= 20
        ):
            confidence = 0.6
            if confidence >= _MIN_CONFIDENCE_MODERATE:
                structural.append(StructuralDiagnosis(
                    failure_pattern="losers_lasting_too_long",
                    evidence=(
                        f"win_rate={s.win_rate:.1f}%, "
                        f"avg_duration={s.trade_duration_avg}min, "
                        f"trades={s.total_trades}"
                    ),
                    root_cause="Stoploss too wide or not triggered",
                    mutation_direction=(
                        "Tighten stoploss or add time-based exit"
                    ),
                    confidence=confidence,
                    severity="moderate",
                ))

        # ------------------------------------------------------------------
        # Rule 5: single_regime_dependency (critical)
        # Detection: in-sample profit > target, OOS profit < 0 or < 50% of in-sample
        # Requires: input.oos_summary — suppressed if None
        # ------------------------------------------------------------------
        if input.oos_summary is not None:
            oos = input.oos_summary
            if (
                s.total_profit > 5.0
                and (oos.total_profit < 0 or oos.total_profit < 0.5 * s.total_profit)
            ):
                confidence = 0.75
                if confidence >= _MIN_CONFIDENCE_CRITICAL:
                    structural.append(StructuralDiagnosis(
                        failure_pattern="single_regime_dependency",
                        evidence=(
                            f"in_sample_profit={s.total_profit:.2f}%, "
                            f"oos_profit={oos.total_profit:.2f}%"
                        ),
                        root_cause=(
                            "Strategy tuned to one market regime"
                        ),
                        mutation_direction=(
                            "Add regime detection, reduce lookback, or test "
                            "on more diverse data"
                        ),
                        confidence=confidence,
                        severity="critical",
                    ))

        # ------------------------------------------------------------------
        # Rule 6: micro_loss_noise (moderate)
        # Detection: > 60% of trades have loss < 0.2%, high trade count
        # We approximate using avg_profit and trade count
        # ------------------------------------------------------------------
        if (
            s.total_trades > 80
            and s.win_rate < 40.0
            and abs(avg_profit_per_trade) < 0.2
        ):
            confidence = 0.55
            if confidence >= _MIN_CONFIDENCE_MODERATE:
                structural.append(StructuralDiagnosis(
                    failure_pattern="micro_loss_noise",
                    evidence=(
                        f"{s.total_trades} trades, win_rate={s.win_rate:.1f}%, "
                        f"avg_profit_per_trade={avg_profit_per_trade:.4f}%"
                    ),
                    root_cause="Strategy enters on noise signals",
                    mutation_direction=(
                        "Add minimum move filter or increase minimum signal strength"
                    ),
                    confidence=confidence,
                    severity="moderate",
                ))

        # ------------------------------------------------------------------
        # Rule 7: filter_stack_too_strict (advisory)
        # Detection: < 0.5 trades per day on a 6-month+ backtest
        # We approximate: if total_trades < 90 (0.5/day * 180 days)
        # ------------------------------------------------------------------
        if s.total_trades < 90 and s.total_trades > 0:
            # Only fire if trade count is very low relative to a 6-month period
            if s.total_trades < 45:  # < 0.25 trades/day over 6 months
                confidence = 0.5
                if confidence >= _MIN_CONFIDENCE_ADVISORY:
                    structural.append(StructuralDiagnosis(
                        failure_pattern="filter_stack_too_strict",
                        evidence=(
                            f"Only {s.total_trades} trades — "
                            "very low signal frequency"
                        ),
                        root_cause="Too many entry conditions stacked",
                        mutation_direction=(
                            "Relax threshold parameters (e.g., widen RSI range, "
                            "reduce confirmation multiplier, increase lookback tolerance)"
                        ),
                        confidence=confidence,
                        severity="advisory",
                    ))

        # ------------------------------------------------------------------
        # Rule 8: high_winrate_bad_payoff (moderate)
        # Detection: win_rate > 65% but profit_factor < 1.2
        # ------------------------------------------------------------------
        if (
            s.win_rate > 65.0
            and 0.0 < s.profit_factor < 1.2
        ):
            confidence = 0.7
            if confidence >= _MIN_CONFIDENCE_MODERATE:
                structural.append(StructuralDiagnosis(
                    failure_pattern="high_winrate_bad_payoff",
                    evidence=(
                        f"win_rate={s.win_rate:.1f}%, "
                        f"profit_factor={s.profit_factor:.2f}"
                    ),
                    root_cause=(
                        "Asymmetric risk/reward — taking small wins and large losses"
                    ),
                    mutation_direction=(
                        "Widen profit targets, tighten stoploss, or invert "
                        "risk/reward ratio"
                    ),
                    confidence=confidence,
                    severity="moderate",
                ))

        # ------------------------------------------------------------------
        # Rule 9: outlier_trade_dependency (moderate)
        # Detection: top 3 trades > 40% of total profit
        # Requires: input.trade_profit_contributions — suppressed if None
        # ------------------------------------------------------------------
        if input.trade_profit_contributions is not None:
            contributions = input.trade_profit_contributions
            if len(contributions) >= 3 and sum(contributions) > 0:
                top3_share = sum(sorted(contributions, reverse=True)[:3])
                if top3_share > 0.40:
                    confidence = 0.65
                    if confidence >= _MIN_CONFIDENCE_MODERATE:
                        structural.append(StructuralDiagnosis(
                            failure_pattern="outlier_trade_dependency",
                            evidence=(
                                f"Top 3 trades contribute "
                                f"{top3_share * 100:.1f}% of total profit"
                            ),
                            root_cause=(
                                "Strategy relies on rare large moves"
                            ),
                            mutation_direction=(
                                "Reduce position sizing on outlier conditions "
                                "or add diversification"
                            ),
                            confidence=confidence,
                            severity="moderate",
                        ))

        # ------------------------------------------------------------------
        # Rule 10: drawdown_after_volatility (advisory)
        # Detection: largest drawdown periods overlap with ATR spikes
        # Requires: input.drawdown_periods AND input.atr_spike_periods
        # ------------------------------------------------------------------
        if (
            input.drawdown_periods is not None
            and input.atr_spike_periods is not None
            and len(input.drawdown_periods) > 0
            and len(input.atr_spike_periods) > 0
        ):
            # Simple heuristic: if there are both drawdown periods and ATR spikes,
            # flag the pattern (full overlap detection would require date parsing)
            confidence = 0.5
            if confidence >= _MIN_CONFIDENCE_ADVISORY:
                structural.append(StructuralDiagnosis(
                    failure_pattern="drawdown_after_volatility",
                    evidence=(
                        f"{len(input.drawdown_periods)} drawdown period(s) detected "
                        f"alongside {len(input.atr_spike_periods)} ATR spike period(s)"
                    ),
                    root_cause=(
                        "Strategy not adapted to volatility expansion"
                    ),
                    mutation_direction=(
                        "Add volatility filter or reduce position size during "
                        "high-ATR periods"
                    ),
                    confidence=confidence,
                    severity="advisory",
                ))

        # ------------------------------------------------------------------
        # Rule 11: stoploss_during_volatility_expansion (moderate)
        # Detection: High stoploss rate with increased trade duration
        # ------------------------------------------------------------------
        stoploss_stats_from_exit = (
            input.exit_reason_analysis.reason_stats.get("stoploss")
            if input.exit_reason_analysis
            else None
        )
        if (
            stoploss_stats_from_exit
            and stoploss_stats_from_exit.frequency_pct > 30.0
            and s.trade_duration_avg > 240  # > 4 hours
            and s.max_drawdown > 15.0
        ):
            confidence = 0.6
            if confidence >= _MIN_CONFIDENCE_MODERATE:
                structural.append(StructuralDiagnosis(
                    failure_pattern="stoploss_during_volatility_expansion",
                    evidence=(
                        f"stoploss_rate={stoploss_stats_from_exit.frequency_pct:.1f}%, "
                        f"avg_duration={s.trade_duration_avg}min, "
                        f"drawdown={s.max_drawdown:.1f}%"
                    ),
                    root_cause="Stoploss being hit during volatility spikes",
                    mutation_direction=(
                        "Widen stoploss during high ATR periods or add volatility filter"
                    ),
                    confidence=confidence,
                    severity="moderate",
                ))

        # ------------------------------------------------------------------
        # Rule 12: roi_cutting_trend_continuation (moderate)
        # Detection: High ROI exit rate but low profit factor with long winners
        # ------------------------------------------------------------------
        roi_stats_from_exit = (
            input.exit_reason_analysis.reason_stats.get("roi")
            if input.exit_reason_analysis
            else None
        )
        if (
            roi_stats_from_exit
            and roi_stats_from_exit.frequency_pct > 40.0
            and 0.0 < s.profit_factor < 1.3
            and roi_stats_from_exit.avg_duration_min > 180  # > 3 hours
        ):
            confidence = 0.65
            if confidence >= _MIN_CONFIDENCE_MODERATE:
                structural.append(StructuralDiagnosis(
                    failure_pattern="roi_cutting_trend_continuation",
                    evidence=(
                        f"roi_rate={roi_stats_from_exit.frequency_pct:.1f}%, "
                        f"profit_factor={s.profit_factor:.2f}, "
                        f"roi_duration={roi_stats_from_exit.avg_duration_min:.0f}min"
                    ),
                    root_cause="ROI targets too conservative, cutting winners early",
                    mutation_direction=(
                        "Widen ROI targets or implement trailing stop for trend continuation"
                    ),
                    confidence=confidence,
                    severity="moderate",
                ))

        # ------------------------------------------------------------------
        # Rule 13: signal_exit_timing_mismatch (moderate)
        # Detection: Signal exits have poor win rate vs other exit reasons
        # ------------------------------------------------------------------
        signal_stats_from_exit = (
            input.exit_reason_analysis.reason_stats.get("signal")
            if input.exit_reason_analysis
            else None
        )
        if (
            signal_stats_from_exit
            and signal_stats_from_exit.win_rate_pct < 35.0
            and signal_stats_from_exit.frequency_pct > 20.0
        ):
            confidence = 0.6
            if confidence >= _MIN_CONFIDENCE_MODERATE:
                structural.append(StructuralDiagnosis(
                    failure_pattern="signal_exit_timing_mismatch",
                    evidence=(
                        f"signal_win_rate={signal_stats_from_exit.win_rate_pct:.1f}%, "
                        f"signal_rate={signal_stats_from_exit.frequency_pct:.1f}%"
                    ),
                    root_cause="Exit signals firing too early or on weak momentum",
                    mutation_direction=(
                        "Add confirmation to exit signals or delay exit until momentum weakens"
                    ),
                    confidence=confidence,
                    severity="moderate",
                ))

        # ------------------------------------------------------------------
        # Rule 14: trailing_stop_underperformance (advisory)
        # Detection: Trailing stop exits with negative returns despite being enabled
        # ------------------------------------------------------------------
        trailing_stats_from_exit = (
            input.exit_reason_analysis.reason_stats.get("trailing_stop")
            if input.exit_reason_analysis
            else None
        )
        if (
            trailing_stats_from_exit
            and trailing_stats_from_exit.total_profit_pct < 0
            and trailing_stats_from_exit.count > 5
        ):
            confidence = 0.55
            if confidence >= _MIN_CONFIDENCE_ADVISORY:
                structural.append(StructuralDiagnosis(
                    failure_pattern="trailing_stop_underperformance",
                    evidence=(
                        f"trailing_profit={trailing_stats_from_exit.total_profit_pct:.2f}%, "
                        f"trailing_count={trailing_stats_from_exit.count}"
                    ),
                    root_cause="Trailing stop parameters not optimal for current volatility",
                    mutation_direction=(
                        "Adjust trailing distance or use dynamic trailing based on ATR"
                    ),
                    confidence=confidence,
                    severity="advisory",
                ))

        return structural

    # ------------------------------------------------------------------
    # Exit reason rules (six rules)
    # ------------------------------------------------------------------

    @staticmethod
    def _run_exit_reason_rules(input: DiagnosisInput) -> list:
        """Generate suggestions from exit reason analysis.

        Args:
            input: DiagnosisInput containing optional exit_reason_analysis.

        Returns:
            List of ExitReasonSuggestion objects. May be empty.
        """
        if input.exit_reason_analysis is None:
            return []

        analysis = input.exit_reason_analysis
        suggestions = []

        # Pattern 1: High stoploss rate with negative returns
        stoploss_stats = analysis.reason_stats.get("stoploss")
        if stoploss_stats and stoploss_stats.frequency_pct > 40.0:
            if stoploss_stats.total_profit_pct < 0:
                suggestions.append(ExitReasonSuggestion(
                    issue=f"High stoploss rate ({stoploss_stats.frequency_pct:.1f}%) with negative returns",
                    affected_reason="stoploss",
                    suggestion="Tighten stoploss to reduce per-trade loss exposure",
                    expected_improvement="Lower drawdown and smaller individual losses",
                    confidence=0.75,
                ))

        # Pattern 2: ROI dominance with low win rate
        roi_stats = analysis.reason_stats.get("roi")
        if roi_stats and roi_stats.frequency_pct > 50.0:
            if roi_stats.win_rate_pct < 45.0:
                suggestions.append(ExitReasonSuggestion(
                    issue=f"ROI exits dominate ({roi_stats.frequency_pct:.1f}%) but with low win rate",
                    affected_reason="roi",
                    suggestion="Tighten ROI targets or review entry timing",
                    expected_improvement="Higher win rate with more achievable targets",
                    confidence=0.6,
                ))

        # Pattern 3: Signal exits with poor performance
        signal_stats = analysis.reason_stats.get("signal")
        if signal_stats and signal_stats.win_rate_pct < 40.0:
            suggestions.append(ExitReasonSuggestion(
                issue=f"Signal exits have poor win rate ({signal_stats.win_rate_pct:.1f}%)",
                affected_reason="signal",
                suggestion="Add entry confirmation filter or improve exit signal logic",
                expected_improvement="Better entry quality and exit timing",
                confidence=0.65,
            ))

        # Pattern 4: Trailing stop underperformance
        trailing_stats = analysis.reason_stats.get("trailing_stop")
        if trailing_stats and trailing_stats.avg_profit_pct < 0:
            suggestions.append(ExitReasonSuggestion(
                issue="Trailing stop exits are losing money on average",
                affected_reason="trailing_stop",
                suggestion="Adjust trailing stop distance or activation threshold",
                expected_improvement="Better profit protection without premature exits",
                confidence=0.6,
            ))

        # Pattern 5: High forced/emergency exit rate
        force_stats = analysis.reason_stats.get("force_exit")
        emergency_stats = analysis.reason_stats.get("emergency_exit")
        total_forced = (force_stats.count if force_stats else 0) + (
            emergency_stats.count if emergency_stats else 0
        )
        if total_forced > 0 and analysis.total_trades > 0:
            forced_pct = (total_forced / analysis.total_trades * 100)
            if forced_pct > 5.0:
                suggestions.append(ExitReasonSuggestion(
                    issue=f"High rate of forced/emergency exits ({forced_pct:.1f}%)",
                    affected_reason="force_exit",
                    suggestion="Reduce position size or add volatility filter",
                    expected_improvement="Fewer forced liquidations and better risk control",
                    confidence=0.7,
                ))

        # Pattern 6: Exit timing mismatch
        if roi_stats and stoploss_stats:
            if stoploss_stats.avg_duration_min > roi_stats.avg_duration_min * 1.5:
                suggestions.append(ExitReasonSuggestion(
                    issue="Losers (stoploss) last much longer than winners (ROI)",
                    affected_reason="timing_mismatch",
                    suggestion="Implement asymmetric exit rules or time-based stop",
                    expected_improvement="Faster exit from losing trades",
                    confidence=0.6,
                ))

        return suggestions
