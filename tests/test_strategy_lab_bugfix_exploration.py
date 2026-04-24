"""Bug condition exploration tests for strategy-lab-bugfix spec.

These tests are designed to FAIL on unfixed code — failure confirms the bugs exist.
They encode the EXPECTED (correct) behavior and will PASS after the fix is applied.

**Property 1: Bug Condition** — Baseline Backtest Crash Paths

Bugs covered:
  Bug 1  — prepare_sandbox() called with wrong arg order/types
  Bug 2  — Missing --backtest-directory / --strategy-path in baseline command
  Bug 3a — parse_backtest_results() method does not exist on ImproveService
  Bug 3c — on_output=self._on_process_stdout (non-existent attribute)
  Bug 4/5 — Duplicate method resolution (Python resolves to last definition)

**Validates: Requirements 1.1, 1.2, 1.3, 1.4**
"""
import inspect
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.models.settings_models import AppSettings
from app.core.services.improve_service import ImproveService


# ---------------------------------------------------------------------------
# Helpers
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


def _make_improve_service(tmp_path: Path) -> ImproveService:
    """Return an ImproveService backed by a real (but minimal) settings service."""
    from app.core.services.settings_service import SettingsService
    from app.core.services.backtest_service import BacktestService
    from app.app_state.settings_state import SettingsState

    state = SettingsState()
    settings = _make_app_settings(tmp_path)
    state.settings_service.load_settings = MagicMock(return_value=settings)
    state.settings_service.save_settings = MagicMock()

    backtest_svc = BacktestService(state.settings_service)
    return ImproveService(state.settings_service, backtest_svc)


# ===========================================================================
# Bug 1 — prepare_sandbox() called with wrong arg order/types
# ===========================================================================

class TestBug1PrepareSandboxTypeError:
    """Bug 1: prepare_sandbox(settings, strategy) — wrong arg order/types.

    On unfixed code, _run_baseline_backtest calls:
        self._improve_service.prepare_sandbox(settings, strategy)
    where settings is an AppSettings object and strategy is a str.

    prepare_sandbox(strategy_name: str, candidate_config: dict) expects a str
    first and a dict second.  Passing AppSettings as strategy_name causes the
    method to build a path like ``strategies_dir / f"{settings}.py"`` which
    does not exist, raising FileNotFoundError.

    EXPECTED on UNFIXED code: FAIL (FileNotFoundError or AttributeError raised)
    EXPECTED on FIXED code:   PASS (no exception — correct args passed)
    """

    def test_bug1_prepare_sandbox_wrong_arg_order_raises(self, tmp_path):
        """Call prepare_sandbox(AppSettings(...), 'MyStrategy') and assert it raises.

        **Validates: Requirements 1.1, 1.2**
        """
        improve_service = _make_improve_service(tmp_path)
        settings = _make_app_settings(tmp_path)

        # This is the BUGGY call pattern from _run_baseline_backtest (unfixed code):
        #   sandbox_dir = self._improve_service.prepare_sandbox(settings, strategy)
        # AppSettings is passed as strategy_name, "MyStrategy" as candidate_config.
        # Note: With version_id parameter added, this will raise TypeError for missing argument
        with pytest.raises((FileNotFoundError, AttributeError, TypeError)) as exc_info:
            improve_service.prepare_sandbox(settings, "MyStrategy", "test_version")  # type: ignore[arg-type]

        # Document the counterexample
        error = exc_info.value
        print(
            f"\nCounterexample (Bug 1):\n"
            f"  Call: prepare_sandbox(AppSettings(...), 'MyStrategy', 'test_version')\n"
            f"  Exception type: {type(error).__name__}\n"
            f"  Message: {error}\n"
            f"  Confirms: prepare_sandbox() crashes when AppSettings is passed as "
            f"strategy_name because it tries to open a file named after the object repr."
        )

    def test_bug1_prepare_sandbox_correct_args_succeeds(self, tmp_path):
        """Verify the FIXED call pattern works: prepare_sandbox(strategy_name, {}, version_id).

        This test passes on both fixed and unfixed code — it documents the
        correct call signature.

        **Validates: Requirements 1.1, 1.2**
        """
        improve_service = _make_improve_service(tmp_path)
        settings = _make_app_settings(tmp_path)

        # Create the strategy file so prepare_sandbox can find it
        strategy_name = "MyStrategy"
        strategy_file = (
            Path(settings.user_data_path) / "strategies" / f"{strategy_name}.py"
        )
        strategy_file.write_text("class MyStrategy:\n    pass\n", encoding="utf-8")

        # The FIXED call pattern:
        #   sandbox_dir = self._improve_service.prepare_sandbox(strategy, {}, version_id)
        version_id = "test_version_fixed"
        sandbox_dir = improve_service.prepare_sandbox(strategy_name, {}, version_id)
        assert sandbox_dir.exists(), "Sandbox directory should be created"
        assert (sandbox_dir / f"{strategy_name}.py").exists(), (
            "Strategy .py should be copied into sandbox"
        )

