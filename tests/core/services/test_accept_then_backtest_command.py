"""
Integration test: accept_candidate() → build_backtest_command() param propagation.

Validates that after ImproveService.accept_candidate() writes improved parameters
to the live strategy JSON, a subsequent call to build_backtest_command() (as
triggered by the Backtest page) does NOT include --max-open-trades or
--dry-run-wallet flags that would override those parameters.

This is the regression test for the bug where the Backtest page was passing
--max-open-trades as a CLI flag, silently overriding the accepted improvements.

Correctness properties tested:
  P1 — accept_candidate() writes the improved stoploss and max_open_trades to
       {strategies_dir}/{strategy_name}.json in freqtrade nested format.
  P2 — build_backtest_command() (called without max_open_trades/dry_run_wallet)
       does NOT include --max-open-trades or --dry-run-wallet in its arg list.
  P3 — The written JSON is readable back via _load_params_from_live_strategy()
       and the values match what was accepted.
  P4 — Rollback restores the previous params to the JSON file correctly.
"""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.services.improve_service import ImproveService
from app.core.services.backtest_service import BacktestService
from app.core.services.settings_service import SettingsService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings_service(tmp_path: Path) -> MagicMock:
    """Return a mock SettingsService whose load_settings() points at tmp_path."""
    mock_settings = MagicMock()
    mock_settings.user_data_path = str(tmp_path)
    mock_settings.venv_path = None
    mock_settings.python_executable = "python"
    mock_settings.freqtrade_executable = "freqtrade"
    mock_settings.use_module_execution = False
    mock_settings.project_path = None
    svc = MagicMock(spec=SettingsService)
    svc.load_settings.return_value = mock_settings
    return svc


def _make_improve_service(tmp_path: Path) -> ImproveService:
    settings_svc = _make_settings_service(tmp_path)
    backtest_svc = MagicMock(spec=BacktestService)
    return ImproveService(settings_svc, backtest_svc)


def _setup_user_data(tmp_path: Path, strategy_name: str) -> Path:
    """Create the minimal user_data directory structure needed for the tests."""
    strategies_dir = tmp_path / "strategies"
    strategies_dir.mkdir(parents=True)
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    backtest_results_dir = tmp_path / "backtest_results"
    backtest_results_dir.mkdir(parents=True)

    # Minimal strategy .py file
    (strategies_dir / f"{strategy_name}.py").write_text(
        f"class {strategy_name}:\n    stoploss = -0.10\n    max_open_trades = 2\n",
        encoding="utf-8",
    )
    # Minimal config.json
    (tmp_path / "config.json").write_text(
        json.dumps({"exchange": {"name": "binance"}, "stake_currency": "USDT"}),
        encoding="utf-8",
    )
    return strategies_dir


# ---------------------------------------------------------------------------
# P1 — accept_candidate() writes improved params to the live JSON
# ---------------------------------------------------------------------------

def test_p1_accept_candidate_writes_improved_params(tmp_path):
    """
    P1: After accept_candidate(), the live strategy JSON contains the improved
    stoploss and max_open_trades in freqtrade nested format.
    """
    strategy = "MyStrategy"
    strategies_dir = _setup_user_data(tmp_path, strategy)
    service = _make_improve_service(tmp_path)

    improved_params = {"stoploss": -0.05, "max_open_trades": 5}
    service.accept_candidate(strategy, improved_params)

    live_json = strategies_dir / f"{strategy}.json"
    assert live_json.exists(), "accept_candidate() must write the live strategy JSON"

    written = json.loads(live_json.read_text(encoding="utf-8"))
    assert written["ft_stratparam_v"] == 1
    assert written["strategy_name"] == strategy

    params = written["params"]
    assert params["stoploss"]["stoploss"] == -0.05, (
        f"Expected stoploss -0.05 in params, got {params.get('stoploss')}"
    )
    assert params["max_open_trades"]["max_open_trades"] == 5, (
        f"Expected max_open_trades 5 in params, got {params.get('max_open_trades')}"
    )


# ---------------------------------------------------------------------------
# P2 — build_backtest_command() does NOT pass --max-open-trades or
#       --dry-run-wallet when called without those arguments
# ---------------------------------------------------------------------------

