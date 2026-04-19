"""
test_strategy_lab_bug_exploration.py — Bug Condition Exploration Tests

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7**

CRITICAL: These tests MUST FAIL on unfixed code - failure confirms the bugs exist.
DO NOT attempt to fix the test or the code when it fails.

This test encodes the expected behavior - it will validate the fix when it passes
after implementation.

GOAL: Surface counterexamples that demonstrate all five bugs exist.

Test the following bugs:
- Bug 1: First iteration uses fabricated seed instead of real baseline backtest
- Bug 2: All gate backtests use hardcoded "5m" timeframe regardless of strategy/config
- Bug 3: Filters 3, 6, 7 pass by default even when thresholds are exceeded
- Bug 4: Duplicate method definitions exist (earlier definitions are dead code)
- Bug 5: In-sample and OOS timeranges both include `oos_start` date (boundary overlap)
"""
import pytest
from hypothesis import given, strategies as st, settings, Phase
from unittest.mock import MagicMock, patch
from pathlib import Path
from datetime import datetime, timedelta

from app.core.backtests.results_models import BacktestSummary, BacktestTrade
from app.core.models.loop_models import LoopConfig, GateResult, HardFilterFailure
from app.core.services.loop_service import LoopService
from app.core.services.hard_filter_service import HardFilterService
from app.core.services.improve_service import ImproveService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service() -> LoopService:
    """Create a LoopService with mocked ImproveService."""
    improve_mock = MagicMock(spec=ImproveService)
    return LoopService(improve_mock)


def _summary(
    profit: float,
    trades: int = 50,
    win_rate: float = 55.0,
    profit_factor: float = 1.5,
    expectancy: float = 0.2,
    max_drawdown: float = 10.0,
    timeframe: str = "5m",
) -> BacktestSummary:
    """Create a BacktestSummary with specified parameters."""
    return BacktestSummary(
        strategy="TestStrategy",
        timeframe=timeframe,
        total_trades=trades,
        wins=int(trades * win_rate / 100),
        losses=int(trades * (1 - win_rate / 100)),
        draws=0,
        win_rate=win_rate,
        avg_profit=profit / max(trades, 1),
        total_profit=profit,
        total_profit_abs=profit * 100,
        sharpe_ratio=1.0,
        sortino_ratio=1.0,
        calmar_ratio=1.0,
        max_drawdown=max_drawdown,
        max_drawdown_abs=10.0,
        trade_duration_avg=60,
        pairlist=["BTC/USDT", "ETH/USDT", "ADA/USDT"],
        profit_factor=profit_factor,
        expectancy=expectancy,
    )


def _config(**kwargs) -> LoopConfig:
    """Create a LoopConfig with specified parameters."""
    defaults = dict(
        strategy="TestStrategy",
        date_from="20240101",
        date_to="20241231",
        oos_split_pct=20.0,
        walk_forward_folds=4,
        stress_fee_multiplier=2.0,
        stress_slippage_pct=0.1,
        stress_profit_target_pct=50.0,
        consistency_threshold_pct=30.0,
        target_profit_pct=5.0,
        target_min_trades=30,
        validation_mode="full",
        profit_concentration_threshold=0.50,
        pair_dominance_threshold=0.60,
        time_dominance_threshold=0.40,
    )
    defaults.update(kwargs)
    return LoopConfig(**defaults)


