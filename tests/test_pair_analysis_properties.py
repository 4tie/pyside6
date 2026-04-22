"""test_pair_analysis_properties.py — Property-based tests for PairAnalysisService.

Uses Hypothesis to generate random BacktestResults and verify invariants.
"""
from typing import List

import pytest
from hypothesis import given, strategies as st

from app.core.backtests.results_models import BacktestResults, BacktestTrade, BacktestSummary
from app.core.services.pair_analysis_service import PairAnalysisService


# Hypothesis strategies
@st.composite
def backtest_trade_strategy(draw) -> BacktestTrade:
    """Generate a random BacktestTrade."""
    pairs = ["BTC/USDT", "ETH/USDT", "ADA/USDT", "XRP/USDT", "SOL/USDT"]
    pair = draw(st.sampled_from(pairs))
    profit = draw(st.floats(min_value=-5.0, max_value=5.0))

    return BacktestTrade(
        pair=pair,
        stake_amount=100.0,
        amount=1.0,
        open_date="2026-01-01T00:00:00Z",
        close_date="2026-01-01T01:00:00Z",
        open_rate=100.0,
        close_rate=100.0 * (1 + profit / 100),
        profit=profit,
        profit_abs=profit,
        duration=60,
        is_open=False,
        exit_reason="sell",
    )


@st.composite
def backtest_results_strategy(draw, min_trades: int = 0, max_trades: int = 100) -> BacktestResults:
    """Generate a random BacktestResults."""
    trades = draw(
        st.lists(backtest_trade_strategy(), min_size=min_trades, max_size=max_trades)
    )

    summary = BacktestSummary(
        strategy="TestStrategy",
        timeframe="5m",
        total_trades=len(trades),
        wins=len([t for t in trades if t.profit > 0]),
        losses=len([t for t in trades if t.profit < 0]),
        draws=len([t for t in trades if t.profit == 0]),
        win_rate=len([t for t in trades if t.profit > 0]) / len(trades) * 100 if trades else 0,
        avg_profit=sum(t.profit for t in trades) / len(trades) if trades else 0,
        total_profit=sum(t.profit for t in trades),
        total_profit_abs=sum(t.profit for t in trades),
        sharpe_ratio=None,
        sortino_ratio=None,
        calmar_ratio=None,
        max_drawdown=5.0,
        max_drawdown_abs=5.0,
        trade_duration_avg=60,
    )

    return BacktestResults(
        trades=trades,
        summary=summary,
    )


class TestPairAnalysisProperties:
    """Property-based tests for PairAnalysisService."""

    @given(backtest_results_strategy(min_trades=1, max_trades=100))
    def test_trade_count_invariant(self, results: BacktestResults) -> None:
        """Verify: sum of trade counts equals total trades.

        For any non-empty BacktestResults, the sum of trade_count across
        all PairMetrics must equal len(trades).
        """
        analysis = PairAnalysisService.analyse(results)
        total_pair_trades = sum(pm.trade_count for pm in analysis.pair_metrics)
        assert total_pair_trades == len(results.trades), (
            f"Trade count mismatch: pairs={total_pair_trades}, total={len(results.trades)}"
        )

    def test_empty_trades_returns_empty_analysis(self) -> None:
        """Verify: empty trades returns empty PairAnalysis."""
        results = BacktestResults(
            trades=[],
            summary=BacktestSummary(
                strategy="TestStrategy",
                timeframe="5m",
                total_trades=0,
                wins=0,
                losses=0,
                draws=0,
                win_rate=0.0,
                avg_profit=0.0,
                total_profit=0.0,
                total_profit_abs=0.0,
                sharpe_ratio=None,
                sortino_ratio=None,
                calmar_ratio=None,
                max_drawdown=0.0,
                max_drawdown_abs=0.0,
                trade_duration_avg=0,
            ),
        )

        analysis = PairAnalysisService.analyse(results)

        assert analysis.pair_metrics == []
        assert analysis.best_pairs == []
        assert analysis.worst_pairs == []
        assert analysis.dominance_flags == []

    @given(backtest_results_strategy(min_trades=1, max_trades=100))
    def test_profit_share_sums_to_one_or_zero(self, results: BacktestResults) -> None:
        """Verify: profit_share values are normalized (sum to 1 or 0 when no profit)."""
        analysis = PairAnalysisService.analyse(results)

        if not analysis.pair_metrics:
            return

        # If any profits, shares should sum to ~1.0
        total_profit = sum(pm.total_profit_pct for pm in analysis.pair_metrics)
        if abs(total_profit) > 1e-10:  # Non-zero total (relaxed threshold for float precision)
            total_share = sum(abs(pm.profit_share) for pm in analysis.pair_metrics)
            assert abs(total_share - 1.0) < 0.01, f"Profit shares don't sum to 1.0: {total_share}"
        # For near-zero or exactly zero totals, shares may be 0.0 or 1.0 (depending on single pair edge case)

    @given(backtest_results_strategy(min_trades=1, max_trades=100))
    def test_best_pairs_are_sorted_desc(self, results: BacktestResults) -> None:
        """Verify: best_pairs are sorted by profit_pct descending."""
        analysis = PairAnalysisService.analyse(results)

        if len(analysis.best_pairs) < 2:
            return  # Can't verify sort with < 2 items

        for i in range(len(analysis.best_pairs) - 1):
            assert (
                analysis.best_pairs[i].total_profit_pct >= analysis.best_pairs[i + 1].total_profit_pct
            ), "Best pairs not sorted descending"

    @given(backtest_results_strategy(min_trades=1, max_trades=100))
    def test_worst_pairs_are_sorted_asc(self, results: BacktestResults) -> None:
        """Verify: worst_pairs are sorted by profit_pct ascending."""
        analysis = PairAnalysisService.analyse(results)

        if len(analysis.worst_pairs) < 2:
            return  # Can't verify sort with < 2 items

        for i in range(len(analysis.worst_pairs) - 1):
            assert (
                analysis.worst_pairs[i].total_profit_pct <= analysis.worst_pairs[i + 1].total_profit_pct
            ), "Worst pairs not sorted ascending"

    @given(backtest_results_strategy(min_trades=1, max_trades=100))
    def test_dominance_flags_concentration(self, results: BacktestResults) -> None:
        """Verify: profit_concentration flag set when max profit_share > 0.60."""
        analysis = PairAnalysisService.analyse(results)

        if not analysis.pair_metrics:
            return

        max_share = max(pm.profit_share for pm in analysis.pair_metrics)

        if max_share > 0.60:
            assert "profit_concentration" in analysis.dominance_flags, (
                f"profit_concentration flag missing when max_share={max_share} > 0.60"
            )
        else:
            assert "profit_concentration" not in analysis.dominance_flags, (
                f"profit_concentration flag present when max_share={max_share} <= 0.60"
            )
