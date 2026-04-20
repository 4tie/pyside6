"""
Preservation property test for Property 2: Hard Filter Evaluation for Filters 1, 2, 4, 5.

This test encodes the EXPECTED preservation behavior and is designed to PASS on
the unfixed code, confirming that filters 1, 2, 4, 5 (min_trade_count, max_drawdown,
profit_factor_floor, expectancy_floor) are evaluated correctly after Gate 1.

**Property 2: Preservation** - Hard Filter Evaluation for Filters 1, 2, 4, 5

After the fix is applied, this test should STILL PASS (no regression).

**Validates: Requirements 3.2, 3.7, 3.8**
"""
import pytest
from unittest.mock import MagicMock
from pathlib import Path

from app.core.services.hard_filter_service import HardFilterService
from app.core.services.loop_service import LoopService
from app.core.models.loop_models import LoopConfig, GateResult, HardFilterFailure
from app.core.backtests.results_models import BacktestSummary, BacktestTrade

from hypothesis import given, settings as h_settings, assume
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_loop_config(
    target_min_trades: int = 30,
    target_max_drawdown: float = 20.0,
    profit_factor_floor: float = 1.0,
) -> LoopConfig:
    """Return a minimal LoopConfig for testing."""
    return LoopConfig(
        strategy="TestStrategy",
        timeframe="5m",
        max_iterations=5,
        target_profit_pct=5.0,
        target_win_rate=55.0,
        target_max_drawdown=target_max_drawdown,
        target_min_trades=target_min_trades,
        date_from="20240101",
        date_to="20240131",
        oos_split_pct=20.0,
        profit_factor_floor=profit_factor_floor,
    )


def _make_gate1_result(
    total_trades: int = 100,
    max_drawdown: float = 15.0,
    profit_factor: float = 1.5,
    expectancy: float = 0.5,
) -> GateResult:
    """Return a GateResult with specified metrics."""
    summary = BacktestSummary(
        strategy="TestStrategy",
        timeframe="5m",
        total_trades=total_trades,
        wins=60,
        losses=35,
        draws=5,
        win_rate=60.0,
        avg_profit=1.5,
        total_profit=150.0,
        total_profit_abs=150.0,
        sharpe_ratio=1.8,
        sortino_ratio=2.1,
        calmar_ratio=1.5,
        max_drawdown=max_drawdown,
        max_drawdown_abs=max_drawdown,
        trade_duration_avg=120,
        profit_factor=profit_factor,
        expectancy=expectancy,
    )
    
    return GateResult(
        gate_name="in_sample",
        passed=True,
        metrics=summary,
        fold_summaries=None,
    )


# ---------------------------------------------------------------------------
# Preservation property tests
# ---------------------------------------------------------------------------

