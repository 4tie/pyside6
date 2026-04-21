"""Preservation property tests for strategy-lab-bugfix spec.

These tests are designed to PASS on unfixed code -- they encode the baseline
behavior that must be preserved after the fix is applied.

**Property 2: Preservation** -- Gate Backtests and Non-Baseline Paths Unchanged

Behaviors verified:
  3.2  _start_gate_backtest() routes output to terminal.append_output / append_error
  3.3  _run_next_iteration() calls prepare_sandbox(config.strategy, iteration.params_after)
  3.4  _parse_current_gate_results() calls parse_candidate_run(export_dir, started_at)
  3.5  Canonical run_gate_sequence calls build_in_sample_gate_result + evaluate_gate1_hard_filters
  3.6  _restore_preferences / _save_preferences round-trip preserves all field values

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**
"""
import inspect
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest
from hypothesis import given, settings as h_settings, HealthCheck, assume
from hypothesis import strategies as st

from PySide6.QtWidgets import QApplication

from app.core.models.loop_models import LoopConfig, LoopIteration, GateResult
from app.core.models.settings_models import AppSettings, StrategyLabPreferences
from app.core.services.loop_service import LoopService
from app.core.services.improve_service import ImproveService
from app.app_state.settings_state import SettingsState
from app.core.backtests.results_models import BacktestSummary


# ---------------------------------------------------------------------------
# QApplication fixture (session-scoped to avoid multiple instances)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def qapp():
    """Create or reuse a QApplication for the test session."""
    app = QApplication.instance() or QApplication([])
    yield app


# ---------------------------------------------------------------------------
# Shared helpers
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


def _make_backtest_summary(
    strategy: str = "TestStrategy",
    total_trades: int = 50,
    win_rate: float = 55.0,
    total_profit: float = 5.0,
) -> BacktestSummary:
    """Return a minimal BacktestSummary."""
    return BacktestSummary(
        strategy=strategy,
        timeframe="5m",
        total_trades=total_trades,
        wins=int(total_trades * win_rate / 100),
        losses=total_trades - int(total_trades * win_rate / 100),
        draws=0,
        win_rate=win_rate,
        avg_profit=total_profit / max(total_trades, 1),
        total_profit=total_profit,
        total_profit_abs=total_profit * 10,
        sharpe_ratio=1.2,
        sortino_ratio=1.5,
        calmar_ratio=0.8,
        max_drawdown=10.0,
        max_drawdown_abs=10.0,
        trade_duration_avg=60,
    )


def _make_loop_iteration(
    iteration_number: int = 1,
    params_after: dict = None,
) -> LoopIteration:
    """Return a minimal LoopIteration."""
    return LoopIteration(
        iteration_number=iteration_number,
        params_before={},
        params_after=params_after if params_after is not None else {"buy_rsi": 30},
        changes_summary=["Changed buy_rsi from 35 to 30"],
    )


# ===========================================================================
# Property 3.2 -- Gate backtest callbacks unchanged
# ===========================================================================

