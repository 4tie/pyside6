"""
UI tests for Strategy Lab LoopPage date sync and launch guards.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.models.settings_models import AppSettings, StrategyLabPreferences


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def _make_state(base_path: Path):
    settings = AppSettings(
        user_data_path=str(base_path),
        strategy_lab=StrategyLabPreferences(),
    )

    settings_service = MagicMock()
    settings_service.load_settings.return_value = settings
    settings_service.save_settings.side_effect = lambda value: value

    state = MagicMock()
    state.settings_service = settings_service
    state.settings_changed = MagicMock()
    state.settings_changed.connect = MagicMock()
    return state


def _make_page(qapp):
    state = _make_state(Path.cwd())
    with (
        patch("app.ui.pages.loop_page.ImproveService") as mock_improve,
        patch("app.ui.pages.loop_page.BacktestService"),
    ):
        improve = mock_improve.return_value
        improve.get_available_strategies.return_value = ["TestStrategy"]
        improve.cleanup_stale_sandboxes.return_value = None
        improve.load_baseline_params.return_value = {"stoploss": -0.10}

        from app.ui.pages.loop_page import LoopPage

        page = LoopPage(state)
        return page, state, improve


def test_date_fields_sync_timerange(qapp):
    page, _, _ = _make_page(qapp)

    page._date_from_edit.setText("20240101")
    page._date_to_edit.setText("20240201")

    assert page._timerange_edit.text() == "20240101-20240201"


def test_timerange_syncs_date_fields(qapp):
    page, _, _ = _make_page(qapp)

    page._timerange_edit.setText("20240301-20240401")

    assert page._date_from_edit.text() == "20240301"
    assert page._date_to_edit.text() == "20240401"


def test_start_blocked_when_dates_missing(qapp):
    page, _, _ = _make_page(qapp)
    page._strategy_combo.setCurrentText("TestStrategy")
    page._date_from_edit.setText("")
    page._date_to_edit.setText("")

    with patch("app.ui.pages.loop_page.QMessageBox.warning") as warning:
        page._on_start()

    warning.assert_called_once()
    assert "Start Date" in warning.call_args.args[2]


def test_hyperopt_mode_visibly_blocked(qapp):
    page, _, _ = _make_page(qapp)

    page._iteration_mode_combo.setCurrentIndex(1)

    assert page._start_btn.isEnabled() is False
    assert page._hyperopt_block_lbl.isHidden() is False

    with patch("app.ui.pages.loop_page.QMessageBox.warning") as warning:
        page._on_start()

    warning.assert_called_once()
    assert "Hyperopt-guided" in warning.call_args.args[2]