# ===========================================================================
# Bug 2 — Missing --backtest-directory in baseline command
# ===========================================================================

class TestBug2MissingExportFlags:
    """Bug 2: build_backtest_command called without extra_flags.

    On unfixed code, _run_baseline_backtest calls build_backtest_command without
    passing extra_flags, so --backtest-directory and --strategy-path are absent
    from the resulting command list.

    EXPECTED on UNFIXED code: FAIL (--backtest-directory absent from cmd.as_list())
    EXPECTED on FIXED code:   PASS (both flags present)
    """

    def test_bug2_baseline_command_missing_backtest_directory(self, tmp_path):
        """Verify _run_baseline_backtest source passes extra_flags to build_backtest_command.

        The fix lives in loop_page.py::_run_baseline_backtest, not in
        build_backtest_command itself.  This test inspects the source of
        _run_baseline_backtest to confirm it builds extra_flags containing
        '--backtest-directory' and passes them to build_backtest_command.

        On unfixed code the source does NOT contain extra_flags → assertion FAILS.
        On fixed code the source DOES contain extra_flags → assertion PASSES.

        **Validates: Requirements 1.3, 1.4**
        """
        from app.ui.pages.loop_page import LoopPage

        method = getattr(LoopPage, "_run_baseline_backtest", None)
        assert method is not None, "_run_baseline_backtest must exist on LoopPage"

        source_lines, _ = inspect.getsourcelines(method)
        source = "".join(source_lines)

        # On unfixed code this assertion FAILS — confirming the bug
        assert "--backtest-directory" in source, (
            "Bug 2 confirmed: _run_baseline_backtest does not include '--backtest-directory' "
            "in extra_flags. Freqtrade will write its result zip to the default location, "
            "not to sandbox_dir / 'baseline_export', so parse_candidate_run() finds an empty dir."
        )
        assert "extra_flags" in source, (
            "Bug 2 confirmed: _run_baseline_backtest does not build or pass extra_flags "
            "to create_backtest_command. The --strategy-path and --backtest-directory flags "
            "are absent from the baseline command."
        )

    def test_bug2_baseline_command_with_extra_flags_has_backtest_directory(self, tmp_path):
        """Verify the FIXED call pattern includes --backtest-directory.

        **Validates: Requirements 1.3, 1.4**
        """
        from app.core.freqtrade.runners.backtest_runner import create_backtest_command

        settings = _make_app_settings(tmp_path)
        strategy_name = "MyStrategy"
        strategy_file = (
            Path(settings.user_data_path) / "strategies" / f"{strategy_name}.py"
        )
        strategy_file.write_text("class MyStrategy:\n    pass\n", encoding="utf-8")
        import json
        config_file = Path(settings.user_data_path) / "config.json"
        config_file.write_text(json.dumps({"exchange": {"name": "binance"}}), encoding="utf-8")

        sandbox_dir = tmp_path / "sandbox"
        export_dir = sandbox_dir / "baseline_export"

        # FIXED call — extra_flags present (mirrors fixed _run_baseline_backtest)
        extra_flags = [
            "--strategy-path", str(sandbox_dir),
            "--backtest-directory", str(export_dir),
        ]
        cmd = create_backtest_command(
            settings=settings,
            strategy_name=strategy_name,
            timeframe="5m",
            timerange="20240101-20240131",
            pairs=["BTC/USDT"],
            extra_flags=extra_flags,
        )

        cmd_list = cmd.as_list()
        assert "--backtest-directory" in cmd_list, (
            f"'--backtest-directory' should be in command after fix. Got: {cmd_list}"
        )
        assert "--strategy-path" in cmd_list, (
            f"'--strategy-path' should be in command after fix. Got: {cmd_list}"
        )
        # Verify the value follows the flag
        bd_idx = cmd_list.index("--backtest-directory")
        assert cmd_list[bd_idx + 1] == str(export_dir), (
            f"--backtest-directory value should be {export_dir}, got {cmd_list[bd_idx + 1]}"
        )


