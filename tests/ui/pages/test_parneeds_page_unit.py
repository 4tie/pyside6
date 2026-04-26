"""Example-based unit tests for ParNeedsPage.

Tests verify UI structure, default values, config panel visibility,
results table layout, and export button state — without running any
subprocess or backtest.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTableWidgetItem

from app.core.models.parneeds_models import CandleCoverageReport
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
    (user_data / "config.json").write_text(
        '{"exchange": {"name": "binance"}}', encoding="utf-8"
    )
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


# ---------------------------------------------------------------------------
# Task 19.1: Workflow selector shows/hides correct config panels
# ---------------------------------------------------------------------------


def test_workflow_selector_default_is_timerange(qt_app, tmp_path):
    """Default workflow is Timerange (index 0) with no extra config panel."""
    page = _make_page(tmp_path)
    assert page._workflow_combo.currentIndex() == 0
    assert page._workflow_combo.currentText() == "Timerange workflow"
    # Stack index 0 = empty panel for Timerange
    assert page._workflow_stack.currentIndex() == 0


def test_workflow_selector_walk_forward_shows_wf_panel(qt_app, tmp_path):
    """Selecting Walk-Forward shows the WF config panel (index 1)."""
    page = _make_page(tmp_path)
    page._workflow_combo.setCurrentIndex(1)
    assert page._workflow_stack.currentIndex() == 1
    # WF-specific widgets must be present
    assert hasattr(page, "_wf_folds_spin")
    assert hasattr(page, "_wf_split_spin")
    assert hasattr(page, "_wf_mode_combo")


def test_workflow_selector_monte_carlo_shows_mc_panel(qt_app, tmp_path):
    """Selecting Monte Carlo shows the MC config panel (index 2)."""
    page = _make_page(tmp_path)
    page._workflow_combo.setCurrentIndex(2)
    assert page._workflow_stack.currentIndex() == 2
    assert hasattr(page, "_mc_iterations_spin")
    assert hasattr(page, "_mc_randomise_chk")
    assert hasattr(page, "_mc_noise_chk")
    assert hasattr(page, "_mc_max_dd_spin")


def test_workflow_selector_param_sensitivity_shows_ps_panel(qt_app, tmp_path):
    """Selecting Parameter Sensitivity shows the PS config panel (index 3)."""
    page = _make_page(tmp_path)
    page._workflow_combo.setCurrentIndex(3)
    assert page._workflow_stack.currentIndex() == 3
    assert hasattr(page, "_ps_mode_combo")
    assert hasattr(page, "_ps_param_table")
    assert hasattr(page, "_ps_discover_btn")


def test_workflow_selector_ignored_while_running(qt_app, tmp_path):
    """Workflow combo changes are ignored while a run is in progress (Req 14.3)."""
    page = _make_page(tmp_path)
    page._workflow_combo.setCurrentIndex(1)  # Walk-Forward
    page._set_running(True)

    # Try to switch to Monte Carlo while running
    page._workflow_combo.setCurrentIndex(2)

    # Should revert to Walk-Forward (index 1)
    assert page._workflow_combo.currentIndex() == 1
    assert page._workflow_stack.currentIndex() == 1

    page._set_running(False)


# ---------------------------------------------------------------------------
# Task 19.2: Config panel default values
# ---------------------------------------------------------------------------


def test_wf_panel_default_values(qt_app, tmp_path):
    """Walk-Forward config panel has correct default values (Req 4.1)."""
    page = _make_page(tmp_path)
    assert page._wf_folds_spin.value() == 5
    assert page._wf_folds_spin.minimum() == 2
    assert page._wf_folds_spin.maximum() == 20
    assert page._wf_split_spin.value() == 80
    assert page._wf_split_spin.minimum() == 50
    assert page._wf_split_spin.maximum() == 95
    assert page._wf_mode_combo.currentText() == "anchored"


def test_mc_panel_default_values(qt_app, tmp_path):
    """Monte Carlo config panel has correct default values (Req 7.1)."""
    page = _make_page(tmp_path)
    assert page._mc_iterations_spin.value() == 500
    assert page._mc_iterations_spin.minimum() == 10
    assert page._mc_iterations_spin.maximum() == 5000
    assert page._mc_randomise_chk.isChecked() is True
    assert page._mc_noise_chk.isChecked() is True
    assert page._mc_max_dd_spin.value() == 20.0


def test_ps_panel_default_values(qt_app, tmp_path):
    """Parameter Sensitivity config panel has correct default values (Req 11.1)."""
    page = _make_page(tmp_path)
    assert page._ps_mode_combo.currentText() == "One-at-a-time"
    assert page._ps_mode_combo.count() == 2
    assert page._ps_mode_combo.itemText(0) == "One-at-a-time"
    assert page._ps_mode_combo.itemText(1) == "Grid"


# ---------------------------------------------------------------------------
# Task 19.3: Grid > 200 points confirmation; no params disables Start
# ---------------------------------------------------------------------------


def test_no_parameters_found_disables_start_button(qt_app, tmp_path):
    """When no sweepable parameters are found, Start button is disabled (Req 8.4)."""
    page = _make_page(tmp_path)
    page._workflow_combo.setCurrentIndex(3)  # Parameter Sensitivity

    # Mock discover to return empty list
    page._parneeds_svc.discover_strategy_parameters = MagicMock(return_value=[])

    # Set up settings so _require_settings() works
    page._strategy_combo.setCurrentText("DemoStrategy")

    page._discover_ps_parameters()

    assert page._start_btn.isEnabled() is False


def test_parameters_found_enables_start_button(qt_app, tmp_path):
    """When parameters are found, Start button is re-enabled (Req 8.4)."""
    from app.core.models.parneeds_models import SweepParameterDef, SweepParamType

    page = _make_page(tmp_path)
    page._workflow_combo.setCurrentIndex(3)

    page._parneeds_svc.discover_strategy_parameters = MagicMock(
        return_value=[
            SweepParameterDef(
                name="rsi_period",
                param_type=SweepParamType.INT,
                default_value=14,
                min_value=10.0,
                max_value=20.0,
                step=1.0,
                enabled=False,
            )
        ]
    )
    page._strategy_combo.setCurrentText("DemoStrategy")

    page._discover_ps_parameters()

    assert page._start_btn.isEnabled() is True
    assert page._ps_param_table.rowCount() == 1


def test_grid_large_sweep_shows_confirmation_dialog(qt_app, tmp_path):
    """Grid mode with > 200 points shows a confirmation dialog (Req 11.4)."""
    from app.core.models.parneeds_models import SweepParameterDef, SweepParamType

    page = _make_page(tmp_path)
    page._workflow_combo.setCurrentIndex(3)
    page._ps_mode_combo.setCurrentText("Grid")

    page.sync_from_backtest({
        "strategy": "DemoStrategy",
        "timeframe": "5m",
        "timerange": "20240101-20240201",
        "pairs": ["BTC/USDT"],
        "dry_run_wallet": 80.0,
        "max_open_trades": 2,
    })

    # Add a row with a large range to the param table (10 × 10 × 3 = 300 points)
    page._ps_param_table.setRowCount(3)
    for row, (lo, hi, step) in enumerate([(1, 10, 1), (1, 10, 1), (1, 3, 1)]):
        chk = QTableWidgetItem()
        chk.setCheckState(Qt.Checked)
        page._ps_param_table.setItem(row, 0, chk)
        page._ps_param_table.setItem(row, 1, QTableWidgetItem(f"param_{row}"))
        page._ps_param_table.setItem(row, 2, QTableWidgetItem("int"))
        page._ps_param_table.setItem(row, 3, QTableWidgetItem(str(lo)))
        page._ps_param_table.setItem(row, 4, QTableWidgetItem(str(hi)))
        page._ps_param_table.setItem(row, 5, QTableWidgetItem(str(step)))

    page._parneeds_svc.validate_candle_coverage = MagicMock(
        return_value=[
            CandleCoverageReport(
                pair="BTC/USDT",
                timeframe="5m",
                timerange="20240101-20240201",
                first_candle="2024-01-01 00:00",
                last_candle="2024-01-31 23:55",
                expected_candles=100000,
                actual_candles=100000,
            )
        ]
    )
    page._start_process = MagicMock()

    # Patch QMessageBox.question to return No (cancel)
    with patch(
        "app.ui.pages.parneeds_page.QMessageBox.question",
        return_value=QMessageBox_No(),
    ) as mock_dialog:
        page.start_param_sensitivity_workflow()

    mock_dialog.assert_called_once()
    # Run should not have started (user cancelled)
    assert page._running is False


def QMessageBox_No():
    """Return the QMessageBox.No value."""
    from PySide6.QtWidgets import QMessageBox
    return QMessageBox.No


# ---------------------------------------------------------------------------
# Task 19.4: Results table columns; Export button state
# ---------------------------------------------------------------------------


def test_results_table_has_17_columns(qt_app, tmp_path):
    """Results table has exactly 17 columns with correct headers (Req 12.1)."""
    page = _make_page(tmp_path)
    assert page._results.columnCount() == 17

    expected_headers = [
        "Run/Trial", "Workflow", "Strategy", "Pair(s)", "Timeframe", "Timerange",
        "Profit %", "Total Profit", "Win Rate", "Max DD %", "Trades",
        "Profit Factor", "Sharpe Ratio", "Score", "Status", "Result Path", "Log Path",
    ]
    for col, expected in enumerate(expected_headers):
        header_item = page._results.horizontalHeaderItem(col)
        assert header_item is not None, f"Column {col} has no header item"
        assert header_item.text() == expected, (
            f"Column {col} header '{header_item.text()}' != '{expected}'"
        )


def test_export_button_disabled_when_table_empty(qt_app, tmp_path):
    """Export button is disabled when the results table is empty (Req 13.1)."""
    page = _make_page(tmp_path)
    assert page._results.rowCount() == 0
    assert page._export_btn.isEnabled() is False


def test_export_button_enabled_when_table_has_rows(qt_app, tmp_path):
    """Export button is enabled when the results table has at least one row (Req 13.1)."""
    from app.core.models.parneeds_models import ParNeedsRunResult

    page = _make_page(tmp_path)
    result = ParNeedsRunResult(
        run_trial="Fold 1 OOS",
        workflow="walk_forward",
        strategy="DemoStrategy",
        profit_pct=5.5,
        status="completed",
    )
    page._append_result_row(result)

    assert page._results.rowCount() == 1
    assert page._export_btn.isEnabled() is True


def test_none_fields_display_as_dash(qt_app, tmp_path):
    """None optional fields display as '-' in the results table (Req 12.2)."""
    from app.core.models.parneeds_models import ParNeedsRunResult

    page = _make_page(tmp_path)
    result = ParNeedsRunResult(
        run_trial="Iter 1",
        workflow="monte_carlo",
        strategy="DemoStrategy",
        # All optional numeric fields left as None
    )
    page._append_result_row(result)

    row = 0
    # profit_pct is column 6
    profit_item = page._results.item(row, 6)
    assert profit_item is not None
    assert profit_item.text() == "-"

    # trades is column 10
    trades_item = page._results.item(row, 10)
    assert trades_item is not None
    assert trades_item.text() == "-"

    # sharpe_ratio is column 12
    sharpe_item = page._results.item(row, 12)
    assert sharpe_item is not None
    assert sharpe_item.text() == "-"


def test_results_preserved_on_workflow_switch(qt_app, tmp_path):
    """Existing result rows are preserved when switching workflows (Req 12.3)."""
    from app.core.models.parneeds_models import ParNeedsRunResult

    page = _make_page(tmp_path)
    result = ParNeedsRunResult(
        run_trial="2w 1",
        workflow="timerange",
        strategy="DemoStrategy",
        profit_pct=3.2,
        status="completed",
    )
    page._append_result_row(result)
    assert page._results.rowCount() == 1

    # Switch workflow — rows must be preserved
    page._workflow_combo.setCurrentIndex(1)
    assert page._results.rowCount() == 1


# ---------------------------------------------------------------------------
# Task 19.5: Fold row colour-coding; best sweep point highlight
# ---------------------------------------------------------------------------


def test_wf_oos_positive_profit_row_coloured_green(qt_app, tmp_path):
    """OOS fold rows with positive profit are coloured green (Req 3.4)."""
    from PySide6.QtGui import QColor
    from app.core.models.parneeds_models import ParNeedsRunResult
    from app.ui import theme

    page = _make_page(tmp_path)
    result = ParNeedsRunResult(
        run_trial="Fold 1 OOS",
        workflow="walk_forward",
        strategy="DemoStrategy",
        profit_pct=4.5,
        status="completed",
    )
    page._append_result_row(result)

    # Trigger colour-coding
    page._colour_wf_rows()

    # Check that the row has green foreground
    item = page._results.item(0, 0)
    assert item is not None
    assert item.foreground().color() == QColor(theme.GREEN)


def test_wf_oos_negative_profit_row_coloured_red(qt_app, tmp_path):
    """OOS fold rows with negative profit are coloured red (Req 3.4)."""
    from PySide6.QtGui import QColor
    from app.core.models.parneeds_models import ParNeedsRunResult
    from app.ui import theme

    page = _make_page(tmp_path)
    result = ParNeedsRunResult(
        run_trial="Fold 2 OOS",
        workflow="walk_forward",
        strategy="DemoStrategy",
        profit_pct=-2.1,
        status="completed",
    )
    page._append_result_row(result)

    page._colour_wf_rows()

    item = page._results.item(0, 0)
    assert item is not None
    assert item.foreground().color() == QColor(theme.RED)


def test_wf_failed_fold_row_coloured_red(qt_app, tmp_path):
    """Failed OOS fold rows are coloured red (Req 3.4)."""
    from PySide6.QtGui import QColor
    from app.core.models.parneeds_models import ParNeedsRunResult
    from app.ui import theme

    page = _make_page(tmp_path)
    result = ParNeedsRunResult(
        run_trial="Fold 3 OOS",
        workflow="walk_forward",
        strategy="DemoStrategy",
        profit_pct=None,
        status="failed (1)",
    )
    page._append_result_row(result)

    page._colour_wf_rows()

    item = page._results.item(0, 0)
    assert item is not None
    assert item.foreground().color() == QColor(theme.RED)


def test_wf_is_rows_not_colour_coded(qt_app, tmp_path):
    """IS fold rows are not colour-coded by _colour_wf_rows (only OOS rows are)."""
    from PySide6.QtGui import QColor
    from app.core.models.parneeds_models import ParNeedsRunResult
    from app.ui import theme

    page = _make_page(tmp_path)
    result = ParNeedsRunResult(
        run_trial="Fold 1 IS",
        workflow="walk_forward",
        strategy="DemoStrategy",
        profit_pct=5.0,
        status="completed",
    )
    page._append_result_row(result)

    page._colour_wf_rows()

    # IS rows should not be coloured green or red by _colour_wf_rows
    item = page._results.item(0, 0)
    assert item is not None
    # The foreground should NOT be green (IS rows are skipped)
    assert item.foreground().color() != QColor(theme.GREEN)


def test_best_sweep_point_row_highlighted(qt_app, tmp_path):
    """The row with the highest Profit % is highlighted after PS run (Req 10.4)."""
    from PySide6.QtGui import QColor
    from app.core.models.parneeds_models import ParNeedsRunResult
    from app.ui import theme

    page = _make_page(tmp_path)

    results = [
        ParNeedsRunResult(
            run_trial="Sweep 1",
            workflow="param_sensitivity",
            strategy="DemoStrategy",
            profit_pct=2.0,
            status="completed",
        ),
        ParNeedsRunResult(
            run_trial="Sweep 2",
            workflow="param_sensitivity",
            strategy="DemoStrategy",
            profit_pct=8.5,
            status="completed",
        ),
        ParNeedsRunResult(
            run_trial="Sweep 3",
            workflow="param_sensitivity",
            strategy="DemoStrategy",
            profit_pct=1.0,
            status="completed",
        ),
    ]
    for r in results:
        page._append_result_row(r)

    # Highlight the best row (Sweep 2 at row index 1)
    page._highlight_best_ps_row("Sweep 2")

    # Row 1 (Sweep 2) should have a non-default background
    best_item = page._results.item(1, 0)
    assert best_item is not None
    # Background should be set (not the default transparent/invalid color)
    bg_color = best_item.background().color()
    assert bg_color.isValid()
    assert bg_color != QColor(0, 0, 0, 0)  # not transparent

    # Other rows should not be highlighted
    other_item = page._results.item(0, 0)
    assert other_item is not None
    other_bg = other_item.background().color()
    assert other_bg != bg_color
