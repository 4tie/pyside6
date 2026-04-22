"""Unit tests for RunConfigForm widget.

Tests cover: get_config dict shape, set_config round-trip, config_changed signal,
and validate() error reporting.

Requires a QApplication instance — provided by pytest-qt's qtbot fixture.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure a QApplication exists before importing any Qt widgets.
# pytest-qt creates one automatically when qtbot is used; we also guard here
# for environments where pytest-qt may not be installed.
try:
    from pytestqt.plugin import QtBot  # noqa: F401 — just checking availability
    _HAS_PYTEST_QT = True
except ImportError:
    _HAS_PYTEST_QT = False


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_settings_state(tmp_path: Path):
    """Return a SettingsState with a minimal AppSettings pointing at tmp_path."""
    from app.app_state.settings_state import SettingsState
    from app.core.models.settings_models import AppSettings

    state = SettingsState()
    settings = AppSettings(user_data_path=str(tmp_path))
    state.current_settings = settings
    return state


def _make_strategies_dir(tmp_path: Path, names: list[str]) -> None:
    """Create a strategies/ directory under tmp_path with stub .py files."""
    strategies_dir = tmp_path / "strategies"
    strategies_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        (strategies_dir / f"{name}.py").write_text(f"# {name}", encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRunConfigFormGetConfig:
    """Tests for get_config() return shape."""

    def test_get_config_returns_dict(self, qtbot):
        """After construction, get_config() returns a dict with the four required keys."""
        from app.ui.widgets.run_config_form import RunConfigForm

        tmp = Path(tempfile.mkdtemp())
        state = _make_settings_state(tmp)
        form = RunConfigForm(settings_state=state)
        qtbot.addWidget(form)

        cfg = form.get_config()

        assert isinstance(cfg, dict)
        assert "strategy" in cfg
        assert "timeframe" in cfg
        assert "timerange" in cfg
        assert "pairs" in cfg

    def test_get_config_pairs_is_list(self, qtbot):
        """get_config()['pairs'] is always a list."""
        from app.ui.widgets.run_config_form import RunConfigForm

        tmp = Path(tempfile.mkdtemp())
        state = _make_settings_state(tmp)
        form = RunConfigForm(settings_state=state)
        qtbot.addWidget(form)

        assert isinstance(form.get_config()["pairs"], list)


class TestRunConfigFormSetConfig:
    """Tests for set_config() round-trip."""

    def test_set_config_populates_timeframe(self, qtbot):
        """set_config with timeframe='4h' is reflected in get_config."""
        from app.ui.widgets.run_config_form import RunConfigForm

        tmp = Path(tempfile.mkdtemp())
        state = _make_settings_state(tmp)
        form = RunConfigForm(settings_state=state)
        qtbot.addWidget(form)

        form.set_config({"timeframe": "4h"})

        assert form.get_config()["timeframe"] == "4h"

    def test_set_config_populates_timerange(self, qtbot):
        """set_config with timerange='20240101-20241231' is reflected in get_config."""
        from app.ui.widgets.run_config_form import RunConfigForm

        tmp = Path(tempfile.mkdtemp())
        state = _make_settings_state(tmp)
        form = RunConfigForm(settings_state=state)
        qtbot.addWidget(form)

        form.set_config({"timerange": "20240101-20241231"})

        assert form.get_config()["timerange"] == "20240101-20241231"

    def test_set_config_populates_pairs(self, qtbot):
        """set_config with pairs=['BTC/USDT'] is reflected in get_config."""
        from app.ui.widgets.run_config_form import RunConfigForm

        tmp = Path(tempfile.mkdtemp())
        state = _make_settings_state(tmp)
        form = RunConfigForm(settings_state=state)
        qtbot.addWidget(form)

        form.set_config({"pairs": ["BTC/USDT"]})

        assert form.get_config()["pairs"] == ["BTC/USDT"]

    def test_set_config_full_round_trip(self, qtbot):
        """Full set_config round-trip: all fields survive get_config."""
        from app.ui.widgets.run_config_form import RunConfigForm

        tmp = Path(tempfile.mkdtemp())
        _make_strategies_dir(tmp, ["MyStrategy"])
        state = _make_settings_state(tmp)
        form = RunConfigForm(settings_state=state)
        qtbot.addWidget(form)

        cfg_in = {
            "strategy": "MyStrategy",
            "timeframe": "4h",
            "timerange": "20240101-20241231",
            "pairs": ["BTC/USDT"],
        }
        form.set_config(cfg_in)
        cfg_out = form.get_config()

        assert cfg_out["timeframe"] == cfg_in["timeframe"]
        assert cfg_out["timerange"] == cfg_in["timerange"]
        assert cfg_out["pairs"] == cfg_in["pairs"]
        # strategy only matches if the file exists in the strategies dir
        assert cfg_out["strategy"] == cfg_in["strategy"]


class TestRunConfigFormSignal:
    """Tests for config_changed signal emission."""

    def test_config_changed_signal_fires_on_timeframe_change(self, qtbot):
        """Changing the timeframe combo emits config_changed."""
        from app.ui.widgets.run_config_form import RunConfigForm

        tmp = Path(tempfile.mkdtemp())
        state = _make_settings_state(tmp)
        form = RunConfigForm(settings_state=state)
        qtbot.addWidget(form)

        received: list[dict] = []
        form.config_changed.connect(received.append)

        # Change timeframe to something other than the default
        form._timeframe_combo.setCurrentIndex(5)  # "1h"

        assert len(received) >= 1
        assert "timeframe" in received[-1]

    def test_config_changed_signal_fires_on_timerange_change(self, qtbot):
        """Editing the timerange field emits config_changed."""
        from app.ui.widgets.run_config_form import RunConfigForm

        tmp = Path(tempfile.mkdtemp())
        state = _make_settings_state(tmp)
        form = RunConfigForm(settings_state=state)
        qtbot.addWidget(form)

        received: list[dict] = []
        form.config_changed.connect(received.append)

        form._timerange_edit.setText("20240101-20241231")

        assert len(received) >= 1


class TestRunConfigFormValidation:
    """Tests for validate() error reporting."""

    def test_validate_returns_errors_for_empty_strategy(self, qtbot):
        """When show_strategy=True and no strategy is selected, validate() returns errors."""
        from app.ui.widgets.run_config_form import RunConfigForm

        tmp = Path(tempfile.mkdtemp())
        state = _make_settings_state(tmp)
        # No strategies dir → combo will be empty
        form = RunConfigForm(settings_state=state, show_strategy=True)
        qtbot.addWidget(form)

        errors = form.validate()

        assert isinstance(errors, list)
        assert len(errors) > 0
        assert any("strategy" in e.lower() for e in errors)

    def test_validate_no_errors_when_strategy_hidden(self, qtbot):
        """When show_strategy=False, missing strategy does not produce an error."""
        from app.ui.widgets.run_config_form import RunConfigForm

        tmp = Path(tempfile.mkdtemp())
        state = _make_settings_state(tmp)
        form = RunConfigForm(
            settings_state=state,
            show_strategy=False,
            show_pairs=False,
        )
        qtbot.addWidget(form)

        errors = form.validate()

        assert not any("strategy" in e.lower() for e in errors)

    def test_validate_invalid_timerange_format(self, qtbot):
        """An invalid timerange string produces a validation error."""
        from app.ui.widgets.run_config_form import RunConfigForm

        tmp = Path(tempfile.mkdtemp())
        state = _make_settings_state(tmp)
        form = RunConfigForm(
            settings_state=state,
            show_strategy=False,
            show_pairs=False,
        )
        qtbot.addWidget(form)

        form._timerange_edit.setText("not-a-date")
        errors = form.validate()

        assert any("timerange" in e.lower() for e in errors)

    def test_validate_valid_timerange_no_error(self, qtbot):
        """A correctly formatted timerange produces no timerange error."""
        from app.ui.widgets.run_config_form import RunConfigForm

        tmp = Path(tempfile.mkdtemp())
        state = _make_settings_state(tmp)
        form = RunConfigForm(
            settings_state=state,
            show_strategy=False,
            show_pairs=False,
        )
        qtbot.addWidget(form)

        form._timerange_edit.setText("20240101-20241231")
        errors = form.validate()

        assert not any("timerange" in e.lower() for e in errors)
