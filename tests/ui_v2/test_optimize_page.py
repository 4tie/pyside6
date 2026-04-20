"""Unit tests for OptimizePage (app/ui_v2/pages/optimize_page.py).

Tests:
- Page constructs without errors
- RunConfigForm config round-trip
- Hyperopt options initial state
- Inline validation warnings
- Splitter has two children
- Revert button initial state

Requirements: 14.1, 14.5, 8.6
"""
import pytest
from unittest.mock import MagicMock, patch

from app.ui_v2.pages.optimize_page import OptimizePage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def settings_state():
    """Return a minimal mock SettingsState."""
    state = MagicMock()
    state.current_settings = MagicMock()
    state.current_settings.user_data_path = ""
    state.current_settings.optimize_preferences = MagicMock()
    state.current_settings.optimize_preferences.last_strategy = ""
    state.current_settings.optimize_preferences.default_timeframe = "5m"
    state.current_settings.optimize_preferences.default_timerange = ""
    state.current_settings.optimize_preferences.default_pairs = ""
    state.current_settings.optimize_preferences.epochs = 100
    state.current_settings.optimize_preferences.spaces = "buy sell roi stoploss trailing"
    state.current_settings.optimize_preferences.hyperopt_loss = "SharpeHyperOptLoss"
    state.current_settings.favorite_pairs = []
    state.settings_changed = MagicMock()
    state.settings_changed.connect = MagicMock()
    return state


@pytest.fixture
def page(qtbot, settings_state):
    """Construct an OptimizePage with mocked services and return it."""
    with patch(
        "app.ui_v2.pages.optimize_page.OptimizeService.get_available_strategies",
        return_value=["SampleStrategy", "RSIStrategy"],
    ):
        w = OptimizePage(settings_state=settings_state)
        qtbot.addWidget(w)
        w.show()
        return w


# ---------------------------------------------------------------------------
# Construction tests
# ---------------------------------------------------------------------------


class TestOptimizePageConstruction:
    """Verify the page constructs correctly."""

    def test_page_is_qwidget(self, page):
        """OptimizePage is a QWidget subclass."""
        from PySide6.QtWidgets import QWidget
        assert isinstance(page, QWidget)

    def test_run_config_form_present(self, page):
        """run_config_form attribute is a RunConfigForm instance."""
        from app.ui_v2.widgets.run_config_form import RunConfigForm
        assert isinstance(page.run_config_form, RunConfigForm)

    def test_run_button_initially_enabled(self, page):
        """Optimize button is enabled on construction."""
        assert page._run_btn.isEnabled()

    def test_stop_button_initially_disabled(self, page):
        """Stop button is disabled on construction (no process running)."""
        assert not page._stop_btn.isEnabled()

    def test_revert_button_initially_disabled(self, page):
        """Revert button is disabled on construction (no run yet)."""
        assert not page._revert_btn.isEnabled()

    def test_splitter_has_two_children(self, page):
        """QSplitter contains exactly two child widgets."""
        assert page._splitter.count() == 2

    def test_splitter_handle_width(self, page):
        """QSplitter handle width is 4px."""
        assert page._splitter.handleWidth() == 4

    def test_terminal_present(self, page):
        """TerminalWidget is present in the right panel."""
        from app.ui.widgets.terminal_widget import TerminalWidget
        assert isinstance(page._terminal, TerminalWidget)

    def test_advisor_section_present(self, page):
        """Advisor SectionHeader is present."""
        from app.ui_v2.widgets.section_header import SectionHeader
        assert isinstance(page._advisor_section, SectionHeader)

    def test_advisor_section_collapsed_by_default(self, page):
        """Advisor section is collapsed by default."""
        assert page._advisor_section.is_collapsed


# ---------------------------------------------------------------------------
# Hyperopt options tests
# ---------------------------------------------------------------------------