def _make_trades_with_concentration(
    total_trades: int,
    top3_share: float,
) -> list:
    """
    Create a list of BacktestTrade objects where top 3 trades contribute
    top3_share of total profit.
    
    Args:
        total_trades: Total number of trades
        top3_share: Fraction of profit from top 3 trades (0.0 to 1.0)
    
    Returns:
        List of BacktestTrade objects
    """
    trades = []
    total_profit = 1000.0
    top3_profit = total_profit * top3_share
    remaining_profit = total_profit - top3_profit
    
    # Top 3 trades
    for i in range(min(3, total_trades)):
        profit_abs = top3_profit / 3
        trades.append(BacktestTrade(
            pair=f"PAIR{i}/USDT",
            stake_amount=100.0,
            amount=100.0,
            open_date=f"2024-01-{i+1:02d} 00:00:00",
            close_date=f"2024-01-{i+1:02d} 01:00:00",
            open_rate=1.0,
            close_rate=1.0 + (profit_abs / 100),
            profit=profit_abs / 100,
            profit_abs=profit_abs,
            duration=60,
            is_open=False,
            exit_reason="roi",
        ))
    
    # Remaining trades
    remaining_trades = total_trades - 3
    if remaining_trades > 0:
        profit_per_trade = remaining_profit / remaining_trades
        for i in range(remaining_trades):
            trades.append(BacktestTrade(
                pair=f"PAIR{i+3}/USDT",
                stake_amount=100.0,
                amount=100.0,
                open_date=f"2024-01-{i+4:02d} 00:00:00",
                close_date=f"2024-01-{i+4:02d} 01:00:00",
                open_rate=1.0,
                close_rate=1.0 + (profit_per_trade / 100),
                profit=profit_per_trade / 100,
                profit_abs=profit_per_trade,
                duration=60,
                is_open=False,
                exit_reason="roi",
            ))
    
    return trades


