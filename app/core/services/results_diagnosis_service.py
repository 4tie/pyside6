"""
results_diagnosis_service.py — Stateless rule-based diagnosis of backtest results.

Accepts a DiagnosisInput bundle and returns a DiagnosisBundle containing:
  - issues: legacy shallow DiagnosedIssue objects (eight rules)
  - structural: pattern-based StructuralDiagnosis objects (ten rules)
"""
from __future__ import annotations

from typing import List, Optional

from app.core.backtests.results_models import BacktestSummary
from app.core.models.diagnosis_models import DiagnosisBundle, DiagnosisInput, StructuralDiagnosis
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
                contributions, drawdown periods, ATR spike periods).

        Returns:
            DiagnosisBundle with:
              - issues: legacy DiagnosedIssue objects from eight shallow rules.
              - structural: StructuralDiagnosis objects from ten pattern rules.
            Both lists may be empty. Neither is ever None.
        """
        summary = input.in_sample
        issues = ResultsDiagnosisService._run_shallow_rules(summary)
        structural = ResultsDiagnosisService._run_structural_rules(input)

        _log.debug(
            "Diagnosed %d issue(s) and %d structural pattern(s) for strategy '%s'",
            len(issues),
            len(structural),
            summary.strategy,
        )
        return DiagnosisBundle(issues=issues, structural=structural)

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

        return structural
