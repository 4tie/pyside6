"""Unit tests for RollbackDialog."""
from __future__ import annotations
import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QDialogButtonBox

# ---------------------------------------------------------------------------
# QApplication singleton
# ---------------------------------------------------------------------------

_app = None


def _get_app():
    global _app
    if QApplication.instance() is None:
        _app = QApplication(sys.argv[:1])
    return QApplication.instance()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_dialog(has_params=True, has_config=True):
    _get_app()
    from app.ui.dialogs.rollback_dialog import RollbackDialog
    return RollbackDialog(
        strategy_name="TestStrategy",
        run_id="run_20240315T143022_abc123",
        has_params=has_params,
        has_config=has_config,
        params_path=Path("/user_data/strategies/TestStrategy.json"),
        config_path=Path("/user_data/config.json"),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_ok_button_disabled_when_both_unchecked():
    """OK button is disabled when both checkboxes are unchecked."""
    dlg = _make_dialog(has_params=True, has_config=True)
    dlg._params_cb.setChecked(False)
    dlg._config_cb.setChecked(False)
    ok_btn = dlg._button_box.button(QDialogButtonBox.Ok)
    assert ok_btn is not None
    assert not ok_btn.isEnabled(), "OK button should be disabled when both checkboxes are unchecked"
    dlg.close()


def test_ok_button_enabled_when_params_checked():
    """OK button is enabled when only the params checkbox is checked."""
    dlg = _make_dialog(has_params=True, has_config=True)
    dlg._params_cb.setChecked(True)
    dlg._config_cb.setChecked(False)
    ok_btn = dlg._button_box.button(QDialogButtonBox.Ok)
    assert ok_btn is not None
    assert ok_btn.isEnabled(), "OK button should be enabled when params checkbox is checked"
    dlg.close()


def test_ok_button_enabled_when_config_checked():
    """OK button is enabled when only the config checkbox is checked."""
    dlg = _make_dialog(has_params=True, has_config=True)
    dlg._params_cb.setChecked(False)
    dlg._config_cb.setChecked(True)
    ok_btn = dlg._button_box.button(QDialogButtonBox.Ok)
    assert ok_btn is not None
    assert ok_btn.isEnabled(), "OK button should be enabled when config checkbox is checked"
    dlg.close()


def test_restore_params_property_reflects_checkbox():
    """restore_params property reflects the params checkbox state."""
    dlg = _make_dialog(has_params=True, has_config=True)

    dlg._params_cb.setChecked(True)
    assert dlg.restore_params is True, "restore_params should be True when checkbox is checked"

    dlg._params_cb.setChecked(False)
    assert dlg.restore_params is False, "restore_params should be False when checkbox is unchecked"

    dlg.close()


def test_restore_config_property_reflects_checkbox():
    """restore_config property reflects the config checkbox state."""
    dlg = _make_dialog(has_params=True, has_config=True)

    dlg._config_cb.setChecked(True)
    assert dlg.restore_config is True, "restore_config should be True when checkbox is checked"

    dlg._config_cb.setChecked(False)
    assert dlg.restore_config is False, "restore_config should be False when checkbox is unchecked"

    dlg.close()


def test_params_checkbox_checked_by_default_when_has_params_true():
    """Params checkbox is checked by default when has_params=True."""
    dlg = _make_dialog(has_params=True, has_config=False)
    assert dlg._params_cb.isChecked(), (
        "Params checkbox should be checked by default when has_params=True"
    )
    dlg.close()


def test_config_checkbox_unchecked_by_default_when_has_config_true():
    """Config checkbox is NOT checked by default even when has_config=True."""
    dlg = _make_dialog(has_params=True, has_config=True)
    assert not dlg._config_cb.isChecked(), (
        "Config checkbox should be unchecked by default even when has_config=True"
    )
    dlg.close()


def test_params_checkbox_disabled_when_has_params_false():
    """Params checkbox is disabled when has_params=False."""
    dlg = _make_dialog(has_params=False, has_config=True)
    assert not dlg._params_cb.isEnabled(), (
        "Params checkbox should be disabled when has_params=False"
    )
    dlg.close()


def test_config_checkbox_disabled_when_has_config_false():
    """Config checkbox is disabled when has_config=False."""
    dlg = _make_dialog(has_params=True, has_config=False)
    assert not dlg._config_cb.isEnabled(), (
        "Config checkbox should be disabled when has_config=False"
    )
    dlg.close()


def test_validation_message_visible_when_both_unchecked():
    """Validation message is not hidden when both checkboxes are unchecked.

    Uses isHidden() because isVisible() returns False for unshown dialogs
    regardless of the explicit visibility flag.
    """
    dlg = _make_dialog(has_params=True, has_config=True)
    dlg._params_cb.setChecked(False)
    dlg._config_cb.setChecked(False)
    assert not dlg._validation_lbl.isHidden(), (
        "Validation message should not be hidden when both checkboxes are unchecked"
    )
    dlg.close()


def test_validation_message_hidden_when_at_least_one_checked():
    """Validation message is hidden when at least one checkbox is checked."""
    dlg = _make_dialog(has_params=True, has_config=True)
    dlg._params_cb.setChecked(True)
    assert dlg._validation_lbl.isHidden(), (
        "Validation message should be hidden when params checkbox is checked"
    )
    dlg.close()


def test_window_title_is_confirm_rollback():
    """Dialog window title is 'Confirm Rollback'."""
    dlg = _make_dialog()
    assert dlg.windowTitle() == "Confirm Rollback"
    dlg.close()


def test_minimum_width_is_480():
    """Dialog minimum width is 480."""
    dlg = _make_dialog()
    assert dlg.minimumWidth() == 480
    dlg.close()
