"""
Tests for HardFilterService:
  - evaluate_post_gate1 (property tests + unit tests)
  - evaluate_post_gate (unit tests)
"""
from __future__ import annotations

from typing import List, Optional

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.backtests.results_models import BacktestSummary
from app.core.models.loop_models import GateResult, LoopConfig
from app.core.services.hard_filter_service import HardFilterService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_summary(
    total_profit: float = 10.0,
    win_rate: float = 55.0,
    max_drawdown: float = 15.0,
    total_trades: int = 50,
    profit_factor: float = 1.5,
    expectancy: float = 0.5,
) -> BacktestSummary:
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
        trade_duration_avg=60,
        profit_factor=profit_factor,
        expectancy=expectancy,
    )


def _make_config(
    target_min_trades: int = 30,
    target_max_drawdown: float = 20.0,
    profit_concentration_threshold: float = 0.50,
    profit_factor_floor: float = 1.1,
    pair_dominance_threshold: float = 0.60,
    time_dominance_threshold: float = 0.40,
    validation_variance_ceiling: float = 1.0,
) -> LoopConfig:
    return LoopConfig(
        strategy="TestStrategy",
        target_min_trades=target_min_trades,
        target_max_drawdown=target_max_drawdown,
        profit_concentration_threshold=profit_concentration_threshold,
        profit_factor_floor=profit_factor_floor,
        pair_dominance_threshold=pair_dominance_threshold,
        time_dominance_threshold=time_dominance_threshold,
        validation_variance_ceiling=validation_variance_ceiling,
    )


def _make_gate1_result(summary: BacktestSummary) -> GateResult:
    return GateResult(
        gate_name="in_sample",
        passed=True,
        metrics=summary,
    )


# ---------------------------------------------------------------------------
# Property tests: evaluate_post_gate1
# ---------------------------------------------------------------------------