class TestHyperoptOptions:
    """Verify hyperopt options widgets are correctly initialized."""

    def test_epochs_spinbox_default(self, page):
        """Epochs spinbox defaults to 100."""
        assert page._epochs_spin.value() == 100

    def test_epochs_spinbox_range(self, page):
        """Epochs spinbox range is 1 to 100000."""
        assert page._epochs_spin.minimum() == 1
        assert page._epochs_spin.maximum() == 100_000

    def test_spaces_combo_has_items(self, page):
        """Spaces combo has predefined options."""
        assert page._spaces_combo.count() > 0

    def test_spaces_combo_default(self, page):
        """Spaces combo defaults to full spaces string."""
        assert "buy" in page._spaces_combo.currentText()
        assert "sell" in page._spaces_combo.currentText()

    def test_loss_combo_has_items(self, page):
        """Loss function combo has predefined options."""
        assert page._loss_combo.count() > 0

    def test_loss_combo_default(self, page):
        """Loss function combo defaults to SharpeHyperOptLoss."""
        assert page._loss_combo.currentText() == "SharpeHyperOptLoss"

    def test_epochs_warning_hidden_initially(self, page):
        """Epochs warning label is hidden when epochs >= 50."""
        assert not page._epochs_warning.isVisible()

    def test_epochs_warning_shown_for_low_value(self, page, qtbot):
        """Epochs warning label appears when epochs < 50."""
        page._epochs_spin.setValue(10)
        assert page._epochs_warning.isVisible()

    def test_epochs_warning_hidden_for_valid_value(self, page, qtbot):
        """Epochs warning label hides when epochs >= 50."""
        page._epochs_spin.setValue(10)
        page._epochs_spin.setValue(100)
        assert not page._epochs_warning.isVisible()

    def test_spaces_warning_hidden_initially(self, page):
        """Spaces warning label is hidden when spaces are set."""
        assert not page._spaces_warning.isVisible()

    def test_spaces_warning_shown_for_empty_spaces(self, page, qtbot):
        """Spaces warning label appears when spaces text is cleared."""
        page._spaces_combo.setCurrentText("")
        assert page._spaces_warning.isVisible()


# ---------------------------------------------------------------------------
# Config round-trip tests
# ---------------------------------------------------------------------------


class TestRunConfigFormRoundTrip:
    """Verify RunConfigForm set_config / get_config round-trip via OptimizePage."""

    def test_strategy_round_trip(self, page):
        """set_config strategy -> get_config returns same strategy."""
        page.run_config_form.set_config({"strategy": "SampleStrategy"})
        assert page.run_config_form.get_config()["strategy"] == "SampleStrategy"

    def test_timeframe_round_trip(self, page):
        """set_config timeframe -> get_config returns same timeframe."""
        page.run_config_form.set_config({"timeframe": "4h"})
        assert page.run_config_form.get_config()["timeframe"] == "4h"

    def test_timerange_round_trip(self, page):
        """set_config timerange -> get_config returns same timerange."""
        page.run_config_form.set_config({"timerange": "20230101-20231231"})
        assert page.run_config_form.get_config()["timerange"] == "20230101-20231231"

    def test_pairs_round_trip(self, page):
        """set_config pairs -> get_config returns same pairs."""
        cfg = {"pairs": ["BTC/USDT", "ETH/USDT"]}
        page.run_config_form.set_config(cfg)
        result = page.run_config_form.get_config()["pairs"]
        assert sorted(result) == sorted(cfg["pairs"])

    def test_full_config_round_trip(self, page):
        """Full config dict survives a set_config -> get_config round-trip."""
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


# ---------------------------------------------------------------------------
# get_current_config tests
# ---------------------------------------------------------------------------


class TestGetCurrentConfig:
    """Verify get_current_config returns all fields."""

    def test_includes_epochs(self, page):
        """get_current_config includes epochs."""
        page._epochs_spin.setValue(200)
        cfg = page.get_current_config()
        assert cfg["epochs"] == 200

    def test_includes_spaces(self, page):
        """get_current_config includes spaces as a list."""
        page._spaces_combo.setCurrentText("buy sell")
        cfg = page.get_current_config()
        assert "buy" in cfg["spaces"]
        assert "sell" in cfg["spaces"]

    def test_includes_hyperopt_loss(self, page):
        """get_current_config includes hyperopt_loss."""
        page._loss_combo.setCurrentText("MaxDrawDownHyperOptLoss")
        cfg = page.get_current_config()
        assert cfg["hyperopt_loss"] == "MaxDrawDownHyperOptLoss"
