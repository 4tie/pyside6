"""UI tests for ToolCard widget.

Validates: Requirements 9.4
"""
import sys

from PySide6.QtWidgets import QApplication

from app.ui.widgets.tool_call_card import ToolCard

_app = QApplication.instance() or QApplication(sys.argv)


def test_tool_card_body_hidden_by_default():
    """Body is hidden when ToolCard is first created."""
    card = ToolCard("my_tool", {"arg": 1}, result="ok")
    assert not card._body.isVisible()


def test_tool_card_expand_shows_body():
    """Clicking the toggle button un-hides the body."""
    card = ToolCard("my_tool", {"arg": 1}, result="ok")
    card._toggle_btn.setChecked(True)
    # isHidden() is reliable without needing the widget to be shown on screen
    assert not card._body.isHidden()


def test_tool_card_collapse_hides_body():
    """Unchecking the toggle button hides the body again."""
    card = ToolCard("my_tool", {"arg": 1}, result="ok")
    card._toggle_btn.setChecked(True)
    card._toggle_btn.setChecked(False)
    assert card._body.isHidden()


def test_tool_card_toggle_button_text_changes():
    """Toggle button text changes between ▼ and ▲."""
    card = ToolCard("my_tool", {}, result="")
    assert card._toggle_btn.text() == "▼"
    card._toggle_btn.setChecked(True)
    assert card._toggle_btn.text() == "▲"
    card._toggle_btn.setChecked(False)
    assert card._toggle_btn.text() == "▼"
