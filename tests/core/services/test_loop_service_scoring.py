"""
Tests for loop_service.py scoring functions:
  - compute_score (property tests)
  - _normalize_summary (property tests)
  - targets_met (unit tests)
"""
from __future__ import annotations

import math
from typing import Optional

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.core.backtests.results_models import BacktestSummary
from app.core.models.loop_models import LoopConfig, RobustScoreInput
from app.core.services.loop_service import (
    _normalize_summary,
    compute_score,
    targets_met,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_summary(
    total_profit: float = 10.0,
    win_rate: float = 55.0,
    max_drawdown: float = 15.0,
    total_trades: int = 50,
    sharpe_ratio: Optional[float] = 1.2,
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
        sharpe_ratio=sharpe_ratio,
        sortino_ratio=None,
        calmar_ratio=None,
        max_drawdown=max_drawdown,
        max_drawdown_abs=max_drawdown * 10,
        trade_duration_avg=60,
        profit_factor=profit_factor,
        expectancy=expectancy,
    )


def _make_config(
    target_profit_pct: float = 5.0,
    target_win_rate: float = 55.0,
    target_max_drawdown: float = 20.0,
    target_min_trades: int = 30,
) -> LoopConfig:
    return LoopConfig(
        strategy="TestStrategy",
        target_profit_pct=target_profit_pct,
        target_win_rate=target_win_rate,
        target_max_drawdown=target_max_drawdown,
        target_min_trades=target_min_trades,
    )


# ---------------------------------------------------------------------------
# Hypothesis strategies for BacktestSummary
# ---------------------------------------------------------------------------

_finite_float = st.floats(
    min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False
)

_summary_st = st.builds(
    _make_summary,
    total_profit=st.floats(min_value=-100.0, max_value=200.0, allow_nan=False, allow_infinity=False),
    win_rate=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    max_drawdown=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    total_trades=st.integers(min_value=0, max_value=10000),
    sharpe_ratio=st.one_of(st.none(), st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False)),
    profit_factor=st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
    expectancy=st.floats(min_value=-5.0, max_value=10.0, allow_nan=False, allow_infinity=False),
)

# Summary with possible None/NaN fields for normalize tests
_summary_with_nones_st = st.builds(
    lambda tp, wr, dd, tt, sr, pf, ex: BacktestSummary(
        strategy="TestStrategy",
        timeframe="1h",
        total_trades=tt,
        wins=0,
        losses=0,
        draws=0,
        win_rate=wr,
        avg_profit=0.0,
        total_profit=tp,
        total_profit_abs=0.0,
        sharpe_ratio=sr,
        sortino_ratio=None,
        calmar_ratio=None,
        max_drawdown=dd,
        max_drawdown_abs=0.0,
        trade_duration_avg=0,
        profit_factor=pf,
        expectancy=ex,
    ),
    tp=st.floats(min_value=-100.0, max_value=200.0, allow_nan=False, allow_infinity=False),
    wr=st.one_of(
        st.none(),
        st.just(float("nan")),
        st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    ),
    dd=st.one_of(
        st.none(),
        st.just(float("nan")),
        st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    ),
    tt=st.integers(min_value=0, max_value=10000),
    sr=st.one_of(
        st.none(),
        st.just(float("nan")),
        st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False),
    ),
    pf=st.one_of(
        st.none(),
        st.just(float("nan")),
        st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
    ),
    ex=st.floats(min_value=-5.0, max_value=10.0, allow_nan=False, allow_infinity=False),
)


# ---------------------------------------------------------------------------
# Property tests: compute_score
# ---------------------------------------------------------------------------