@pytest.mark.preservation
@given(
    total_trades=st.integers(min_value=30, max_value=200),
    max_drawdown=st.floats(min_value=5.0, max_value=20.0),
    profit_factor=st.floats(min_value=1.0, max_value=3.0),
    expectancy=st.floats(min_value=0.0, max_value=2.0),
)
@h_settings(max_examples=20, deadline=None)
def test_preservation_filters_1_2_4_5_pass(
    total_trades, max_drawdown, profit_factor, expectancy
):
    """
    **Property 2: Preservation** - Hard Filter Evaluation for Filters 1, 2, 4, 5
    
    Preservation condition: NOT isBugCondition4(input) where:
      - Filters 1, 2, 4, 5 do not require trades parameter
      - These filters work correctly on unfixed code
    
    This test verifies that filters 1, 2, 4, 5 are evaluated correctly
    after Gate 1 completion, using only the BacktestSummary metrics.
    
    EXPECTED OUTCOME on unfixed code: PASS
      Filters 1, 2, 4, 5 are evaluated correctly and pass when metrics
      meet the thresholds.
      
    EXPECTED OUTCOME after fix: PASS (no regression)
      Filters 1, 2, 4, 5 continue to be evaluated correctly.
    
    **Validates: Requirements 3.2, 3.7, 3.8**
    """
    # Create config with thresholds that should pass
    config = _make_loop_config(
        target_min_trades=30,
        target_max_drawdown=20.0,
        profit_factor_floor=1.0,
    )
    
    # Create gate1 result with metrics that pass all filters
    gate1_result = _make_gate1_result(
        total_trades=total_trades,
        max_drawdown=max_drawdown,
        profit_factor=profit_factor,
        expectancy=expectancy,
    )
    
    # Evaluate filters 1, 2, 4, 5 (no trades parameter needed)
    failures = HardFilterService.evaluate_post_gate1(
        gate1_result, config, trades=None
    )
    
    # Filter out failures from filters 3, 6, 7 (which require trades)
    # We only care about filters 1, 2, 4, 5 for this preservation test
    relevant_failures = [
        f for f in failures
        if f.filter_name in ["min_trade_count", "max_drawdown", "profit_factor_floor", "expectancy_floor"]
    ]
    
    # Assert: Filters 1, 2, 4, 5 should pass (no failures)
    assert len(relevant_failures) == 0, (
        f"Preservation violated: Filters 1, 2, 4, 5 failed when they should pass.\n"
        f"Config: min_trades={config.target_min_trades}, max_dd={config.target_max_drawdown}, "
        f"pf_floor={config.profit_factor_floor}\n"
        f"Metrics: trades={total_trades}, dd={max_drawdown}, pf={profit_factor}, exp={expectancy}\n"
        f"Failures: {[f.filter_name for f in relevant_failures]}\n"
        f"This indicates a regression: filters 1, 2, 4, 5 should continue to work correctly."
    )


@pytest.mark.preservation
@given(
    total_trades=st.integers(min_value=10, max_value=29),
)
@h_settings(max_examples=10, deadline=None)
def test_preservation_filter_1_min_trade_count_fails(total_trades):
    """
    **Property 2: Preservation** - Filter 1 (min_trade_count) Fails Correctly
    
    This test verifies that filter 1 (min_trade_count) correctly rejects
    iterations with too few trades.
    
    EXPECTED OUTCOME on unfixed code: PASS
      Filter 1 fails when total_trades < target_min_trades.
      
    EXPECTED OUTCOME after fix: PASS (no regression)
      Filter 1 continues to fail correctly.
    
    **Validates: Requirements 3.2, 3.7, 3.8**
    """
    config = _make_loop_config(target_min_trades=30)
    
    gate1_result = _make_gate1_result(
        total_trades=total_trades,
        max_drawdown=15.0,
        profit_factor=1.5,
        expectancy=0.5,
    )
    
    failures = HardFilterService.evaluate_post_gate1(
        gate1_result, config, trades=None
    )
    
    # Check if filter 1 failed
    filter_1_failures = [f for f in failures if f.filter_name == "min_trade_count"]
    
    assert len(filter_1_failures) == 1, (
        f"Preservation violated: Filter 1 (min_trade_count) did not fail correctly.\n"
        f"Expected: 1 failure (trades={total_trades} < min={config.target_min_trades})\n"
        f"Actual: {len(filter_1_failures)} failures\n"
        f"This indicates a regression: filter 1 should reject iterations with too few trades."
    )
    
    # Verify the failure reason
    failure = filter_1_failures[0]
    assert str(total_trades) in failure.reason, (
        f"Preservation violated: Filter 1 failure reason does not mention trade count.\n"
        f"Reason: {failure.reason}\n"
    )


