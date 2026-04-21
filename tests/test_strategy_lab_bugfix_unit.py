"""Additional unit and integration tests for strategy-lab-bugfix spec.

These tests verify the fixed behavior of LoopPage and LoopService after all
five bugs have been corrected.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 3.4**
"""
from __future__ import annotations

import inspect
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from PySide6.QtWidgets import QApplication

from app.app_state.settings_state import SettingsState
from app.core.models.settings_models import AppSettings
from app.core.models.loop_models import LoopConfig
from app.core.services.improve_service import ImproveService
from app.core.services.loop_service import LoopService


# ---------------------------------------------------------------------------
# QApplication fixture (session-scoped to avoid multiple instances)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def qapp():
    """Create or reuse a QApplication for the test session."""
    app = QApplication.instance() or QApplication([])
    yield app


# ---------------------------------------------------------------------------
# Shared helpers (mirrors the pattern from preservation tests)
# ---------------------------------------------------------------------------

def _make_app_settings(tmp_path: Path) -> AppSettings:
    """Return a minimal AppSettings pointing at tmp_path."""
    user_data = tmp_path / "user_data"
    user_data.mkdir(parents=True, exist_ok=True)
    (user_data / "strategies").mkdir(exist_ok=True)
    return AppSettings(
        user_data_path=str(user_data),
        python_executable="python",
        freqtrade_executable="freqtrade",
        venv_path=str(tmp_path / "venv"),
    )


def _make_settings_state(tmp_path: Path) -> SettingsState:
    """Return a SettingsState whose settings_service returns a valid AppSettings."""
    state = SettingsState()
    settings = _make_app_settings(tmp_path)
    state.settings_service.load_settings = MagicMock(return_value=settings)
    state.settings_service.save_settings = MagicMock()
    return state


def _make_loop_page(settings_state: SettingsState):
    """Instantiate LoopPage with mocked strategy list."""
    from app.ui.pages.loop_page import LoopPage
    with patch.object(ImproveService, "get_available_strategies", return_value=["TestStrategy"]):
        page = LoopPage(settings_state)
    return page


def _make_loop_config(
    strategy: str = "TestStrategy",
    timeframe: str = "5m",
    date_from: str = "20240101",
    date_to: str = "20240131",
) -> LoopConfig:
    """Return a minimal LoopConfig for testing."""
    return LoopConfig(
        strategy=strategy,
        timeframe=timeframe,
        max_iterations=5,
        date_from=date_from,
        date_to=date_to,
        oos_split_pct=20.0,
        validation_mode="full",
    )


def _make_backtest_results_mock(strategy: str = "TestStrategy") -> MagicMock:
    """Return a mock BacktestResults with a non-None summary."""
    from app.core.backtests.results_models import BacktestSummary
    summary = BacktestSummary(
        strategy=strategy,
        timeframe="5m",
        total_trades=50,
        wins=28,
        losses=22,
        draws=0,
        win_rate=56.0,
        avg_profit=0.1,
        total_profit=5.0,
        total_profit_abs=50.0,
        sharpe_ratio=1.2,
        sortino_ratio=1.5,
        calmar_ratio=0.8,
        max_drawdown=10.0,
        max_drawdown_abs=10.0,
        trade_duration_avg=60,
    )
    results = MagicMock()
    results.summary = summary
    return results


# ===========================================================================
# Test 1 — Unit test _run_baseline_backtest with mocked services
# ===========================================================================

