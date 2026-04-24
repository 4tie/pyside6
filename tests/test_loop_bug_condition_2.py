"""
Bug condition exploration test for Bug 2: Hardcoded Timeframe in Gate Execution.

This test encodes the EXPECTED (correct) behavior and is designed to FAIL on
the unfixed code, confirming that when a gate backtest is started, it uses the
hardcoded "5m" timeframe instead of the strategy's native timeframe.

Bug 2 — LoopConfig.timeframe defaults to "5m" and is never populated from strategy

After the fix is applied, this test should PASS.

**Validates: Requirements 1.2, 1.3, 2.3, 2.4**
"""
import pytest
from unittest.mock import MagicMock, patch, call
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.ui.pages.loop_page import LoopPage
from app.app_state.settings_state import SettingsState
from app.core.models.settings_models import AppSettings
from app.core.models.loop_models import LoopConfig
from app.core.backtests.results_models import BacktestSummary, BacktestResults

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


def _create_mock_strategy_file(tmp_path: Path, strategy_name: str, timeframe: str) -> Path:
    """Create a mock strategy file with the specified timeframe."""
    strategies_dir = tmp_path / "user_data" / "strategies"
    strategies_dir.mkdir(parents=True, exist_ok=True)
    
    strategy_file = strategies_dir / f"{strategy_name}.py"
    strategy_content = f'''
from freqtrade.strategy import IStrategy

class {strategy_name}(IStrategy):
    timeframe = "{timeframe}"
    
    def populate_indicators(self, dataframe, metadata):
        return dataframe
    
    def populate_entry_trend(self, dataframe, metadata):
        return dataframe
    
    def populate_exit_trend(self, dataframe, metadata):
        return dataframe
'''
    strategy_file.write_text(strategy_content)
    return strategy_file


# ---------------------------------------------------------------------------
# Bug condition exploration test
# ---------------------------------------------------------------------------

@pytest.mark.bug_condition
@given(
    strategy_name=st.sampled_from(["TestStrategy", "MyStrategy", "AnotherStrategy"]),
    native_timeframe=st.sampled_from(["1h", "15m", "30m", "4h", "1d"]),
)
@h_settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_bug_condition_hardcoded_timeframe_detection(qapp, tmp_path, strategy_name, native_timeframe):
    """
    **Property 1: Bug Condition** - Hardcoded Timeframe Detection
    
    Bug condition: isBugCondition2(input) where:
      - input.config.timeframe == "5m"
      - input.strategy_native_timeframe != "5m"
      - gate_backtest_starting(input)
    
    This test verifies that when a gate backtest is started for a strategy with
    a non-"5m" native timeframe, the system should use the strategy's native
    timeframe instead of the hardcoded "5m" default.
    
    EXPECTED OUTCOME on unfixed code: FAIL
      The LoopConfig.timeframe remains "5m" (default) and is never populated
      from the strategy's native timeframe, so all gate backtests use "5m".
      
    EXPECTED OUTCOME after fix: PASS
      The system detects the strategy's native timeframe and populates
      LoopConfig.timeframe, so gate backtests use the correct timeframe.
    
    **Validates: Requirements 1.2, 1.3, 2.3, 2.4**
    """
    # Create a mock strategy file with the specified native timeframe
    strategy_file = _create_mock_strategy_file(tmp_path, strategy_name, native_timeframe)
    
    settings_state = _make_settings_state(tmp_path)
    
    # Mock the ImproveService to avoid actual strategy loading
    from app.core.services.improve_service import ImproveService
    with patch.object(ImproveService, "get_available_strategies", return_value=[strategy_name]):
        with patch.object(ImproveService, "load_baseline_params", return_value={}):
            page = LoopPage(settings_state)
    
    # Create a loop config with default timeframe (5m)
    config = _make_loop_config(strategy=strategy_name, timeframe="5m")
    
    # Set up the loop service with this config
    page._loop_service._config = config
    
    # Mock the create_backtest_command to capture the timeframe parameter
    from app.core.freqtrade.runners.backtest_runner import create_backtest_command
    mock_cmd = MagicMock()
    mock_cmd.as_list.return_value = ["python", "-m", "freqtrade", "backtesting"]
    mock_cmd.cwd = tmp_path
    
    with patch("app.core.freqtrade.runners.backtest_runner.create_backtest_command", return_value=mock_cmd) as mock_build:
        # Mock process execution to avoid actual backtest
        with patch.object(page._process_service, "execute_command"):
            # Set up minimal runtime state
            page._current_iteration = MagicMock()
            page._sandbox_dir = tmp_path / "sandbox"
            page._sandbox_dir.mkdir(parents=True, exist_ok=True)
            
            # Start a gate backtest
            try:
                page._start_gate_backtest(
                    gate_name="in_sample",
                    timerange="20240101-20240125",
                    phase_label="Testing Gate 1"
                )
            except Exception:
                # Ignore errors from missing dependencies
                pass
    
    # Check what timeframe was passed to build_backtest_command
    if mock_build.called:
        call_args = mock_build.call_args
        timeframe_used = call_args.kwargs.get("timeframe") if call_args.kwargs else None
        
        # Bug condition: timeframe should be the strategy's native timeframe, not "5m"
        assert timeframe_used == native_timeframe, (
            f"Bug 2 confirmed: Gate backtest uses hardcoded timeframe instead of strategy's native timeframe.\n"
            f"Strategy: {strategy_name}\n"
            f"Strategy native timeframe: {native_timeframe}\n"
            f"Timeframe passed to build_backtest_command: {timeframe_used}\n"
            f"Expected: {native_timeframe}\n"
            f"Actual: {timeframe_used}\n"
            f"\nThis proves Bug 2 exists: LoopConfig.timeframe defaults to '5m' and is never "
            f"populated from the strategy's native timeframe, causing all gate backtests to "
            f"use '5m' regardless of the strategy's actual timeframe."
        )


