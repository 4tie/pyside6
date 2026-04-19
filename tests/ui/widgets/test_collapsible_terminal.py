"""Unit tests for CollapsibleTerminal widget."""
import sys

import pytest
from PySide6.QtWidgets import QApplication

from app.ui.widgets.collapsible_terminal import CollapsibleTerminal
from app.ui.widgets.terminal_widget import TerminalWidget
from app.core.models.settings_models import TerminalPreferences


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
# Helper
# ---------------------------------------------------------------------------

@pytest.fixture()
def widget(qt_app):
    """Return a fresh CollapsibleTerminal for each test."""
    w = CollapsibleTerminal()
    yield w
    w.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_initial_state_collapsed(widget):
    """CollapsibleTerminal starts collapsed with the correct label."""
    assert widget.is_expanded() is False
    assert widget._toggle_btn.text() == CollapsibleTerminal.LABEL_COLLAPSED


def test_show_terminal_expands(widget):
    """show_terminal() sets is_expanded True and updates the label."""
    widget.show_terminal()
    assert widget.is_expanded() is True
    assert widget._toggle_btn.text() == CollapsibleTerminal.LABEL_EXPANDED


def test_hide_terminal_collapses(widget):
    """hide_terminal() sets is_expanded False and restores the collapsed label."""
    widget.show_terminal()
    widget.hide_terminal()
    assert widget.is_expanded() is False
    assert widget._toggle_btn.text() == CollapsibleTerminal.LABEL_COLLAPSED


def test_toggle_collapsed_to_expanded(widget):
    """toggle() on a collapsed terminal expands it."""
    assert widget.is_expanded() is False
    widget.toggle()
    assert widget.is_expanded() is True
    assert widget._toggle_btn.text() == CollapsibleTerminal.LABEL_EXPANDED


def test_toggle_expanded_to_collapsed(widget):
    """toggle() on an expanded terminal collapses it."""
    widget.show_terminal()
    widget.toggle()
    assert widget.is_expanded() is False
    assert widget._toggle_btn.text() == CollapsibleTerminal.LABEL_COLLAPSED


def test_terminal_property_returns_terminal_widget(widget):
    """The terminal property returns the inner TerminalWidget instance."""
    assert isinstance(widget.terminal, TerminalWidget)


def test_apply_preferences_does_not_raise(widget):
    """apply_preferences() delegates to the inner terminal without raising."""
    prefs = TerminalPreferences(font_family="Courier", font_size=12)
    widget.apply_preferences(prefs)  # should not raise


def test_inner_terminal_starts_hidden(widget):
    """The inner TerminalWidget is hidden on construction."""
    assert widget._terminal.isHidden() is True


def test_show_terminal_makes_inner_visible(widget):
    """show_terminal() makes the inner TerminalWidget explicitly visible (not hidden)."""
    widget.show_terminal()
    # isHidden() reflects the explicit setVisible() call regardless of parent visibility
    assert widget._terminal.isHidden() is False


def test_hide_terminal_hides_inner(widget):
    """hide_terminal() hides the inner TerminalWidget."""
    widget.show_terminal()
    widget.hide_terminal()
    assert widget._terminal.isHidden() is True