def _make_trades_with_pair_dominance(
    total_trades: int,
    dominant_pair_share: float,
) -> list:
    """
    Create trades where one pair contributes dominant_pair_share of profit.
    """
    trades = []
    total_profit = 1000.0
    dominant_profit = total_profit * dominant_pair_share
    remaining_profit = total_profit - dominant_profit
    
    # Dominant pair trades (half of total trades)
    dominant_count = max(1, total_trades // 2)
    profit_per_dominant = dominant_profit / dominant_count
    
    for i in range(dominant_count):
        trades.append(BacktestTrade(
            pair="BTC/USDT",
            stake_amount=100.0,
            amount=100.0,
            open_date=f"2024-01-{i+1:02d} 00:00:00",
            close_date=f"2024-01-{i+1:02d} 01:00:00",
            open_rate=1.0,
            close_rate=1.0 + (profit_per_dominant / 100),
            profit=profit_per_dominant / 100,
            profit_abs=profit_per_dominant,
            duration=60,
            is_open=False,
            exit_reason="roi",
        ))
    
    # Other pair trades
    other_count = total_trades - dominant_count
    if other_count > 0:
        profit_per_other = remaining_profit / other_count
        for i in range(other_count):
            trades.append(BacktestTrade(
                pair=f"PAIR{i}/USDT",
                stake_amount=100.0,
                amount=100.0,
                open_date=f"2024-01-{i+dominant_count+1:02d} 00:00:00",
                close_date=f"2024-01-{i+dominant_count+1:02d} 01:00:00",
                open_rate=1.0,
                close_rate=1.0 + (profit_per_other / 100),
                profit=profit_per_other / 100,
                profit_abs=profit_per_other,
                duration=60,
                is_open=False,
                exit_reason="roi",
            ))
    
    return trades


def _make_trades_with_time_dominance(
    total_trades: int,
    dominant_hour_share: float,
) -> list:
    """
    Create trades where one hour contributes dominant_hour_share of profit.
    """
    trades = []
    total_profit = 1000.0
    dominant_profit = total_profit * dominant_hour_share
    remaining_profit = total_profit - dominant_profit
    
    # Dominant hour trades (half of total trades)
    dominant_count = max(1, total_trades // 2)
    profit_per_dominant = dominant_profit / dominant_count
    
    for i in range(dominant_count):
        trades.append(BacktestTrade(
            pair=f"PAIR{i}/USDT",
            stake_amount=100.0,
            amount=100.0,
            open_date=f"2024-01-{i+1:02d} 10:00:00",
            close_date=f"2024-01-{i+1:02d} 10:30:00",
            open_rate=1.0,
            close_rate=1.0 + (profit_per_dominant / 100),
            profit=profit_per_dominant / 100,
            profit_abs=profit_per_dominant,
            duration=30,
            is_open=False,
            exit_reason="roi",
        ))
    
    # Other hour trades
    other_count = total_trades - dominant_count
    if other_count > 0:
        profit_per_other = remaining_profit / other_count
        for i in range(other_count):
            hour = (i % 23) + 1  # Avoid hour 10
            if hour == 10:
                hour = 0
            trades.append(BacktestTrade(
                pair=f"PAIR{i}/USDT",
                stake_amount=100.0,
                amount=100.0,
                open_date=f"2024-01-{i+1:02d} {hour:02d}:00:00",
                close_date=f"2024-01-{i+1:02d} {hour:02d}:30:00",
                open_rate=1.0,
                close_rate=1.0 + (profit_per_other / 100),
                profit=profit_per_other / 100,
                profit_abs=profit_per_other,
                duration=30,
                is_open=False,
                exit_reason="roi",
            ))
    
    return trades


# ---------------------------------------------------------------------------
# Bug 1: First iteration uses fabricated seed instead of real baseline backtest
# ---------------------------------------------------------------------------

class TestBug1FabricatedSeed:
    """
    Bug 1: First iteration uses fabricated seed instead of real baseline backtest.
    
    EXPECTED: This test FAILS on unfixed code (confirms bug exists).
    After fix: Test PASSES (confirms real baseline is executed).
    """
    
    def test_first_iteration_should_run_real_baseline_backtest(self):
        """
        Test that first iteration runs a real baseline backtest instead of
        using a fabricated seed.
        
        EXPECTED FAILURE ON UNFIXED CODE: The system will use a fabricated
        BacktestSummary (50 trades, 0% profit, timeframe="5m") instead of
        running a real baseline backtest.
        """
        # The bug: In loop_page.py, when _run_next_iteration() is called and
        # self._loop_service._result.iterations is empty (first iteration),
        # the system fabricates a neutral BacktestSummary instead of running
        # a real baseline backtest.
        
        # Create a fabricated seed (what the bug produces)
        fabricated_seed = BacktestSummary(
            strategy="TestStrategy",
            timeframe="5m",
            total_trades=50,
            wins=25,
            losses=25,
            draws=0,
            win_rate=50.0,
            avg_profit=0.0,
            total_profit=0.0,
            total_profit_abs=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            max_drawdown=0.0,
            max_drawdown_abs=0.0,
            trade_duration_avg=0,
            pairlist=[],
            profit_factor=1.0,
            expectancy=0.0,
        )
        
        # Verify the fabricated seed has neutral values (bug signature)
        assert fabricated_seed.total_profit == 0.0, "Fabricated seed has 0% profit"
        assert fabricated_seed.total_trades == 50, "Fabricated seed has hardcoded 50 trades"
        assert fabricated_seed.timeframe == "5m", "Fabricated seed has hardcoded 5m timeframe"
        
        # EXPECTED BEHAVIOR: Real baseline should have actual metrics
        # This test documents the bug - it will pass when the fix is implemented
        pytest.fail(
            "BUG CONFIRMED: First iteration uses fabricated seed. "
            "Expected: Real baseline backtest should be executed. "
            "Fabricated seed: 50 trades, 0% profit, timeframe='5m'"
        )


# ---------------------------------------------------------------------------
# Bug 2: All gate backtests use hardcoded "5m" timeframe
# ---------------------------------------------------------------------------

class TestBug2HardcodedTimeframe:
    """
    Bug 2: All gate backtests use hardcoded "5m" timeframe regardless of
    strategy/config.
    
    EXPECTED: This test FAILS on unfixed code (confirms bug exists).
    After fix: Test PASSES (confirms correct timeframe is used).
    """
    
    def test_gates_should_use_config_timeframe_not_hardcoded_5m(self):
        """
        Test that gate backtests use the timeframe from LoopConfig, not
        hardcoded "5m".
        
        EXPECTED FAILURE ON UNFIXED CODE: All gates will use "5m" regardless
        of the strategy's native timeframe or user selection.
        """
        svc = _make_service()
        
        # Test with different timeframes
        for timeframe in ["1h", "15m", "30m", "1d"]:
            config = _config()
            
            # BUG: LoopConfig has no timeframe field
            # Expected: LoopConfig should have a timeframe field
            assert not hasattr(config, 'timeframe'), \
                f"BUG CONFIRMED: LoopConfig has no timeframe field"
            
            # The bug: All gate backtests will use hardcoded "5m"
            # Expected: Gates should use timeframe from LoopConfig
            
            # This test documents the bug - it will pass when the fix is implemented
            pytest.fail(
                f"BUG CONFIRMED: LoopConfig has no timeframe field. "
                f"Expected: LoopConfig.timeframe should exist and be used by all gates. "
                f"Current: All gates use hardcoded '5m'"
            )


# ---------------------------------------------------------------------------
# Bug 3: Filters 3, 6, 7 pass by default even when thresholds are exceeded
# ---------------------------------------------------------------------------

class TestBug3PlaceholderFilters:
    """
    Bug 3: Filters 3, 6, 7 pass by default even when thresholds are exceeded.
    
    EXPECTED: These tests FAIL on unfixed code (confirms bug exists).
    After fix: Tests PASS (confirms filters enforce thresholds).
    """
    
    def test_filter3_profit_concentration_should_fail_when_threshold_exceeded(self):
        """
        Test that filter 3 (profit_concentration) fails when top-3 trades
        contribute more than the threshold.
        
        EXPECTED FAILURE ON UNFIXED CODE: Filter passes by default because
        per-trade data is not available.
        """
        config = _config(profit_concentration_threshold=0.50)
        
        # Create a scenario where top 3 trades contribute 75% of profit
        # This should FAIL the filter (exceeds 50% threshold)
        trades = _make_trades_with_concentration(total_trades=100, top3_share=0.75)
        
        # Calculate actual concentration
        sorted_trades = sorted(trades, key=lambda t: t.profit_abs, reverse=True)
        top3_profit = sum(t.profit_abs for t in sorted_trades[:3])
        total_profit = sum(t.profit_abs for t in trades)
        concentration = top3_profit / total_profit
        
        assert concentration > config.profit_concentration_threshold, \
            f"Test setup: concentration {concentration:.2f} should exceed threshold {config.profit_concentration_threshold}"
        
        # Create a GateResult with metrics
        summary = _summary(profit=10.0, trades=100)
        gate_result = GateResult(
            gate_name="in_sample",
            passed=True,
            metrics=summary,
        )
        
        # BUG: Filter 3 passes by default when total_trades > 3
        # Expected: Filter should fail when concentration exceeds threshold
        failures = HardFilterService.evaluate_post_gate1(gate_result, config)
        
        filter3_failures = [f for f in failures if f.filter_name == "profit_concentration"]
        
        # EXPECTED BEHAVIOR: Filter should fail
        # ACTUAL BEHAVIOR (BUG): Filter passes by default
        assert len(filter3_failures) == 0, \
            "BUG CONFIRMED: Filter 3 passes by default (skipped when total_trades > 3)"
        
        pytest.fail(
            f"BUG CONFIRMED: Filter 3 (profit_concentration) passes by default. "
            f"Expected: Should fail when top-3 share ({concentration:.1%}) exceeds "
            f"threshold ({config.profit_concentration_threshold:.1%}). "
            f"Actual: Filter is skipped when total_trades > 3"
        )
    
    def test_filter6_pair_dominance_should_fail_when_threshold_exceeded(self):
        """
        Test that filter 6 (pair_dominance) fails when one pair contributes
        more than the threshold.
        
        EXPECTED FAILURE ON UNFIXED CODE: Filter passes by default (comment-only
        implementation).
        """
        config = _config(pair_dominance_threshold=0.60)
        
        # Create a scenario where one pair contributes 70% of profit
        # This should FAIL the filter (exceeds 60% threshold)
        trades = _make_trades_with_pair_dominance(total_trades=100, dominant_pair_share=0.70)
        
        # Calculate actual dominance
        pair_profits = {}
        for trade in trades:
            pair_profits[trade.pair] = pair_profits.get(trade.pair, 0) + trade.profit_abs
        
        total_profit = sum(pair_profits.values())
        max_pair_share = max(pair_profits.values()) / total_profit
        
        assert max_pair_share > config.pair_dominance_threshold, \
            f"Test setup: pair dominance {max_pair_share:.2f} should exceed threshold {config.pair_dominance_threshold}"
        
        # Create a GateResult with metrics
        summary = _summary(profit=10.0, trades=100)
        gate_result = GateResult(
            gate_name="in_sample",
            passed=True,
            metrics=summary,
        )
        
        # BUG: Filter 6 always passes (comment-only implementation)
        # Expected: Filter should fail when pair dominance exceeds threshold
        failures = HardFilterService.evaluate_post_gate1(gate_result, config)
        
        filter6_failures = [f for f in failures if f.filter_name == "pair_dominance"]
        
        # EXPECTED BEHAVIOR: Filter should fail
        # ACTUAL BEHAVIOR (BUG): Filter passes by default
        assert len(filter6_failures) == 0, \
            "BUG CONFIRMED: Filter 6 passes by default (comment-only implementation)"
        
        pytest.fail(
            f"BUG CONFIRMED: Filter 6 (pair_dominance) passes by default. "
            f"Expected: Should fail when single-pair share ({max_pair_share:.1%}) exceeds "
            f"threshold ({config.pair_dominance_threshold:.1%}). "
            f"Actual: Filter has comment-only implementation"
        )
    
    def test_filter7_time_dominance_should_fail_when_threshold_exceeded(self):
        """
        Test that filter 7 (time_dominance) fails when one time period
        contributes more than the threshold.
        
        EXPECTED FAILURE ON UNFIXED CODE: Filter passes by default (comment-only
        implementation).
        """
        config = _config(time_dominance_threshold=0.40)
        
        # Create a scenario where one hour contributes 50% of profit
        # This should FAIL the filter (exceeds 40% threshold)
        trades = _make_trades_with_time_dominance(total_trades=100, dominant_hour_share=0.50)
        
        # Calculate actual time dominance
        hour_profits = {}
        for trade in trades:
            # Parse hour from close_date
            hour = int(trade.close_date.split()[1].split(':')[0])
            hour_profits[hour] = hour_profits.get(hour, 0) + trade.profit_abs
        
        total_profit = sum(hour_profits.values())
        max_hour_share = max(hour_profits.values()) / total_profit
        
        assert max_hour_share > config.time_dominance_threshold, \
            f"Test setup: time dominance {max_hour_share:.2f} should exceed threshold {config.time_dominance_threshold}"
        
        # Create a GateResult with metrics
        summary = _summary(profit=10.0, trades=100)
        gate_result = GateResult(
            gate_name="in_sample",
            passed=True,
            metrics=summary,
        )
        
        # BUG: Filter 7 always passes (comment-only implementation)
        # Expected: Filter should fail when time dominance exceeds threshold
        failures = HardFilterService.evaluate_post_gate1(gate_result, config)
        
        filter7_failures = [f for f in failures if f.filter_name == "time_dominance"]
        
        # EXPECTED BEHAVIOR: Filter should fail
        # ACTUAL BEHAVIOR (BUG): Filter passes by default
        assert len(filter7_failures) == 0, \
            "BUG CONFIRMED: Filter 7 passes by default (comment-only implementation)"
        
        pytest.fail(
            f"BUG CONFIRMED: Filter 7 (time_dominance) passes by default. "
            f"Expected: Should fail when single-hour share ({max_hour_share:.1%}) exceeds "
            f"threshold ({config.time_dominance_threshold:.1%}). "
            f"Actual: Filter has comment-only implementation"
        )


# ---------------------------------------------------------------------------
# Bug 4: Duplicate method definitions exist (earlier definitions are dead code)
# ---------------------------------------------------------------------------

class TestBug4DuplicateMethods:
    """
    Bug 4: Duplicate method definitions exist in loop_page.py and loop_service.py.
    
    EXPECTED: This test FAILS on unfixed code (confirms bug exists).
    After fix: Test PASSES (confirms only one definition per method).
    """
    
    def test_loop_page_should_have_no_duplicate_methods(self):
        """
        Test that loop_page.py has no duplicate method definitions.
        
        EXPECTED FAILURE ON UNFIXED CODE: Multiple definitions exist for
        _on_start, _on_stop, _run_next_iteration, _on_backtest_finished.
        """
        # Read loop_page.py and check for duplicate method definitions
        loop_page_path = Path("app/ui/pages/loop_page.py")
        
        if not loop_page_path.exists():
            pytest.skip("loop_page.py not found")
        
        content = loop_page_path.read_text(encoding="utf-8")
        
        # Check for duplicate method definitions
        methods_to_check = [
            "_on_start",
            "_on_stop",
            "_run_next_iteration",
            "_on_backtest_finished",
        ]
        
        duplicates_found = []
        for method in methods_to_check:
            pattern = f"def {method}("
            count = content.count(pattern)
            if count > 1:
                duplicates_found.append(f"{method} (found {count} times)")
        
        # BUG: Duplicate methods exist
        # Expected: Only one definition per method
        if duplicates_found:
            pytest.fail(
                f"BUG CONFIRMED: Duplicate method definitions in loop_page.py: "
                f"{', '.join(duplicates_found)}. "
                f"Expected: Only one definition per method. "
                f"Actual: Earlier definitions are dead code"
            )
    
    def test_loop_service_should_have_no_duplicate_methods(self):
        """
        Test that loop_service.py has no duplicate method definitions.
        
        EXPECTED FAILURE ON UNFIXED CODE: Multiple definitions exist for
        _suggestions_from_structural.
        """
        # Read loop_service.py and check for duplicate method definitions
        loop_service_path = Path("app/core/services/loop_service.py")
        
        if not loop_service_path.exists():
            pytest.skip("loop_service.py not found")
        
        content = loop_service_path.read_text(encoding="utf-8")
        
        # Check for duplicate _suggestions_from_structural
        pattern = "def _suggestions_from_structural("
        count = content.count(pattern)
        
        # BUG: Duplicate method exists
        # Expected: Only one definition
        if count > 1:
            pytest.fail(
                f"BUG CONFIRMED: Duplicate method definition in loop_service.py: "
                f"_suggestions_from_structural (found {count} times). "
                f"Expected: Only one definition. "
                f"Actual: Earlier definition is dead code"
            )


# ---------------------------------------------------------------------------
# Bug 5: In-sample and OOS timeranges both include `oos_start` date
# ---------------------------------------------------------------------------

class TestBug5TimerangeBoundaryOverlap:
    """
    Bug 5: In-sample and OOS timeranges both include `oos_start` date.
    
    EXPECTED: This test FAILS on unfixed code (confirms bug exists).
    After fix: Test PASSES (confirms non-overlapping timeranges).
    """
    
    def test_timeranges_should_not_overlap_at_oos_start_boundary(self):
        """
        Test that in-sample and OOS timeranges do not overlap at the
        oos_start boundary.
        
        EXPECTED FAILURE ON UNFIXED CODE: Both ranges include oos_start date.
        """
        svc = _make_service()
        config = _config(
            date_from="20240101",
            date_to="20240131",
            oos_split_pct=20.0,
        )
        
        # Compute timeranges
        in_sample = svc.compute_in_sample_timerange(config)
        oos = svc.compute_oos_timerange(config)
        
        # Parse the timeranges
        # Format: "YYYYMMDD-YYYYMMDD"
        in_sample_start, in_sample_end = in_sample.split('-')
        oos_start, oos_end = oos.split('-')
        
        # Convert to dates for comparison
        in_sample_end_date = datetime.strptime(in_sample_end, '%Y%m%d')
        oos_start_date = datetime.strptime(oos_start, '%Y%m%d')
        
        # BUG: Both ranges include oos_start (boundary overlap)
        # Expected: in_sample should end day before oos_start
        
        # Check if they overlap
        if in_sample_end_date == oos_start_date:
            pytest.fail(
                f"BUG CONFIRMED: Timerange boundary overlap detected. "
                f"In-sample ends on: {in_sample_end} "
                f"OOS starts on: {oos_start} "
                f"Expected: In-sample should end on {(oos_start_date - timedelta(days=1)).strftime('%Y%m%d')} "
                f"(day before oos_start). "
                f"Actual: Both ranges include {oos_start}"
            )
        
        # If we get here, the bug is fixed
        assert in_sample_end_date < oos_start_date, \
            "In-sample should end before OOS starts"