@pytest.mark.preservation
@given(
    max_drawdown=st.floats(min_value=20.1, max_value=50.0),
)
@h_settings(max_examples=10, deadline=None)
def test_preservation_filter_2_max_drawdown_fails(max_drawdown):
    """
    **Property 2: Preservation** - Filter 2 (max_drawdown) Fails Correctly
    
    This test verifies that filter 2 (max_drawdown) correctly rejects
    iterations with excessive drawdown.
    
    EXPECTED OUTCOME on unfixed code: PASS
      Filter 2 fails when max_drawdown > target_max_drawdown.
      
    EXPECTED OUTCOME after fix: PASS (no regression)
      Filter 2 continues to fail correctly.
    
    **Validates: Requirements 3.2, 3.7, 3.8**
    """
    config = _make_loop_config(target_max_drawdown=20.0)
    
    gate1_result = _make_gate1_result(
        total_trades=100,
        max_drawdown=max_drawdown,
        profit_factor=1.5,
        expectancy=0.5,
    )
    
    failures = HardFilterService.evaluate_post_gate1(
        gate1_result, config, trades=None
    )
    
    # Check if filter 2 failed
    filter_2_failures = [f for f in failures if f.filter_name == "max_drawdown"]
    
    assert len(filter_2_failures) == 1, (
        f"Preservation violated: Filter 2 (max_drawdown) did not fail correctly.\n"
        f"Expected: 1 failure (dd={max_drawdown} > max={config.target_max_drawdown})\n"
        f"Actual: {len(filter_2_failures)} failures\n"
        f"This indicates a regression: filter 2 should reject iterations with excessive drawdown."
    )
    
    # Verify the failure reason
    failure = filter_2_failures[0]
    assert "drawdown" in failure.reason.lower(), (
        f"Preservation violated: Filter 2 failure reason does not mention drawdown.\n"
        f"Reason: {failure.reason}\n"
    )


@pytest.mark.preservation
@given(
    profit_factor=st.floats(min_value=0.1, max_value=0.99),
)
@h_settings(max_examples=10, deadline=None)
def test_preservation_filter_4_profit_factor_floor_fails(profit_factor):
    """
    **Property 2: Preservation** - Filter 4 (profit_factor_floor) Fails Correctly
    
    This test verifies that filter 4 (profit_factor_floor) correctly rejects
    iterations with low profit factor.
    
    EXPECTED OUTCOME on unfixed code: PASS
      Filter 4 fails when profit_factor < profit_factor_floor.
      
    EXPECTED OUTCOME after fix: PASS (no regression)
      Filter 4 continues to fail correctly.
    
    **Validates: Requirements 3.2, 3.7, 3.8**
    """
    config = _make_loop_config(profit_factor_floor=1.0)
    
    gate1_result = _make_gate1_result(
        total_trades=100,
        max_drawdown=15.0,
        profit_factor=profit_factor,
        expectancy=0.5,
    )
    
    failures = HardFilterService.evaluate_post_gate1(
        gate1_result, config, trades=None
    )
    
    # Check if filter 4 failed
    filter_4_failures = [f for f in failures if f.filter_name == "profit_factor_floor"]
    
    assert len(filter_4_failures) == 1, (
        f"Preservation violated: Filter 4 (profit_factor_floor) did not fail correctly.\n"
        f"Expected: 1 failure (pf={profit_factor} < floor={config.profit_factor_floor})\n"
        f"Actual: {len(filter_4_failures)} failures\n"
        f"This indicates a regression: filter 4 should reject iterations with low profit factor."
    )
    
    # Verify the failure reason
    failure = filter_4_failures[0]
    assert "profit factor" in failure.reason.lower(), (
        f"Preservation violated: Filter 4 failure reason does not mention profit factor.\n"
        f"Reason: {failure.reason}\n"
    )


