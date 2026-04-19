"""
Tests for ResultsDiagnosisService.diagnose() with the new DiagnosisInput/DiagnosisBundle API.

Covers:
  - Legacy shallow rules (eight rules) via DiagnosisInput
  - Structural pattern rules (ten rules)
  - Optional field suppression
  - DiagnosisBundle structure
"""
from __future__ import annotations

from typing import List, Optional

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.backtests.results_models import BacktestSummary
from app.core.models.diagnosis_models import DiagnosisInput
from app.core.services.results_diagnosis_service import ResultsDiagnosisService

# ---------------------------------------------------------------------------
# Shared field strategies
# ---------------------------------------------------------------------------
_float_st = st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False)
_int_st = st.integers(min_value=0, max_value=1000)
_str_st = st.text(min_size=1, max_size=20)
_pairlist_st = st.lists(st.text(min_size=1, max_size=10), min_size=0, max_size=10)
_opt_float_st = st.one_of(st.none(), _float_st)


def _summary_strategy():
    """Return a hypothesis strategy that builds arbitrary BacktestSummary instances."""
    return st.builds(
        BacktestSummary,
        strategy=_str_st,
        timeframe=_str_st,
        total_trades=_int_st,
        wins=_int_st,
        losses=_int_st,
        draws=_int_st,
        win_rate=_float_st,
        avg_profit=_float_st,
        total_profit=_float_st,
        total_profit_abs=_float_st,
        sharpe_ratio=_opt_float_st,
        sortino_ratio=_opt_float_st,
        calmar_ratio=_opt_float_st,
        max_drawdown=_float_st,
        max_drawdown_abs=_float_st,
        trade_duration_avg=_int_st,
        starting_balance=_float_st,
        final_balance=_float_st,
        timerange=_str_st,
        pairlist=_pairlist_st,
        backtest_start=_str_st,
        backtest_end=_str_st,
        expectancy=_float_st,
        profit_factor=_float_st,
        max_consecutive_wins=_int_st,
        max_consecutive_losses=_int_st,
    )


def _make_summary(
    total_profit: float = 10.0,
    win_rate: float = 55.0,
    max_drawdown: float = 15.0,
    total_trades: int = 50,
    profit_factor: float = 1.5,
    expectancy: float = 0.5,
    trade_duration_avg: int = 60,
    pairlist: Optional[List[str]] = None,
) -> BacktestSummary:
    if pairlist is None:
        pairlist = ["BTC/USDT", "ETH/USDT", "BNB/USDT"]
    return BacktestSummary(
        strategy="TestStrategy",
        timeframe="1h",
        total_trades=total_trades,
        wins=int(total_trades * win_rate / 100),
        losses=total_trades - int(total_trades * win_rate / 100),
        draws=0,
        win_rate=win_rate,
        avg_profit=total_profit / max(total_trades, 1),
        total_profit=total_profit,
        total_profit_abs=total_profit * 10,
        sharpe_ratio=1.0,
        sortino_ratio=None,
        calmar_ratio=None,
        max_drawdown=max_drawdown,
        max_drawdown_abs=max_drawdown * 10,
        trade_duration_avg=trade_duration_avg,
        profit_factor=profit_factor,
        expectancy=expectancy,
        pairlist=pairlist,
    )


# ---------------------------------------------------------------------------
# Property test: legacy shallow rules still work via DiagnosisInput
# ---------------------------------------------------------------------------

@given(summary=_summary_strategy())
@settings(max_examples=200)
def test_diagnosis_threshold_rules_exhaustive_and_correct(summary: BacktestSummary):
    """Legacy shallow rules fire correctly when called via DiagnosisInput.

    Validates: Requirements 4.1–4.7 (backward compatibility)
    """
    bundle = ResultsDiagnosisService.diagnose(DiagnosisInput(in_sample=summary))
    issue_ids = {issue.issue_id for issue in bundle.issues}

    # stoploss_too_wide: max_drawdown > 20.0
    if summary.max_drawdown > 20.0:
        assert "stoploss_too_wide" in issue_ids
    else:
        assert "stoploss_too_wide" not in issue_ids

    # trades_too_low: total_trades < 30
    if summary.total_trades < 30:
        assert "trades_too_low" in issue_ids
    else:
        assert "trades_too_low" not in issue_ids

    # weak_win_rate: win_rate < 45.0
    if summary.win_rate < 45.0:
        assert "weak_win_rate" in issue_ids
    else:
        assert "weak_win_rate" not in issue_ids

    # drawdown_high: max_drawdown > 30.0
    if summary.max_drawdown > 30.0:
        assert "drawdown_high" in issue_ids
    else:
        assert "drawdown_high" not in issue_ids

    # poor_pair_concentration: len(pairlist) < 3
    if len(summary.pairlist) < 3:
        assert "poor_pair_concentration" in issue_ids
    else:
        assert "poor_pair_concentration" not in issue_ids

    # negative_profit: total_profit < 0.0
    if summary.total_profit < 0.0:
        assert "negative_profit" in issue_ids
    else:
        assert "negative_profit" not in issue_ids