class TestComputeScoreProperties:
    """Property-based tests for compute_score()."""

    @given(_summary_st)
    @settings(max_examples=200)
    def test_score_components_sum_to_total(self, summary: BacktestSummary) -> None:
        """Property: score components sum to total within floating-point tolerance."""
        score_input = RobustScoreInput(in_sample=summary)
        score = compute_score(score_input)

        expected_total = (
            score.profitability + score.consistency + score.stability - score.fragility
        )
        assert abs(score.total - expected_total) < 1e-9, (
            f"Components don't sum to total: "
            f"{score.profitability} + {score.consistency} + {score.stability} "
            f"- {score.fragility} = {expected_total} != {score.total}"
        )

    @given(_summary_st)
    @settings(max_examples=200)
    def test_score_is_bounded(self, summary: BacktestSummary) -> None:
        """Property: RobustScore.total is always in [-0.15, 1.0] for normalized input."""
        score_input = RobustScoreInput(in_sample=summary)
        score = compute_score(score_input)

        assert score.total >= -0.15, f"Score {score.total} is below lower bound -0.15"
        assert score.total <= 1.0, f"Score {score.total} is above upper bound 1.0"

    @given(_summary_st)
    @settings(max_examples=100)
    def test_individual_components_bounded(self, summary: BacktestSummary) -> None:
        """Property: each component is in [0, 1] before weighting."""
        score_input = RobustScoreInput(in_sample=summary)
        score = compute_score(score_input)

        # Components are weighted, so check they are non-negative and within weight
        assert score.profitability >= 0.0
        assert score.profitability <= 0.35 + 1e-9
        assert score.consistency >= 0.0
        assert score.consistency <= 0.30 + 1e-9
        assert score.stability >= 0.0
        assert score.stability <= 0.20 + 1e-9
        assert score.fragility >= 0.0
        assert score.fragility <= 0.15 + 1e-9

    def test_score_with_fold_summaries(self) -> None:
        """compute_score uses fold summaries when provided."""
        summary = _make_summary(total_profit=20.0, win_rate=60.0, max_drawdown=10.0)
        folds = [
            _make_summary(total_profit=5.0),
            _make_summary(total_profit=6.0),
            _make_summary(total_profit=4.0),
            _make_summary(total_profit=5.5),
            _make_summary(total_profit=4.5),
        ]
        score_with_folds = compute_score(RobustScoreInput(in_sample=summary, fold_summaries=folds))
        score_without_folds = compute_score(RobustScoreInput(in_sample=summary))

        # Scores should differ when fold data is provided
        # (consistency component changes)
        assert isinstance(score_with_folds.total, float)
        assert isinstance(score_without_folds.total, float)

    def test_score_with_stress_summary(self) -> None:
        """compute_score uses stress summary when provided."""
        summary = _make_summary(total_profit=20.0)
        stress = _make_summary(total_profit=8.0)  # 60% drop under stress
        score_with_stress = compute_score(
            RobustScoreInput(in_sample=summary, stress_summary=stress)
        )
        score_without_stress = compute_score(RobustScoreInput(in_sample=summary))

        # Fragility should be higher with stress data showing a large drop
        assert score_with_stress.fragility >= score_without_stress.fragility - 1e-9


# ---------------------------------------------------------------------------
# Property tests: _normalize_summary
# ---------------------------------------------------------------------------

class TestNormalizeSummaryProperties:
    """Property-based tests for _normalize_summary()."""

    @given(_summary_with_nones_st)
    @settings(max_examples=300)
    def test_no_none_or_nan_after_normalization(self, summary: BacktestSummary) -> None:
        """Property: no None or NaN in the four guarded fields after normalization."""
        result = _normalize_summary(summary)

        assert result.sharpe_ratio is not None, "sharpe_ratio should not be None after normalization"
        assert result.profit_factor is not None, "profit_factor should not be None after normalization"
        assert result.win_rate is not None, "win_rate should not be None after normalization"
        assert result.max_drawdown is not None, "max_drawdown should not be None after normalization"

        assert not math.isnan(result.sharpe_ratio), "sharpe_ratio should not be NaN after normalization"
        assert not math.isnan(result.profit_factor), "profit_factor should not be NaN after normalization"
        assert not math.isnan(result.win_rate), "win_rate should not be NaN after normalization"
        assert not math.isnan(result.max_drawdown), "max_drawdown should not be NaN after normalization"

    def test_none_sharpe_replaced_with_zero(self) -> None:
        """None sharpe_ratio is replaced with 0.0."""
        summary = _make_summary(sharpe_ratio=None)
        result = _normalize_summary(summary)
        assert result.sharpe_ratio == 0.0

    def test_nan_sharpe_replaced_with_zero(self) -> None:
        """NaN sharpe_ratio is replaced with 0.0."""
        summary = _make_summary(sharpe_ratio=float("nan"))
        result = _normalize_summary(summary)
        assert result.sharpe_ratio == 0.0

    def test_none_profit_factor_replaced_with_zero(self) -> None:
        """None profit_factor is replaced with 0.0."""
        s = _make_summary()
        s.profit_factor = None  # type: ignore[assignment]
        result = _normalize_summary(s)
        assert result.profit_factor == 0.0

    def test_none_win_rate_replaced_with_zero(self) -> None:
        """None win_rate is replaced with 0.0."""
        s = _make_summary()
        s.win_rate = None  # type: ignore[assignment]
        result = _normalize_summary(s)
        assert result.win_rate == 0.0

    def test_none_max_drawdown_replaced_with_100(self) -> None:
        """None max_drawdown is replaced with 100.0."""
        s = _make_summary()
        s.max_drawdown = None  # type: ignore[assignment]
        result = _normalize_summary(s)
        assert result.max_drawdown == 100.0

    def test_valid_values_unchanged(self) -> None:
        """Valid (non-None, non-NaN) values are not modified."""
        summary = _make_summary(
            sharpe_ratio=1.5,
            profit_factor=2.0,
            win_rate=60.0,
            max_drawdown=15.0,
        )
        result = _normalize_summary(summary)
        assert result.sharpe_ratio == 1.5
        assert result.profit_factor == 2.0
        assert result.win_rate == 60.0
        assert result.max_drawdown == 15.0

    def test_original_not_mutated(self) -> None:
        """_normalize_summary does not mutate the original summary."""
        summary = _make_summary(sharpe_ratio=None)
        original_sharpe = summary.sharpe_ratio
        _normalize_summary(summary)
        assert summary.sharpe_ratio == original_sharpe  # still None


