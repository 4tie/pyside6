"""Collapsible tool call card widget for the AI Chat panel."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget


class ToolCard(QWidget):
    """Collapsible widget displaying a tool call's name, arguments, and result.

    The tool name is always visible in the header. Arguments and result are
    shown in a collapsible body toggled by a QToolButton.

    Args:
        tool_name: Name of the tool that was called.
        arguments: Dictionary of input arguments passed to the tool.
        result: Result string returned by the tool.
        error: Error string if the tool call failed.
        parent: Optional parent widget.
    """

    def __init__(
        self,
        tool_name: str,
        arguments: dict,
        result: str = "",
        error: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.setStyleSheet("border: 1px solid #ddd; border-radius: 4px; padding: 4px;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # --- Header ---
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(4, 4, 4, 4)

        name_label = QLabel(f"🔧 {tool_name}")
        name_label.setStyleSheet("border: none;")

        self._toggle_btn = QToolButton()
        self._toggle_btn.setText("▼")
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.setStyleSheet("border: none;")

        header_layout.addWidget(name_label)
        header_layout.addStretch()
        header_layout.addWidget(self._toggle_btn)

        # --- Body ---
        self._body = QWidget()
        self._body.setStyleSheet("border: none;")
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(4, 4, 4, 4)
        body_layout.setSpacing(2)

        args_title = QLabel("Arguments:")
        args_title.setStyleSheet("border: none; font-weight: bold;")
        args_value = QLabel(str(arguments))
        args_value.setWordWrap(True)
        args_value.setStyleSheet("border: none; font-family: monospace;")
        args_value.setTextInteractionFlags(Qt.TextSelectableByMouse)

        result_title = QLabel("Result:")
        result_title.setStyleSheet("border: none; font-weight: bold;")
        result_value = QLabel(result or error)
        result_value.setWordWrap(True)
        result_value.setStyleSheet("border: none; font-family: monospace;")
        result_value.setTextInteractionFlags(Qt.TextSelectableByMouse)

        body_layout.addWidget(args_title)
        body_layout.addWidget(args_value)
        body_layout.addWidget(result_title)
        body_layout.addWidget(result_value)

        self._body.setVisible(False)

        outer.addWidget(header)
        outer.addWidget(self._body)

        self._toggle_btn.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked: bool) -> None:
        """Show or hide the body based on toggle state.

        Args:
            checked: True when expanded, False when collapsed.
        """
        self._toggle_btn.setText("▲" if checked else "▼")
        self._body.setVisible(checked)