class TestGateBacktestCallbacksPreserved:
    """Requirement 3.2: _start_gate_backtest() continues to route subprocess output
    to self._terminal.append_output and self._terminal.append_error.

    Observation on UNFIXED code:
        _start_gate_backtest() calls self._process_service.execute_command(
            ...,
            on_output=self._terminal.append_output,
            on_error=self._terminal.append_error,
            ...
        )
    This is the correct pattern and must not change after the fix.
    """

    def test_gate_backtest_source_uses_terminal_callbacks(self):
        """Inspect _start_gate_backtest source to confirm terminal callbacks are used.

        **Validates: Requirements 3.2**
        """
        from app.ui.pages.loop_page import LoopPage

        method = LoopPage._start_gate_backtest
        source_lines, _ = inspect.getsourcelines(method)
        source = "".join(source_lines)

        assert "self._terminal.append_output" in source, (
            "Preservation violated: _start_gate_backtest no longer passes "
            "self._terminal.append_output as on_output callback. This is a regression."
        )
        assert "self._terminal.append_error" in source, (
            "Preservation violated: _start_gate_backtest no longer passes "
            "self._terminal.append_error as on_error callback. This is a regression."
        )

    def test_gate_backtest_routes_to_terminal_at_runtime(self, qapp, tmp_path):
        """Verify _start_gate_backtest passes terminal callbacks to execute_command at runtime.

        **Validates: Requirements 3.2**
        """
        settings_state = _make_settings_state(tmp_path)
        page = _make_loop_page(settings_state)

        config = _make_loop_config()
        iteration = _make_loop_iteration()
        sandbox_dir = tmp_path / "sandbox"
        sandbox_dir.mkdir()

        page._loop_service._config = config
        page._current_iteration = iteration
        page._sandbox_dir = sandbox_dir

        captured_kwargs = {}

        def fake_execute_command(cmd_list, **kwargs):
            captured_kwargs.update(kwargs)

        with patch.object(page._process_service, "execute_command", side_effect=fake_execute_command):
            with patch("app.core.freqtrade.runners.backtest_runner.build_backtest_command") as mock_build:
                mock_cmd = MagicMock()
                mock_cmd.as_list.return_value = ["python", "-m", "freqtrade", "backtesting"]
                mock_cmd.cwd = str(tmp_path)
                mock_build.return_value = mock_cmd
                with patch("app.core.freqtrade.resolvers.config_resolver.resolve_config_file", return_value=tmp_path / "config.json"):
                    page._start_gate_backtest("in_sample", "20240101-20240115", "Gate 1")

        assert "on_output" in captured_kwargs, "execute_command was not called with on_output kwarg"
        assert "on_error" in captured_kwargs, "execute_command was not called with on_error kwarg"
        assert captured_kwargs["on_output"] == page._terminal.append_output, (
            f"Preservation violated: on_output={captured_kwargs['on_output']!r}, "
            f"expected self._terminal.append_output."
        )
        assert captured_kwargs["on_error"] == page._terminal.append_error, (
            f"Preservation violated: on_error={captured_kwargs['on_error']!r}, "
            f"expected self._terminal.append_error."
        )