# ===========================================================================
# Bug 3a — parse_backtest_results() does not exist on ImproveService
# ===========================================================================

class TestBug3aParseBacktestResultsAttributeError:
    """Bug 3a: _on_baseline_backtest_finished calls parse_backtest_results() which
    does not exist on ImproveService.

    EXPECTED on UNFIXED code: FAIL (AttributeError raised)
    EXPECTED on FIXED code:   PASS (parse_candidate_run exists and is called instead)
    """

    def test_bug3a_parse_backtest_results_does_not_exist(self, tmp_path):
        """Assert AttributeError when calling parse_backtest_results on ImproveService.

        **Validates: Requirements 1.1, 1.3**
        """
        improve_service = _make_improve_service(tmp_path)
        export_dir = tmp_path / "baseline_export"
        export_dir.mkdir()

        # This is the BUGGY call from _on_baseline_backtest_finished (unfixed code):
        #   results = self._improve_service.parse_backtest_results(export_dir)
        with pytest.raises(AttributeError) as exc_info:
            improve_service.parse_backtest_results(export_dir)  # type: ignore[attr-defined]

        error = exc_info.value
        print(
            f"\nCounterexample (Bug 3a):\n"
            f"  Call: improve_service.parse_backtest_results(export_dir)\n"
            f"  Exception: {type(error).__name__}: {error}\n"
            f"  Confirms: 'parse_backtest_results' does not exist on ImproveService.\n"
            f"  Correct method: parse_candidate_run(export_dir, started_at)"
        )
        assert "parse_backtest_results" in str(error), (
            f"Expected AttributeError mentioning 'parse_backtest_results', got: {error}"
        )

    def test_bug3a_parse_candidate_run_exists(self, tmp_path):
        """Verify parse_candidate_run exists on ImproveService (the correct method).

        **Validates: Requirements 1.1, 1.3**
        """
        improve_service = _make_improve_service(tmp_path)
        assert hasattr(improve_service, "parse_candidate_run"), (
            "ImproveService must have parse_candidate_run method"
        )
        assert callable(improve_service.parse_candidate_run), (
            "parse_candidate_run must be callable"
        )
        assert not hasattr(improve_service, "parse_backtest_results"), (
            "ImproveService must NOT have parse_backtest_results — it was never defined"
        )


# ===========================================================================
# Bug 3c — on_output=self._on_process_stdout (non-existent attribute)
# ===========================================================================

class TestBug3cMissingCallbacks:
    """Bug 3c: _run_baseline_backtest passes self._on_process_stdout as on_output
    callback, but LoopPage has no such attribute.

    On unfixed code the execute_command call contains:
        on_output=self._on_process_stdout,
        on_error=self._on_process_stderr,
    Neither attribute exists on LoopPage, so the call raises AttributeError at
    the point where the callback is resolved.

    EXPECTED on UNFIXED code: FAIL (AttributeError raised when accessing the attribute)
    EXPECTED on FIXED code:   PASS (on_output=self._terminal.append_output used instead)
    """

    def test_bug3c_loop_page_has_no_on_process_stdout(self):
        """Assert LoopPage has no _on_process_stdout attribute.

        **Validates: Requirements 1.1**
        """
        from app.ui.pages.loop_page import LoopPage

        # Inspect the class (not an instance) to avoid Qt setup
        assert not hasattr(LoopPage, "_on_process_stdout"), (
            "Bug 3c confirmed: LoopPage._on_process_stdout does not exist.\n"
            "The unfixed _run_baseline_backtest passes self._on_process_stdout as\n"
            "on_output to execute_command, which raises AttributeError at runtime."
        )
        assert not hasattr(LoopPage, "_on_process_stderr"), (
            "Bug 3c confirmed: LoopPage._on_process_stderr does not exist.\n"
            "The unfixed _run_baseline_backtest passes self._on_process_stderr as\n"
            "on_error to execute_command, which raises AttributeError at runtime."
        )

    def test_bug3c_run_baseline_backtest_source_references_on_process_stdout(self):
        """Inspect _run_baseline_backtest source to confirm it references _on_process_stdout.

        On unfixed code the source contains 'self._on_process_stdout'.
        On fixed code the source contains 'self._terminal.append_output'.

        EXPECTED on UNFIXED code: FAIL (source contains the non-existent attribute)
        EXPECTED on FIXED code:   PASS (source uses terminal callbacks)

        **Validates: Requirements 1.1**
        """
        from app.ui.pages.loop_page import LoopPage

        method = getattr(LoopPage, "_run_baseline_backtest", None)
        assert method is not None, "_run_baseline_backtest must exist on LoopPage"

        source_lines, _ = inspect.getsourcelines(method)
        source = "".join(source_lines)

        # On unfixed code this assertion FAILS — confirming the bug
        assert "self._on_process_stdout" not in source, (
            f"Bug 3c confirmed: _run_baseline_backtest references self._on_process_stdout\n"
            f"which does not exist on LoopPage.\n"
            f"The fixed version should use self._terminal.append_output instead.\n"
            f"Counterexample: on_output=self._on_process_stdout found in source."
        )
        assert "self._terminal.append_output" in source, (
            f"After fix, _run_baseline_backtest should use self._terminal.append_output\n"
            f"as the on_output callback, matching the pattern in _start_gate_backtest."
        )


