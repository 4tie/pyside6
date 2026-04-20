"""
Preservation property test for Property 2: Loop Behavior with Existing Baseline.

This test encodes the EXPECTED preservation behavior and is designed to PASS on
the unfixed code, confirming that when a loop starts with an existing baseline
(previous diagnosis input), the system proceeds normally to the first iteration
without running the baseline backtest again.

**Property 2: Preservation** - Loop starts normally when baseline exists

After the fix is applied, this test should STILL PASS (no regression).

**Validates: Requirements 3.1, 3.2, 3.3**
"""
import pytest
from unittest.mock import MagicMock, patch, call
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.ui.pages.loop_page import LoopPage
from app.app_state.settings_state import SettingsState
from app.core.models.settings_models import AppSettings
from app.core.models.loop_models import LoopConfig
from app.core.models.diagnosis_models import DiagnosisInput
from app.core.backtests.results_models import BacktestSummary, BacktestResults

from hypothesis import given, settings as h_settings, HealthCheck, assume
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# QApplication fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def qapp():
    """Create or reuse a QApplication for the test session."""
    app = QApplication.instance() or QApplication([])
    yield app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings_state(tmp_path) -> SettingsState:
    """Return a real SettingsState whose settings_service returns a valid AppSettings."""
    state = SettingsState()
    settings = AppSettings(
        user_data_path=str(tmp_path / "user_data"),
        python_executable="python",
        freqtrade_executable="freqtrade",
        venv_path=str(tmp_path / "venv"),
    )
    state.settings_service.load_settings = MagicMock(return_value=settings)
    state.settings_service.save_settings = MagicMock()
    return state


def _make_loop_config(strategy: str = "TestStrategy", timeframe: str = "5m") -> LoopConfig:
    """Return a minimal LoopConfig for testing."""
    return LoopConfig(
        strategy=strategy,
        timeframe=timeframe,
        max_iterations=5,
        target_profit_pct=5.0,
        target_win_rate=55.0,
        target_max_drawdown=20.0,
        target_min_trades=30,
        date_from="20240101",
        date_to="20240131",
        oos_split_pct=20.0,
    )


def _make_diagnosis_input(strategy: str = "TestStrategy", timeframe: str = "5m") -> DiagnosisInput:
    """Return a mock DiagnosisInput with realistic baseline data."""
    in_sample_summary = BacktestSummary(
        strategy=strategy,
        timeframe=timeframe,
        total_trades=100,
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
        max_drawdown=15.0,
        max_drawdown_abs=15.0,
        trade_duration_avg=120,
    )
    
    return DiagnosisInput(
        in_sample=in_sample_summary,
        oos_summary=None,
        fold_summaries=None,
        trade_profit_contributions=None,
        drawdown_periods=None,
        atr_spike_periods=None,
    )


# ---------------------------------------------------------------------------
# Preservation property test
# ---------------------------------------------------------------------------

