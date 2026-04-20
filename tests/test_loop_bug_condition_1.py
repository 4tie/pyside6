"""
Bug condition exploration test for Bug 1: Fake First-Iteration Seed.

This test encodes the EXPECTED (correct) behavior and is designed to FAIL on
the unfixed code, confirming that when a loop starts without a previous diagnosis
input, the system fabricates a dummy BacktestSummary instead of running a real
baseline backtest.

Bug 1 — Fake baseline seed with hardcoded values (50 trades, 50% win rate, 0% profit)

After the fix is applied, this test should PASS.

**Validates: Requirements 1.1, 2.1, 2.2**
"""
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.ui.pages.loop_page import LoopPage
from app.app_state.settings_state import SettingsState
from app.core.models.settings_models import AppSettings
from app.core.models.loop_models import LoopConfig
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


def _make_loop_config(strategy: str = "TestStrategy") -> LoopConfig:
    """Return a minimal LoopConfig for testing."""
    return LoopConfig(
        strategy=strategy,
        timeframe="5m",
        max_iterations=5,
        target_profit_pct=5.0,
        target_win_rate=55.0,
        target_max_drawdown=20.0,
        target_min_trades=30,
        date_from="20240101",
        date_to="20240131",
        oos_split_pct=20.0,
    )


# ---------------------------------------------------------------------------
# Bug condition exploration test
# ---------------------------------------------------------------------------

@pytest.mark.bug_condition
@given(
    strategy_name=st.sampled_from(["TestStrategy", "MyStrategy", "AnotherStrategy"]),
)
@h_settings(max_examples=5, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_bug_condition_fake_baseline_seed_detection(qapp, tmp_path, strategy_name):
    """
    **Property 1: Expected Behavior** - Real Baseline Backtest Triggered
    
    Bug condition: isBugCondition1(input) where input.has_previous_diagnosis_input == False
    
    This test verifies that when a loop starts with no previous diagnosis input,
    the system correctly raises a RuntimeError from _current_diagnosis_seed(),
    which forces _on_start() to trigger a real baseline backtest.
    
    EXPECTED OUTCOME on unfixed code: FAIL
      The _current_diagnosis_seed() method returns a dummy BacktestSummary with:
      - total_trades = 50
      - win_rate = 50.0
      - total_profit = 0.0
      - avg_profit = 0.0
      
    EXPECTED OUTCOME after fix: PASS
      The _current_diagnosis_seed() method raises RuntimeError when no baseline exists,
      forcing the system to run a real baseline backtest via _on_start().
    
    **Validates: Requirements 1.1, 2.1, 2.2**
    """
    settings_state = _make_settings_state(tmp_path)
    
    # Mock the ImproveService to avoid actual strategy loading
    from app.core.services.improve_service import ImproveService
    with patch.object(ImproveService, "get_available_strategies", return_value=[strategy_name]):
        with patch.object(ImproveService, "load_baseline_params", return_value={}):
            page = LoopPage(settings_state)
    
    # Create a loop config
    config = _make_loop_config(strategy=strategy_name)
    
    # Ensure no previous diagnosis input exists (this is the bug condition)
    page._latest_diagnosis_input = None
    
    # After the fix, _current_diagnosis_seed() should raise RuntimeError
    # when no baseline exists, forcing _on_start() to run a baseline backtest
    with pytest.raises(RuntimeError, match="No baseline diagnosis input available"):
        seed_summary, seed_input = page._current_diagnosis_seed(config)
    
    # The test passes if RuntimeError is raised (correct behavior after fix)


@pytest.mark.bug_condition
def test_bug_condition_fake_baseline_seed_simple(qapp, tmp_path):
    """
    **Property 1: Expected Behavior** - Real Baseline Backtest Triggered (Simple Case)
    
    A simpler, non-property-based version of the bug condition test.
    This test directly checks that _current_diagnosis_seed() raises RuntimeError
    when no previous diagnosis input exists, forcing _on_start() to run a baseline.
    
    EXPECTED OUTCOME on unfixed code: FAIL
      The _current_diagnosis_seed() method returns the hardcoded dummy.
      
    EXPECTED OUTCOME after fix: PASS
      The _current_diagnosis_seed() method raises RuntimeError, forcing
      _on_start() to trigger a baseline backtest.
    
    **Validates: Requirements 1.1, 2.1, 2.2**
    """
    settings_state = _make_settings_state(tmp_path)
    
    from app.core.services.improve_service import ImproveService
    with patch.object(ImproveService, "get_available_strategies", return_value=["TestStrategy"]):
        with patch.object(ImproveService, "load_baseline_params", return_value={}):
            page = LoopPage(settings_state)
    
    config = _make_loop_config(strategy="TestStrategy")
    
    # Bug condition: no previous diagnosis input
    page._latest_diagnosis_input = None
    
    # After the fix, this should raise RuntimeError
    with pytest.raises(RuntimeError, match="No baseline diagnosis input available"):
        seed_summary, seed_input = page._current_diagnosis_seed(config)
    
    # The test passes if RuntimeError is raised (correct behavior after fix)