@given(
    strategy_name=st.sampled_from(["TestStrategy", "MyStrategy", "SampleStrat"]),
    gate_name=st.sampled_from(["in_sample", "out_of_sample", "walk_forward"]),
    timerange=st.sampled_from([
        "20240101-20240115",
        "20240115-20240131",
        "20230601-20230701",
    ]),
)
@h_settings(max_examples=8, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_pbt_gate_backtest_always_uses_terminal_callbacks(qapp, tmp_path, strategy_name, gate_name, timerange):
    """Property-based test: for any LoopConfig with valid strategy/timerange,
    _start_gate_backtest always routes output to terminal.append_output /
    terminal.append_error (not to any non-existent callback).

    **Validates: Requirements 3.2**
    """
    settings_state = _make_settings_state(tmp_path)
    page = _make_loop_page(settings_state)

    config = _make_loop_config(strategy=strategy_name)
    iteration = _make_loop_iteration()
    sandbox_dir = tmp_path / "sandbox"
    sandbox_dir.mkdir(exist_ok=True)

    page._loop_service._config = config
    page._current_iteration = iteration
    page._sandbox_dir = sandbox_dir

    captured_on_output = []
    captured_on_error = []

    def fake_execute_command(cmd_list, **kwargs):
        captured_on_output.append(kwargs.get("on_output"))
        captured_on_error.append(kwargs.get("on_error"))

    with patch.object(page._process_service, "execute_command", side_effect=fake_execute_command):
        with patch("app.core.freqtrade.runners.backtest_runner.build_backtest_command") as mock_build:
            mock_cmd = MagicMock()
            mock_cmd.as_list.return_value = ["python", "-m", "freqtrade", "backtesting"]
            mock_cmd.cwd = str(tmp_path)
            mock_build.return_value = mock_cmd
            with patch("app.core.freqtrade.resolvers.config_resolver.resolve_config_file", return_value=tmp_path / "config.json"):
                page._start_gate_backtest(gate_name, timerange, f"Gate {gate_name}")

    assert len(captured_on_output) == 1, "execute_command should have been called once"
    assert captured_on_output[0] == page._terminal.append_output, (
        f"PBT: on_output={captured_on_output[0]!r} is not terminal.append_output. "
        f"strategy={strategy_name!r}, gate={gate_name!r}, timerange={timerange!r}"
    )
    assert captured_on_error[0] == page._terminal.append_error, (
        f"PBT: on_error={captured_on_error[0]!r} is not terminal.append_error. "
        f"strategy={strategy_name!r}, gate={gate_name!r}, timerange={timerange!r}"
    )


# ===========================================================================
# Property 3.3 -- prepare_sandbox from _run_next_iteration unchanged
# ===========================================================================

class TestPrepareSandboxFromRunNextIterationPreserved:
    """Requirement 3.3: _run_next_iteration() continues to call
    prepare_sandbox(config.strategy, iteration.params_after).

    Observation on UNFIXED code:
        self._sandbox_dir = self._improve_service.prepare_sandbox(
            config.strategy,          # str
            iteration.params_after,   # dict
        )
    First arg is a str (strategy name), second is a dict (params).
    This must not change after the fix.
    """

    def test_run_next_iteration_source_calls_prepare_sandbox_correctly(self):
        """Inspect _run_next_iteration source to confirm prepare_sandbox call signature.

        **Validates: Requirements 3.3**
        """
        from app.ui.pages.loop_page import LoopPage

        method = LoopPage._run_next_iteration
        source_lines, _ = inspect.getsourcelines(method)
        source = "".join(source_lines)

        assert "prepare_sandbox(" in source, (
            "Preservation violated: _run_next_iteration no longer calls prepare_sandbox."
        )
        assert "config.strategy" in source, (
            "Preservation violated: _run_next_iteration no longer passes config.strategy "
            "as first arg to prepare_sandbox."
        )
        assert "iteration.params_after" in source, (
            "Preservation violated: _run_next_iteration no longer passes iteration.params_after "
            "as second arg to prepare_sandbox."
        )

    def test_run_next_iteration_calls_prepare_sandbox_with_str_and_dict(self, qapp, tmp_path):
        """Verify _run_next_iteration calls prepare_sandbox(str, dict) at runtime.

        **Validates: Requirements 3.3**
        """
        settings_state = _make_settings_state(tmp_path)
        page = _make_loop_page(settings_state)

        strategy_name = "TestStrategy"
        params_after = {"buy_rsi": 30, "sell_rsi": 70}
        config = _make_loop_config(strategy=strategy_name)
        iteration = _make_loop_iteration(params_after=params_after)

        page._loop_service._config = config
        page._latest_diagnosis_input = MagicMock()
        page._latest_diagnosis_input.in_sample = _make_backtest_summary()

        captured_args = []

        def fake_prepare_sandbox(strategy_arg, params_arg):
            captured_args.append((strategy_arg, params_arg))
            sandbox = tmp_path / "sandbox"
            sandbox.mkdir(exist_ok=True)
            return sandbox

        with patch.object(page._improve_service, "prepare_sandbox", side_effect=fake_prepare_sandbox):
            with patch.object(page._loop_service, "should_continue", return_value=True):
                with patch.object(
                    page._loop_service,
                    "prepare_next_iteration",
                    return_value=(iteration, []),
                ):
                    with patch.object(page._loop_service, "compute_in_sample_timerange", return_value="20240101-20240115"):
                        with patch.object(page, "_start_gate_backtest"):
                            page._run_next_iteration()

        assert len(captured_args) == 1, (
            f"prepare_sandbox should have been called once, got {len(captured_args)} calls"
        )
        strategy_arg, params_arg = captured_args[0]
        assert isinstance(strategy_arg, str), (
            f"Preservation violated: prepare_sandbox first arg is {type(strategy_arg).__name__}, "
            f"expected str. Got: {strategy_arg!r}"
        )
        assert isinstance(params_arg, dict), (
            f"Preservation violated: prepare_sandbox second arg is {type(params_arg).__name__}, "
            f"expected dict. Got: {params_arg!r}"
        )
        assert strategy_arg == strategy_name, (
            f"Preservation violated: prepare_sandbox called with strategy={strategy_arg!r}, "
            f"expected {strategy_name!r}"
        )
        assert params_arg == params_after, (
            f"Preservation violated: prepare_sandbox called with params={params_arg!r}, "
            f"expected {params_after!r}"
        )


@given(
    strategy_name=st.sampled_from(["TestStrategy", "MyStrategy", "SampleStrat"]),
    params_after=st.fixed_dictionaries({
        "buy_rsi": st.integers(min_value=10, max_value=50),
        "sell_rsi": st.integers(min_value=50, max_value=90),
    }),
)
@h_settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_pbt_run_next_iteration_prepare_sandbox_arg_types(
    qapp, tmp_path, strategy_name, params_after
):
    """Property-based test: for any (strategy_name: str, params_after: dict) pair,
    _run_next_iteration always calls prepare_sandbox with a str first arg and a
    dict second arg.

    **Validates: Requirements 3.3**
    """
    settings_state = _make_settings_state(tmp_path)
    page = _make_loop_page(settings_state)

    config = _make_loop_config(strategy=strategy_name)
    iteration = _make_loop_iteration(params_after=params_after)

    page._loop_service._config = config
    page._latest_diagnosis_input = MagicMock()
    page._latest_diagnosis_input.in_sample = _make_backtest_summary()

    captured_args = []

    def fake_prepare_sandbox(strategy_arg, params_arg):
        captured_args.append((strategy_arg, params_arg))
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir(exist_ok=True)
        return sandbox

    with patch.object(page._improve_service, "prepare_sandbox", side_effect=fake_prepare_sandbox):
        with patch.object(page._loop_service, "should_continue", return_value=True):
            with patch.object(
                page._loop_service,
                "prepare_next_iteration",
                return_value=(iteration, []),
            ):
                with patch.object(page._loop_service, "compute_in_sample_timerange", return_value="20240101-20240115"):
                    with patch.object(page, "_start_gate_backtest"):
                        page._run_next_iteration()

    assert len(captured_args) == 1, (
        f"PBT: prepare_sandbox should be called once, got {len(captured_args)}"
    )
    strategy_arg, params_arg = captured_args[0]
    assert isinstance(strategy_arg, str), (
        f"PBT: prepare_sandbox first arg type={type(strategy_arg).__name__}, expected str. "
        f"strategy_name={strategy_name!r}, params_after={params_after!r}"
    )
    assert isinstance(params_arg, dict), (
        f"PBT: prepare_sandbox second arg type={type(params_arg).__name__}, expected dict. "
        f"strategy_name={strategy_name!r}, params_after={params_after!r}"
    )
    assert strategy_arg == strategy_name, (
        f"PBT: prepare_sandbox first arg={strategy_arg!r}, expected {strategy_name!r}"
    )
    assert params_arg == params_after, (
        f"PBT: prepare_sandbox second arg={params_arg!r}, expected {params_after!r}"
    )


# ===========================================================================
# Property 3.4 -- parse_candidate_run from _parse_current_gate_results unchanged
# ===========================================================================

class TestParseCandidateRunFromGateResultsPreserved:
    """Requirement 3.4: _parse_current_gate_results() continues to call
    parse_candidate_run(self._current_gate_export_dir, self._gate_run_started_at).

    Observation on UNFIXED code:
        return self._improve_service.parse_candidate_run(
            self._current_gate_export_dir,   # Path
            self._gate_run_started_at,        # float
        )
    First arg is a Path, second is a float timestamp.
    This must not change after the fix.
    """

    def test_parse_current_gate_results_source_calls_parse_candidate_run(self):
        """Inspect _parse_current_gate_results source to confirm parse_candidate_run call.

        **Validates: Requirements 3.4**
        """
        from app.ui.pages.loop_page import LoopPage

        method = LoopPage._parse_current_gate_results
        source_lines, _ = inspect.getsourcelines(method)
        source = "".join(source_lines)

        assert "parse_candidate_run(" in source, (
            "Preservation violated: _parse_current_gate_results no longer calls parse_candidate_run."
        )
        assert "self._current_gate_export_dir" in source, (
            "Preservation violated: _parse_current_gate_results no longer passes "
            "self._current_gate_export_dir as first arg."
        )
        assert "self._gate_run_started_at" in source, (
            "Preservation violated: _parse_current_gate_results no longer passes "
            "self._gate_run_started_at as second arg."
        )

    def test_parse_current_gate_results_passes_path_and_float(self, qapp, tmp_path):
        """Verify _parse_current_gate_results calls parse_candidate_run(Path, float) at runtime.

        **Validates: Requirements 3.4**
        """
        settings_state = _make_settings_state(tmp_path)
        page = _make_loop_page(settings_state)

        export_dir = tmp_path / "gate_export"
        export_dir.mkdir()
        started_at = time.time() - 10.0

        page._current_gate_export_dir = export_dir
        page._gate_run_started_at = started_at

        captured_args = []

        def fake_parse_candidate_run(export_dir_arg, started_at_arg):
            captured_args.append((export_dir_arg, started_at_arg))
            return MagicMock()

        with patch.object(page._improve_service, "parse_candidate_run", side_effect=fake_parse_candidate_run):
            page._parse_current_gate_results()

        assert len(captured_args) == 1, (
            f"parse_candidate_run should have been called once, got {len(captured_args)}"
        )
        export_dir_arg, started_at_arg = captured_args[0]
        assert isinstance(export_dir_arg, Path), (
            f"Preservation violated: parse_candidate_run first arg is {type(export_dir_arg).__name__}, "
            f"expected Path. Got: {export_dir_arg!r}"
        )
        assert isinstance(started_at_arg, float), (
            f"Preservation violated: parse_candidate_run second arg is {type(started_at_arg).__name__}, "
            f"expected float. Got: {started_at_arg!r}"
        )
        assert export_dir_arg == export_dir, (
            f"Preservation violated: parse_candidate_run called with export_dir={export_dir_arg!r}, "
            f"expected {export_dir!r}"
        )
        assert started_at_arg == started_at, (
            f"Preservation violated: parse_candidate_run called with started_at={started_at_arg!r}, "
            f"expected {started_at!r}"
        )


# ===========================================================================
# Property 3.5 -- Canonical run_gate_sequence behaviour preserved
# ===========================================================================

class TestCanonicalRunGateSequencePreserved:
    """Requirement 3.5: The canonical run_gate_sequence (second definition in
    loop_service.py) calls build_in_sample_gate_result and evaluate_gate1_hard_filters.

    Observation on UNFIXED code:
        Python resolves LoopService.run_gate_sequence to the LAST definition
        (lines ~1914+) which calls:
            gate1 = self.build_in_sample_gate_result(in_sample_summary)
            gate1_failures = self.evaluate_gate1_hard_filters(gate1, config)
        The stale first definition (lines ~1001) uses direct GateResult(...) construction
        and does NOT call build_in_sample_gate_result or evaluate_gate1_hard_filters.
    """

    def test_canonical_run_gate_sequence_source_calls_build_in_sample_gate_result(self):
        """Inspect run_gate_sequence source to confirm it calls build_in_sample_gate_result.

        **Validates: Requirements 3.5**
        """
        method = LoopService.run_gate_sequence
        source_lines, _ = inspect.getsourcelines(method)
        source = "".join(source_lines)

        assert "build_in_sample_gate_result" in source, (
            "Preservation violated: run_gate_sequence no longer calls build_in_sample_gate_result. "
            "Python may have resolved to the stale first definition."
        )
        assert "evaluate_gate1_hard_filters" in source, (
            "Preservation violated: run_gate_sequence no longer calls evaluate_gate1_hard_filters. "
            "Python may have resolved to the stale first definition."
        )

    def test_canonical_run_gate_sequence_does_not_use_direct_gate_result_construction(self):
        """Confirm the resolved run_gate_sequence does NOT use direct GateResult(...) for gate1.

        The stale definition constructs gate1 directly:
            gate1 = GateResult(gate_name="in_sample", passed=True, metrics=in_sample_summary)
        The canonical definition delegates to build_in_sample_gate_result.

        **Validates: Requirements 3.5**
        """
        method = LoopService.run_gate_sequence
        source_lines, start_line = inspect.getsourcelines(method)
        source = "".join(source_lines)

        # The stale definition has: gate1 = GateResult(gate_name="in_sample", passed=True, ...
        # The canonical definition does NOT have this pattern.
        stale_pattern = 'gate1 = GateResult('
        assert stale_pattern not in source, (
            f"Preservation violated: run_gate_sequence at line {start_line} uses direct "
            f"GateResult() construction for gate1. This is the stale definition. "
            f"The canonical definition should call build_in_sample_gate_result instead."
        )

    def test_canonical_run_gate_sequence_calls_mark_hard_filter_rejection_on_failure(self, tmp_path):
        """Run the canonical run_gate_sequence with a mock that triggers hard filter failure
        and assert _mark_hard_filter_rejection is called.

        **Validates: Requirements 3.5**
        """
        from app.core.models.loop_models import HardFilterFailure

        improve_service = MagicMock()
        loop_service = LoopService(improve_service)

        config = _make_loop_config()
        iteration = _make_loop_iteration()
        in_sample_summary = _make_backtest_summary(total_trades=5, win_rate=30.0, total_profit=-2.0)
        sandbox_dir = tmp_path / "sandbox"
        sandbox_dir.mkdir()

        # Make evaluate_gate1_hard_filters return a failure
        hard_filter_failure = HardFilterFailure(
            filter_name="min_trades",
            reason="Too few trades",
            evidence="5 < 30",
        )
        with patch.object(
            loop_service,
            "evaluate_gate1_hard_filters",
            return_value=[hard_filter_failure],
        ) as mock_eval:
            with patch.object(loop_service, "_mark_hard_filter_rejection") as mock_mark:
                result = loop_service.run_gate_sequence(
                    iteration=iteration,
                    in_sample_summary=in_sample_summary,
                    config=config,
                    sandbox_dir=sandbox_dir,
                    run_backtest_fn=None,
                )

        assert result is False, (
            "Preservation violated: run_gate_sequence should return False when hard filters fail."
        )
        mock_mark.assert_called_once(), (
            "Preservation violated: _mark_hard_filter_rejection was not called on hard filter failure."
        )


@given(
    strategy_name=st.sampled_from(["TestStrategy", "MyStrategy", "SampleStrat"]),
    total_trades=st.integers(min_value=1, max_value=200),
    win_rate=st.floats(min_value=10.0, max_value=90.0),
    total_profit=st.floats(min_value=-50.0, max_value=100.0),
)
@h_settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_pbt_canonical_run_gate_sequence_calls_build_in_sample_gate_result(
    tmp_path, strategy_name, total_trades, win_rate, total_profit
):
    """Property-based test: for any LoopConfig, the canonical run_gate_sequence
    always calls build_in_sample_gate_result (not the stale direct GateResult(...)
    construction).

    **Validates: Requirements 3.5**
    """
    improve_service = MagicMock()
    loop_service = LoopService(improve_service)

    config = _make_loop_config(strategy=strategy_name)
    iteration = _make_loop_iteration()
    in_sample_summary = _make_backtest_summary(
        strategy=strategy_name,
        total_trades=total_trades,
        win_rate=win_rate,
        total_profit=total_profit,
    )
    sandbox_dir = tmp_path / "sandbox"
    sandbox_dir.mkdir(exist_ok=True)

    build_called_with = []

    original_build = loop_service.build_in_sample_gate_result

    def tracking_build(summary):
        build_called_with.append(summary)
        return original_build(summary)

    with patch.object(loop_service, "build_in_sample_gate_result", side_effect=tracking_build):
        loop_service.run_gate_sequence(
            iteration=iteration,
            in_sample_summary=in_sample_summary,
            config=config,
            sandbox_dir=sandbox_dir,
            run_backtest_fn=None,
        )

    assert len(build_called_with) == 1, (
        f"PBT: build_in_sample_gate_result should be called once, got {len(build_called_with)}. "
        f"strategy={strategy_name!r}, total_trades={total_trades}, win_rate={win_rate}"
    )
    assert build_called_with[0] is in_sample_summary, (
        f"PBT: build_in_sample_gate_result called with wrong summary. "
        f"Expected the in_sample_summary passed to run_gate_sequence."
    )


# ===========================================================================
# Property 3.6 -- _restore_preferences / _save_preferences round-trip
# ===========================================================================

class TestPreferencesRoundTripPreserved:
    """Requirement 3.6: The canonical _restore_preferences and _save_preferences
    implementations read/write the same fields.

    Observation on UNFIXED code:
        Python resolves _restore_preferences and _save_preferences to the LAST
        definitions (lines ~1352+ and ~1411+) which handle all StrategyLabPreferences
        fields including date_from, date_to, and the newer fields.
        The stale first definitions (lines ~714, ~753) are dead code.
    """

    def test_save_then_restore_round_trips_all_fields(self, qapp, tmp_path):
        """Call _save_preferences then _restore_preferences and assert the same
        field values are recovered.

        **Validates: Requirements 3.6**
        """
        settings_state = _make_settings_state(tmp_path)
        page = _make_loop_page(settings_state)

        # Set specific values in the UI widgets
        page._max_iter_spin.setValue(15)
        page._target_profit_spin.setValue(7.5)
        page._target_wr_spin.setValue(60.0)
        page._target_dd_spin.setValue(15.0)
        page._target_trades_spin.setValue(50)
        page._stop_on_target_chk.setChecked(False)
        page._date_from_edit.setText("20240101")
        page._date_to_edit.setText("20240131")
        page._timerange_edit.setText("20240101-20240131")
        page._oos_split_spin.setValue(25.0)
        page._wf_folds_spin.setValue(3)
        page._stress_fee_spin.setValue(3.0)
        page._stress_slippage_spin.setValue(0.2)
        page._stress_profit_spin.setValue(60.0)
        page._consistency_spin.setValue(25.0)
        page._validation_mode_combo.setCurrentIndex(1)  # "quick"
        page._iteration_mode_combo.setCurrentIndex(0)   # "rule_based"
        page._hyperopt_epochs_spin.setValue(300)
        page._ai_advisor_chk.setChecked(True)
        page._selected_pairs = ["BTC/USDT", "ETH/USDT"]
        page._pairs_btn.setText("Select Pairs (2)")

        # Capture the settings that will be saved
        saved_settings = []

        def fake_save_settings(settings_obj):
            import copy
            saved_settings.append(copy.deepcopy(settings_obj))

        settings_state.settings_service.save_settings = MagicMock(side_effect=fake_save_settings)

        # Save preferences
        page._save_preferences()

        assert len(saved_settings) == 1, "save_settings should have been called once"
        saved_prefs = saved_settings[0].strategy_lab

        # Verify saved values match what was set in the UI
        assert saved_prefs.max_iterations == 15, (
            f"Round-trip failed: max_iterations saved as {saved_prefs.max_iterations}, expected 15"
        )
        assert saved_prefs.target_profit_pct == 7.5, (
            f"Round-trip failed: target_profit_pct saved as {saved_prefs.target_profit_pct}, expected 7.5"
        )
        assert saved_prefs.target_win_rate == 60.0, (
            f"Round-trip failed: target_win_rate saved as {saved_prefs.target_win_rate}, expected 60.0"
        )
        assert saved_prefs.target_max_drawdown == 15.0, (
            f"Round-trip failed: target_max_drawdown saved as {saved_prefs.target_max_drawdown}, expected 15.0"
        )
        assert saved_prefs.target_min_trades == 50, (
            f"Round-trip failed: target_min_trades saved as {saved_prefs.target_min_trades}, expected 50"
        )
        assert saved_prefs.stop_on_first_profitable is False, (
            f"Round-trip failed: stop_on_first_profitable saved as {saved_prefs.stop_on_first_profitable}, expected False"
        )
        assert saved_prefs.date_from == "20240101", (
            f"Round-trip failed: date_from saved as {saved_prefs.date_from!r}, expected '20240101'"
        )
        assert saved_prefs.date_to == "20240131", (
            f"Round-trip failed: date_to saved as {saved_prefs.date_to!r}, expected '20240131'"
        )
        assert saved_prefs.oos_split_pct == 25.0, (
            f"Round-trip failed: oos_split_pct saved as {saved_prefs.oos_split_pct}, expected 25.0"
        )
        assert saved_prefs.walk_forward_folds == 3, (
            f"Round-trip failed: walk_forward_folds saved as {saved_prefs.walk_forward_folds}, expected 3"
        )
        assert saved_prefs.validation_mode == "quick", (
            f"Round-trip failed: validation_mode saved as {saved_prefs.validation_mode!r}, expected 'quick'"
        )
        assert saved_prefs.hyperopt_epochs == 300, (
            f"Round-trip failed: hyperopt_epochs saved as {saved_prefs.hyperopt_epochs}, expected 300"
        )
        assert saved_prefs.ai_advisor_enabled is True, (
            f"Round-trip failed: ai_advisor_enabled saved as {saved_prefs.ai_advisor_enabled}, expected True"
        )
        assert saved_prefs.pairs == "BTC/USDT,ETH/USDT", (
            f"Round-trip failed: pairs saved as {saved_prefs.pairs!r}, expected 'BTC/USDT,ETH/USDT'"
        )

        # Now restore from the saved settings and verify the UI is updated
        settings_state.settings_service.load_settings = MagicMock(return_value=saved_settings[0])

        # Reset UI to defaults before restoring
        page._max_iter_spin.setValue(10)
        page._target_profit_spin.setValue(5.0)
        page._date_from_edit.setText("")
        page._date_to_edit.setText("")

        page._restore_preferences()

        # Verify the UI was restored to the saved values
        assert page._max_iter_spin.value() == 15, (
            f"Round-trip failed: max_iter_spin restored to {page._max_iter_spin.value()}, expected 15"
        )
        assert page._target_profit_spin.value() == 7.5, (
            f"Round-trip failed: target_profit_spin restored to {page._target_profit_spin.value()}, expected 7.5"
        )
        assert page._date_from_edit.text() == "20240101", (
            f"Round-trip failed: date_from_edit restored to {page._date_from_edit.text()!r}, expected '20240101'"
        )
        assert page._date_to_edit.text() == "20240131", (
            f"Round-trip failed: date_to_edit restored to {page._date_to_edit.text()!r}, expected '20240131'"
        )
        assert page._oos_split_spin.value() == 25.0, (
            f"Round-trip failed: oos_split_spin restored to {page._oos_split_spin.value()}, expected 25.0"
        )
        assert page._validation_mode_combo.currentIndex() == 1, (
            f"Round-trip failed: validation_mode_combo restored to index {page._validation_mode_combo.currentIndex()}, expected 1 (quick)"
        )
        assert page._hyperopt_epochs_spin.value() == 300, (
            f"Round-trip failed: hyperopt_epochs_spin restored to {page._hyperopt_epochs_spin.value()}, expected 300"
        )


    def test_canonical_restore_preferences_uses_ensure_loop_runtime_state(self):
        """Confirm the resolved _restore_preferences calls _ensure_loop_runtime_state.

        The canonical definition (lines ~1352+) calls _ensure_loop_runtime_state().
        The stale definition (lines ~714) does NOT.
        Python resolves to the canonical definition on unfixed code.

        **Validates: Requirements 3.6**
        """
        from app.ui.pages.loop_page import LoopPage

        method = LoopPage._restore_preferences
        source_lines, start_line = inspect.getsourcelines(method)
        source = "".join(source_lines)

        assert "_ensure_loop_runtime_state" in source, (
            f"Preservation violated: _restore_preferences at line {start_line} does not call "
            f"_ensure_loop_runtime_state(). Python may have resolved to the stale definition."
        )
        assert "_date_from_edit" in source, (
            f"Preservation violated: _restore_preferences at line {start_line} does not reference "
            f"_date_from_edit. Python may have resolved to the stale definition."
        )

    def test_canonical_save_preferences_uses_ensure_loop_runtime_state(self):
        """Confirm the resolved _save_preferences calls _ensure_loop_runtime_state.

        **Validates: Requirements 3.6**
        """
        from app.ui.pages.loop_page import LoopPage

        method = LoopPage._save_preferences
        source_lines, start_line = inspect.getsourcelines(method)
        source = "".join(source_lines)

        assert "_ensure_loop_runtime_state" in source, (
            f"Preservation violated: _save_preferences at line {start_line} does not call "
            f"_ensure_loop_runtime_state(). Python may have resolved to the stale definition."
        )
        assert "_date_from_edit" in source, (
            f"Preservation violated: _save_preferences at line {start_line} does not reference "
            f"_date_from_edit. Python may have resolved to the stale definition."
        )


# ===========================================================================
# Additional source-level preservation checks
# ===========================================================================

class TestSourceLevelPreservation:
    """Source-level checks that confirm the canonical definitions are intact
    and the stale copies are still present (on unfixed code).
    """

    def _count_method_definitions(self, filepath: Path, method_name: str) -> list:
        """Return line numbers of all definitions of method_name in filepath."""
        import ast
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
        lines = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == method_name:
                lines.append(node.lineno)
        return lines

    def test_python_resolves_run_gate_sequence_to_canonical_definition(self):
        """Confirm Python resolves run_gate_sequence to the canonical definition
        that calls build_in_sample_gate_result.

        On unfixed code there are TWO definitions; Python resolves to the last one.
        This test confirms the resolved definition is the canonical one.

        **Validates: Requirements 3.5**
        """
        method = LoopService.run_gate_sequence
        source_lines, start_line = inspect.getsourcelines(method)
        source = "".join(source_lines)

        assert "build_in_sample_gate_result" in source, (
            f"Python resolved run_gate_sequence to line {start_line} which does NOT call "
            f"build_in_sample_gate_result. This is the stale definition."
        )
        assert "evaluate_gate1_hard_filters" in source, (
            f"Python resolved run_gate_sequence to line {start_line} which does NOT call "
            f"evaluate_gate1_hard_filters. This is the stale definition."
        )

    def test_python_resolves_restore_preferences_to_canonical_definition(self):
        """Confirm Python resolves _restore_preferences to the canonical definition.

        **Validates: Requirements 3.6**
        """
        from app.ui.pages.loop_page import LoopPage

        method = LoopPage._restore_preferences
        source_lines, start_line = inspect.getsourcelines(method)
        source = "".join(source_lines)

        assert "_ensure_loop_runtime_state" in source, (
            f"Python resolved _restore_preferences to line {start_line} (stale definition). "
            f"The canonical definition calls _ensure_loop_runtime_state()."
        )

    def test_start_gate_backtest_does_not_reference_on_process_stdout(self):
        """Confirm _start_gate_backtest does NOT reference _on_process_stdout.

        The buggy _run_baseline_backtest uses self._on_process_stdout.
        The correct _start_gate_backtest uses self._terminal.append_output.
        This test confirms the gate backtest method is unaffected.

        **Validates: Requirements 3.2**
        """
        from app.ui.pages.loop_page import LoopPage

        method = LoopPage._start_gate_backtest
        source_lines, _ = inspect.getsourcelines(method)
        source = "".join(source_lines)

        assert "_on_process_stdout" not in source, (
            "Preservation violated: _start_gate_backtest references _on_process_stdout. "
            "This non-existent attribute should only appear in the buggy _run_baseline_backtest."
        )
        assert "_on_process_stderr" not in source, (
            "Preservation violated: _start_gate_backtest references _on_process_stderr. "
            "This non-existent attribute should only appear in the buggy _run_baseline_backtest."
        )

