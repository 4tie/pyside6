"""Unit tests for BacktestPage (app/ui_v2/pages/backtest_page.py).

Tests:
- RunConfigForm config round-trip: set_config → get_config returns same values
- Page constructs without errors
- Run/Stop button initial states

Requirements: 4.1, 4.3
"""
import pytest
from unittest.mock import MagicMock, patch

from app.ui_v2.pages.backtest_page import BacktestPage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def settings_state():
    """Return a minimal mock SettingsState."""
    state = MagicMock()
    state.current_settings = MagicMock()
    state.current_settings.user_data_path = ""
    state.current_settings.backtest_preferences = MagicMock()
    state.current_settings.backtest_preferences.last_strategy = ""
    state.current_settings.backtest_preferences.default_timeframe = "5m"
    state.current_settings.backtest_preferences.default_timerange = ""
    state.current_settings.backtest_preferences.default_pairs = ""
    state.current_settings.backtest_preferences.dry_run_wallet = 80.0
    state.current_settings.backtest_preferences.max_open_trades = 2
    state.current_settings.favorite_pairs = []
    # settings_changed is a real Qt signal on the real object; mock it as a
    # simple MagicMock so connect() calls don't raise.
    state.settings_changed = MagicMock()
    state.settings_changed.connect = MagicMock()
    return state


@pytest.fixture
def page(qtbot, settings_state):
    """Construct a BacktestPage with mocked services and return it."""
    with (
        patch(
            "app.ui_v2.pages.backtest_page.BacktestService.get_available_strategies",
            return_value=["SampleStrategy", "RSIStrategy"],
        ),
        patch(
            "app.ui_v2.pages.backtest_page.BacktestService.rebuild_index",
            return_value=None,
        ),
        patch(
            "app.ui_v2.pages.backtest_page.IndexStore.get_strategy_runs",
            return_value=[],
        ),
    ):
        w = BacktestPage(settings_state=settings_state)
        qtbot.addWidget(w)
        w.show()
        return w


# ---------------------------------------------------------------------------
# Construction tests
# ---------------------------------------------------------------------------


class TestBacktestPageConstruction:
    """Verify the page constructs correctly."""

    def test_page_is_qwidget(self, page):
        """BacktestPage is a QWidget subclass."""
        from PySide6.QtWidgets import QWidget
        assert isinstance(page, QWidget)

    def test_run_config_form_present(self, page):
        """run_config_form attribute is a RunConfigForm instance."""
        from app.ui_v2.widgets.run_config_form import RunConfigForm
        assert isinstance(page.run_config_form, RunConfigForm)

    def test_run_button_initially_enabled(self, page):
        """Run button is enabled on construction."""
        assert page._run_btn.isEnabled()

    def test_stop_button_initially_disabled(self, page):
        """Stop button is disabled on construction (no process running)."""
        assert not page._stop_btn.isEnabled()

    def test_splitter_has_two_children(self, page):
        """QSplitter contains exactly two child widgets."""
        assert page._splitter.count() == 2

    def test_output_tabs_has_two_tabs(self, page):
        """Output tab widget has Results, Pair Results, Compare, and Terminal tabs."""
        assert page._output_tabs.count() == 4
        assert page._output_tabs.tabText(0) == "Results"
        assert page._output_tabs.tabText(1) == "Pair Results"
        assert page._output_tabs.tabText(2) == "Compare"
        assert page._output_tabs.tabText(3) == "Terminal"

    def test_loop_completed_signal_exists(self, page):
        """loop_completed signal is declared on the page."""
        assert hasattr(page, "loop_completed")


# ---------------------------------------------------------------------------
# Config round-trip tests (sub-task 7.1)
# ---------------------------------------------------------------------------


class TestRunConfigFormRoundTrip:
    """Verify RunConfigForm set_config / get_config round-trip via BacktestPage."""

    def test_strategy_round_trip(self, page):
        """set_config strategy → get_config returns same strategy."""
        cfg = {"strategy": "SampleStrategy"}
        page.run_config_form.set_config(cfg)
        assert page.run_config_form.get_config()["strategy"] == "SampleStrategy"

    def test_timeframe_round_trip(self, page):
        """set_config timeframe → get_config returns same timeframe."""
        cfg = {"timeframe": "4h"}
        page.run_config_form.set_config(cfg)
        assert page.run_config_form.get_config()["timeframe"] == "4h"

    def test_timerange_round_trip(self, page):
        """set_config timerange → get_config returns same timerange."""
        cfg = {"timerange": "20230101-20231231"}
        page.run_config_form.set_config(cfg)
        assert page.run_config_form.get_config()["timerange"] == "20230101-20231231"

    def test_pairs_round_trip(self, page):
        """set_config pairs → get_config returns same pairs."""
        cfg = {"pairs": ["BTC/USDT", "ETH/USDT"]}
        page.run_config_form.set_config(cfg)
        result = page.run_config_form.get_config()["pairs"]
        assert sorted(result) == sorted(cfg["pairs"])

    def test_full_config_round_trip(self, page):
        """Full config dict survives a set_config → get_config round-trip.

        Validates: Requirements 4.1, 4.3
        """
        cfg = {
            "strategy": "RSIStrategy",
            "timeframe": "1h",
            "timerange": "20230601-20230901",
            "pairs": ["BTC/USDT", "SOL/USDT"],
        }
        page.run_config_form.set_config(cfg)
        result = page.run_config_form.get_config()

        assert result["strategy"] == cfg["strategy"]
        assert result["timeframe"] == cfg["timeframe"]
        assert result["timerange"] == cfg["timerange"]
        assert sorted(result["pairs"]) == sorted(cfg["pairs"])

    def test_empty_timerange_round_trip(self, page):
        """Empty timerange survives round-trip."""
        page.run_config_form.set_config({"timerange": ""})
        assert page.run_config_form.get_config()["timerange"] == ""

    def test_empty_pairs_round_trip(self, page):
        """Empty pairs list survives round-trip."""
        page.run_config_form.set_config({"pairs": []})
        assert page.run_config_form.get_config()["pairs"] == []

    def test_get_current_config_includes_advanced(self, page):
        """get_current_config includes dry_run_wallet and max_open_trades."""
        page.run_config_form.set_config({"strategy": "S", "timeframe": "5m"})
        page._dry_run_wallet.setValue(100.0)
        page._max_open_trades.setValue(5)
        full = page.get_current_config()
        assert full["dry_run_wallet"] == 100.0
        assert full["max_open_trades"] == 5
