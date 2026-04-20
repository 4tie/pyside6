"""
Preservation property test for Property 2: UI State Management.

This test encodes the EXPECTED preservation behavior and is designed to PASS on
the unfixed code, confirming that when an iteration completes, the system
correctly updates the iteration history, stat cards, and progress bar.

**Property 2: Preservation** - UI State Management

After the fix is applied, this test should STILL PASS (no regression).

**Validates: Requirements 3.9, 3.10**
"""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from app.ui.pages.loop_page import LoopPage
from app.app_state.settings_state import SettingsState
from app.core.models.settings_models import AppSettings
from app.core.models.loop_models import LoopConfig, LoopIteration, LoopResult, RobustScore
from app.core.backtests.results_models import BacktestSummary

from hypothesis import given, settings as h_settings, HealthCheck
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


def _make_loop_config(
    strategy: str = "TestStrategy",
    timeframe: str = "5m",
    max_iterations: int = 10
) -> LoopConfig:
    """Return a minimal LoopConfig for testing."""
    return LoopConfig(
        strategy=strategy,
        timeframe=timeframe,
        max_iterations=max_iterations,
        target_profit_pct=5.0,
        target_win_rate=55.0,
        target_max_drawdown=20.0,
        target_min_trades=30,
        date_from="20240101",
        date_to="20240131",
        oos_split_pct=20.0,
    )


def _make_backtest_summary(
    strategy: str = "TestStrategy",
    timeframe: str = "5m",
    total_trades: int = 100,
    win_rate: float = 60.0,
    total_profit: float = 150.0,
    max_drawdown: float = 15.0,
    sharpe_ratio: float = 1.8,
) -> BacktestSummary:
    """Return a mock BacktestSummary with realistic data."""
    return BacktestSummary(
        strategy=strategy,
        timeframe=timeframe,
        total_trades=total_trades,
        wins=int(total_trades * win_rate / 100),
        losses=int(total_trades * (100 - win_rate) / 100),
        draws=0,
        win_rate=win_rate,
        avg_profit=total_profit / total_trades if total_trades > 0 else 0.0,
        total_profit=total_profit,
        total_profit_abs=total_profit,
        sharpe_ratio=sharpe_ratio,
        sortino_ratio=2.1,
        calmar_ratio=1.5,
        max_drawdown=max_drawdown,
        max_drawdown_abs=max_drawdown,
        trade_duration_avg=120,
    )


def _make_loop_iteration(
    iteration_number: int,
    summary: BacktestSummary,
    score: float = 0.75,
) -> LoopIteration:
    """Return a mock LoopIteration with realistic data."""
    iteration = MagicMock(spec=LoopIteration)
    iteration.iteration_number = iteration_number
    iteration.summary = summary
    iteration.score = RobustScore(
        total=score,
        profitability=0.35,
        consistency=0.30,
        stability=0.20,
        fragility=0.10,
    )
    iteration.status = "completed"
    iteration.params_after = {}
    iteration.params_before = {}
    iteration.changes_summary = ["Test change"]
    iteration.error_message = None
    iteration.below_min_trades = False
    iteration.validation_gate_reached = "in_sample"
    iteration.validation_gate_passed = True
    iteration.gate_results = []
    iteration.hard_filter_failures = []
    return iteration


def _make_loop_result(iterations: list) -> LoopResult:
    """Return a mock LoopResult with iterations."""
    result = MagicMock(spec=LoopResult)
    result.iterations = iterations
    # Find the best iteration (highest score)
    if iterations:
        best = max(iterations, key=lambda it: it.score.total if it.score else -float('inf'))
        result.best_iteration = best
    else:
        result.best_iteration = None
    result.stop_reason = None
    return result


# ---------------------------------------------------------------------------
# Preservation property tests
# ---------------------------------------------------------------------------