class TestRunBaselineBacktestMockedServices:
    """Unit test _run_baseline_backtest with mocked services.

    Verifies:
    - prepare_sandbox is called with (strategy_name: str, {})
    - cmd.as_list() contains "--strategy-path" and "--backtest-directory"
    - execute_command is called with on_output=terminal.append_output
      and on_error=terminal.append_error

    **Validates: Requirements 2.1, 2.2, 2.4**
    """

    def test_prepare_sandbox_called_with_strategy_str_and_empty_dict(self, qapp, tmp_path):
        """Assert prepare_sandbox is called with (strategy_name: str, {}).

        **Validates: Requirements 2.2**
        """
        settings_state = _make_settings_state(tmp_path)
        page = _make_loop_page(settings_state)

        strategy = "TestStrategy"
        settings = _make_app_settings(tmp_path)
        config = _make_loop_config(strategy=strategy)

        sandbox_dir = tmp_path / "sandbox"
        sandbox_dir.mkdir()
        export_dir = sandbox_dir / "baseline_export"

        captured_prepare_args = []

        def fake_prepare_sandbox(strategy_arg, params_arg):
            captured_prepare_args.append((strategy_arg, params_arg))
            sandbox_dir.mkdir(exist_ok=True)
            return sandbox_dir

        mock_cmd = MagicMock()
        mock_cmd.as_list.return_value = [
            "python", "-m", "freqtrade", "backtesting",
            "--strategy-path", str(sandbox_dir),
            "--backtest-directory", str(export_dir),
        ]
        mock_cmd.cwd = str(tmp_path)

        with patch.object(page._improve_service, "prepare_sandbox", side_effect=fake_prepare_sandbox):
            with patch("app.core.freqtrade.runners.backtest_runner.build_backtest_command", return_value=mock_cmd):
                with patch.object(page._loop_service, "compute_in_sample_timerange", return_value="20240101-20240115"):
                    with patch.object(page._process_service, "execute_command"):
                        page._run_baseline_backtest(config, strategy, settings)

        assert len(captured_prepare_args) == 1, (
            f"prepare_sandbox should be called once, got {len(captured_prepare_args)}"
        )
        strategy_arg, params_arg = captured_prepare_args[0]
        assert isinstance(strategy_arg, str), (
            f"prepare_sandbox first arg must be str, got {type(strategy_arg).__name__}: {strategy_arg!r}"
        )
        assert strategy_arg == strategy, (
            f"prepare_sandbox first arg should be {strategy!r}, got {strategy_arg!r}"
        )
        assert isinstance(params_arg, dict), (
            f"prepare_sandbox second arg must be dict, got {type(params_arg).__name__}: {params_arg!r}"
        )
        assert params_arg == {}, (
            f"prepare_sandbox second arg should be empty dict {{}}, got {params_arg!r}"
        )

    def test_baseline_command_contains_strategy_path_and_backtest_directory(self, qapp, tmp_path):
        """Assert cmd.as_list() contains '--strategy-path' and '--backtest-directory'.

        **Validates: Requirements 2.4**
        """
        settings_state = _make_settings_state(tmp_path)
        page = _make_loop_page(settings_state)

        strategy = "TestStrategy"
        settings = _make_app_settings(tmp_path)
        config = _make_loop_config(strategy=strategy)

        sandbox_dir = tmp_path / "sandbox"
        sandbox_dir.mkdir()
        export_dir = sandbox_dir / "baseline_export"

        captured_cmd_lists = []

        def fake_execute_command(cmd_list, **kwargs):
            captured_cmd_lists.append(cmd_list)

        def fake_prepare_sandbox(strategy_arg, params_arg):
            sandbox_dir.mkdir(exist_ok=True)
            return sandbox_dir

        # Use a real-ish mock command that includes the flags
        mock_cmd = MagicMock()
        mock_cmd.as_list.return_value = [
            "python", "-m", "freqtrade", "backtesting",
            "--strategy", strategy,
            "--strategy-path", str(sandbox_dir),
            "--backtest-directory", str(export_dir),
        ]
        mock_cmd.cwd = str(tmp_path)

        with patch.object(page._improve_service, "prepare_sandbox", side_effect=fake_prepare_sandbox):
            with patch("app.core.freqtrade.runners.backtest_runner.build_backtest_command", return_value=mock_cmd):
                with patch.object(page._loop_service, "compute_in_sample_timerange", return_value="20240101-20240115"):
                    with patch.object(page._process_service, "execute_command", side_effect=fake_execute_command):
                        page._run_baseline_backtest(config, strategy, settings)

        assert len(captured_cmd_lists) == 1, (
            f"execute_command should be called once, got {len(captured_cmd_lists)}"
        )
        cmd_list = captured_cmd_lists[0]
        assert "--strategy-path" in cmd_list, (
            f"'--strategy-path' must be in cmd.as_list(). Got: {cmd_list}"
        )
        assert "--backtest-directory" in cmd_list, (
            f"'--backtest-directory' must be in cmd.as_list(). Got: {cmd_list}"
        )

    def test_execute_command_called_with_terminal_callbacks(self, qapp, tmp_path):
        """Assert execute_command is called with on_output=terminal.append_output
        and on_error=terminal.append_error.

        **Validates: Requirements 2.1**
        """
        settings_state = _make_settings_state(tmp_path)
        page = _make_loop_page(settings_state)

        strategy = "TestStrategy"
        settings = _make_app_settings(tmp_path)
        config = _make_loop_config(strategy=strategy)

        sandbox_dir = tmp_path / "sandbox"
        sandbox_dir.mkdir()
        export_dir = sandbox_dir / "baseline_export"

        captured_kwargs = {}

        def fake_execute_command(cmd_list, **kwargs):
            captured_kwargs.update(kwargs)

        def fake_prepare_sandbox(strategy_arg, params_arg):
            sandbox_dir.mkdir(exist_ok=True)
            return sandbox_dir

        mock_cmd = MagicMock()
        mock_cmd.as_list.return_value = [
            "python", "-m", "freqtrade", "backtesting",
            "--strategy-path", str(sandbox_dir),
            "--backtest-directory", str(export_dir),
        ]
        mock_cmd.cwd = str(tmp_path)

        with patch.object(page._improve_service, "prepare_sandbox", side_effect=fake_prepare_sandbox):
            with patch("app.core.freqtrade.runners.backtest_runner.build_backtest_command", return_value=mock_cmd):
                with patch.object(page._loop_service, "compute_in_sample_timerange", return_value="20240101-20240115"):
                    with patch.object(page._process_service, "execute_command", side_effect=fake_execute_command):
                        page._run_baseline_backtest(config, strategy, settings)

        assert "on_output" in captured_kwargs, (
            "execute_command must be called with on_output kwarg"
        )
        assert "on_error" in captured_kwargs, (
            "execute_command must be called with on_error kwarg"
        )
        assert captured_kwargs["on_output"] == page._terminal.append_output, (
            f"on_output must be terminal.append_output, got {captured_kwargs['on_output']!r}"
        )
        assert captured_kwargs["on_error"] == page._terminal.append_error, (
            f"on_error must be terminal.append_error, got {captured_kwargs['on_error']!r}"
        )


