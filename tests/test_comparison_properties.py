"""test_comparison_properties.py — Property-based tests for ComparisonService.

Uses Hypothesis to generate random BacktestSummary pairs and verify
comparison invariants.
"""
import pytest
from hypothesis import given, strategies as st

from app.core.backtests.results_models import BacktestSummary
from app.core.services.comparison_service import ComparisonService


@st.composite
def backtest_summary_strategy(draw) -> BacktestSummary:
    """Generate a random BacktestSummary."""
    total_trades = draw(st.integers(min_value=5, max_value=200))
    wins = draw(st.integers(min_value=0, max_value=total_trades))
    losses = total_trades - wins
    win_rate = wins / total_trades * 100 if total_trades > 0 else 0
    avg_profit = draw(st.floats(min_value=-5.0, max_value=5.0))
    total_profit = avg_profit * total_trades

    return BacktestSummary(
        strategy="TestStrategy",
        timeframe="5m",
        total_trades=total_trades,
        wins=wins,
        losses=losses,
        draws=0,
        win_rate=win_rate,
        avg_profit=avg_profit,
        total_profit=total_profit,
        total_profit_abs=abs(total_profit),
        sharpe_ratio=None,
        sortino_ratio=None,
        calmar_ratio=None,
        max_drawdown=draw(st.floats(min_value=0.1, max_value=30.0)),
        max_drawdown_abs=draw(st.floats(min_value=0.1, max_value=30.0)),
        trade_duration_avg=60,
    )