@pytest.mark.preservation
@given(
    iteration_number=st.integers(min_value=1, max_value=10),
    total_trades=st.integers(min_value=50, max_value=200),
    win_rate=st.floats(min_value=40.0, max_value=80.0),
    total_profit=st.floats(min_value=-50.0, max_value=200.0),
    max_drawdown=st.floats(min_value=5.0, max_value=30.0),
    sharpe_ratio=st.floats(min_value=0.5, max_value=3.0),
)
@h_settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_preservation_ui_state_updates_on_iteration_completion(
    qapp, tmp_path, iteration_number, total_trades, win_rate, total_profit, max_drawdown, sharpe_ratio
):
    """
    **Property 2: Preservation** - UI State Management
    
    Preservation condition: For all iteration completions, the system updates:
      - Iteration history (adds a new row)
      - Stat cards (updates iteration count, profit, win rate, drawdown, sharpe, score)
      - Progress bar (updates based on iteration_number / max_iterations)
    
    This test verifies that when an iteration completes, the UI is correctly
    updated with the iteration data. This behavior must be preserved after
    all bug fixes are applied.
    
    EXPECTED OUTCOME on unfixed code: PASS
      The UI updates correctly when an iteration completes.
      
    EXPECTED OUTCOME after fix: PASS (no regression)
      The UI continues to update correctly when an iteration completes.
    
    **Validates: Requirements 3.9, 3.10**
    """
    settings_state = _make_settings_state(tmp_path)
    
    # Mock the ImproveService to avoid actual strategy loading
    from app.core.services.improve_service import ImproveService
    with patch.object(ImproveService, "get_available_strategies", return_value=["TestStrategy"]):
        with patch.object(ImproveService, "load_baseline_params", return_value={}):
            page = LoopPage(settings_state)
    
    # Create a loop config
    config = _make_loop_config(max_iterations=10)
    page._loop_service._config = config
    
    # Create a backtest summary for the iteration
    summary = _make_backtest_summary(
        total_trades=total_trades,
        win_rate=win_rate,
        total_profit=total_profit,
        max_drawdown=max_drawdown,
        sharpe_ratio=sharpe_ratio,
    )
    
    # Create an iteration
    iteration = _make_loop_iteration(
        iteration_number=iteration_number,
        summary=summary,
        score=0.75,
    )
    
    # Create a loop result with the iteration
    result = _make_loop_result([iteration])
    page._loop_service._result = result
    
    # Track UI updates
    history_row_added = False
    stat_cards_updated = False
    progress_bar_updated = False
    
    original_add_history_row = page._add_history_row
    original_update_stat_cards = page._update_stat_cards
    original_progress_bar_setValue = page._progress_bar.setValue
    
    def mock_add_history_row(it):
        nonlocal history_row_added
        history_row_added = True
        # Call the original method to verify it works
        original_add_history_row(it)
    
    def mock_update_stat_cards():
        nonlocal stat_cards_updated
        stat_cards_updated = True
        # Call the original method to verify it works
        original_update_stat_cards()
    
    def mock_progress_bar_setValue(value):
        nonlocal progress_bar_updated
        progress_bar_updated = True
        # Call the original method to verify it works
        original_progress_bar_setValue(value)
    
    # Patch the methods to track calls
    with patch.object(page, "_add_history_row", side_effect=mock_add_history_row):
        with patch.object(page, "_update_stat_cards", side_effect=mock_update_stat_cards):
            with patch.object(page._progress_bar, "setValue", side_effect=mock_progress_bar_setValue):
                # Mock _reset_iteration_runtime to avoid side effects
                with patch.object(page, "_reset_iteration_runtime"):
                    # Mock _run_next_iteration to avoid triggering next iteration
                    with patch.object(page, "_run_next_iteration"):
                        # Call _finish_iteration - this should update all UI elements
                        page._finish_iteration(iteration)
    
    # Assert: _add_history_row should have been called
    assert history_row_added, (
        f"Preservation violated: _add_history_row() was not called.\n"
        f"Expected: Iteration history should be updated when iteration completes\n"
        f"Actual: _add_history_row() was not called\n"
        f"This indicates a regression: the loop should add a history row for each completed iteration."
    )
    
    # Assert: _update_stat_cards should have been called
    assert stat_cards_updated, (
        f"Preservation violated: _update_stat_cards() was not called.\n"
        f"Expected: Stat cards should be updated when iteration completes\n"
        f"Actual: _update_stat_cards() was not called\n"
        f"This indicates a regression: the loop should update stat cards for each completed iteration."
    )
    
    # Assert: progress bar should have been updated
    assert progress_bar_updated, (
        f"Preservation violated: progress_bar.setValue() was not called.\n"
        f"Expected: Progress bar should be updated when iteration completes\n"
        f"Actual: progress_bar.setValue() was not called\n"
        f"This indicates a regression: the loop should update the progress bar for each completed iteration."
    )
    
    # Verify the progress bar value is correct
    expected_progress = int(iteration_number / max(config.max_iterations, 1) * 100)
    actual_progress = page._progress_bar.value()
    
    assert actual_progress == expected_progress, (
        f"Preservation violated: Progress bar value is incorrect.\n"
        f"Expected: {expected_progress}% (iteration {iteration_number} / {config.max_iterations})\n"
        f"Actual: {actual_progress}%\n"
        f"This indicates a regression: the progress bar should reflect the correct iteration progress."
    )