@pytest.mark.preservation
@given(
    expectancy=st.floats(min_value=-2.0, max_value=-0.01),
)
@h_settings(max_examples=10, deadline=None)
def test_preservation_filter_5_expectancy_floor_fails(expectancy):
    """
    **Property 2: Preservation** - Filter 5 (expectancy_floor) Fails Correctly
    
    This test verifies that filter 5 (expectancy_floor) correctly rejects
    iterations with negative expectancy.
    
    EXPECTED OUTCOME on unfixed code: PASS
      Filter 5 fails when expectancy < 0.0.
      
    EXPECTED OUTCOME after fix: PASS (no regression)
      Filter 5 continues to fail correctly.
    
    **Validates: Requirements 3.2, 3.7, 3.8**
    """
    config = _make_loop_config()
    
    gate1_result = _make_gate1_result(
        total_trades=100,
        max_drawdown=15.0,
        profit_factor=1.5,
        expectancy=expectancy,
    )
    
    failures = HardFilterService.evaluate_post_gate1(
        gate1_result, config, trades=None
    )
    
    # Check if filter 5 failed
    filter_5_failures = [f for f in failures if f.filter_name == "expectancy_floor"]
    
    assert len(filter_5_failures) == 1, (
        f"Preservation violated: Filter 5 (expectancy_floor) did not fail correctly.\n"
        f"Expected: 1 failure (exp={expectancy} < 0.0)\n"
        f"Actual: {len(filter_5_failures)} failures\n"
        f"This indicates a regression: filter 5 should reject iterations with negative expectancy."
    )
    
    # Verify the failure reason
    failure = filter_5_failures[0]
    assert "expectancy" in failure.reason.lower(), (
        f"Preservation violated: Filter 5 failure reason does not mention expectancy.\n"
        f"Reason: {failure.reason}\n"
    )


@pytest.mark.preservation
def test_preservation_filters_1_2_4_5_simple():
    """
    **Property 2: Preservation** - Hard Filter Evaluation (Simple Case)
    
    A simpler, non-property-based version of the preservation test.
    This test directly checks that filters 1, 2, 4, 5 are evaluated
    correctly after Gate 1 completion.
    
    EXPECTED OUTCOME on unfixed code: PASS
      Filters 1, 2, 4, 5 are evaluated correctly.
      
    EXPECTED OUTCOME after fix: PASS (no regression)
      Filters 1, 2, 4, 5 continue to be evaluated correctly.
    
    **Validates: Requirements 3.2, 3.7, 3.8**
    """
    config = _make_loop_config(
        target_min_trades=30,
        target_max_drawdown=20.0,
        profit_factor_floor=1.0,
    )
    
    # Test case 1: All filters pass
    gate1_result = _make_gate1_result(
        total_trades=100,
        max_drawdown=15.0,
        profit_factor=1.5,
        expectancy=0.5,
    )
    
    failures = HardFilterService.evaluate_post_gate1(
        gate1_result, config, trades=None
    )
    
    relevant_failures = [
        f for f in failures
        if f.filter_name in ["min_trade_count", "max_drawdown", "profit_factor_floor", "expectancy_floor"]
    ]
    
    assert len(relevant_failures) == 0, (
        f"Preservation violated: Filters 1, 2, 4, 5 failed when they should pass.\n"
        f"Failures: {[f.filter_name for f in relevant_failures]}"
    )
    
    # Test case 2: Filter 1 fails (too few trades)
    gate1_result = _make_gate1_result(
        total_trades=20,
        max_drawdown=15.0,
        profit_factor=1.5,
        expectancy=0.5,
    )
    
    failures = HardFilterService.evaluate_post_gate1(
        gate1_result, config, trades=None
    )
    
    filter_1_failures = [f for f in failures if f.filter_name == "min_trade_count"]
    assert len(filter_1_failures) == 1, (
        "Preservation violated: Filter 1 did not fail for too few trades."
    )
    
    # Test case 3: Filter 2 fails (excessive drawdown)
    gate1_result = _make_gate1_result(
        total_trades=100,
        max_drawdown=25.0,
        profit_factor=1.5,
        expectancy=0.5,
    )
    
    failures = HardFilterService.evaluate_post_gate1(
        gate1_result, config, trades=None
    )
    
    filter_2_failures = [f for f in failures if f.filter_name == "max_drawdown"]
    assert len(filter_2_failures) == 1, (
        "Preservation violated: Filter 2 did not fail for excessive drawdown."
    )
    
    # Test case 4: Filter 4 fails (low profit factor)
    gate1_result = _make_gate1_result(
        total_trades=100,
        max_drawdown=15.0,
        profit_factor=0.8,
        expectancy=0.5,
    )
    
    failures = HardFilterService.evaluate_post_gate1(
        gate1_result, config, trades=None
    )
    
    filter_4_failures = [f for f in failures if f.filter_name == "profit_factor_floor"]
    assert len(filter_4_failures) == 1, (
        "Preservation violated: Filter 4 did not fail for low profit factor."
    )
    
    # Test case 5: Filter 5 fails (negative expectancy)
    gate1_result = _make_gate1_result(
        total_trades=100,
        max_drawdown=15.0,
        profit_factor=1.5,
        expectancy=-0.5,
    )
    
    failures = HardFilterService.evaluate_post_gate1(
        gate1_result, config, trades=None
    )
    
    filter_5_failures = [f for f in failures if f.filter_name == "expectancy_floor"]
    assert len(filter_5_failures) == 1, (
        "Preservation violated: Filter 5 did not fail for negative expectancy."
    )