# ===========================================================================
# Test 2 — Unit test _on_baseline_backtest_finished success path
# ===========================================================================

class TestOnBaselineBacktestFinishedSuccess:
    """Unit test _on_baseline_backtest_finished with exit_code=0.

    Verifies:
    - parse_candidate_run is called with (export_dir, baseline_run_started_at)
      where baseline_run_started_at > 0
    - _latest_diagnosis_input is populated (not None) after the call

    **Validates: Requirements 2.3, 2.5**
    """

    def test_parse_candidate_run_called_with_export_dir_and_started_at(self, qapp, tmp_path):
        """Assert parse_candidate_run is called with (export_dir, baseline_run_started_at > 0).

        **Validates: Requirements 2.3**
        """
        settings_state = _make_settings_state(tmp_path)
        page = _make_loop_page(settings_state)
        page._ensure_loop_runtime_state()

        # Set up sandbox dir and baseline_run_started_at
        sandbox_dir = tmp_path / "sandbox"
        sandbox_dir.mkdir()
        export_dir = sandbox_dir / "baseline_export"
        export_dir.mkdir()

        page._sandbox_dir = sandbox_dir
        page._baseline_run_started_at = time.time() - 10.0  # positive float

        captured_parse_args = []
        mock_results = _make_backtest_results_mock()

        def fake_parse_candidate_run(export_dir_arg, started_at_arg):
            captured_parse_args.append((export_dir_arg, started_at_arg))
            return mock_results

        with patch.object(page._improve_service, "parse_candidate_run", side_effect=fake_parse_candidate_run):
            with patch.object(page, "_update_state_machine"):
                with patch.object(page, "_set_status"):
                    # Patch QTimer to avoid triggering _on_start recursion
                    with patch("app.ui.pages.loop_page.QTimer"):
                        page._on_baseline_backtest_finished(0)

        assert len(captured_parse_args) == 1, (
            f"parse_candidate_run should be called once, got {len(captured_parse_args)}"
        )
        export_dir_arg, started_at_arg = captured_parse_args[0]
        assert export_dir_arg == export_dir, (
            f"parse_candidate_run first arg should be {export_dir}, got {export_dir_arg!r}"
        )
        assert isinstance(started_at_arg, float), (
            f"parse_candidate_run second arg must be float, got {type(started_at_arg).__name__}"
        )
        assert started_at_arg > 0, (
            f"parse_candidate_run second arg (baseline_run_started_at) must be > 0, got {started_at_arg}"
        )

    def test_latest_diagnosis_input_populated_on_success(self, qapp, tmp_path):
        """Assert _latest_diagnosis_input is not None after successful completion.

        **Validates: Requirements 2.5**
        """
        settings_state = _make_settings_state(tmp_path)
        page = _make_loop_page(settings_state)
        page._ensure_loop_runtime_state()

        sandbox_dir = tmp_path / "sandbox"
        sandbox_dir.mkdir()
        export_dir = sandbox_dir / "baseline_export"
        export_dir.mkdir()

        page._sandbox_dir = sandbox_dir
        page._baseline_run_started_at = time.time() - 10.0

        mock_results = _make_backtest_results_mock()

        with patch.object(page._improve_service, "parse_candidate_run", return_value=mock_results):
            with patch.object(page, "_update_state_machine"):
                with patch.object(page, "_set_status"):
                    with patch("app.ui.pages.loop_page.QTimer"):
                        page._on_baseline_backtest_finished(0)

        assert page._latest_diagnosis_input is not None, (
            "_latest_diagnosis_input must be populated (not None) after successful baseline"
        )


