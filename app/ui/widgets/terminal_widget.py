"""Live terminal output widget with ANSI color support."""
from __future__ import annotations
import re
from PySide6.QtWidgets import QPlainTextEdit, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QTextCursor, QFont, QColor, QTextCharFormat
from app.ui import theme

_ANSI_RE = re.compile(r'\x1b\[([0-9;]*)m')

_ANSI_COLORS = {
    '30': '#4a5568', '31': theme.RED, '32': theme.GREEN,
    '33': theme.YELLOW, '34': theme.ACCENT, '35': theme.PURPLE,
    '36': '#38bdf8', '37': theme.TEXT_PRIMARY,
    '90': theme.TEXT_MUTED, '91': '#ff8080', '92': '#80ffb0',
    '93': '#ffe080', '94': '#80b0ff', '95': '#d0a0ff',
    '96': '#80e0ff', '97': '#ffffff',
}


class TerminalWidget(QWidget):
    """Scrolling terminal with ANSI color rendering and clear/copy controls."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar
        header = QWidget()
        header.setFixedHeight(36)
        header.setStyleSheet(f"background: {theme.BG_ELEVATED}; border-bottom: 1px solid {theme.BG_BORDER};")
        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(12, 0, 8, 0)

        title = QLabel("● Terminal")
        title.setStyleSheet(f"color: {theme.GREEN}; font-size: 12px; font-weight: 600; font-family: {theme.FONT_MONO};")
        hlay.addWidget(title)
        hlay.addStretch()

        self._status_lbl = QLabel("idle")
        self._status_lbl.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 11px;")
        hlay.addWidget(self._status_lbl)
        hlay.addSpacing(8)

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedSize(52, 24)
        clear_btn.setStyleSheet(f"""
            QPushButton {{ background: {theme.BG_BORDER}; color: {theme.TEXT_SECONDARY};
                           border: none; border-radius: 4px; font-size: 11px; }}
            QPushButton:hover {{ background: {theme.BG_ELEVATED}; color: {theme.TEXT_PRIMARY}; }}
        """)
        clear_btn.clicked.connect(self.clear)
        hlay.addWidget(clear_btn)

        layout.addWidget(header)

        # Text area
        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self._text.setMaximumBlockCount(5000)
        font = QFont(theme.FONT_MONO.split(",")[0].strip(), 11)
        self._text.setFont(font)
        self._text.setStyleSheet(f"""
            QPlainTextEdit {{
                background: {theme.BG_BASE};
                color: {theme.TEXT_PRIMARY};
                border: none;
                padding: 8px;
                selection-background-color: {theme.ACCENT_DIM};
            }}
        """)
        layout.addWidget(self._text)

    def append_output(self, text: str):
        """Append stdout text with ANSI color parsing."""
        self._append_colored(text, default_color=theme.TEXT_PRIMARY)
        self._scroll_to_bottom()

    def append_error(self, text: str):
        """Append stderr text in muted red."""
        self._append_colored(text, default_color="#cc8888")
        self._scroll_to_bottom()

    def append_info(self, text: str, color: str = theme.ACCENT):
        """Append an info/system message."""
        cursor = self._text.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.insertText(text, fmt)
        self._scroll_to_bottom()

    def set_status(self, status: str, color: str = theme.TEXT_MUTED):
        self._status_lbl.setText(status)
        self._status_lbl.setStyleSheet(f"color: {color}; font-size: 11px;")

    def clear(self):
        self._text.clear()

    def _append_colored(self, text: str, default_color: str):
        cursor = self._text.textCursor()
        cursor.movePosition(QTextCursor.End)
        parts = _ANSI_RE.split(text)
        current_color = default_color
        bold = False
        i = 0
        while i < len(parts):
            chunk = parts[i]
            if i % 2 == 0:
                # Text chunk
                if chunk:
                    fmt = QTextCharFormat()
                    fmt.setForeground(QColor(current_color))
                    if bold:
                        from PySide6.QtGui import QFont as _QFont
                        f = _QFont()
                        f.setBold(True)
                        fmt.setFont(f)
                    cursor.insertText(chunk, fmt)
            else:
                # ANSI code
                codes = chunk.split(';') if chunk else ['0']
                for code in codes:
                    if code in ('0', ''):
                        current_color = default_color
                        bold = False
                    elif code == '1':
                        bold = True
                    elif code in _ANSI_COLORS:
                        current_color = _ANSI_COLORS[code]
            i += 1

    def _scroll_to_bottom(self):
        sb = self._text.verticalScrollBar()
        sb.setValue(sb.maximum())