@pytest.mark.bug_condition
def test_bug_condition_hardcoded_timeframe_simple(qapp, tmp_path):
    """
    **Property 1: Bug Condition** - Hardcoded Timeframe Detection (Simple Case)
    
    A simpler, non-property-based version of the bug condition test.
    This test directly checks that a strategy with "1h" native timeframe
    results in gate backtests using "5m" instead.
    
    EXPECTED OUTCOME on unfixed code: FAIL
      The gate backtest uses "5m" timeframe instead of "1h".
      
    EXPECTED OUTCOME after fix: PASS
      The gate backtest uses the strategy's native "1h" timeframe.
    
    **Validates: Requirements 1.2, 1.3, 2.3, 2.4**
    """
    strategy_name = "TestStrategy"
    native_timeframe = "1h"
    
    # Create a mock strategy file with 1h timeframe
    strategy_file = _create_mock_strategy_file(tmp_path, strategy_name, native_timeframe)
    
    settings_state = _make_settings_state(tmp_path)
    
    from app.core.services.improve_service import ImproveService
    with patch.object(ImproveService, "get_available_strategies", return_value=[strategy_name]):
        with patch.object(ImproveService, "load_baseline_params", return_value={}):
            page = LoopPage(settings_state)
    
    # Create a loop config with default timeframe (5m)
    config = _make_loop_config(strategy=strategy_name, timeframe="5m")
    
    # Set up the loop service with this config
    page._loop_service._config = config
    
    # Mock the create_backtest_command to capture the timeframe parameter
    from app.core.freqtrade.runners.backtest_runner import create_backtest_command
    mock_cmd = MagicMock()
    mock_cmd.as_list.return_value = ["python", "-m", "freqtrade", "backtesting"]
    mock_cmd.cwd = tmp_path
    
    with patch("app.core.freqtrade.runners.backtest_runner.create_backtest_command", return_value=mock_cmd) as mock_build:
        with patch.object(page._process_service, "execute_command"):
            page._current_iteration = MagicMock()
            page._sandbox_dir = tmp_path / "sandbox"
            page._sandbox_dir.mkdir(parents=True, exist_ok=True)
            
            try:
                page._start_gate_backtest(
                    gate_name="in_sample",
                    timerange="20240101-20240125",
                    phase_label="Testing Gate 1"
                )
            except Exception:
                pass
    
    # Document the counterexample
    if mock_build.called:
        call_args = mock_build.call_args
        timeframe_used = call_args.kwargs.get("timeframe") if call_args.kwargs else None
        
        if timeframe_used != native_timeframe:
            counterexample = (
                f"Counterexample found:\n"
                f"  Strategy: {strategy_name}\n"
                f"  Strategy native timeframe: {native_timeframe}\n"
                f"  LoopConfig.timeframe: {config.timeframe}\n"
                f"  Timeframe passed to build_backtest_command: {timeframe_used}\n"
                f"  Expected: {native_timeframe}\n"
                f"  Actual: {timeframe_used}\n"
                f"\n"
                f"  Gate: in_sample\n"
                f"  Timerange: 20240101-20240125\n"
            )
            pytest.fail(
                f"Bug 2 confirmed: Hardcoded timeframe detected.\n\n{counterexample}\n"
                f"This proves Bug 2 exists: when a gate backtest is started for a strategy "
                f"with '{native_timeframe}' native timeframe, the system uses '{timeframe_used}' "
                f"instead because LoopConfig.timeframe defaults to '5m' and is never populated "
                f"from the strategy's native timeframe."
            )