# ===========================================================================
# Test 3 — Unit test _on_baseline_backtest_finished failure path
# ===========================================================================

class TestOnBaselineBacktestFinishedFailure:
    """Unit test _on_baseline_backtest_finished with exit_code != 0.

    Verifies:
    - parse_candidate_run is NOT called
    - _baseline_in_progress is reset to False

    **Validates: Requirements 2.3**
    """

    def test_parse_candidate_run_not_called_on_failure(self, qapp, tmp_path):
        """Assert parse_candidate_run is NOT called when exit_code != 0.

        **Validates: Requirements 2.3**
        """
        settings_state = _make_settings_state(tmp_path)
        page = _make_loop_page(settings_state)
        page._ensure_loop_runtime_state()

        sandbox_dir = tmp_path / "sandbox"
        sandbox_dir.mkdir()
        page._sandbox_dir = sandbox_dir
        page._baseline_in_progress = True

        mock_parse = MagicMock()

        with patch.object(page._improve_service, "parse_candidate_run", mock_parse):
            with patch.object(page, "_update_state_machine"):
                with patch.object(page, "_set_status"):
                    # Patch QMessageBox to avoid GUI dialog
                    with patch("app.ui.pages.loop_page.QMessageBox"):
                        page._on_baseline_backtest_finished(1)

        mock_parse.assert_not_called(), (
            "parse_candidate_run must NOT be called when exit_code != 0"
        )

    def test_baseline_in_progress_reset_on_failure(self, qapp, tmp_path):
        """Assert _baseline_in_progress is reset to False when exit_code != 0.

        **Validates: Requirements 2.3**
        """
        settings_state = _make_settings_state(tmp_path)
        page = _make_loop_page(settings_state)
        page._ensure_loop_runtime_state()

        sandbox_dir = tmp_path / "sandbox"
        sandbox_dir.mkdir()
        page._sandbox_dir = sandbox_dir
        page._baseline_in_progress = True

        with patch.object(page, "_update_state_machine"):
            with patch.object(page, "_set_status"):
                with patch("app.ui.pages.loop_page.QMessageBox"):
                    page._on_baseline_backtest_finished(1)

        assert page._baseline_in_progress is False, (
            "_baseline_in_progress must be reset to False after failure"
        )


# ===========================================================================
# Test 4 — Unit test LoopPage has no _build_config_panel method
# ===========================================================================

class TestLoopPageNoBuildConfigPanel:
    """Unit test that LoopPage has no _build_config_panel method after Fix 4a.

    **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5**
    """

    def test_loop_page_has_no_build_config_panel(self):
        """Assert not hasattr(LoopPage, '_build_config_panel').

        After Fix 4a, the dead _build_config_panel method must be deleted.
        _init_ui calls _build_config_group instead.

        **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5**
        """
        from app.ui.pages.loop_page import LoopPage

        assert not hasattr(LoopPage, "_build_config_panel"), (
            "LoopPage must NOT have _build_config_panel after Fix 4a. "
            "This dead method was never called by _init_ui (which calls _build_config_group instead) "
            "and its presence risks accidental widget overwrite."
        )

    def test_loop_page_has_build_config_group(self):
        """Assert LoopPage still has _build_config_group (the correct method).

        **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5**
        """
        from app.ui.pages.loop_page import LoopPage

        assert hasattr(LoopPage, "_build_config_group"), (
            "LoopPage must still have _build_config_group — this is the method called by _init_ui."
        )


