"""Smoke tests for BacktestPage instantiation with injected ProcessRunManager.

Validates that BacktestPage accepts a ProcessRunManager via constructor
injection and no longer holds a _process_svc attribute.
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

from app.app_state.settings_state import SettingsState
from app.core.services.process_run_manager import ProcessRunManager
from app.ui.pages.backtest_page import BacktestPage


# ---------------------------------------------------------------------------
# Session-scoped QApplication fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def qt_app():
    """Create (or reuse) a QApplication for the test session."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    return app


# ---------------------------------------------------------------------------
# Smoke tests
# ---------------------------------------------------------------------------


def test_backtest_page_instantiates_with_injected_manager(qt_app):
    """BacktestPage can be instantiated with a mock SettingsState and real ProcessRunManager."""
    settings_state = MagicMock(spec=SettingsState)
    settings_state.current_settings = None

    process_manager = ProcessRunManager()

    # _load_strategies calls _backtest_svc.get_available_strategies() which may
    # fail if settings aren't configured — patch it to return an empty list.
    with patch(
        "app.core.services.backtest_service.BacktestService.get_available_strategies",
        return_value=[],
    ):
        page = BacktestPage(settings_state=settings_state, process_manager=process_manager)

    assert page is not None


def test_backtest_page_has_no_process_svc_attribute(qt_app):
    """BacktestPage must NOT have a _process_svc attribute after migration."""
    settings_state = MagicMock(spec=SettingsState)
    settings_state.current_settings = None

    process_manager = ProcessRunManager()

    with patch(
        "app.core.services.backtest_service.BacktestService.get_available_strategies",
        return_value=[],
    ):
        page = BacktestPage(settings_state=settings_state, process_manager=process_manager)

    assert not hasattr(page, "_process_svc"), (
        "BacktestPage should not have _process_svc after migration to ProcessRunManager"
    )


def test_backtest_page_has_process_manager_attribute(qt_app):
    """BacktestPage must have a _process_manager attribute after migration."""
    settings_state = MagicMock(spec=SettingsState)
    settings_state.current_settings = None

    process_manager = ProcessRunManager()

    with patch(
        "app.core.services.backtest_service.BacktestService.get_available_strategies",
        return_value=[],
    ):
        page = BacktestPage(settings_state=settings_state, process_manager=process_manager)

    assert hasattr(page, "_process_manager"), (
        "BacktestPage must expose _process_manager after migration"
    )
    assert page._process_manager is process_manager