@pytest.mark.preservation
def test_preservation_loop_service_evaluate_gate1_hard_filters():
    """
    **Property 2: Preservation** - LoopService.evaluate_gate1_hard_filters()
    
    This test verifies that LoopService.evaluate_gate1_hard_filters() correctly
    delegates to HardFilterService.evaluate_post_gate1() and returns the same
    results for filters 1, 2, 4, 5.
    
    EXPECTED OUTCOME on unfixed code: PASS
      LoopService correctly delegates to HardFilterService.
      
    EXPECTED OUTCOME after fix: PASS (no regression)
      LoopService continues to delegate correctly.
    
    **Validates: Requirements 3.2, 3.7, 3.8**
    """
    config = _make_loop_config(
        target_min_trades=30,
        target_max_drawdown=20.0,
        profit_factor_floor=1.0,
    )
    
    gate1_result = _make_gate1_result(
        total_trades=100,
        max_drawdown=15.0,
        profit_factor=1.5,
        expectancy=0.5,
    )
    
    # Create a LoopService instance with mocked ImproveService
    from app.core.services.improve_service import ImproveService
    mock_improve_service = MagicMock(spec=ImproveService)
    loop_service = LoopService(improve_service=mock_improve_service)
    
    # Call evaluate_gate1_hard_filters (without trades parameter)
    failures = loop_service.evaluate_gate1_hard_filters(
        gate1_result, config, trades=None
    )
    
    # Filter out failures from filters 3, 6, 7
    relevant_failures = [
        f for f in failures
        if f.filter_name in ["min_trade_count", "max_drawdown", "profit_factor_floor", "expectancy_floor"]
    ]
    
    # Assert: Filters 1, 2, 4, 5 should pass
    assert len(relevant_failures) == 0, (
        f"Preservation violated: LoopService.evaluate_gate1_hard_filters() "
        f"returned failures for filters 1, 2, 4, 5 when they should pass.\n"
        f"Failures: {[f.filter_name for f in relevant_failures]}\n"
        f"This indicates a regression: LoopService should correctly delegate "
        f"to HardFilterService and return the same results."
    )
    
    # Test with failing filters
    gate1_result_fail = _make_gate1_result(
        total_trades=20,  # Too few trades
        max_drawdown=25.0,  # Excessive drawdown
        profit_factor=0.8,  # Low profit factor
        expectancy=-0.5,  # Negative expectancy
    )
    
    failures = loop_service.evaluate_gate1_hard_filters(
        gate1_result_fail, config, trades=None
    )
    
    # Check that all 4 filters failed
    filter_1_failures = [f for f in failures if f.filter_name == "min_trade_count"]
    filter_2_failures = [f for f in failures if f.filter_name == "max_drawdown"]
    filter_4_failures = [f for f in failures if f.filter_name == "profit_factor_floor"]
    filter_5_failures = [f for f in failures if f.filter_name == "expectancy_floor"]
    
    assert len(filter_1_failures) == 1, (
        "Preservation violated: Filter 1 did not fail via LoopService."
    )
    assert len(filter_2_failures) == 1, (
        "Preservation violated: Filter 2 did not fail via LoopService."
    )
    assert len(filter_4_failures) == 1, (
        "Preservation violated: Filter 4 did not fail via LoopService."
    )
    assert len(filter_5_failures) == 1, (
        "Preservation violated: Filter 5 did not fail via LoopService."
    )