@pytest.mark.preservation
@given(
    strategy_name=st.sampled_from(["TestStrategy", "MyStrategy", "AnotherStrategy"]),
    timeframe=st.sampled_from(["5m", "15m", "1h", "4h"]),
    total_trades=st.integers(min_value=50, max_value=200),
    win_rate=st.floats(min_value=40.0, max_value=80.0),
)
@h_settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_preservation_loop_with_existing_baseline(
    qapp, tmp_path, strategy_name, timeframe, total_trades, win_rate
):
    """
    **Property 2: Preservation** - Loop Behavior with Existing Baseline
    
    Preservation condition: NOT isBugCondition1(input) where:
      - input.has_previous_diagnosis_input == True
      - Loop starts with existing baseline
    
    This test verifies that when a loop starts with an existing baseline
    (previous diagnosis input), the system proceeds normally to the first
    iteration WITHOUT running the baseline backtest again.
    
    EXPECTED OUTCOME on unfixed code: PASS
      The loop uses the existing diagnosis input and proceeds to iteration 1.
      
    EXPECTED OUTCOME after fix: PASS (no regression)
      The loop continues to use the existing diagnosis input and proceeds
      to iteration 1 without running baseline again.
    
    **Validates: Requirements 3.1, 3.2, 3.3**
    """
    settings_state = _make_settings_state(tmp_path)
    
    # Mock the ImproveService to avoid actual strategy loading
    from app.core.services.improve_service import ImproveService
    with patch.object(ImproveService, "get_available_strategies", return_value=[strategy_name]):
        with patch.object(ImproveService, "load_baseline_params", return_value={}):
            page = LoopPage(settings_state)
    
    # Create a loop config
    config = _make_loop_config(strategy=strategy_name, timeframe=timeframe)
    
    # Create a realistic diagnosis input (existing baseline)
    diagnosis_input = _make_diagnosis_input(strategy=strategy_name, timeframe=timeframe)
    diagnosis_input.in_sample.total_trades = total_trades
    diagnosis_input.in_sample.win_rate = win_rate
    
    # Set the existing diagnosis input (this is the preservation condition)
    page._latest_diagnosis_input = diagnosis_input
    
    # Call _current_diagnosis_seed() - should return the existing baseline
    seed_summary, seed_input = page._current_diagnosis_seed(config)
    
    # Assert: The returned summary should be the existing baseline, not a dummy
    assert seed_summary is diagnosis_input.in_sample, (
        f"Preservation violated: _current_diagnosis_seed() did not return the existing baseline.\n"
        f"Expected: Existing diagnosis input with {total_trades} trades and {win_rate}% win rate\n"
        f"Actual: Different summary object\n"
        f"This indicates a regression: the loop should use the existing baseline when available."
    )
    
    # Assert: seed_input should be the existing diagnosis input
    assert seed_input is diagnosis_input, (
        f"Preservation violated: _current_diagnosis_seed() did not return the existing diagnosis input.\n"
        f"Expected: Existing diagnosis input object\n"
        f"Actual: Different input object\n"
        f"This indicates a regression: the loop should use the existing diagnosis input when available."
    )
    
    # Assert: The summary should have the expected values (not dummy values)
    assert seed_summary.total_trades == total_trades, (
        f"Preservation violated: Summary total_trades does not match existing baseline.\n"
        f"Expected: {total_trades}\n"
        f"Actual: {seed_summary.total_trades}\n"
    )
    
    assert seed_summary.win_rate == win_rate, (
        f"Preservation violated: Summary win_rate does not match existing baseline.\n"
        f"Expected: {win_rate}\n"
        f"Actual: {seed_summary.win_rate}\n"
    )
    
    # Assert: The summary should NOT be the dummy values
    is_dummy = (
        seed_summary.total_trades == 50
        and seed_summary.win_rate == 50.0
        and seed_summary.total_profit == 0.0
        and seed_summary.avg_profit == 0.0
    )
    
    assert not is_dummy, (
        f"Preservation violated: _current_diagnosis_seed() returned dummy values "
        f"even though an existing baseline was provided.\n"
        f"This indicates a regression: the loop should use the existing baseline, "
        f"not fabricate a dummy."
    )