# Strategy for "all thresholds satisfied" summaries
_passing_summary_st = st.builds(
    _make_summary,
    total_profit=st.floats(min_value=5.0, max_value=200.0, allow_nan=False, allow_infinity=False),
    win_rate=st.floats(min_value=55.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    max_drawdown=st.floats(min_value=0.0, max_value=19.9, allow_nan=False, allow_infinity=False),
    total_trades=st.integers(min_value=30, max_value=10000),
    profit_factor=st.floats(min_value=1.1, max_value=10.0, allow_nan=False, allow_infinity=False),
    expectancy=st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
)


class TestEvaluatePostGate1Properties:
    """Property-based tests for HardFilterService.evaluate_post_gate1."""

    @given(_passing_summary_st)
    @settings(max_examples=200)
    def test_empty_list_when_all_thresholds_satisfied(
        self, summary: BacktestSummary
    ) -> None:
        """Property: returns [] when all seven filter conditions are within bounds."""
        config = _make_config(
            target_min_trades=30,
            target_max_drawdown=20.0,
            profit_factor_floor=1.1,
        )
        gate1 = _make_gate1_result(summary)
        failures = HardFilterService.evaluate_post_gate1(gate1, config)
        assert failures == [], (
            f"Expected no failures for passing summary, got: "
            f"{[f.filter_name for f in failures]}"
        )

    def test_all_failures_recorded_even_after_first(self) -> None:
        """Property: when multiple filters fail, all are present in the returned list."""
        # Make a summary that fails multiple filters simultaneously
        summary = _make_summary(
            total_trades=5,       # fails min_trade_count (< 30)
            max_drawdown=30.0,    # fails max_drawdown (> 20.0)
            profit_factor=0.8,    # fails profit_factor_floor (< 1.1)
            expectancy=-0.5,      # fails expectancy_floor (< 0.0)
        )
        config = _make_config(
            target_min_trades=30,
            target_max_drawdown=20.0,
            profit_factor_floor=1.1,
        )
        gate1 = _make_gate1_result(summary)
        failures = HardFilterService.evaluate_post_gate1(gate1, config)

        filter_names = [f.filter_name for f in failures]
        assert "min_trade_count" in filter_names
        assert "max_drawdown" in filter_names
        assert "profit_factor_floor" in filter_names
        assert "expectancy_floor" in filter_names
        assert len(failures) >= 4, f"Expected at least 4 failures, got {len(failures)}"


class TestEvaluatePostGate1Units:
    """Unit tests for HardFilterService.evaluate_post_gate1."""

    def test_min_trade_count_fails(self) -> None:
        """Returns min_trade_count failure when trades < minimum."""
        summary = _make_summary(total_trades=10)
        config = _make_config(target_min_trades=30)
        gate1 = _make_gate1_result(summary)
        failures = HardFilterService.evaluate_post_gate1(gate1, config)
        names = [f.filter_name for f in failures]
        assert "min_trade_count" in names

    def test_min_trade_count_passes(self) -> None:
        """No min_trade_count failure when trades >= minimum."""
        summary = _make_summary(total_trades=30)
        config = _make_config(target_min_trades=30)
        gate1 = _make_gate1_result(summary)
        failures = HardFilterService.evaluate_post_gate1(gate1, config)
        names = [f.filter_name for f in failures]
        assert "min_trade_count" not in names

    def test_max_drawdown_fails(self) -> None:
        """Returns max_drawdown failure when drawdown > limit."""
        summary = _make_summary(max_drawdown=25.0)
        config = _make_config(target_max_drawdown=20.0)
        gate1 = _make_gate1_result(summary)
        failures = HardFilterService.evaluate_post_gate1(gate1, config)
        names = [f.filter_name for f in failures]
        assert "max_drawdown" in names

    def test_max_drawdown_passes(self) -> None:
        """No max_drawdown failure when drawdown <= limit."""
        summary = _make_summary(max_drawdown=20.0)
        config = _make_config(target_max_drawdown=20.0)
        gate1 = _make_gate1_result(summary)
        failures = HardFilterService.evaluate_post_gate1(gate1, config)
        names = [f.filter_name for f in failures]
        assert "max_drawdown" not in names

    def test_profit_factor_floor_fails(self) -> None:
        """Returns profit_factor_floor failure when profit_factor < floor."""
        summary = _make_summary(profit_factor=0.9)
        config = _make_config(profit_factor_floor=1.1)
        gate1 = _make_gate1_result(summary)
        failures = HardFilterService.evaluate_post_gate1(gate1, config)
        names = [f.filter_name for f in failures]
        assert "profit_factor_floor" in names

    def test_profit_factor_floor_passes(self) -> None:
        """No profit_factor_floor failure when profit_factor >= floor."""
        summary = _make_summary(profit_factor=1.1)
        config = _make_config(profit_factor_floor=1.1)
        gate1 = _make_gate1_result(summary)
        failures = HardFilterService.evaluate_post_gate1(gate1, config)
        names = [f.filter_name for f in failures]
        assert "profit_factor_floor" not in names

    def test_expectancy_floor_fails(self) -> None:
        """Returns expectancy_floor failure when expectancy < 0."""
        summary = _make_summary(expectancy=-0.1)
        config = _make_config()
        gate1 = _make_gate1_result(summary)
        failures = HardFilterService.evaluate_post_gate1(gate1, config)
        names = [f.filter_name for f in failures]
        assert "expectancy_floor" in names

    def test_expectancy_floor_passes(self) -> None:
        """No expectancy_floor failure when expectancy >= 0."""
        summary = _make_summary(expectancy=0.0)
        config = _make_config()
        gate1 = _make_gate1_result(summary)
        failures = HardFilterService.evaluate_post_gate1(gate1, config)
        names = [f.filter_name for f in failures]
        assert "expectancy_floor" not in names

    def test_none_metrics_returns_empty(self) -> None:
        """Returns empty list when gate1_result.metrics is None."""
        gate1 = GateResult(gate_name="in_sample", passed=True, metrics=None)
        config = _make_config()
        failures = HardFilterService.evaluate_post_gate1(gate1, config)
        assert failures == []


# ---------------------------------------------------------------------------
# Unit tests: evaluate_post_gate
# ---------------------------------------------------------------------------

class TestEvaluatePostGate:
    """Unit tests for HardFilterService.evaluate_post_gate."""

    # ---- Filter 8: oos_negativity ----

    def test_oos_negativity_fails_when_negative_profit(self) -> None:
        """Returns oos_negativity failure when OOS profit < 0."""
        oos_summary = _make_summary(total_profit=-2.0)
        gate2 = GateResult(
            gate_name="out_of_sample",
            passed=True,
            metrics=oos_summary,
        )
        config = _make_config()
        failures = HardFilterService.evaluate_post_gate("out_of_sample", gate2, config)
        names = [f.filter_name for f in failures]
        assert "oos_negativity" in names
        assert len(failures) == 1

    def test_oos_negativity_passes_when_zero_profit(self) -> None:
        """No oos_negativity failure when OOS profit == 0."""
        oos_summary = _make_summary(total_profit=0.0)
        gate2 = GateResult(
            gate_name="out_of_sample",
            passed=True,
            metrics=oos_summary,
        )
        config = _make_config()
        failures = HardFilterService.evaluate_post_gate("out_of_sample", gate2, config)
        assert failures == []

    def test_oos_negativity_passes_when_positive_profit(self) -> None:
        """No oos_negativity failure when OOS profit > 0."""
        oos_summary = _make_summary(total_profit=5.0)
        gate2 = GateResult(
            gate_name="out_of_sample",
            passed=True,
            metrics=oos_summary,
        )
        config = _make_config()
        failures = HardFilterService.evaluate_post_gate("out_of_sample", gate2, config)
        assert failures == []

    # ---- Filter 9: validation_variance ----

    def test_validation_variance_fails_when_cv_above_ceiling(self) -> None:
        """Returns validation_variance failure when CV > ceiling."""
        # High variance folds: profits are very spread out
        fold_summaries = [
            _make_summary(total_profit=100.0),
            _make_summary(total_profit=1.0),
            _make_summary(total_profit=2.0),
            _make_summary(total_profit=1.5),
            _make_summary(total_profit=1.0),
        ]
        gate3 = GateResult(
            gate_name="walk_forward",
            passed=True,
            fold_summaries=fold_summaries,
        )
        config = _make_config(validation_variance_ceiling=1.0)
        failures = HardFilterService.evaluate_post_gate("walk_forward", gate3, config)
        names = [f.filter_name for f in failures]
        assert "validation_variance" in names

    def test_validation_variance_passes_when_cv_below_ceiling(self) -> None:
        """No validation_variance failure when CV <= ceiling."""
        # Low variance folds: profits are consistent
        fold_summaries = [
            _make_summary(total_profit=10.0),
            _make_summary(total_profit=11.0),
            _make_summary(total_profit=9.5),
            _make_summary(total_profit=10.5),
            _make_summary(total_profit=10.0),
        ]
        gate3 = GateResult(
            gate_name="walk_forward",
            passed=True,
            fold_summaries=fold_summaries,
        )
        config = _make_config(validation_variance_ceiling=1.0)
        failures = HardFilterService.evaluate_post_gate("walk_forward", gate3, config)
        assert failures == []

    def test_validation_variance_fails_when_mean_zero(self) -> None:
        """Returns validation_variance failure when mean fold profit <= 0."""
        fold_summaries = [
            _make_summary(total_profit=5.0),
            _make_summary(total_profit=-5.0),
            _make_summary(total_profit=0.0),
        ]
        gate3 = GateResult(
            gate_name="walk_forward",
            passed=True,
            fold_summaries=fold_summaries,
        )
        config = _make_config(validation_variance_ceiling=1.0)
        failures = HardFilterService.evaluate_post_gate("walk_forward", gate3, config)
        names = [f.filter_name for f in failures]
        assert "validation_variance" in names

    def test_validation_variance_fails_when_mean_negative(self) -> None:
        """Returns validation_variance failure when mean fold profit < 0."""
        fold_summaries = [
            _make_summary(total_profit=-5.0),
            _make_summary(total_profit=-3.0),
            _make_summary(total_profit=-4.0),
        ]
        gate3 = GateResult(
            gate_name="walk_forward",
            passed=True,
            fold_summaries=fold_summaries,
        )
        config = _make_config(validation_variance_ceiling=1.0)
        failures = HardFilterService.evaluate_post_gate("walk_forward", gate3, config)
        names = [f.filter_name for f in failures]
        assert "validation_variance" in names

    def test_unknown_gate_name_returns_empty(self) -> None:
        """Returns empty list for unknown gate names."""
        gate = GateResult(gate_name="stress_test", passed=True)
        config = _make_config()
        failures = HardFilterService.evaluate_post_gate("stress_test", gate, config)
        assert failures == []

    def test_oos_none_metrics_returns_empty(self) -> None:
        """Returns empty list when OOS gate_result.metrics is None."""
        gate2 = GateResult(gate_name="out_of_sample", passed=True, metrics=None)
        config = _make_config()
        failures = HardFilterService.evaluate_post_gate("out_of_sample", gate2, config)
        assert failures == []