def test_p2_backtest_command_has_no_override_flags(tmp_path):
    """
    P2: build_backtest_command() called without max_open_trades/dry_run_wallet
    must NOT include --max-open-trades or --dry-run-wallet in the command args.

    This is the core regression test: the Backtest page previously passed these
    flags, overriding the accepted strategy params.
    """
    from app.core.freqtrade.runners.backtest_runner import build_backtest_command
    from app.core.models.settings_models import AppSettings

    strategy = "MyStrategy"
    _setup_user_data(tmp_path, strategy)

    # Build a minimal AppSettings pointing at tmp_path
    settings = MagicMock(spec=AppSettings)
    settings.user_data_path = str(tmp_path)
    settings.venv_path = None
    settings.python_executable = "python"
    settings.freqtrade_executable = "freqtrade"
    settings.use_module_execution = False
    settings.project_path = None

    # Patch resolve_config_file and resolve_strategy_file to avoid real FS lookups
    with (
        patch(
            "app.core.freqtrade.runners.backtest_runner.resolve_run_paths"
        ) as mock_resolve,
        patch(
            "app.core.freqtrade.runners.backtest_runner.build_command"
        ) as mock_build,
    ):
        from app.core.freqtrade.resolvers.runtime_resolver import ResolvedRunPaths
        mock_resolve.return_value = ResolvedRunPaths(
            project_dir=tmp_path,
            user_data_dir=tmp_path,
            config_file=tmp_path / "config.json",
            strategies_dir=tmp_path / "strategies",
            strategy_file=tmp_path / "strategies" / f"{strategy}.py",
        )

        from app.core.freqtrade.runners.base_runner import RunCommand
        captured_args = []

        def capture_build(settings_arg, *args):
            captured_args.extend(args)
            cmd = MagicMock(spec=RunCommand)
            cmd.program = "python"
            cmd.args = list(args)
            cmd.cwd = str(tmp_path)
            return cmd

        mock_build.side_effect = capture_build

        # Call WITHOUT max_open_trades and dry_run_wallet — as the fixed page does
        build_backtest_command(
            settings=settings,
            strategy_name=strategy,
            timeframe="5m",
            pairs=["BTC/USDT"],
        )

    assert "--max-open-trades" not in captured_args, (
        "build_backtest_command() must NOT include --max-open-trades when "
        "max_open_trades is not passed. This flag overrides the strategy params file."
    )
    assert "--dry-run-wallet" not in captured_args, (
        "build_backtest_command() must NOT include --dry-run-wallet when "
        "dry_run_wallet is not passed."
    )


# ---------------------------------------------------------------------------
# P3 — Accepted params are readable back via _load_params_from_live_strategy()
# ---------------------------------------------------------------------------

def test_p3_accepted_params_readable_via_live_strategy_loader(tmp_path):
    """
    P3: After accept_candidate(), _load_params_from_live_strategy() must return
    a flat dict with the same stoploss and max_open_trades that were accepted.

    This validates the full round-trip: accept writes → loader reads back.
    """
    strategy = "MyStrategy"
    _setup_user_data(tmp_path, strategy)
    service = _make_improve_service(tmp_path)

    improved_params = {"stoploss": -0.07, "max_open_trades": 4}
    service.accept_candidate(strategy, improved_params)

    loaded = service._load_params_from_live_strategy(strategy)

    assert loaded.get("stoploss") == -0.07, (
        f"Round-trip stoploss mismatch: expected -0.07, got {loaded.get('stoploss')}"
    )
    assert loaded.get("max_open_trades") == 4, (
        f"Round-trip max_open_trades mismatch: expected 4, got {loaded.get('max_open_trades')}"
    )


# ---------------------------------------------------------------------------
# P4 — Rollback restores the previous params
# ---------------------------------------------------------------------------