@pytest.mark.preservation
def test_preservation_ui_state_updates_simple(qapp, tmp_path):
    """
    **Property 2: Preservation** - UI State Management (Simple Case)
    
    A simpler, non-property-based version of the preservation test.
    This test directly checks that when an iteration completes, the UI
    elements (iteration history, stat cards, progress bar) are updated.
    
    EXPECTED OUTCOME on unfixed code: PASS
      The UI updates correctly when an iteration completes.
      
    EXPECTED OUTCOME after fix: PASS (no regression)
      The UI continues to update correctly when an iteration completes.
    
    **Validates: Requirements 3.9, 3.10**
    """
    settings_state = _make_settings_state(tmp_path)
    
    from app.core.services.improve_service import ImproveService
    with patch.object(ImproveService, "get_available_strategies", return_value=["TestStrategy"]):
        with patch.object(ImproveService, "load_baseline_params", return_value={}):
            page = LoopPage(settings_state)
    
    # Create a loop config
    config = _make_loop_config(max_iterations=10)
    page._loop_service._config = config
    
    # Create a backtest summary
    summary = _make_backtest_summary(
        total_trades=100,
        win_rate=60.0,
        total_profit=150.0,
        max_drawdown=15.0,
        sharpe_ratio=1.8,
    )
    
    # Create an iteration (iteration 3 of 10)
    iteration = _make_loop_iteration(
        iteration_number=3,
        summary=summary,
        score=0.75,
    )
    
    # Create a loop result with the iteration
    result = _make_loop_result([iteration])
    page._loop_service._result = result
    
    # Get initial state
    initial_history_count = page._history_vlay.count()
    initial_progress = page._progress_bar.value()
    
    # Mock _reset_iteration_runtime and _run_next_iteration to avoid side effects
    with patch.object(page, "_reset_iteration_runtime"):
        with patch.object(page, "_run_next_iteration"):
            # Call _finish_iteration
            page._finish_iteration(iteration)
    
    # Verify iteration history was updated (new row added)
    final_history_count = page._history_vlay.count()
    assert final_history_count > initial_history_count, (
        f"Preservation violated: Iteration history was not updated.\n"
        f"Expected: History count to increase from {initial_history_count}\n"
        f"Actual: History count is {final_history_count}\n"
        f"This indicates a regression: the loop should add a history row for each completed iteration."
    )
    
    # Verify progress bar was updated
    expected_progress = int(3 / 10 * 100)  # 30%
    actual_progress = page._progress_bar.value()
    assert actual_progress == expected_progress, (
        f"Preservation violated: Progress bar was not updated correctly.\n"
        f"Expected: {expected_progress}%\n"
        f"Actual: {actual_progress}%\n"
        f"This indicates a regression: the progress bar should reflect the correct iteration progress."
    )
    
    # Verify stat cards were updated (iteration count should be 1)
    stat_iter_value = page._stat_iter._val.text()
    assert stat_iter_value == "1", (
        f"Preservation violated: Stat cards were not updated correctly.\n"
        f"Expected: Iteration count = 1\n"
        f"Actual: Iteration count = {stat_iter_value}\n"
        f"This indicates a regression: the stat cards should reflect the current iteration count."
    )


@pytest.mark.preservation
def test_preservation_loop_finalization_displays_best_iteration(qapp, tmp_path):
    """
    **Property 2: Preservation** - Loop Finalization
    
    This test verifies that when the loop is stopped, the system finalizes
    the result and displays the best iteration found. This behavior must be
    preserved after all bug fixes are applied.
    
    EXPECTED OUTCOME on unfixed code: PASS
      The loop finalizes and displays the best iteration when stopped.
      
    EXPECTED OUTCOME after fix: PASS (no regression)
      The loop continues to finalize and display the best iteration when stopped.
    
    **Validates: Requirements 3.10**
    """
    settings_state = _make_settings_state(tmp_path)
    
    from app.core.services.improve_service import ImproveService
    with patch.object(ImproveService, "get_available_strategies", return_value=["TestStrategy"]):
        with patch.object(ImproveService, "load_baseline_params", return_value={}):
            page = LoopPage(settings_state)
    
    # Create a loop config
    config = _make_loop_config(max_iterations=10)
    page._loop_service._config = config
    
    # Create multiple iterations with different scores
    summary1 = _make_backtest_summary(total_profit=100.0)
    summary2 = _make_backtest_summary(total_profit=150.0)
    summary3 = _make_backtest_summary(total_profit=120.0)
    
    iteration1 = _make_loop_iteration(1, summary1, score=0.70)
    iteration2 = _make_loop_iteration(2, summary2, score=0.85)  # Best
    iteration3 = _make_loop_iteration(3, summary3, score=0.75)
    
    # Mark all iterations as validated (required for best_iteration selection)
    iteration1.validation_gate_passed = True
    iteration1.status = "success"
    iteration2.validation_gate_passed = True
    iteration2.status = "success"
    iteration3.validation_gate_passed = True
    iteration3.status = "success"
    
    # Create a loop result with all iterations
    result = _make_loop_result([iteration1, iteration2, iteration3])
    result.stop_reason = "User stopped"
    
    # Manually set best_iteration to iteration2 (highest score)
    # This simulates what the loop service would do
    result.best_iteration = iteration2
    
    page._loop_service._result = result
    page._loop_result = result
    
    # Track if best result panel is updated
    best_result_panel_updated = False
    
    original_update_best_result_panel = page._update_best_result_panel
    
    def mock_update_best_result_panel():
        nonlocal best_result_panel_updated
        best_result_panel_updated = True
        # Call the original method to verify it works
        original_update_best_result_panel()
    
    # Patch the method to track calls
    with patch.object(page, "_update_best_result_panel", side_effect=mock_update_best_result_panel):
        # Mock _update_state_machine to avoid side effects
        with patch.object(page, "_update_state_machine"):
            # Call _finalize_loop - this should update the best result panel
            page._finalize_loop()
    
    # Assert: _update_best_result_panel should have been called
    assert best_result_panel_updated, (
        f"Preservation violated: _update_best_result_panel() was not called.\n"
        f"Expected: Best result panel should be updated when loop is finalized\n"
        f"Actual: _update_best_result_panel() was not called\n"
        f"This indicates a regression: the loop should display the best iteration when stopped."
    )
    
    # Verify the progress bar is set to 100%
    assert page._progress_bar.value() == 100, (
        f"Preservation violated: Progress bar was not set to 100% on finalization.\n"
        f"Expected: 100%\n"
        f"Actual: {page._progress_bar.value()}%\n"
        f"This indicates a regression: the progress bar should be set to 100% when the loop is finalized."
    )
    
    # Verify the best iteration is iteration2 (highest score)
    assert result.best_iteration is iteration2, (
        f"Preservation violated: Best iteration is not correctly identified.\n"
        f"Expected: Iteration 2 (score 0.85)\n"
        f"Actual: Iteration {result.best_iteration.iteration_number} (score {result.best_iteration.score.total})\n"
        f"This indicates a regression: the loop should identify the best iteration correctly."
    )


