"""Tests for download-data-prepend-erase feature.

Covers:
- Property 1: prepend flag presence matches parameter (Requirements 2.1, 2.2)
- Property 2: erase flag presence matches parameter (Requirements 4.2, 4.3)
- Property 3: DownloadPreferences round-trip serialization (Requirements 6.3, 6.4, 6.5)
- Unit tests for DownloadDataService.build_command (Requirements 3.1–3.4)
- Unit tests for DownloadPage checkbox initialisation and preferences (Requirements 1.4, 1.5, 5.3, 5.4, 6.4, 6.5)
"""
from __future__ import annotations

from typing import List, Optional
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from app.core.freqtrade.runners.download_data_runner import create_download_data_command
from app.core.models.settings_models import AppSettings, DownloadPreferences


# ---------------------------------------------------------------------------
# Shared mock helpers
# ---------------------------------------------------------------------------

def _make_mock_settings() -> AppSettings:
    """Return a minimal AppSettings mock that avoids filesystem access."""
    return AppSettings(
        python_executable="/usr/bin/python3",
        user_data_path="/tmp/user_data",
    )


# ---------------------------------------------------------------------------
# Property 3: DownloadPreferences round-trip serialization
# ---------------------------------------------------------------------------

@given(prepend=st.booleans(), erase=st.booleans())
@h_settings(max_examples=100)
def test_preferences_round_trip(prepend: bool, erase: bool) -> None:
    """Feature: download-data-prepend-erase, Property 3: preferences round-trip.

    For any combination of prepend and erase boolean values, saving those
    values to DownloadPreferences and then loading them back SHALL produce
    the same boolean values.

    Validates: Requirements 6.3, 6.4, 6.5
    """
    prefs = DownloadPreferences(prepend=prepend, erase=erase)
    serialized = prefs.model_dump()
    restored = DownloadPreferences(**serialized)
    assert restored.prepend == prepend
    assert restored.erase == erase


def test_download_preferences_defaults() -> None:
    """DownloadPreferences defaults prepend and erase to False (Requirements 6.1, 6.2)."""
    prefs = DownloadPreferences()
    assert prefs.prepend is False
    assert prefs.erase is False


# ---------------------------------------------------------------------------
# Property 1: Prepend flag presence matches parameter
# ---------------------------------------------------------------------------

@given(
    timeframe=st.sampled_from(["1m", "5m", "1h", "1d"]),
    timerange=st.one_of(st.none(), st.text(min_size=1, max_size=20)),
    pairs=st.lists(st.text(min_size=3, max_size=10), max_size=5),
    erase=st.booleans(),
    prepend=st.booleans(),
)
@h_settings(max_examples=100)
def test_prepend_flag_matches_parameter(
    timeframe: str,
    timerange: Optional[str],
    pairs: List[str],
    erase: bool,
    prepend: bool,
) -> None:
    """Feature: download-data-prepend-erase, Property 1: prepend flag presence matches parameter.

    For any valid combination of timeframe, timerange, pairs, and erase values,
    the --prepend flag SHALL appear in the generated argument list if and only
    if prepend=True.

    Validates: Requirements 2.1, 2.2
    """
    mock_settings = _make_mock_settings()
    with patch(
        "app.core.freqtrade.runners.download_data_runner.find_run_paths"
    ) as mock_paths:
        mock_paths.return_value = MagicMock(
            user_data_dir="/tmp/user_data",
            config_file="/tmp/user_data/config/config.json",
            strategy_file="/tmp/user_data/strategies/strategy.py",
        )
        cmd = create_download_data_command(
            settings=mock_settings,
            timeframe=timeframe,
            timerange=timerange,
            pairs=pairs,
            prepend=prepend,
            erase=erase,
        )
    assert ("--prepend" in cmd.args) == prepend


# ---------------------------------------------------------------------------
# Property 2: Erase flag presence matches parameter
# ---------------------------------------------------------------------------

@given(
    timeframe=st.sampled_from(["1m", "5m", "1h", "1d"]),
    timerange=st.one_of(st.none(), st.text(min_size=1, max_size=20)),
    pairs=st.lists(st.text(min_size=3, max_size=10), max_size=5),
    erase=st.booleans(),
    prepend=st.booleans(),
)
@h_settings(max_examples=100)
def test_erase_flag_matches_parameter(
    timeframe: str,
    timerange: Optional[str],
    pairs: List[str],
    erase: bool,
    prepend: bool,
) -> None:
    """Feature: download-data-prepend-erase, Property 2: erase flag presence matches parameter.

    For any valid combination of timeframe, timerange, pairs, and prepend values,
    the --erase flag SHALL appear in the generated argument list if and only
    if erase=True.

    Validates: Requirements 4.2, 4.3
    """
    mock_settings = _make_mock_settings()
    with patch(
        "app.core.freqtrade.runners.download_data_runner.find_run_paths"
    ) as mock_paths:
        mock_paths.return_value = MagicMock(
            user_data_dir="/tmp/user_data",
            config_file="/tmp/user_data/config/config.json",
            strategy_file="/tmp/user_data/strategies/strategy.py",
        )
        cmd = create_download_data_command(
            settings=mock_settings,
            timeframe=timeframe,
            timerange=timerange,
            pairs=pairs,
            prepend=prepend,
            erase=erase,
        )
    assert ("--erase" in cmd.args) == erase