def test_p4_rollback_restores_previous_params(tmp_path):
    """
    P4: After accept_candidate() followed by rollback(), the live strategy JSON
    must contain the original (pre-accept) params, not the accepted ones.
    """
    strategy = "MyStrategy"
    strategies_dir = _setup_user_data(tmp_path, strategy)
    service = _make_improve_service(tmp_path)

    original_params = {"stoploss": -0.10, "max_open_trades": 2}
    improved_params = {"stoploss": -0.05, "max_open_trades": 5}

    # Accept the improvement
    service.accept_candidate(strategy, improved_params)

    # Verify improvement was written
    after_accept = service._load_params_from_live_strategy(strategy)
    assert after_accept.get("stoploss") == -0.05

    # Rollback to original
    service.rollback(strategy, original_params)

    after_rollback = service._load_params_from_live_strategy(strategy)
    assert after_rollback.get("stoploss") == -0.10, (
        f"Rollback must restore stoploss to -0.10, got {after_rollback.get('stoploss')}"
    )
    assert after_rollback.get("max_open_trades") == 2, (
        f"Rollback must restore max_open_trades to 2, got {after_rollback.get('max_open_trades')}"
    )


# ---------------------------------------------------------------------------
# P5 — The old (buggy) backtest page behaviour would have overridden params
#       This test documents the bug and confirms it no longer exists in the
#       command built by the fixed page.
# ---------------------------------------------------------------------------

def test_p5_old_page_would_have_overridden_params_new_page_does_not(tmp_path):
    """
    P5: Regression test documenting the original bug.

    The old BacktestPage passed max_open_trades=2 (from the UI spinner) to
    build_backtest_command(), which emitted --max-open-trades 2 and overrode
    the accepted value of 5 in the strategy JSON.

    The fixed page passes no max_open_trades, so the flag is absent.
    """
    from app.core.freqtrade.runners.backtest_runner import build_backtest_command
    from app.core.models.settings_models import AppSettings

    strategy = "MyStrategy"
    _setup_user_data(tmp_path, strategy)

    settings = MagicMock(spec=AppSettings)
    settings.user_data_path = str(tmp_path)
    settings.venv_path = None
    settings.python_executable = "python"
    settings.freqtrade_executable = "freqtrade"
    settings.use_module_execution = False
    settings.project_path = None

    from app.core.freqtrade.resolvers.runtime_resolver import ResolvedRunPaths
    from app.core.freqtrade.runners.base_runner import RunCommand

    resolved = ResolvedRunPaths(
        project_dir=tmp_path,
        user_data_dir=tmp_path,
        config_file=tmp_path / "config.json",
        strategies_dir=tmp_path / "strategies",
        strategy_file=tmp_path / "strategies" / f"{strategy}.py",
    )

    def _fake_cmd(*args):
        cmd = MagicMock(spec=RunCommand)
        cmd.program = "python"
        cmd.args = list(args)
        cmd.cwd = str(tmp_path)
        return cmd

    # --- OLD page: passes max_open_trades=2 (spinner value) ---
    old_page_args = []
    with (
        patch("app.core.freqtrade.runners.backtest_runner.resolve_run_paths", return_value=resolved),
        patch("app.core.freqtrade.runners.backtest_runner.build_command",
              side_effect=lambda s, *a: (old_page_args.extend(a), _fake_cmd(*a))[1]),
    ):
        build_backtest_command(
            settings=settings,
            strategy_name=strategy,
            timeframe="5m",
            pairs=["BTC/USDT"],
            max_open_trades=2,   # ← old bug: spinner value overrides strategy JSON
        )

    # --- NEW (fixed) page: passes nothing ---
    new_page_args = []
    with (
        patch("app.core.freqtrade.runners.backtest_runner.resolve_run_paths", return_value=resolved),
        patch("app.core.freqtrade.runners.backtest_runner.build_command",
              side_effect=lambda s, *a: (new_page_args.extend(a), _fake_cmd(*a))[1]),
    ):
        build_backtest_command(
            settings=settings,
            strategy_name=strategy,
            timeframe="5m",
            pairs=["BTC/USDT"],
            # no max_open_trades ← fixed
        )

    # Old page DID include the override flag (documents the bug)
    assert "--max-open-trades" in old_page_args, (
        "Old page behaviour should have included --max-open-trades (documenting the bug)"
    )

    # New page does NOT include the override flag (confirms the fix)
    assert "--max-open-trades" not in new_page_args, (
        "Fixed page must NOT include --max-open-trades so the strategy JSON is respected"
    )
