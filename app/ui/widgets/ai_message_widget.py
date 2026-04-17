"""Message bubble widgets for the AI Chat panel."""

import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.core.utils.app_logger import get_logger

_log = get_logger("ui.ai_message_widget")


class UserMessageWidget(QWidget):
    """Right-aligned user message bubble."""

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 4, 8, 4)
        label = QLabel(text)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignRight)
        label.setStyleSheet(
            "background-color: #0e639c;"
            "color: #ffffff;"
            "border-radius: 10px;"
            "padding: 8px 12px;"
            "font-size: 13px;"
        )
        layout.addWidget(label)


class AssistantMessageWidget(QWidget):
    """Left-aligned assistant message bubble with incremental token support."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 60, 4)
        self._label = QLabel("")
        self._label.setWordWrap(True)
        self._label.setAlignment(Qt.AlignLeft)
        self._label.setStyleSheet(
            "background-color: #2d2d2d;"
            "color: #d4d4d4;"
            "border-radius: 10px;"
            "padding: 8px 12px;"
            "font-size: 13px;"
            "border: 1px solid #3c3c3c;"
        )
        self._label.setTextFormat(Qt.RichText)
        layout.addWidget(self._label)
        self._text = ""

    def append_token(self, delta: str) -> None:
        """Append a streaming token to the message.

        Args:
            delta: The incremental text to append.
        """
        self._text += delta
        self._label.setText(self._render(self._text))

    def set_text(self, text: str) -> None:
        """Set the full message text.

        Args:
            text: The complete message text to display.
        """
        self._text = text
        self._label.setText(self._render(text))

    def _render(self, text: str) -> str:
        """Render text with basic fenced code block support.

        Args:
            text: Raw text possibly containing fenced code blocks.

        Returns:
            HTML string suitable for QLabel with RichText format.
        """
        # Replace fenced code blocks with monospace styled pre blocks
        text = re.sub(
            r"```(?:\w+)?\n?(.*?)```",
            r'<pre style="background:#2d2d2d;color:#f8f8f2;padding:8px;'
            r'border-radius:4px;font-family:monospace;">\1</pre>',
            text,
            flags=re.DOTALL,
        )
        # Preserve newlines outside code blocks
        return text.replace("\n", "<br>")