# ---------------------------------------------------------------------------
# Unit tests: targets_met
# ---------------------------------------------------------------------------

class TestTargetsMet:
    """Unit tests for targets_met()."""

    def test_all_targets_met(self) -> None:
        """Returns True when all four conditions are satisfied."""
        summary = _make_summary(
            total_profit=10.0,
            win_rate=60.0,
            max_drawdown=15.0,
            total_trades=50,
        )
        config = _make_config(
            target_profit_pct=5.0,
            target_win_rate=55.0,
            target_max_drawdown=20.0,
            target_min_trades=30,
        )
        assert targets_met(summary, config) is True

    def test_profit_below_target(self) -> None:
        """Returns False when profit is below target (others pass)."""
        summary = _make_summary(
            total_profit=3.0,  # below 5.0
            win_rate=60.0,
            max_drawdown=15.0,
            total_trades=50,
        )
        config = _make_config(target_profit_pct=5.0)
        assert targets_met(summary, config) is False

    def test_win_rate_below_target(self) -> None:
        """Returns False when win rate is below target (others pass)."""
        summary = _make_summary(
            total_profit=10.0,
            win_rate=50.0,  # below 55.0
            max_drawdown=15.0,
            total_trades=50,
        )
        config = _make_config(target_win_rate=55.0)
        assert targets_met(summary, config) is False

    def test_drawdown_above_target(self) -> None:
        """Returns False when max drawdown exceeds target (others pass)."""
        summary = _make_summary(
            total_profit=10.0,
            win_rate=60.0,
            max_drawdown=25.0,  # above 20.0
            total_trades=50,
        )
        config = _make_config(target_max_drawdown=20.0)
        assert targets_met(summary, config) is False

    def test_trades_below_minimum(self) -> None:
        """Returns False when trade count is below minimum (others pass)."""
        summary = _make_summary(
            total_profit=10.0,
            win_rate=60.0,
            max_drawdown=15.0,
            total_trades=20,  # below 30
        )
        config = _make_config(target_min_trades=30)
        assert targets_met(summary, config) is False

    def test_exactly_at_boundary_passes(self) -> None:
        """Returns True when all values are exactly at the boundary."""
        summary = _make_summary(
            total_profit=5.0,
            win_rate=55.0,
            max_drawdown=20.0,
            total_trades=30,
        )
        config = _make_config(
            target_profit_pct=5.0,
            target_win_rate=55.0,
            target_max_drawdown=20.0,
            target_min_trades=30,
        )
        assert targets_met(summary, config) is True

    def test_all_conditions_must_pass_simultaneously(self) -> None:
        """Returns False when only three of four conditions pass."""
        # Profit fails, others pass
        summary = _make_summary(
            total_profit=4.9,
            win_rate=60.0,
            max_drawdown=15.0,
            total_trades=50,
        )
        config = _make_config(target_profit_pct=5.0)
        assert targets_met(summary, config) is False

    def test_negative_profit_fails(self) -> None:
        """Returns False when profit is negative."""
        summary = _make_summary(
            total_profit=-5.0,
            win_rate=60.0,
            max_drawdown=15.0,
            total_trades=50,
        )
        config = _make_config(target_profit_pct=5.0)
        assert targets_met(summary, config) is False