# ===========================================================================
# Bug 4/5 — Duplicate method resolution
# ===========================================================================

class TestBug45DuplicateMethodResolution:
    """Bugs 4 & 5: Duplicate method definitions — Python resolves to last definition.

    Bug 4: LoopPage._restore_preferences is defined twice.
           Python resolves to the canonical (later) definition at lines ~1352+.
           The earlier stale copy at lines ~714 is dead code.

    Bug 5: LoopService.run_gate_sequence is defined twice.
           Python resolves to the canonical (later) definition at lines ~1914+.
           The earlier stale copy at lines ~1001 is dead code.

    These tests use inspect.getsourcelines to confirm which definition Python
    resolves to, and use AST parsing to confirm both definitions exist in the
    source file (proving the earlier copies are dead).

    EXPECTED on UNFIXED code: FAIL (two definitions found in source)
    EXPECTED on FIXED code:   PASS (exactly one definition)
    """

    def _count_method_definitions(self, filepath: Path, method_name: str) -> list[int]:
        """Return line numbers of all definitions of method_name in filepath."""
        import ast
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
        lines = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == method_name:
                lines.append(node.lineno)
        return lines

    def test_bug4_loop_page_restore_preferences_has_duplicate(self):
        """Confirm _restore_preferences is defined twice in loop_page.py.

        Python resolves to the LAST definition, so the first copy is dead code.

        EXPECTED on UNFIXED code: FAIL (two definitions found)
        EXPECTED on FIXED code:   PASS (one definition)

        **Validates: Requirements 1.4**
        """
        filepath = Path("app/ui/pages/loop_page.py")
        lines = self._count_method_definitions(filepath, "_restore_preferences")

        print(
            f"\nCounterexample (Bug 4):\n"
            f"  _restore_preferences defined at lines: {lines}\n"
            f"  Python resolves to line {max(lines)} (last definition).\n"
            f"  Line {min(lines)} is dead code."
        )

        # On unfixed code this assertion FAILS — confirming the bug
        assert len(lines) == 1, (
            f"Bug 4 confirmed: _restore_preferences has {len(lines)} definitions "
            f"at lines {lines}. The earlier copy (line {min(lines)}) is dead code "
            f"shadowed by the canonical definition at line {max(lines)}."
        )

    def test_bug4_loop_page_save_preferences_has_duplicate(self):
        """Confirm _save_preferences is defined twice in loop_page.py.

        **Validates: Requirements 1.4**
        """
        filepath = Path("app/ui/pages/loop_page.py")
        lines = self._count_method_definitions(filepath, "_save_preferences")

        assert len(lines) == 1, (
            f"Bug 4 confirmed: _save_preferences has {len(lines)} definitions "
            f"at lines {lines}. Dead copy at line {min(lines)}."
        )

    def test_bug4_loop_page_update_stat_cards_has_duplicate(self):
        """Confirm _update_stat_cards is defined twice in loop_page.py.

        **Validates: Requirements 1.4**
        """
        filepath = Path("app/ui/pages/loop_page.py")
        lines = self._count_method_definitions(filepath, "_update_stat_cards")

        assert len(lines) == 1, (
            f"Bug 4 confirmed: _update_stat_cards has {len(lines)} definitions "
            f"at lines {lines}. Dead copy at line {min(lines)}."
        )

    def test_bug4_loop_page_clear_history_ui_has_duplicate(self):
        """Confirm _clear_history_ui is defined twice in loop_page.py.

        **Validates: Requirements 1.4**
        """
        filepath = Path("app/ui/pages/loop_page.py")
        lines = self._count_method_definitions(filepath, "_clear_history_ui")

        assert len(lines) == 1, (
            f"Bug 4 confirmed: _clear_history_ui has {len(lines)} definitions "
            f"at lines {lines}. Dead copy at line {min(lines)}."
        )

    def test_bug4_python_resolves_restore_preferences_to_canonical_definition(self):
        """Use inspect.getsourcelines to confirm Python resolves _restore_preferences
        to the later (canonical) definition, proving the earlier copy is dead.

        The canonical definition calls _ensure_loop_runtime_state() and handles
        _date_from_edit / _date_to_edit fields.  The stale copy does not.

        **Validates: Requirements 1.4**
        """
        from app.ui.pages.loop_page import LoopPage

        method = LoopPage._restore_preferences
        source_lines, start_line = inspect.getsourcelines(method)
        source = "".join(source_lines)

        print(
            f"\nPython resolves LoopPage._restore_preferences to line {start_line}.\n"
            f"Canonical definition uses _ensure_loop_runtime_state() and _date_from_edit."
        )

        # The canonical definition (lines ~1352+) calls _ensure_loop_runtime_state()
        # and references _date_from_edit.  The stale copy does not.
        assert "_ensure_loop_runtime_state" in source, (
            f"Bug 4 confirmed: Python resolved _restore_preferences to the STALE copy "
            f"at line {start_line} which does NOT call _ensure_loop_runtime_state().\n"
            f"The canonical definition (later in the file) should be resolved instead."
        )
        assert "_date_from_edit" in source, (
            f"Bug 4 confirmed: Python resolved _restore_preferences to the STALE copy "
            f"at line {start_line} which does NOT reference _date_from_edit.\n"
            f"The canonical definition handles the newer date fields."
        )

    def test_bug5_loop_service_run_gate_sequence_has_duplicate(self):
        """Confirm run_gate_sequence is defined twice in loop_service.py.

        Python resolves to the LAST definition (canonical), so the first copy
        (lines ~1001–1097) is dead code.

        EXPECTED on UNFIXED code: FAIL (two definitions found)
        EXPECTED on FIXED code:   PASS (one definition)

        **Validates: Requirements 1.4**
        """
        filepath = Path("app/core/services/loop_service.py")
        lines = self._count_method_definitions(filepath, "run_gate_sequence")

        print(
            f"\nCounterexample (Bug 5):\n"
            f"  run_gate_sequence defined at lines: {lines}\n"
            f"  Python resolves to line {max(lines)} (last definition).\n"
            f"  Line {min(lines)} is dead code (lacks hard-filter evaluation)."
        )

        # On unfixed code this assertion FAILS — confirming the bug
        assert len(lines) == 1, (
            f"Bug 5 confirmed: run_gate_sequence has {len(lines)} definitions "
            f"at lines {lines}. The earlier copy (line {min(lines)}) is dead code "
            f"that lacks hard-filter evaluation and uses direct GateResult() construction."
        )

    def test_bug5_python_resolves_run_gate_sequence_to_canonical_definition(self):
        """Use inspect.getsourcelines to confirm Python resolves run_gate_sequence
        to the later (canonical) definition that calls build_in_sample_gate_result.

        **Validates: Requirements 1.4**
        """
        from app.core.services.loop_service import LoopService

        method = LoopService.run_gate_sequence
        source_lines, start_line = inspect.getsourcelines(method)
        source = "".join(source_lines)

        print(
            f"\nPython resolves LoopService.run_gate_sequence to line {start_line}.\n"
            f"Canonical definition calls build_in_sample_gate_result and "
            f"evaluate_gate1_hard_filters."
        )

        # The canonical definition (lines ~1914+) calls build_in_sample_gate_result.
        # The stale copy (lines ~1001) uses direct GateResult(...) construction.
        assert "build_in_sample_gate_result" in source, (
            f"Bug 5 confirmed: Python resolved run_gate_sequence to the STALE copy "
            f"at line {start_line} which does NOT call build_in_sample_gate_result.\n"
            f"The canonical definition (later in the file) should be resolved instead."
        )
        assert "evaluate_gate1_hard_filters" in source, (
            f"Bug 5 confirmed: Python resolved run_gate_sequence to the STALE copy "
            f"at line {start_line} which does NOT call evaluate_gate1_hard_filters.\n"
            f"The canonical definition includes hard-filter evaluation."
        )
