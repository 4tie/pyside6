"""Unit tests for RunConfigForm (app/ui_v2/widgets/run_config_form.py).

Tests:
- get_config returns correct dict after setting each field
- set_config populates all visible fields
- config_changed signal fires on field change
- Inline validation rejects empty required fields

Requirements: 4.3
"""
import pytest
from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication

from app.ui_v2.widgets.run_config_form import RunConfigForm


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def settings_state():
    """Return a minimal mock SettingsState."""
    state = MagicMock()
    state.current_settings = MagicMock()
    state.current_settings.favorite_pairs = ["BTC/USDT", "ETH/USDT"]
    state.current_settings.backtest_preferences = MagicMock()
    state.current_settings.backtest_preferences.max_open_trades = 3
    return state


@pytest.fixture
def form(qtbot, settings_state):
    """Return a fully-visible RunConfigForm with all sections enabled."""
    w = RunConfigForm(
        settings_state=settings_state,
        show_strategy=True,
        show_timeframe=True,
        show_timerange=True,
        show_pairs=True,
    )
    qtbot.addWidget(w)
    w.show()
    return w


@pytest.fixture
def form_no_strategy(qtbot, settings_state):
    """Return a RunConfigForm with strategy hidden (DownloadPage use-case)."""
    w = RunConfigForm(
        settings_state=settings_state,
        show_strategy=False,
        show_timeframe=True,
        show_timerange=True,
        show_pairs=True,
    )
    qtbot.addWidget(w)
    w.show()
    return w


# ---------------------------------------------------------------------------
# get_config tests
# ---------------------------------------------------------------------------


class TestGetConfig:
    """Verify get_config returns the correct dict after field changes."""

    def test_default_config_has_expected_keys(self, form):
        """get_config returns dict with all four keys when all sections shown."""
        config = form.get_config()
        assert set(config.keys()) == {"strategy", "timeframe", "timerange", "pairs"}

    def test_default_timeframe_is_5m(self, form):
        """Default timeframe is '5m'."""
        assert form.get_config()["timeframe"] == "5m"

    def test_default_strategy_is_empty(self, form):
        """Default strategy is empty string."""
        assert form.get_config()["strategy"] == ""

    def test_default_pairs_is_empty_list(self, form):
        """Default pairs is an empty list."""
        assert form.get_config()["pairs"] == []

    def test_strategy_field_reflected_in_get_config(self, form):
        """Setting strategy text is reflected in get_config."""
        form._strategy_combo.setCurrentText("MyStrategy")
        assert form.get_config()["strategy"] == "MyStrategy"

    def test_timeframe_field_reflected_in_get_config(self, form):
        """Changing timeframe is reflected in get_config."""
        form._timeframe_combo.setCurrentText("1h")
        assert form.get_config()["timeframe"] == "1h"

    def test_timerange_field_reflected_in_get_config(self, form):
        """Typing a timerange is reflected in get_config."""
        form._timerange_edit.setText("20230101-20231231")
        assert form.get_config()["timerange"] == "20230101-20231231"

    def test_hidden_strategy_key_absent(self, form_no_strategy):
        """When show_strategy=False, 'strategy' key is absent from get_config."""
        config = form_no_strategy.get_config()
        assert "strategy" not in config

    def test_pairs_set_directly_reflected(self, form):
        """Directly setting _selected_pairs is reflected in get_config."""
        form._selected_pairs = ["BTC/USDT", "ETH/USDT"]
        form._update_pairs_label()
        assert form.get_config()["pairs"] == ["BTC/USDT", "ETH/USDT"]


# ---------------------------------------------------------------------------
# set_config tests
# ---------------------------------------------------------------------------


class TestSetConfig:
    """Verify set_config populates all visible fields."""

    def test_set_config_strategy(self, form):
        """set_config populates the strategy field."""
        form.set_config({"strategy": "SampleStrategy"})
        assert form._strategy_combo.currentText() == "SampleStrategy"

    def test_set_config_timeframe(self, form):
        """set_config populates the timeframe field."""
        form.set_config({"timeframe": "4h"})
        assert form._timeframe_combo.currentText() == "4h"

    def test_set_config_timerange(self, form):
        """set_config populates the timerange field."""
        form.set_config({"timerange": "20220101-20221231"})
        assert form._timerange_edit.text() == "20220101-20221231"

    def test_set_config_pairs(self, form):
        """set_config populates the pairs list."""
        form.set_config({"pairs": ["BTC/USDT", "SOL/USDT"]})
        assert form.get_config()["pairs"] == ["BTC/USDT", "SOL/USDT"]

    def test_set_config_full_round_trip(self, form):
        """set_config followed by get_config returns the same values."""
        cfg = {
            "strategy": "RSIStrategy",
            "timeframe": "15m",
            "timerange": "20230601-20230901",
            "pairs": ["ETH/USDT", "BNB/USDT"],
        }
        form.set_config(cfg)
        result = form.get_config()
        assert result["strategy"] == cfg["strategy"]
        assert result["timeframe"] == cfg["timeframe"]
        assert result["timerange"] == cfg["timerange"]
        assert sorted(result["pairs"]) == sorted(cfg["pairs"])

    def test_set_config_partial_does_not_clear_other_fields(self, form):
        """set_config with partial dict does not reset unmentioned fields."""
        form.set_config({"timeframe": "1d"})
        form.set_config({"strategy": "MyStrat"})
        # timeframe should still be 1d
        assert form._timeframe_combo.currentText() == "1d"

    def test_set_config_known_timeframe_accepted(self, form):
        """set_config with a known timeframe string is accepted."""
        form.set_config({"timeframe": "1d"})
        assert form._timeframe_combo.currentText() == "1d"


