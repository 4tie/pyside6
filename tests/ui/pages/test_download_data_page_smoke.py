"""Smoke tests for DownloadPage instantiation with injected ProcessRunManager.

Validates that DownloadPage accepts a ProcessRunManager via constructor
injection and no longer holds a _process_svc attribute.
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

from app.app_state.settings_state import SettingsState
from app.core.services.process_run_manager import ProcessRunManager
from app.ui.pages.download_page import DownloadPage


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
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_settings():
    """Return a mock AppSettings with download_preferences populated."""
    mock_prefs = MagicMock()
    mock_prefs.prepend = False
    mock_prefs.erase = False

    mock_settings = MagicMock()
    mock_settings.download_preferences = mock_prefs
    return mock_settings


# ---------------------------------------------------------------------------
# Smoke tests
# ---------------------------------------------------------------------------


def test_download_page_instantiates_with_injected_manager(qt_app):
    """DownloadPage can be instantiated with a mock SettingsState and real ProcessRunManager."""
    settings_state = MagicMock(spec=SettingsState)
    settings_state.current_settings = None

    process_manager = ProcessRunManager()

    # _restore_preferences calls SettingsService.load_settings() — patch it so
    # no real settings file is required.
    with patch(
        "app.core.services.settings_service.SettingsService.load_settings",
        return_value=_make_mock_settings(),
    ):
        page = DownloadPage(settings_state=settings_state, process_manager=process_manager)

    assert page is not None


def test_download_page_has_no_process_svc_attribute(qt_app):
    """DownloadPage must NOT have a _process_svc attribute after migration."""
    settings_state = MagicMock(spec=SettingsState)
    settings_state.current_settings = None

    process_manager = ProcessRunManager()

    with patch(
        "app.core.services.settings_service.SettingsService.load_settings",
        return_value=_make_mock_settings(),
    ):
        page = DownloadPage(settings_state=settings_state, process_manager=process_manager)

    assert not hasattr(page, "_process_svc"), (
        "DownloadPage should not have _process_svc after migration to ProcessRunManager"
    )


def test_download_page_has_process_manager_attribute(qt_app):
    """DownloadPage must have a _process_manager attribute after migration."""
    settings_state = MagicMock(spec=SettingsState)
    settings_state.current_settings = None

    process_manager = ProcessRunManager()

    with patch(
        "app.core.services.settings_service.SettingsService.load_settings",
        return_value=_make_mock_settings(),
    ):
        page = DownloadPage(settings_state=settings_state, process_manager=process_manager)

    assert hasattr(page, "_process_manager"), (
        "DownloadPage must expose _process_manager after migration"
    )
    assert page._process_manager is process_manager