class TestComparisonServiceProperties:
    """Property-based tests for ComparisonService."""

    @given(backtest_summary_strategy(), backtest_summary_strategy())
    def test_profit_diff_antisymmetry(self, run_a: BacktestSummary, run_b: BacktestSummary) -> None:
        """Verify: compare(a,b).profit_diff == -compare(b,a).profit_diff.

        This property ensures that the comparison is properly antisymmetric.
        """
        comparison_ab = ComparisonService.compare(run_a, run_b)
        comparison_ba = ComparisonService.compare(run_b, run_a)

        assert abs(comparison_ab.profit_diff + comparison_ba.profit_diff) < 0.001, (
            f"Profit diff not antisymmetric: ab={comparison_ab.profit_diff}, ba={comparison_ba.profit_diff}"
        )

    @given(backtest_summary_strategy(), backtest_summary_strategy())
    def test_winrate_diff_antisymmetry(self, run_a: BacktestSummary, run_b: BacktestSummary) -> None:
        """Verify: compare(a,b).winrate_diff == -compare(b,a).winrate_diff."""
        comparison_ab = ComparisonService.compare(run_a, run_b)
        comparison_ba = ComparisonService.compare(run_b, run_a)

        assert abs(comparison_ab.winrate_diff + comparison_ba.winrate_diff) < 0.01, (
            f"Win rate diff not antisymmetric: ab={comparison_ab.winrate_diff}, ba={comparison_ba.winrate_diff}"
        )

    @given(backtest_summary_strategy(), backtest_summary_strategy())
    def test_drawdown_diff_antisymmetry(self, run_a: BacktestSummary, run_b: BacktestSummary) -> None:
        """Verify: compare(a,b).drawdown_diff == -compare(b,a).drawdown_diff."""
        comparison_ab = ComparisonService.compare(run_a, run_b)
        comparison_ba = ComparisonService.compare(run_b, run_a)

        assert abs(comparison_ab.drawdown_diff + comparison_ba.drawdown_diff) < 0.01, (
            f"Drawdown diff not antisymmetric: ab={comparison_ab.drawdown_diff}, ba={comparison_ba.drawdown_diff}"
        )

    @given(backtest_summary_strategy())
    def test_identical_runs_are_neutral(self, run: BacktestSummary) -> None:
        """Verify: compare(a,a) → 'neutral' verdict."""
        comparison = ComparisonService.compare(run, run)

        assert comparison.profit_diff == 0.0
        assert comparison.winrate_diff == 0.0
        assert comparison.drawdown_diff == 0.0
        assert comparison.verdict == "neutral"

    def test_clearly_improved_verdict(self) -> None:
        """Verify: improved verdict when run_b is better across all metrics."""
        run_a = BacktestSummary(
            strategy="Old",
            timeframe="5m",
            total_trades=100,
            wins=40,
            losses=60,
            draws=0,
            win_rate=40.0,
            avg_profit=0.5,
            total_profit=50.0,
            total_profit_abs=50.0,
            sharpe_ratio=1.0,
            sortino_ratio=1.0,
            calmar_ratio=1.0,
            max_drawdown=15.0,
            max_drawdown_abs=15.0,
            trade_duration_avg=60,
        )

        run_b = BacktestSummary(
            strategy="New",
            timeframe="5m",
            total_trades=100,
            wins=60,
            losses=40,
            draws=0,
            win_rate=60.0,
            avg_profit=1.5,
            total_profit=150.0,
            total_profit_abs=150.0,
            sharpe_ratio=2.0,
            sortino_ratio=2.0,
            calmar_ratio=2.0,
            max_drawdown=10.0,
            max_drawdown_abs=10.0,
            trade_duration_avg=60,
        )

        comparison = ComparisonService.compare(run_a, run_b)

        assert comparison.profit_diff > 0  # 150 - 50
        assert comparison.winrate_diff > 0  # 60 - 40
        assert comparison.drawdown_diff < 0  # 10 - 15 (negative is good)
        assert comparison.verdict == "improved"

    def test_clearly_degraded_verdict(self) -> None:
        """Verify: degraded verdict when run_b is worse across all metrics."""
        run_a = BacktestSummary(
            strategy="Good",
            timeframe="5m",
            total_trades=100,
            wins=60,
            losses=40,
            draws=0,
            win_rate=60.0,
            avg_profit=1.5,
            total_profit=150.0,
            total_profit_abs=150.0,
            sharpe_ratio=2.0,
            sortino_ratio=2.0,
            calmar_ratio=2.0,
            max_drawdown=10.0,
            max_drawdown_abs=10.0,
            trade_duration_avg=60,
        )

        run_b = BacktestSummary(
            strategy="Bad",
            timeframe="5m",
            total_trades=100,
            wins=30,
            losses=70,
            draws=0,
            win_rate=30.0,
            avg_profit=-0.5,
            total_profit=-50.0,
            total_profit_abs=50.0,
            sharpe_ratio=0.5,
            sortino_ratio=0.5,
            calmar_ratio=0.5,
            max_drawdown=20.0,
            max_drawdown_abs=20.0,
            trade_duration_avg=60,
        )

        comparison = ComparisonService.compare(run_a, run_b)

        assert comparison.profit_diff < 0  # -50 - 150
        assert comparison.winrate_diff < 0  # 30 - 60
        assert comparison.drawdown_diff > 0  # 20 - 10 (positive is bad)
        assert comparison.verdict == "degraded"

    def test_mixed_metrics_neutral_verdict(self) -> None:
        """Verify: neutral verdict when metrics are mixed (not clearly improved/degraded)."""
        run_a = BacktestSummary(
            strategy="Baseline",
            timeframe="5m",
            total_trades=100,
            wins=50,
            losses=50,
            draws=0,
            win_rate=50.0,
            avg_profit=1.0,
            total_profit=100.0,
            total_profit_abs=100.0,
            sharpe_ratio=1.0,
            sortino_ratio=1.0,
            calmar_ratio=1.0,
            max_drawdown=10.0,
            max_drawdown_abs=10.0,
            trade_duration_avg=60,
        )

        run_b = BacktestSummary(
            strategy="Mixed",
            timeframe="5m",
            total_trades=100,
            wins=55,
            losses=45,
            draws=0,
            win_rate=55.0,  # Better (+5%)
            avg_profit=1.0,  # Same
            total_profit=100.0,  # Same
            total_profit_abs=100.0,
            sharpe_ratio=1.0,
            sortino_ratio=1.0,
            calmar_ratio=1.0,
            max_drawdown=10.0,  # Same
            max_drawdown_abs=10.0,
            trade_duration_avg=60,
        )

        comparison = ComparisonService.compare(run_a, run_b)

        # profit_diff == 0, winrate_diff > 0, drawdown_diff == 0 → neutral
        # (not all three positive for improved, and no negative values for degraded)
        assert comparison.profit_diff == 0
        assert comparison.winrate_diff > 0
        assert comparison.drawdown_diff == 0
        assert comparison.verdict == "neutral"
