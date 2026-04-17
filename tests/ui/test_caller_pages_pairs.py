# Feature: pair-favorites
"""
Unit tests for caller page integration with the new PairsSelectorDialog signature.

Validates: Requirements 5.2, 5.3
"""
import sys
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Session-scoped QApplication fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def qt_app():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    return app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_prefs():
    """Return a MagicMock preferences object with string fields Qt widgets can accept."""
    prefs = MagicMock()
    prefs.last_strategy = ""
    prefs.default_timeframe = "5m"
    prefs.default_timerange = ""
    prefs.default_pairs = ""
    prefs.dry_run_wallet = 80.0
    prefs.max_open_trades = 2
    prefs.epochs = 100
    prefs.spaces = "buy sell roi stoploss trailing"
    prefs.hyperopt_loss = ""
    prefs.last_timerange_preset = ""
    prefs.paired_favorites = []
    return prefs


def _make_settings_state(favorite_pairs=None):
    """Return a MagicMock SettingsState with a current_settings that has favorite_pairs."""
    state = MagicMock()
    settings = MagicMock()
    settings.favorite_pairs = favorite_pairs or ["BTC/USDT", "ETH/USDT"]
    settings.user_data_path = ""
    prefs = _make_prefs()
    settings.backtest_preferences = prefs
    settings.optimize_preferences = prefs
    settings.download_preferences = prefs
    state.current_settings = settings
    return state


# ---------------------------------------------------------------------------
# BacktestPage
# ---------------------------------------------------------------------------

class TestBacktestPagePairsIntegration:
    def test_on_select_pairs_uses_favorite_pairs(self, qt_app):
        """_on_select_pairs passes settings.favorite_pairs to PairsSelectorDialog."""
        from app.ui.pages.backtest_page import BacktestPage

        state = _make_settings_state(["BTC/USDT", "SOL/USDT"])

        with patch("app.ui.pages.backtest_page.PairsSelectorDialog") as MockDialog:
            mock_dialog_instance = MagicMock()
            mock_dialog_instance.exec.return_value = 0  # QDialog.Rejected
            MockDialog.return_value = mock_dialog_instance

            page = BacktestPage(state)
            page._on_select_pairs()

        MockDialog.assert_called_once()
        _, kwargs = MockDialog.call_args
        assert kwargs["favorites"] == ["BTC/USDT", "SOL/USDT"]

    def test_on_select_pairs_forwards_settings_state(self, qt_app):
        """_on_select_pairs passes self.settings_state to PairsSelectorDialog."""
        from app.ui.pages.backtest_page import BacktestPage

        state = _make_settings_state()

        with patch("app.ui.pages.backtest_page.PairsSelectorDialog") as MockDialog:
            mock_dialog_instance = MagicMock()
            mock_dialog_instance.exec.return_value = 0
            MockDialog.return_value = mock_dialog_instance

            page = BacktestPage(state)
            page._on_select_pairs()

        _, kwargs = MockDialog.call_args
        assert kwargs["settings_state"] is state

    def test_save_preferences_does_not_append_to_paired_favorites(self, qt_app):
        """_save_preferences_to_settings no longer mutates prefs.paired_favorites."""
        from app.ui.pages.backtest_page import BacktestPage

        state = _make_settings_state()
        state.current_settings.backtest_preferences.paired_favorites = []

        page = BacktestPage(state)
        page.selected_pairs = ["BTC/USDT", "ETH/USDT"]
        page._save_preferences_to_settings()

        assert state.current_settings.backtest_preferences.paired_favorites == []


# ---------------------------------------------------------------------------
# OptimizePage
# ---------------------------------------------------------------------------

class TestOptimizePagePairsIntegration:
    def test_on_select_pairs_uses_favorite_pairs(self, qt_app):
        """_on_select_pairs passes settings.favorite_pairs to PairsSelectorDialog."""
        from app.ui.pages.optimize_page import OptimizePage

        state = _make_settings_state(["XRP/USDT"])

        with patch("app.ui.pages.optimize_page.PairsSelectorDialog") as MockDialog:
            mock_dialog_instance = MagicMock()
            mock_dialog_instance.exec.return_value = 0
            MockDialog.return_value = mock_dialog_instance

            page = OptimizePage(state)
            page._on_select_pairs()

        MockDialog.assert_called_once()
        _, kwargs = MockDialog.call_args
        assert kwargs["favorites"] == ["XRP/USDT"]

    def test_on_select_pairs_forwards_settings_state(self, qt_app):
        """_on_select_pairs passes self.settings_state to PairsSelectorDialog."""
        from app.ui.pages.optimize_page import OptimizePage

        state = _make_settings_state()

        with patch("app.ui.pages.optimize_page.PairsSelectorDialog") as MockDialog:
            mock_dialog_instance = MagicMock()
            mock_dialog_instance.exec.return_value = 0
            MockDialog.return_value = mock_dialog_instance

            page = OptimizePage(state)
            page._on_select_pairs()

        _, kwargs = MockDialog.call_args
        assert kwargs["settings_state"] is state

    def test_save_preferences_does_not_append_to_paired_favorites(self, qt_app):
        """_save_preferences no longer mutates prefs.paired_favorites."""
        from app.ui.pages.optimize_page import OptimizePage

        state = _make_settings_state()
        state.current_settings.optimize_preferences.paired_favorites = []

        page = OptimizePage(state)
        page.selected_pairs = ["BTC/USDT"]
        page._save_preferences()

        assert state.current_settings.optimize_preferences.paired_favorites == []


# ---------------------------------------------------------------------------
# DownloadDataPage
# ---------------------------------------------------------------------------

class TestDownloadDataPagePairsIntegration:
    def test_on_select_pairs_uses_favorite_pairs(self, qt_app):
        """_on_select_pairs passes settings.favorite_pairs to PairsSelectorDialog."""
        from app.ui.pages.download_data_page import DownloadDataPage

        state = _make_settings_state(["ADA/USDT", "DOT/USDT"])

        with patch("app.ui.pages.download_data_page.PairsSelectorDialog") as MockDialog:
            mock_dialog_instance = MagicMock()
            mock_dialog_instance.exec.return_value = 0
            MockDialog.return_value = mock_dialog_instance

            page = DownloadDataPage(state)
            page._on_select_pairs()

        MockDialog.assert_called_once()
        _, kwargs = MockDialog.call_args
        assert kwargs["favorites"] == ["ADA/USDT", "DOT/USDT"]

    def test_on_select_pairs_forwards_settings_state(self, qt_app):
        """_on_select_pairs passes self.settings_state to PairsSelectorDialog."""
        from app.ui.pages.download_data_page import DownloadDataPage

        state = _make_settings_state()

        with patch("app.ui.pages.download_data_page.PairsSelectorDialog") as MockDialog:
            mock_dialog_instance = MagicMock()
            mock_dialog_instance.exec.return_value = 0
            MockDialog.return_value = mock_dialog_instance

            page = DownloadDataPage(state)
            page._on_select_pairs()

        _, kwargs = MockDialog.call_args
        assert kwargs["settings_state"] is state

    def test_save_preferences_does_not_append_to_paired_favorites(self, qt_app):
        """_save_preferences no longer mutates prefs.paired_favorites."""
        from app.ui.pages.download_data_page import DownloadDataPage

        state = _make_settings_state()
        state.current_settings.download_preferences.paired_favorites = []

        page = DownloadDataPage(state)
        page.selected_pairs = ["BTC/USDT", "ETH/USDT"]
        page._save_preferences()

        assert state.current_settings.download_preferences.paired_favorites == []