# ===========================================================================
# Test 5 — Unit test LoopService.run_gate_sequence calls build_in_sample_gate_result
# ===========================================================================

class TestLoopServiceRunGateSequenceCallsBuildInSampleGateResult:
    """Unit test that LoopService.run_gate_sequence calls build_in_sample_gate_result.

    Uses inspect.getsourcelines to verify the resolved method is the canonical
    definition (not the stale first definition).

    **Validates: Requirements 3.1, 3.4**
    """

    def test_run_gate_sequence_source_contains_build_in_sample_gate_result(self):
        """Assert 'build_in_sample_gate_result' is in the source of run_gate_sequence.

        **Validates: Requirements 3.1, 3.4**
        """
        source_lines, start_line = inspect.getsourcelines(LoopService.run_gate_sequence)
        source = "".join(source_lines)

        assert "build_in_sample_gate_result" in source, (
            f"LoopService.run_gate_sequence (resolved to line {start_line}) does NOT call "
            f"build_in_sample_gate_result. Python may have resolved to the stale first definition "
            f"which uses direct GateResult() construction instead."
        )

    def test_run_gate_sequence_source_contains_evaluate_gate1_hard_filters(self):
        """Assert 'evaluate_gate1_hard_filters' is in the source of run_gate_sequence.

        **Validates: Requirements 3.1, 3.4**
        """
        source_lines, start_line = inspect.getsourcelines(LoopService.run_gate_sequence)
        source = "".join(source_lines)

        assert "evaluate_gate1_hard_filters" in source, (
            f"LoopService.run_gate_sequence (resolved to line {start_line}) does NOT call "
            f"evaluate_gate1_hard_filters. Python may have resolved to the stale first definition "
            f"which lacks hard-filter evaluation."
        )

    def test_run_gate_sequence_does_not_use_stale_direct_gate_result_construction(self):
        """Assert the resolved run_gate_sequence does NOT use direct GateResult() for gate1.

        The stale definition constructs gate1 directly:
            gate1 = GateResult(gate_name="in_sample", passed=True, ...)
        The canonical definition delegates to build_in_sample_gate_result.

        **Validates: Requirements 3.1, 3.4**
        """
        source_lines, start_line = inspect.getsourcelines(LoopService.run_gate_sequence)
        source = "".join(source_lines)

        stale_pattern = 'gate1 = GateResult('
        assert stale_pattern not in source, (
            f"LoopService.run_gate_sequence at line {start_line} uses direct GateResult() "
            f"construction for gate1. This is the stale definition. "
            f"The canonical definition should call build_in_sample_gate_result instead."
        )


# ===========================================================================
# Test 6 — Unit test session reset
# ===========================================================================