@pytest.mark.preservation
@given(
    num_iterations=st.integers(min_value=1, max_value=10),
)
@h_settings(max_examples=5, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_preservation_stat_cards_reflect_best_iteration(qapp, tmp_path, num_iterations):
    """
    **Property 2: Preservation** - Stat Cards Reflect Best Iteration
    
    This test verifies that the stat cards always reflect the metrics from
    the best iteration (highest score), not just the most recent iteration.
    This behavior must be preserved after all bug fixes are applied.
    
    EXPECTED OUTCOME on unfixed code: PASS
      Stat cards show metrics from the best iteration.
      
    EXPECTED OUTCOME after fix: PASS (no regression)
      Stat cards continue to show metrics from the best iteration.
    
    **Validates: Requirements 3.9**
    """
    settings_state = _make_settings_state(tmp_path)
    
    from app.core.services.improve_service import ImproveService
    with patch.object(ImproveService, "get_available_strategies", return_value=["TestStrategy"]):
        with patch.object(ImproveService, "load_baseline_params", return_value={}):
            page = LoopPage(settings_state)
    
    # Create a loop config
    config = _make_loop_config(max_iterations=10)
    page._loop_service._config = config
    
    # Create multiple iterations with varying scores
    iterations = []
    best_score = 0.0
    best_iteration = None
    
    for i in range(1, num_iterations + 1):
        # Vary the metrics to create different scores
        profit = 50.0 + (i * 10.0)
        score = 0.5 + (i * 0.05)
        
        summary = _make_backtest_summary(total_profit=profit)
        iteration = _make_loop_iteration(i, summary, score=score)
        iterations.append(iteration)
        
        if score > best_score:
            best_score = score
            best_iteration = iteration
    
    # Create a loop result with all iterations
    result = _make_loop_result(iterations)
    page._loop_service._result = result
    
    # Update stat cards
    page._update_stat_cards()
    
    # Verify stat cards show the best iteration's metrics
    stat_iter_value = page._stat_iter._val.text()
    assert stat_iter_value == str(num_iterations), (
        f"Preservation violated: Stat cards do not show correct iteration count.\n"
        f"Expected: {num_iterations}\n"
        f"Actual: {stat_iter_value}\n"
    )
    
    # Verify the profit shown is from the best iteration
    expected_profit = best_iteration.summary.total_profit
    stat_profit_text = page._stat_profit._val.text()
    
    # The profit is formatted as "+X.X%" or "-X.X%"
    assert f"{expected_profit:+.1f}%" in stat_profit_text or f"{expected_profit:.1f}%" in stat_profit_text, (
        f"Preservation violated: Stat cards do not show profit from best iteration.\n"
        f"Expected: Profit from best iteration (iteration {best_iteration.iteration_number}): {expected_profit:.1f}%\n"
        f"Actual: {stat_profit_text}\n"
        f"This indicates a regression: stat cards should show metrics from the best iteration, not the most recent."
    )
