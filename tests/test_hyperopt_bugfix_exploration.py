"""Bug condition exploration tests for the hyperopt-optimize-bugfix spec.

These tests MUST FAIL on the current (unfixed) code — that failure is the
success condition for this task.  They will PASS once all three bugs are fixed.

Bugs under investigation
------------------------
Bug 1 — commands.create_optimize_command wrapper is missing `epochs`, `spaces`,
         and `hyperopt_loss` parameters.  Any call that passes one of those
         kwargs raises TypeError immediately.

Bug 2 — optimize_runner.create_optimize_command constructs OptimizeRunCommand
         without the required `export_dir` field, raising TypeError on
         dataclass instantiation.

Bug 3 — create_download_data_command calls str(paths.strategy_file)
         unconditionally.  When paths.strategy_file is None (the normal case
         for download-data), the model field is set to the literal string
         "None" instead of None / "".

Expected outcome on UNFIXED code
---------------------------------
All 5 tests FAIL — this confirms the bugs exist:
  • Bug 1 tests: TypeError raised by the wrapper → test fails (expected success)
  • Bug 2 test:  TypeError raised by the runner  → test fails (expected success)
  • Bug 3 test:  result.strategy_file == "None"  → assertion fails

Counterexamples documented at the bottom of this module.
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.models.settings_models import AppSettings
from app.core.models.command_models import OptimizeRunCommand, ResolvedRunPaths


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

def _make_settings(tmp_path: Path) -> AppSettings:
    """Return a minimal AppSettings wired to a temporary directory tree.

    Directory layout created::

        tmp_path/
            user_data/
                config.json          ← required by config_resolver
                strategies/
                    MyStrategy.py    ← required by strategy_resolver (Bug 2)
    """
    user_data = tmp_path / "user_data"
    user_data.mkdir(parents=True)

    strategies_dir = user_data / "strategies"
    strategies_dir.mkdir()

    # Minimal config.json so find_config_file_path succeeds
    config_file = user_data / "config.json"
    config_file.write_text(json.dumps({}), encoding="utf-8")

    # Minimal strategy file so find_strategy_file_path succeeds (needed for Bug 2)
    strategy_file = strategies_dir / "MyStrategy.py"
    strategy_file.write_text(
        "# dummy strategy\nclass MyStrategy:\n    timeframe = '5m'\n",
        encoding="utf-8",
    )

    return AppSettings(
        python_executable=sys.executable,  # real interpreter — create_command needs it
        user_data_path=str(user_data),
        use_module_execution=True,
    )


# ---------------------------------------------------------------------------
# Bug 1 — Wrapper signature mismatch
# ---------------------------------------------------------------------------

class TestBug1WrapperSignatureMismatch:
    """Bug 1: commands.create_optimize_command is missing epochs/spaces/hyperopt_loss.

    **Property 1: Bug Condition** — isBugCondition_1(call) is True when the
    call passes `epochs`, `spaces`, or `hyperopt_loss` as a keyword argument.

    Expected on UNFIXED code: FAIL (TypeError raised — test expects success)
    Expected on FIXED code:   PASS (no TypeError — returns OptimizeRunCommand)

    Validates: Requirements 1.1, 1.2, 1.3
    """

    def test_bug1_epochs_kwarg_does_not_raise(self, tmp_path: Path) -> None:
        """isBugCondition_1: call with epochs= should succeed on fixed code.

        On UNFIXED code this raises TypeError, causing the test to FAIL.
        That failure confirms the bug exists.

        Counterexample (unfixed):
            TypeError: create_optimize_command() got an unexpected keyword
            argument 'epochs'
        """
        from app.core.freqtrade import commands

        settings = _make_settings(tmp_path)

        # On UNFIXED code: TypeError raised → test FAILS (confirms bug)
        # On FIXED code:   returns OptimizeRunCommand → test PASSES
        result = commands.create_optimize_command(
            settings,
            "MyStrategy",
            "5m",
            timerange="20240101-",
            epochs=100,
        )
        assert isinstance(result, OptimizeRunCommand)

    def test_bug1_spaces_kwarg_does_not_raise(self, tmp_path: Path) -> None:
        """isBugCondition_1: call with spaces= should succeed on fixed code.

        On UNFIXED code this raises TypeError, causing the test to FAIL.

        Counterexample (unfixed):
            TypeError: create_optimize_command() got an unexpected keyword
            argument 'spaces'
        """
        from app.core.freqtrade import commands

        settings = _make_settings(tmp_path)

        result = commands.create_optimize_command(
            settings,
            "MyStrategy",
            "5m",
            epochs=100,
            spaces=["roi"],
        )
        assert isinstance(result, OptimizeRunCommand)

    def test_bug1_hyperopt_loss_kwarg_does_not_raise(self, tmp_path: Path) -> None:
        """isBugCondition_1: call with hyperopt_loss= should succeed on fixed code.

        On UNFIXED code this raises TypeError, causing the test to FAIL.

        Counterexample (unfixed):
            TypeError: create_optimize_command() got an unexpected keyword
            argument 'hyperopt_loss'
        """
        from app.core.freqtrade import commands

        settings = _make_settings(tmp_path)

        result = commands.create_optimize_command(
            settings,
            "MyStrategy",
            "5m",
            epochs=100,
            hyperopt_loss="SharpeHyperOptLoss",
        )
        assert isinstance(result, OptimizeRunCommand)


# ---------------------------------------------------------------------------
# Bug 2 — Missing export_dir in OptimizeRunCommand construction
# ---------------------------------------------------------------------------

class TestBug2MissingExportDir:
    """Bug 2: optimize_runner.create_optimize_command omits export_dir.

    **Property 2: Bug Condition** — isBugCondition_2(runner_call) is True for
    any invocation of the runner because OptimizeRunCommand is always
    constructed without export_dir.

    Expected on UNFIXED code: FAIL (TypeError raised — test expects success)
    Expected on FIXED code:   PASS (no TypeError — result.export_dir is set)

    Validates: Requirements 1.2
    """

    def test_bug2_runner_returns_command_with_export_dir(
        self, tmp_path: Path
    ) -> None:
        """isBugCondition_2: runner should return OptimizeRunCommand with export_dir.

        On UNFIXED code this raises TypeError, causing the test to FAIL.
        That failure confirms the bug exists.

        Counterexample (unfixed):
            TypeError: OptimizeRunCommand.__init__() missing 1 required
            positional argument: 'export_dir'
        """
        from app.core.freqtrade.runners import optimize_runner

        settings = _make_settings(tmp_path)

        # On UNFIXED code: TypeError raised → test FAILS (confirms bug)
        # On FIXED code:   returns OptimizeRunCommand with export_dir → PASSES
        result = optimize_runner.create_optimize_command(
            settings,
            "MyStrategy",
            "5m",
            epochs=10,
        )
        assert isinstance(result, OptimizeRunCommand)
        assert result.export_dir is not None
        assert result.export_dir.endswith("hyperopt_results")


# ---------------------------------------------------------------------------
# Bug 3 — "None" string in DownloadDataRunCommand.strategy_file
# ---------------------------------------------------------------------------

class TestBug3NoneStringStrategyFile:
    """Bug 3: create_download_data_command produces "None" string when no strategy.

    **Property 3: Bug Condition** — isBugCondition_3(paths) is True when
    paths.strategy_file is None (the normal case for download-data).

    Expected on UNFIXED code: FAIL (result.strategy_file == "None" — assertion fails)
    Expected on FIXED code:   PASS (result.strategy_file is None or "")

    Validates: Requirements 1.3
    """

    def test_bug3_strategy_file_is_not_none_string_when_no_strategy(
        self, tmp_path: Path
    ) -> None:
        """isBugCondition_3: strategy_file must not be the literal string "None".

        The test patches find_run_paths to return a ResolvedRunPaths where
        strategy_file is None — exactly what the real resolver returns for
        download-data (no strategy_name passed).

        On UNFIXED code: str(None) == "None" → assertion fails → test FAILS.
        That failure confirms the bug exists.

        Counterexample (unfixed):
            result.strategy_file == "None"   (str(None) == "None")
        """
        from app.core.freqtrade.runners.download_data_runner import (
            create_download_data_command,
        )

        settings = _make_settings(tmp_path)
        user_data = Path(settings.user_data_path)

        # Build a ResolvedRunPaths with strategy_file=None (the bug condition)
        fake_paths = ResolvedRunPaths(
            project_dir=user_data,
            user_data_dir=user_data,
            config_file=user_data / "config.json",
            strategies_dir=user_data / "strategies",
            strategy_file=None,  # ← isBugCondition_3 trigger
        )

        with patch(
            "app.core.freqtrade.runners.download_data_runner.find_run_paths",
            return_value=fake_paths,
        ):
            result = create_download_data_command(settings, "5m")

        # On UNFIXED code: result.strategy_file == "None" → assertion FAILS → bug confirmed
        # On FIXED code:   result.strategy_file is None or "" → assertion PASSES
        assert result.strategy_file != "None", (
            f"Bug 3 confirmed: strategy_file is the literal string 'None' "
            f"(got {result.strategy_file!r}). "
            "Expected None or '' when paths.strategy_file is None."
        )


# ---------------------------------------------------------------------------
# Documented counterexamples (from running on unfixed code)
# ---------------------------------------------------------------------------
#
# Bug 1 — test_bug1_epochs_kwarg_does_not_raise
#   FAILED: TypeError: create_optimize_command() got an unexpected keyword
#           argument 'epochs'
#   Root cause: commands.create_optimize_command wrapper signature does not
#   declare `epochs`, `spaces`, or `hyperopt_loss` parameters.
#
# Bug 1 — test_bug1_spaces_kwarg_does_not_raise
#   FAILED: TypeError: create_optimize_command() got an unexpected keyword
#           argument 'spaces'
#
# Bug 1 — test_bug1_hyperopt_loss_kwarg_does_not_raise
#   FAILED: TypeError: create_optimize_command() got an unexpected keyword
#           argument 'hyperopt_loss'
#
# Bug 2 — test_bug2_runner_returns_command_with_export_dir
#   FAILED: TypeError: OptimizeRunCommand.__init__() missing 1 required
#           positional argument: 'export_dir'
#   Root cause: optimize_runner.create_optimize_command constructs
#   OptimizeRunCommand(...) without passing export_dir.
#
# Bug 3 — test_bug3_strategy_file_is_not_none_string_when_no_strategy
#   FAILED: AssertionError: Bug 3 confirmed: strategy_file is the literal
#           string 'None' (got 'None'). Expected None or '' when
#           paths.strategy_file is None.
#   Root cause: download_data_runner does str(paths.strategy_file)
#   unconditionally; str(None) == "None".