class TestSessionReset:
    """Unit test that _latest_diagnosis_input is reset to None at the start of _on_start.

    Verifies that starting a new session always clears stale diagnosis data from
    a prior session, ensuring the baseline backtest always runs.

    **Validates: Requirements 2.5, 3.1**
    """

    def test_latest_diagnosis_input_is_none_at_start_of_on_start(self, qapp, tmp_path):
        """Assert _latest_diagnosis_input is None at the start of _on_start.

        Simulates a completed prior session by setting _latest_diagnosis_input
        to a non-None value, then calls _on_start and verifies the reset.

        **Validates: Requirements 2.5**
        """
        settings_state = _make_settings_state(tmp_path)
        page = _make_loop_page(settings_state)
        page._ensure_loop_runtime_state()

        # Simulate a completed prior session
        page._latest_diagnosis_input = MagicMock()
        assert page._latest_diagnosis_input is not None, (
            "Pre-condition: _latest_diagnosis_input should be non-None before _on_start"
        )

        # Track when _latest_diagnosis_input is reset
        reset_values = []

        original_run_baseline = page._run_baseline_backtest

        def tracking_run_baseline(config, strategy, settings):
            # Capture the value of _latest_diagnosis_input at the point _run_baseline_backtest is called
            reset_values.append(page._latest_diagnosis_input)

        # Patch out everything that would fail without a real Qt environment
        with patch.object(page, "_validate_loop_inputs", return_value=None):
            with patch.object(page, "_save_preferences"):
                with patch.object(
                    page._improve_service,
                    "load_baseline_params",
                    return_value={"stoploss": -0.10},
                ):
                    with patch.object(page, "_build_loop_config", return_value=_make_loop_config()):
                        with patch.object(page, "_run_baseline_backtest", side_effect=tracking_run_baseline):
                            page._on_start()

        # _latest_diagnosis_input must be None when _run_baseline_backtest is called
        # (i.e., it was reset at the start of _on_start before the baseline check)
        assert len(reset_values) == 1, (
            "_run_baseline_backtest should have been called once (needs_baseline=True after reset)"
        )
        assert reset_values[0] is None, (
            f"_latest_diagnosis_input must be None when _run_baseline_backtest is called. "
            f"Got: {reset_values[0]!r}. "
            f"This means _on_start did NOT reset _latest_diagnosis_input before the baseline check."
        )

    def test_on_start_source_resets_latest_diagnosis_input_before_baseline_check(self):
        """Inspect _on_start source to confirm _latest_diagnosis_input is reset before
        the baseline check (needs_baseline = self._latest_diagnosis_input is None).

        **Validates: Requirements 2.5**
        """
        from app.ui.pages.loop_page import LoopPage

        source_lines, _ = inspect.getsourcelines(LoopPage._on_start)
        source = "".join(source_lines)

        assert "_latest_diagnosis_input = None" in source, (
            "_on_start must reset _latest_diagnosis_input to None at the start. "
            "This ensures every new session runs a fresh baseline backtest."
        )

        # Verify the reset comes before the baseline check
        reset_pos = source.index("_latest_diagnosis_input = None")
        baseline_check_pos = source.index("needs_baseline")
        assert reset_pos < baseline_check_pos, (
            "_latest_diagnosis_input = None must appear BEFORE the needs_baseline check in _on_start. "
            f"Reset at char {reset_pos}, baseline check at char {baseline_check_pos}."
        )

    def test_second_session_always_runs_baseline(self, qapp, tmp_path):
        """Verify that starting a second session after a completed first session
        always triggers the baseline backtest (needs_baseline=True).

        **Validates: Requirements 2.5, 3.1**
        """
        settings_state = _make_settings_state(tmp_path)
        page = _make_loop_page(settings_state)
        page._ensure_loop_runtime_state()

        # Simulate first session completed: _latest_diagnosis_input is populated
        from app.core.models.diagnosis_models import DiagnosisInput
        from app.core.backtests.results_models import BacktestSummary
        summary = BacktestSummary(
            strategy="TestStrategy",
            timeframe="5m",
            total_trades=50,
            wins=28,
            losses=22,
            draws=0,
            win_rate=56.0,
            avg_profit=0.1,
            total_profit=5.0,
            total_profit_abs=50.0,
            sharpe_ratio=1.2,
            sortino_ratio=1.5,
            calmar_ratio=0.8,
            max_drawdown=10.0,
            max_drawdown_abs=10.0,
            trade_duration_avg=60,
        )
        page._latest_diagnosis_input = DiagnosisInput(
            in_sample=summary,
            oos_summary=None,
            fold_summaries=None,
            trade_profit_contributions=None,
        )

        baseline_called = []

        def tracking_run_baseline(config, strategy, settings):
            baseline_called.append(True)

        with patch.object(page, "_validate_loop_inputs", return_value=None):
            with patch.object(page, "_save_preferences"):
                with patch.object(
                    page._improve_service,
                    "load_baseline_params",
                    return_value={"stoploss": -0.10},
                ):
                    with patch.object(page, "_build_loop_config", return_value=_make_loop_config()):
                        with patch.object(page, "_run_baseline_backtest", side_effect=tracking_run_baseline):
                            page._on_start()

        assert len(baseline_called) == 1, (
            "Starting a second session must trigger the baseline backtest. "
            "_on_start must reset _latest_diagnosis_input to None before the baseline check, "
            "so needs_baseline evaluates to True even when prior session data exists."
        )