@pytest.mark.preservation
def test_preservation_loop_with_existing_baseline_simple(qapp, tmp_path):
    """
    **Property 2: Preservation** - Loop Behavior with Existing Baseline (Simple Case)
    
    A simpler, non-property-based version of the preservation test.
    This test directly checks that when an existing baseline is provided,
    the loop uses it instead of running a new baseline backtest.
    
    EXPECTED OUTCOME on unfixed code: PASS
      The loop uses the existing diagnosis input.
      
    EXPECTED OUTCOME after fix: PASS (no regression)
      The loop continues to use the existing diagnosis input.
    
    **Validates: Requirements 3.1, 3.2, 3.3**
    """
    strategy_name = "TestStrategy"
    timeframe = "5m"
    
    settings_state = _make_settings_state(tmp_path)
    
    from app.core.services.improve_service import ImproveService
    with patch.object(ImproveService, "get_available_strategies", return_value=[strategy_name]):
        with patch.object(ImproveService, "load_baseline_params", return_value={}):
            page = LoopPage(settings_state)
    
    config = _make_loop_config(strategy=strategy_name, timeframe=timeframe)
    
    # Create an existing baseline with specific values
    diagnosis_input = _make_diagnosis_input(strategy=strategy_name, timeframe=timeframe)
    diagnosis_input.in_sample.total_trades = 100
    diagnosis_input.in_sample.win_rate = 60.0
    diagnosis_input.in_sample.total_profit = 150.0
    
    # Set the existing diagnosis input
    page._latest_diagnosis_input = diagnosis_input
    
    # Call _current_diagnosis_seed()
    seed_summary, seed_input = page._current_diagnosis_seed(config)
    
    # Verify the existing baseline is returned
    assert seed_summary is diagnosis_input.in_sample, (
        "Preservation violated: _current_diagnosis_seed() did not return the existing baseline."
    )
    
    assert seed_input is diagnosis_input, (
        "Preservation violated: _current_diagnosis_seed() did not return the existing diagnosis input."
    )
    
    # Verify the values match the existing baseline
    assert seed_summary.total_trades == 100
    assert seed_summary.win_rate == 60.0
    assert seed_summary.total_profit == 150.0
    
    # Verify it's not the dummy
    is_dummy = (
        seed_summary.total_trades == 50
        and seed_summary.win_rate == 50.0
        and seed_summary.total_profit == 0.0
    )
    
    assert not is_dummy, (
        "Preservation violated: _current_diagnosis_seed() returned dummy values "
        "even though an existing baseline was provided."
    )


@pytest.mark.preservation
def test_preservation_no_duplicate_baseline_run(qapp, tmp_path):
    """
    **Property 2: Preservation** - No Duplicate Baseline Run
    
    This test verifies that when a loop has completed at least one iteration
    (so _latest_diagnosis_input exists), subsequent iterations do NOT run
    the baseline backtest again. The loop should proceed directly to prepare
    the next iteration using the existing diagnosis input.
    
    EXPECTED OUTCOME on unfixed code: PASS
      The baseline backtest is not run for subsequent iterations.
      
    EXPECTED OUTCOME after fix: PASS (no regression)
      The baseline backtest continues to not run for subsequent iterations.
    
    **Validates: Requirements 3.1, 3.2, 3.3**
    """
    strategy_name = "TestStrategy"
    timeframe = "5m"
    
    settings_state = _make_settings_state(tmp_path)
    
    from app.core.services.improve_service import ImproveService
    with patch.object(ImproveService, "get_available_strategies", return_value=[strategy_name]):
        with patch.object(ImproveService, "load_baseline_params", return_value={}):
            page = LoopPage(settings_state)
    
    config = _make_loop_config(strategy=strategy_name, timeframe=timeframe)
    
    # Create an existing baseline (from a previous iteration's Gate 1 completion)
    diagnosis_input = _make_diagnosis_input(strategy=strategy_name, timeframe=timeframe)
    
    # Set the existing diagnosis input
    page._latest_diagnosis_input = diagnosis_input
    
    # Set up the loop service with the config
    page._loop_service._config = config
    page._loop_service._result = MagicMock()
    
    # Simulate that we've already completed one iteration
    # (so is_first_iteration will be False)
    mock_iteration_1 = MagicMock()
    mock_iteration_1.iteration_number = 1
    page._loop_service._result.iterations = [mock_iteration_1]
    
    # Mock _run_baseline_backtest to track if it's called
    with patch.object(page, "_run_baseline_backtest") as mock_baseline:
        # Mock _start_gate_backtest to avoid actual backtest
        with patch.object(page, "_start_gate_backtest"):
            # Mock prepare_sandbox to avoid file operations
            with patch.object(page._improve_service, "prepare_sandbox", return_value=tmp_path / "sandbox"):
                # Mock prepare_next_iteration to return a valid iteration
                mock_iteration_2 = MagicMock()
                mock_iteration_2.iteration_number = 2
                mock_iteration_2.params_after = {}
                
                with patch.object(
                    page._loop_service,
                    "prepare_next_iteration",
                    return_value=(mock_iteration_2, [])
                ):
                    # Mock should_continue to return True
                    with patch.object(page._loop_service, "should_continue", return_value=True):
                        # Call _run_next_iteration - this should NOT call _run_baseline_backtest
                        # because we're on iteration 2 (not the first iteration)
                        try:
                            page._run_next_iteration()
                        except Exception:
                            # Ignore errors from missing dependencies
                            pass
    
    # Assert: _run_baseline_backtest should NOT have been called
    # because this is not the first iteration
    assert not mock_baseline.called, (
        f"Preservation violated: _run_baseline_backtest() was called for iteration 2.\n"
        f"Expected: Baseline backtest should NOT run for subsequent iterations\n"
        f"Actual: _run_baseline_backtest() was called {mock_baseline.call_count} time(s)\n"
        f"This indicates a regression: the loop should use the existing baseline "
        f"from the previous iteration and proceed directly to the next iteration "
        f"without running baseline again."
    )