# ---------------------------------------------------------------------------
# Unit tests for create_download_data_command (no kwargs → neither flag)
# ---------------------------------------------------------------------------

def test_runner_no_flags_by_default() -> None:
    """create_download_data_command without prepend/erase produces neither flag (Requirements 2.3, 4.1)."""
    mock_settings = _make_mock_settings()
    with patch(
        "app.core.freqtrade.runners.download_data_runner.find_run_paths"
    ) as mock_paths:
        mock_paths.return_value = MagicMock(
            user_data_dir="/tmp/user_data",
            config_file="/tmp/user_data/config/config.json",
            strategy_file="/tmp/user_data/strategies/strategy.py",
        )
        cmd = create_download_data_command(
            settings=mock_settings,
            timeframe="5m",
        )
    assert "--prepend" not in cmd.args
    assert "--erase" not in cmd.args


# ---------------------------------------------------------------------------
# Unit tests for DownloadDataService.build_command
# ---------------------------------------------------------------------------

def _make_service():
    """Return a DownloadDataService with a mocked SettingsService."""
    from app.core.services.download_data_service import DownloadDataService

    settings_svc = MagicMock()
    settings_svc.load_settings.return_value = _make_mock_settings()
    return DownloadDataService(settings_svc)


def test_service_no_flags_by_default() -> None:
    """build_command without prepend/erase kwargs produces neither flag (Requirements 3.1, 3.2)."""
    svc = _make_service()
    with patch(
        "app.core.freqtrade.runners.download_data_runner.find_run_paths"
    ) as mock_paths:
        mock_paths.return_value = MagicMock(
            user_data_dir="/tmp/user_data",
            config_file="/tmp/user_data/config/config.json",
            strategy_file="/tmp/user_data/strategies/strategy.py",
        )
        cmd = svc.build_command(timeframe="5m")
    assert "--prepend" not in cmd.args
    assert "--erase" not in cmd.args


def test_service_forwards_prepend_true() -> None:
    """build_command with prepend=True forwards --prepend to the command (Requirement 3.3)."""
    svc = _make_service()
    with patch(
        "app.core.freqtrade.runners.download_data_runner.find_run_paths"
    ) as mock_paths:
        mock_paths.return_value = MagicMock(
            user_data_dir="/tmp/user_data",
            config_file="/tmp/user_data/config/config.json",
            strategy_file="/tmp/user_data/strategies/strategy.py",
        )
        cmd = svc.build_command(timeframe="5m", prepend=True)
    assert "--prepend" in cmd.args


def test_service_forwards_erase_true() -> None:
    """build_command with erase=True forwards --erase to the command (Requirement 3.4)."""
    svc = _make_service()
    with patch(
        "app.core.freqtrade.runners.download_data_runner.find_run_paths"
    ) as mock_paths:
        mock_paths.return_value = MagicMock(
            user_data_dir="/tmp/user_data",
            config_file="/tmp/user_data/config/config.json",
            strategy_file="/tmp/user_data/strategies/strategy.py",
        )
        cmd = svc.build_command(timeframe="5m", erase=True)
    assert "--erase" in cmd.args


# ---------------------------------------------------------------------------
# Unit tests for DownloadPage checkbox initialisation and preferences
# ---------------------------------------------------------------------------

@pytest.fixture()
def page(qtbot):
    """Create a DownloadPage with mocked dependencies."""
    from app.ui.pages.download_page import DownloadPage
    from app.app_state.settings_state import SettingsState

    state = MagicMock(spec=SettingsState)
    state.current_settings = _make_mock_settings()

    with patch("app.ui.pages.download_page.SettingsService") as MockSettingsSvc, \
         patch("app.ui.pages.download_page.DownloadDataService") as MockDownloadSvc, \
         patch("app.ui.pages.download_page.ProcessService"):

        mock_settings_svc_instance = MagicMock()
        mock_settings_svc_instance.load_settings.return_value = _make_mock_settings()
        MockSettingsSvc.return_value = mock_settings_svc_instance

        mock_download_svc_instance = MagicMock()
        MockDownloadSvc.return_value = mock_download_svc_instance

        p = DownloadPage(state)
        qtbot.addWidget(p)
        return p