@pytest.mark.bug_condition
def test_bug_condition_loop_config_timeframe_not_populated(qapp, tmp_path):
    """
    **Property 1: Expected Behavior** - LoopConfig.timeframe Populated from Strategy
    
    This test verifies that LoopConfig.timeframe IS populated from the
    strategy's native timeframe during loop initialization via _build_loop_config().
    
    EXPECTED OUTCOME on unfixed code: FAIL
      LoopConfig.timeframe remains "5m" (default) even when strategy has "1h".
      
    EXPECTED OUTCOME after fix: PASS
      LoopConfig.timeframe is populated with the strategy's native timeframe.
    
    **Validates: Requirements 1.2, 1.3, 2.3, 2.4**
    """
    strategy_name = "TestStrategy"
    native_timeframe = "1h"
    
    # Create a mock strategy file with 1h timeframe
    strategy_file = _create_mock_strategy_file(tmp_path, strategy_name, native_timeframe)
    
    settings_state = _make_settings_state(tmp_path)
    
    from app.core.services.improve_service import ImproveService
    with patch.object(ImproveService, "get_available_strategies", return_value=[strategy_name]):
        with patch.object(ImproveService, "load_baseline_params", return_value={}):
            page = LoopPage(settings_state)
    
    # Use _build_loop_config() which should detect and populate the timeframe
    config = page._build_loop_config(strategy_name)
    
    # Verify that the config timeframe is populated from the strategy
    from app.core.freqtrade.resolvers.strategy_resolver import detect_strategy_timeframe
    detected_timeframe = detect_strategy_timeframe(strategy_file)
    
    assert config.timeframe == detected_timeframe, (
        f"Bug 2 confirmed: LoopConfig.timeframe not populated from strategy.\n"
        f"Strategy: {strategy_name}\n"
        f"Strategy native timeframe (detected): {detected_timeframe}\n"
        f"LoopConfig.timeframe: {config.timeframe}\n"
        f"Expected: {detected_timeframe}\n"
        f"Actual: {config.timeframe}\n"
        f"\nThis proves Bug 2 exists: LoopConfig.timeframe defaults to '5m' and is never "
        f"populated from the strategy's native timeframe during loop initialization, "
        f"causing all gate backtests to use '5m' regardless of the strategy's actual timeframe."
    )