@pytest.mark.preservation
def test_preservation_loop_proceeds_to_first_iteration(qapp, tmp_path):
    """
    **Property 2: Preservation** - Loop Proceeds to Next Iteration
    
    This test verifies that when a loop has completed at least one iteration
    (so _latest_diagnosis_input exists), the next iteration proceeds to prepare
    and execute using the existing diagnosis input as the seed.
    
    EXPECTED OUTCOME on unfixed code: PASS
      The loop proceeds to next iteration with existing baseline.
      
    EXPECTED OUTCOME after fix: PASS (no regression)
      The loop continues to proceed to next iteration with existing baseline.
    
    **Validates: Requirements 3.1, 3.2, 3.3**
    """
    strategy_name = "TestStrategy"
    timeframe = "5m"
    
    settings_state = _make_settings_state(tmp_path)
    
    from app.core.services.improve_service import ImproveService
    with patch.object(ImproveService, "get_available_strategies", return_value=[strategy_name]):
        with patch.object(ImproveService, "load_baseline_params", return_value={}):
            page = LoopPage(settings_state)
    
    config = _make_loop_config(strategy=strategy_name, timeframe=timeframe)
    
    # Create an existing baseline (from a previous iteration's Gate 1 completion)
    diagnosis_input = _make_diagnosis_input(strategy=strategy_name, timeframe=timeframe)
    
    # Set the existing diagnosis input
    page._latest_diagnosis_input = diagnosis_input
    
    # Set up the loop service with the config
    page._loop_service._config = config
    page._loop_service._result = MagicMock()
    
    # Simulate that we've already completed one iteration
    mock_iteration_1 = MagicMock()
    mock_iteration_1.iteration_number = 1
    page._loop_service._result.iterations = [mock_iteration_1]
    
    # Track if prepare_next_iteration is called with the correct seed
    prepare_called = False
    seed_used = None
    
    def mock_prepare_next_iteration(latest_summary, diagnosis_input=None):
        nonlocal prepare_called, seed_used
        prepare_called = True
        seed_used = latest_summary
        mock_iteration_2 = MagicMock()
        mock_iteration_2.iteration_number = 2
        mock_iteration_2.params_after = {}
        return (mock_iteration_2, [])
    
    with patch.object(page, "_run_baseline_backtest"):
        with patch.object(page, "_start_gate_backtest"):
            with patch.object(page._improve_service, "prepare_sandbox", return_value=tmp_path / "sandbox"):
                with patch.object(
                    page._loop_service,
                    "prepare_next_iteration",
                    side_effect=mock_prepare_next_iteration
                ):
                    with patch.object(page._loop_service, "should_continue", return_value=True):
                        try:
                            page._run_next_iteration()
                        except Exception:
                            pass
    
    # Assert: prepare_next_iteration should have been called
    assert prepare_called, (
        f"Preservation violated: prepare_next_iteration() was not called.\n"
        f"Expected: Loop should proceed to next iteration with existing baseline\n"
        f"Actual: prepare_next_iteration() was not called\n"
        f"This indicates a regression: the loop should use the existing baseline "
        f"and proceed to prepare the next iteration."
    )
    
    # Assert: The seed used should be the existing baseline
    assert seed_used is diagnosis_input.in_sample, (
        f"Preservation violated: prepare_next_iteration() was not called with the existing baseline.\n"
        f"Expected: Existing baseline summary\n"
        f"Actual: Different summary object\n"
        f"This indicates a regression: the loop should use the existing baseline as the seed."
    )