# ---------------------------------------------------------------------------
# Unit tests: DiagnosisBundle structure
# ---------------------------------------------------------------------------

class TestDiagnosisBundleStructure:
    """Tests that DiagnosisBundle is always well-formed."""

    def test_bundle_issues_is_list(self) -> None:
        """bundle.issues is always a list, never None."""
        summary = _make_summary()
        bundle = ResultsDiagnosisService.diagnose(DiagnosisInput(in_sample=summary))
        assert isinstance(bundle.issues, list)

    def test_bundle_structural_is_list(self) -> None:
        """bundle.structural is always a list, never None."""
        summary = _make_summary()
        bundle = ResultsDiagnosisService.diagnose(DiagnosisInput(in_sample=summary))
        assert isinstance(bundle.structural, list)

    def test_legacy_issues_present_for_shallow_rules(self) -> None:
        """bundle.issues contains DiagnosedIssue objects for shallow rules."""
        summary = _make_summary(
            total_profit=-5.0,  # triggers negative_profit
            total_trades=10,    # triggers trades_too_low
        )
        bundle = ResultsDiagnosisService.diagnose(DiagnosisInput(in_sample=summary))
        issue_ids = {i.issue_id for i in bundle.issues}
        assert "negative_profit" in issue_ids
        assert "trades_too_low" in issue_ids


# ---------------------------------------------------------------------------
# Unit tests: structural pattern rules
# ---------------------------------------------------------------------------