def test_page_checkboxes_unchecked_by_default(page) -> None:
    """DownloadPage initialises with both checkboxes unchecked when preferences are default (Requirements 1.4, 1.5)."""
    assert page._prepend_cb.isChecked() is False
    assert page._erase_cb.isChecked() is False


def test_page_restore_prepend_true(qtbot) -> None:
    """_restore_preferences sets 'Prepend data' checked when DownloadPreferences.prepend=True (Requirement 6.4)."""
    from app.ui.pages.download_page import DownloadPage
    from app.app_state.settings_state import SettingsState

    settings = _make_mock_settings()
    settings.download_preferences.prepend = True
    settings.download_preferences.erase = False

    state = MagicMock(spec=SettingsState)
    state.current_settings = settings

    with patch("app.ui.pages.download_page.SettingsService") as MockSettingsSvc, \
         patch("app.ui.pages.download_page.DownloadDataService"), \
         patch("app.ui.pages.download_page.ProcessService"):

        mock_settings_svc_instance = MagicMock()
        mock_settings_svc_instance.load_settings.return_value = settings
        MockSettingsSvc.return_value = mock_settings_svc_instance

        p = DownloadPage(state)
        qtbot.addWidget(p)

    assert p._prepend_cb.isChecked() is True
    assert p._erase_cb.isChecked() is False


def test_page_restore_erase_true(qtbot) -> None:
    """_restore_preferences sets 'Erase existing data' checked when DownloadPreferences.erase=True (Requirement 6.5)."""
    from app.ui.pages.download_page import DownloadPage
    from app.app_state.settings_state import SettingsState

    settings = _make_mock_settings()
    settings.download_preferences.prepend = False
    settings.download_preferences.erase = True

    state = MagicMock(spec=SettingsState)
    state.current_settings = settings

    with patch("app.ui.pages.download_page.SettingsService") as MockSettingsSvc, \
         patch("app.ui.pages.download_page.DownloadDataService"), \
         patch("app.ui.pages.download_page.ProcessService"):

        mock_settings_svc_instance = MagicMock()
        mock_settings_svc_instance.load_settings.return_value = settings
        MockSettingsSvc.return_value = mock_settings_svc_instance

        p = DownloadPage(state)
        qtbot.addWidget(p)

    assert p._prepend_cb.isChecked() is False
    assert p._erase_cb.isChecked() is True


def test_page_both_unchecked_no_flags(page) -> None:
    """Both checkboxes unchecked → command contains neither flag (Requirement 5.3)."""
    page._prepend_cb.setChecked(False)
    page._erase_cb.setChecked(False)

    with patch(
        "app.core.freqtrade.runners.download_data_runner.find_run_paths"
    ) as mock_paths:
        mock_paths.return_value = MagicMock(
            user_data_dir="/tmp/user_data",
            config_file="/tmp/user_data/config/config.json",
            strategy_file="/tmp/user_data/strategies/strategy.py",
        )
        # Restore the real service on the page for this test
        from app.core.services.download_data_service import DownloadDataService
        real_svc = DownloadDataService(page._settings_svc)
        page._download_svc = real_svc

        cmd = page._download_svc.build_command(
            timeframe=page._tf_combo.currentText(),
            prepend=page._prepend_cb.isChecked(),
            erase=page._erase_cb.isChecked(),
        )

    assert "--prepend" not in cmd.args
    assert "--erase" not in cmd.args


def test_page_both_checked_both_flags(page) -> None:
    """Both checkboxes checked → command contains both flags (Requirement 5.4)."""
    page._prepend_cb.setChecked(True)
    page._erase_cb.setChecked(True)

    with patch(
        "app.core.freqtrade.runners.download_data_runner.find_run_paths"
    ) as mock_paths:
        mock_paths.return_value = MagicMock(
            user_data_dir="/tmp/user_data",
            config_file="/tmp/user_data/config/config.json",
            strategy_file="/tmp/user_data/strategies/strategy.py",
        )
        from app.core.services.download_data_service import DownloadDataService
        real_svc = DownloadDataService(page._settings_svc)
        page._download_svc = real_svc

        cmd = page._download_svc.build_command(
            timeframe=page._tf_combo.currentText(),
            prepend=page._prepend_cb.isChecked(),
            erase=page._erase_cb.isChecked(),
        )

    assert "--prepend" in cmd.args
    assert "--erase" in cmd.args
