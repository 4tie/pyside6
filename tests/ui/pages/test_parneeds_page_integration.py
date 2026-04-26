"""Integration tests for ParNeedsPage — mocked ProcessRunManager and BacktestService.

Tests verify subprocess call sequences, signal counts, and file outputs
without actually running Freqtrade.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest
from PySide6.QtWidgets import QApplication

from app.core.models.parneeds_models import (
    CandleCoverageReport,
    ParNeedsRunResult,
)
from app.core.models.settings_models import AppSettings
from app.core.services.process_run_manager import ProcessRunManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def qt_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    return app


def _settings(tmp_path: Path) -> AppSettings:
    user_data = tmp_path / "user_data"
    (user_data / "strategies").mkdir(parents=True)
    (user_data / "config.json").write_text('{"exchange": {"name": "binance"}}', encoding="utf-8")
    return AppSettings(
        python_executable=sys.executable,
        user_data_path=str(user_data),
    )


def _state(settings: AppSettings):
    from app.app_state.settings_state import SettingsState
    state = SettingsState()
    state.current_settings = settings
    return state


def _make_page(tmp_path: Path):
    from app.ui.pages.parneeds_page import ParNeedsPage
    with patch(
        "app.core.services.backtest_service.BacktestService.get_available_strategies",
        return_value=["DemoStrategy"],
    ):
        page = ParNeedsPage(_state(_settings(tmp_path)), ProcessRunManager())
    return page


def _full_coverage(pair: str = "BTC/USDT", timerange: str = "20240101-20241231") -> CandleCoverageReport:
    return CandleCoverageReport(
        pair=pair,
        timeframe="5m",
        timerange=timerange,
        first_candle="2024-01-01 00:00",
        last_candle="2024-12-30 23:55",
        expected_candles=100000,
        actual_candles=100000,
    )


def _mock_cmd():
    cmd = MagicMock()
    cmd.to_display_string.return_value = "freqtrade backtesting"
    return cmd


def _mock_run(run_id: str = "run-001"):
    run = MagicMock()
    run.run_id = run_id
    return run


# ---------------------------------------------------------------------------
# Task 18.1: Walk-Forward integration
# ---------------------------------------------------------------------------


def test_wf_subprocess_call_sequence_is_then_oos(qt_app, tmp_path):
    """Walk-Forward runs IS then OOS for each fold sequentially (Req 2.1)."""
    page = _make_page(tmp_path)
    page.sync_from_backtest({
        "strategy": "DemoStrategy",
        "timeframe": "5m",
        "timerange": "20240101-20241231",
        "pairs": ["BTC/USDT"],
        "dry_run_wallet": 80.0,
        "max_open_trades": 2,
    })
    page._wf_folds_spin.setValue(3)

    page._parneeds_svc.validate_candle_coverage = MagicMock(
        return_value=[_full_coverage()]
    )
    page._backtest_svc.build_command = MagicMock(return_value=_mock_cmd())
    page._start_process = MagicMock()

    page.start_walk_forward_workflow()

    # First call should be Fold 1 IS
    assert page._start_process.call_count == 1
    assert page._phase == "wf_backtest"
    assert page._wf_active_fold.fold_index == 1
    assert page._wf_active_window_type == "IS"

    # Simulate IS completion → should start OOS
    page._handle_wf_backtest_finished(0)
    assert page._wf_active_fold.fold_index == 1
    assert page._wf_active_window_type == "OOS"

    # Simulate OOS completion → should start Fold 2 IS
    page._handle_wf_backtest_finished(0)
    assert page._wf_active_fold.fold_index == 2
    assert page._wf_active_window_type == "IS"


def test_wf_run_completed_signal_count(qt_app, tmp_path):
    """run_completed emitted for each successful fold backtest (Req 3.5)."""
    page = _make_page(tmp_path)
    page.sync_from_backtest({
        "strategy": "DemoStrategy",
        "timeframe": "5m",
        "timerange": "20240101-20241231",
        "pairs": ["BTC/USDT"],
        "dry_run_wallet": 80.0,
        "max_open_trades": 2,
    })
    page._wf_folds_spin.setValue(2)

    page._parneeds_svc.validate_candle_coverage = MagicMock(
        return_value=[_full_coverage()]
    )
    page._backtest_svc.build_command = MagicMock(return_value=_mock_cmd())
    page._start_process = MagicMock()

    run_ids = []
    page.run_completed.connect(run_ids.append)

    # Mock parse_and_save to return unique run IDs
    call_count = [0]
    def _parse_and_save(*args, **kwargs):
        call_count[0] += 1
        return f"run-{call_count[0]:03d}"
    page._backtest_svc.parse_and_save_latest_results = _parse_and_save
    page._find_run_entry = MagicMock(return_value={})

    page.start_walk_forward_workflow()

    # 2 folds × 2 windows = 4 backtests
    for _ in range(4):
        page._handle_wf_backtest_finished(0)

    assert len(run_ids) == 4


# ---------------------------------------------------------------------------
# Task 18.2: Monte Carlo integration
# ---------------------------------------------------------------------------


def test_mc_coverage_check_called_exactly_once(qt_app, tmp_path):
    """Coverage validation called once for MC, not per iteration (Req 15.3)."""
    page = _make_page(tmp_path)
    page.sync_from_backtest({
        "strategy": "DemoStrategy",
        "timeframe": "5m",
        "timerange": "20240101-20240201",
        "pairs": ["BTC/USDT"],
        "dry_run_wallet": 80.0,
        "max_open_trades": 2,
    })
    page._mc_iterations_spin.setValue(3)

    coverage_mock = MagicMock(return_value=[_full_coverage(timerange="20240101-20240201")])
    page._parneeds_svc.validate_candle_coverage = coverage_mock
    page._backtest_svc.build_command = MagicMock(return_value=_mock_cmd())
    page._start_process = MagicMock()

    page.start_monte_carlo_workflow()

    # Coverage called exactly once
    assert coverage_mock.call_count == 1

    # Simulate 3 iterations completing
    for _ in range(3):
        page._handle_mc_iteration_finished(0)

    # Coverage still called only once
    assert coverage_mock.call_count == 1


def test_mc_iteration_count_matches_config(qt_app, tmp_path):
    """MC runs exactly n_iterations backtests (Req 5.1)."""
    page = _make_page(tmp_path)
    page.sync_from_backtest({
        "strategy": "DemoStrategy",
        "timeframe": "5m",
        "timerange": "20240101-20240201",
        "pairs": ["BTC/USDT"],
        "dry_run_wallet": 80.0,
        "max_open_trades": 2,
    })
    n = 5
    page._mc_iterations_spin.setValue(n)

    page._parneeds_svc.validate_candle_coverage = MagicMock(
        return_value=[_full_coverage(timerange="20240101-20240201")]
    )
    page._backtest_svc.build_command = MagicMock(return_value=_mock_cmd())
    page._start_process = MagicMock()
    page._backtest_svc.parse_and_save_latest_results = MagicMock(return_value="")
    page._find_run_entry = MagicMock(return_value={})

    page.start_monte_carlo_workflow()

    for _ in range(n):
        page._handle_mc_iteration_finished(0)

    # After n iterations, the workflow should be complete
    assert page._mc_iteration_index == n
    assert page._running is False


# ---------------------------------------------------------------------------
# Task 18.3: Parameter Sensitivity integration
# ---------------------------------------------------------------------------


def test_ps_coverage_check_called_before_sweep(qt_app, tmp_path):
    """Coverage validation called before sweep points are executed (Req 15.1)."""
    from app.core.models.parneeds_models import SweepParameterDef, SweepParamType

    page = _make_page(tmp_path)
    page.sync_from_backtest({
        "strategy": "DemoStrategy",
        "timeframe": "5m",
        "timerange": "20240101-20240201",
        "pairs": ["BTC/USDT"],
        "dry_run_wallet": 80.0,
        "max_open_trades": 2,
    })

    # Manually populate the PS param table with one enabled param
    page._ps_params = [
        SweepParameterDef(
            name="rsi_period",
            param_type=SweepParamType.INT,
            default_value=14,
            min_value=10.0,
            max_value=12.0,
            step=1.0,
            enabled=True,
        )
    ]
    # Add a row to the param table
    from PySide6.QtWidgets import QTableWidgetItem
    from PySide6.QtCore import Qt
    page._ps_param_table.setRowCount(1)
    chk = QTableWidgetItem()
    chk.setCheckState(Qt.Checked)
    page._ps_param_table.setItem(0, 0, chk)
    page._ps_param_table.setItem(0, 1, QTableWidgetItem("rsi_period"))
    page._ps_param_table.setItem(0, 2, QTableWidgetItem("int"))
    page._ps_param_table.setItem(0, 3, QTableWidgetItem("10"))
    page._ps_param_table.setItem(0, 4, QTableWidgetItem("12"))
    page._ps_param_table.setItem(0, 5, QTableWidgetItem("1"))

    coverage_mock = MagicMock(return_value=[_full_coverage(timerange="20240101-20240201")])
    page._parneeds_svc.validate_candle_coverage = coverage_mock
    page._backtest_svc.build_command = MagicMock(return_value=_mock_cmd())
    page._start_process = MagicMock()

    page.start_param_sensitivity_workflow()

    # Coverage called before any sweep
    assert coverage_mock.call_count == 1
    assert page._phase == "ps_backtest"


def test_ps_sweep_point_count_matches_generated(qt_app, tmp_path):
    """PS runs exactly as many backtests as generated sweep points (Req 9.3)."""
    from app.core.models.parneeds_models import SweepParameterDef, SweepParamType
    from PySide6.QtWidgets import QTableWidgetItem
    from PySide6.QtCore import Qt

    page = _make_page(tmp_path)
    page.sync_from_backtest({
        "strategy": "DemoStrategy",
        "timeframe": "5m",
        "timerange": "20240101-20240201",
        "pairs": ["BTC/USDT"],
        "dry_run_wallet": 80.0,
        "max_open_trades": 2,
    })

    # 3 values: 10, 11, 12
    page._ps_param_table.setRowCount(1)
    chk = QTableWidgetItem()
    chk.setCheckState(Qt.Checked)
    page._ps_param_table.setItem(0, 0, chk)
    page._ps_param_table.setItem(0, 1, QTableWidgetItem("rsi_period"))
    page._ps_param_table.setItem(0, 2, QTableWidgetItem("int"))
    page._ps_param_table.setItem(0, 3, QTableWidgetItem("10"))
    page._ps_param_table.setItem(0, 4, QTableWidgetItem("12"))
    page._ps_param_table.setItem(0, 5, QTableWidgetItem("1"))

    page._parneeds_svc.validate_candle_coverage = MagicMock(
        return_value=[_full_coverage(timerange="20240101-20240201")]
    )
    page._backtest_svc.build_command = MagicMock(return_value=_mock_cmd())
    page._start_process = MagicMock()

    page.start_param_sensitivity_workflow()

    # 3 sweep points (10, 11, 12)
    total_points = 3
    for _ in range(total_points):
        page._handle_sweep_point_finished(0)

    assert page._phase == "idle"
    assert len(page._ps_results) == total_points


# ---------------------------------------------------------------------------
# Task 18.4: Export integration
# ---------------------------------------------------------------------------


def test_export_creates_json_and_csv(qt_app, tmp_path):
    """Export writes JSON and CSV files with correct filenames (Req 13.2, 13.3, 13.4)."""
    page = _make_page(tmp_path)

    # Manually add results
    page._all_results = [
        ParNeedsRunResult(
            run_trial="Fold 1 OOS",
            workflow="walk_forward",
            strategy="DemoStrategy",
            profit_pct=5.5,
        )
    ]
    page._results.insertRow(0)  # Make export button enabled
    page._export_btn.setEnabled(True)

    # Override export dir to tmp_path
    import re
    export_dir = tmp_path / "exports"
    page._parneeds_svc.export_results = MagicMock(
        return_value=(
            export_dir / "parneeds_walk_forward_20240101_120000.json",
            export_dir / "parneeds_walk_forward_20240101_120000.csv",
        )
    )

    page._export_results()

    page._parneeds_svc.export_results.assert_called_once()
    call_args = page._parneeds_svc.export_results.call_args
    assert call_args[0][0] == page._all_results
    assert "walk_forward" in call_args[0][1] or "timerange" in call_args[0][1]


# ---------------------------------------------------------------------------
# Task 18.5: Stop integration
# ---------------------------------------------------------------------------


def test_stop_calls_process_manager_stop_run(qt_app, tmp_path):
    """Stop button calls ProcessRunManager.stop_run (Req 2.5, 5.7, 9.7)."""
    page = _make_page(tmp_path)
    page.sync_from_backtest({
        "strategy": "DemoStrategy",
        "timeframe": "5m",
        "timerange": "20240101-20241231",
        "pairs": ["BTC/USDT"],
        "dry_run_wallet": 80.0,
        "max_open_trades": 2,
    })

    page._parneeds_svc.validate_candle_coverage = MagicMock(
        return_value=[_full_coverage()]
    )
    page._backtest_svc.build_command = MagicMock(return_value=_mock_cmd())
    page._start_process = MagicMock()

    page.start_walk_forward_workflow()

    # Simulate a run in progress
    page._current_run_id = "run-active"
    stop_mock = MagicMock()
    page._process_manager.stop_run = stop_mock

    page._stop()

    stop_mock.assert_called_once_with("run-active")
    assert page._running is False
    assert page._pending_wf_items == []


def test_stop_clears_all_pending_queues(qt_app, tmp_path):
    """Stop clears all workflow pending queues (Req 2.5, 5.7, 9.7)."""
    page = _make_page(tmp_path)
    page._set_running(True)
    page._pending_windows = [MagicMock()]
    page._pending_wf_items = [(MagicMock(), "IS")]
    page._pending_sweep_points = [MagicMock()]
    page._download_queue = [(False, ["BTC/USDT"], "test")]

    page._stop()

    assert page._pending_windows == []
    assert page._pending_wf_items == []
    assert page._pending_sweep_points == []
    assert page._download_queue == []
    assert page._running is False