class TestStructuralPatternRules:
    """Unit tests for the ten structural diagnosis rules."""

    def test_entries_too_loose_in_chop_fires(self) -> None:
        """entries_too_loose_in_chop fires when high trades, low win rate, short duration."""
        summary = _make_summary(
            total_trades=150,
            win_rate=38.0,
            trade_duration_avg=60,  # < 120 min
        )
        bundle = ResultsDiagnosisService.diagnose(DiagnosisInput(in_sample=summary))
        patterns = {s.failure_pattern for s in bundle.structural}
        assert "entries_too_loose_in_chop" in patterns

    def test_entries_too_loose_in_chop_suppressed_when_high_winrate(self) -> None:
        """entries_too_loose_in_chop does not fire when win rate is high."""
        summary = _make_summary(
            total_trades=150,
            win_rate=60.0,  # high win rate
            trade_duration_avg=60,
        )
        bundle = ResultsDiagnosisService.diagnose(DiagnosisInput(in_sample=summary))
        patterns = {s.failure_pattern for s in bundle.structural}
        assert "entries_too_loose_in_chop" not in patterns

    def test_exits_cutting_winners_early_fires(self) -> None:
        """exits_cutting_winners_early fires when win_rate > 60% but profit_factor < 1.3."""
        summary = _make_summary(
            win_rate=65.0,
            profit_factor=1.1,
        )
        bundle = ResultsDiagnosisService.diagnose(DiagnosisInput(in_sample=summary))
        patterns = {s.failure_pattern for s in bundle.structural}
        assert "exits_cutting_winners_early" in patterns

    def test_exits_cutting_winners_early_suppressed_when_good_pf(self) -> None:
        """exits_cutting_winners_early does not fire when profit_factor >= 1.3."""
        summary = _make_summary(
            win_rate=65.0,
            profit_factor=1.5,
        )
        bundle = ResultsDiagnosisService.diagnose(DiagnosisInput(in_sample=summary))
        patterns = {s.failure_pattern for s in bundle.structural}
        assert "exits_cutting_winners_early" not in patterns

    def test_losers_lasting_too_long_fires(self) -> None:
        """losers_lasting_too_long fires when low win rate and long duration."""
        summary = _make_summary(
            win_rate=35.0,
            trade_duration_avg=480,  # > 360 min
            total_trades=30,
        )
        bundle = ResultsDiagnosisService.diagnose(DiagnosisInput(in_sample=summary))
        patterns = {s.failure_pattern for s in bundle.structural}
        assert "losers_lasting_too_long" in patterns

    def test_single_regime_dependency_fires_with_oos_data(self) -> None:
        """single_regime_dependency fires when OOS profit is much lower than in-sample."""
        in_sample = _make_summary(total_profit=20.0)
        oos = _make_summary(total_profit=-2.0)  # OOS is negative
        bundle = ResultsDiagnosisService.diagnose(
            DiagnosisInput(in_sample=in_sample, oos_summary=oos)
        )
        patterns = {s.failure_pattern for s in bundle.structural}
        assert "single_regime_dependency" in patterns

    def test_single_regime_dependency_suppressed_when_oos_none(self) -> None:
        """single_regime_dependency is suppressed when oos_summary is None."""
        in_sample = _make_summary(total_profit=20.0)
        bundle = ResultsDiagnosisService.diagnose(
            DiagnosisInput(in_sample=in_sample, oos_summary=None)
        )
        patterns = {s.failure_pattern for s in bundle.structural}
        assert "single_regime_dependency" not in patterns

    def test_high_winrate_bad_payoff_fires(self) -> None:
        """high_winrate_bad_payoff fires when win_rate > 65% but profit_factor < 1.2."""
        summary = _make_summary(
            win_rate=70.0,
            profit_factor=1.05,
        )
        bundle = ResultsDiagnosisService.diagnose(DiagnosisInput(in_sample=summary))
        patterns = {s.failure_pattern for s in bundle.structural}
        assert "high_winrate_bad_payoff" in patterns

    def test_outlier_trade_dependency_fires_with_contributions(self) -> None:
        """outlier_trade_dependency fires when top 3 trades > 40% of total profit."""
        # Top 3 trades contribute 60% of profit
        contributions = [0.25, 0.20, 0.15, 0.10, 0.10, 0.10, 0.10]
        bundle = ResultsDiagnosisService.diagnose(
            DiagnosisInput(
                in_sample=_make_summary(),
                trade_profit_contributions=contributions,
            )
        )
        patterns = {s.failure_pattern for s in bundle.structural}
        assert "outlier_trade_dependency" in patterns

    def test_outlier_trade_dependency_suppressed_when_none(self) -> None:
        """outlier_trade_dependency is suppressed when trade_profit_contributions is None."""
        bundle = ResultsDiagnosisService.diagnose(
            DiagnosisInput(
                in_sample=_make_summary(),
                trade_profit_contributions=None,
            )
        )
        patterns = {s.failure_pattern for s in bundle.structural}
        assert "outlier_trade_dependency" not in patterns

    def test_drawdown_after_volatility_fires_with_both_fields(self) -> None:
        """drawdown_after_volatility fires when both drawdown_periods and atr_spike_periods are present."""
        bundle = ResultsDiagnosisService.diagnose(
            DiagnosisInput(
                in_sample=_make_summary(),
                drawdown_periods=[("2024-01-01", "2024-01-10", 15.0)],
                atr_spike_periods=[("2024-01-01", "2024-01-05")],
            )
        )
        patterns = {s.failure_pattern for s in bundle.structural}
        assert "drawdown_after_volatility" in patterns

    def test_drawdown_after_volatility_suppressed_when_drawdown_none(self) -> None:
        """drawdown_after_volatility is suppressed when drawdown_periods is None."""
        bundle = ResultsDiagnosisService.diagnose(
            DiagnosisInput(
                in_sample=_make_summary(),
                drawdown_periods=None,
                atr_spike_periods=[("2024-01-01", "2024-01-05")],
            )
        )
        patterns = {s.failure_pattern for s in bundle.structural}
        assert "drawdown_after_volatility" not in patterns

    def test_drawdown_after_volatility_suppressed_when_atr_none(self) -> None:
        """drawdown_after_volatility is suppressed when atr_spike_periods is None."""
        bundle = ResultsDiagnosisService.diagnose(
            DiagnosisInput(
                in_sample=_make_summary(),
                drawdown_periods=[("2024-01-01", "2024-01-10", 15.0)],
                atr_spike_periods=None,
            )
        )
        patterns = {s.failure_pattern for s in bundle.structural}
        assert "drawdown_after_volatility" not in patterns

    def test_filter_stack_too_strict_fires_for_very_low_trades(self) -> None:
        """filter_stack_too_strict fires when trade count is very low."""
        summary = _make_summary(total_trades=20)
        bundle = ResultsDiagnosisService.diagnose(DiagnosisInput(in_sample=summary))
        patterns = {s.failure_pattern for s in bundle.structural}
        assert "filter_stack_too_strict" in patterns

    def test_all_optional_fields_none_does_not_crash(self) -> None:
        """diagnose() works correctly when all optional fields are None."""
        summary = _make_summary()
        bundle = ResultsDiagnosisService.diagnose(
            DiagnosisInput(
                in_sample=summary,
                oos_summary=None,
                fold_summaries=None,
                trade_profit_contributions=None,
                drawdown_periods=None,
                atr_spike_periods=None,
            )
        )
        assert isinstance(bundle.issues, list)
        assert isinstance(bundle.structural, list)