# ---------------------------------------------------------------------------
# config_changed signal tests
# ---------------------------------------------------------------------------


class TestConfigChangedSignal:
    """Verify config_changed signal fires on field changes."""

    def test_signal_fires_on_strategy_change(self, qtbot, form):
        """config_changed emitted when strategy text changes."""
        with qtbot.waitSignal(form.config_changed, timeout=1000):
            form._strategy_combo.setCurrentText("NewStrategy")

    def test_signal_fires_on_timeframe_change(self, qtbot, form):
        """config_changed emitted when timeframe changes."""
        with qtbot.waitSignal(form.config_changed, timeout=1000):
            form._timeframe_combo.setCurrentText("1h")

    def test_signal_fires_on_timerange_change(self, qtbot, form):
        """config_changed emitted when timerange text changes."""
        with qtbot.waitSignal(form.config_changed, timeout=1000):
            form._timerange_edit.setText("20230101-20231231")

    def test_signal_payload_is_dict(self, qtbot, form):
        """config_changed payload is a dict."""
        received = []
        form.config_changed.connect(received.append)
        form._strategy_combo.setCurrentText("AnyStrategy")
        assert len(received) >= 1
        assert isinstance(received[-1], dict)

    def test_signal_not_fired_during_set_config(self, qtbot, form):
        """set_config does not emit config_changed (signals are blocked)."""
        received = []
        form.config_changed.connect(received.append)
        form.set_config({"strategy": "Silent", "timeframe": "1h"})
        # set_config blocks signals — no emission expected
        assert len(received) == 0


# ---------------------------------------------------------------------------
# Inline validation tests
# ---------------------------------------------------------------------------


class TestInlineValidation:
    """Verify inline validation rejects empty required fields."""

    def test_empty_strategy_is_invalid(self, form):
        """is_valid returns False when strategy is empty."""
        form._strategy_combo.setCurrentText("")
        assert form.is_valid() is False

    def test_non_empty_strategy_is_valid(self, form):
        """is_valid returns True when strategy is non-empty."""
        form._strategy_combo.setCurrentText("SomeStrategy")
        # Also need valid timeframe (default 5m is fine) and empty timerange is ok
        assert form.is_valid() is True

    def test_invalid_timerange_format_is_invalid(self, form):
        """is_valid returns False for a malformed timerange."""
        form._strategy_combo.setCurrentText("S")
        form._timerange_edit.setText("not-a-date")
        assert form.is_valid() is False

    def test_valid_timerange_format_passes(self, form):
        """is_valid returns True for a correctly formatted timerange."""
        form._strategy_combo.setCurrentText("S")
        form._timerange_edit.setText("20230101-20231231")
        assert form.is_valid() is True

    def test_open_ended_timerange_start_passes(self, form):
        """Open-ended timerange '20230101-' is valid."""
        form._strategy_combo.setCurrentText("S")
        form._timerange_edit.setText("20230101-")
        assert form.is_valid() is True

    def test_open_ended_timerange_end_passes(self, form):
        """Open-ended timerange '-20231231' is valid."""
        form._strategy_combo.setCurrentText("S")
        form._timerange_edit.setText("-20231231")
        assert form.is_valid() is True

    def test_empty_timerange_is_valid(self, form):
        """Empty timerange is valid (optional field)."""
        form._strategy_combo.setCurrentText("S")
        form._timerange_edit.setText("")
        assert form.is_valid() is True

    def test_strategy_error_label_shown_when_empty(self, form):
        """Strategy error label is visible when strategy is empty."""
        form._strategy_combo.setCurrentText("")
        form.is_valid()
        assert form._strategy_error.isVisible()

    def test_strategy_error_label_hidden_when_filled(self, form):
        """Strategy error label is hidden when strategy is non-empty."""
        form._strategy_combo.setCurrentText("MyStrat")
        form.is_valid()
        assert not form._strategy_error.isVisible()

    def test_no_strategy_field_always_valid(self, form_no_strategy):
        """Form with show_strategy=False is valid without a strategy value."""
        assert form_no_strategy.is_valid() is True
