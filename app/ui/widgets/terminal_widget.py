import re
from typing import Optional

from PySide6.QtCore import Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QLabel,
    QLineEdit, QApplication
)
from PySide6.QtGui import QFont, QTextCursor, QColor, QTextCharFormat

from app.core.models.command_models import format_command_string
from app.core.services.process_service import ProcessService
from app.core.models.settings_models import AppSettings, TerminalPreferences

# Table data rows start with box-drawing cell separator
_TABLE_ROW_RE = re.compile(r"^[│┃]")

# A cell that is purely a signed number (with optional trailing spaces/USDT/%/h/m/s)
_NUMBER_CELL_RE = re.compile(r"^\s*(-?\d+\.?\d*)\s*(%|USDT|h|m|s|:\d+:\d+)?\s*$")

_GREEN = QColor("#2ecc71")
_RED   = QColor("#e74c3c")


def _cell_color(cell: str) -> Optional[QColor]:
    """Return green/red if cell contains a signed number, else None."""
    m = _NUMBER_CELL_RE.match(cell)
    if m:
        try:
            return _GREEN if float(m.group(1)) >= 0 else _RED
        except ValueError:
            pass
    return None


def _colorize_line(line: str) -> list[tuple[str, Optional[QColor]]]:
    """Split a table data row into (text, color) segments by cell."""
    if not _TABLE_ROW_RE.match(line):
        return [(line, None)]

    # Split keeping the delimiters │ and ┃
    parts = re.split(r"([│┃])", line)
    segments: list[tuple[str, Optional[QColor]]] = []
    for part in parts:
        if part in ("│", "┃"):
            segments.append((part, None))
        else:
            segments.append((part, _cell_color(part)))
    return segments


class TerminalWidget(QWidget):
    """Terminal widget for command execution and output display."""

    process_started = Signal()
    process_finished = Signal(int)  # exit code
    output_received = Signal(str)   # stdout
    error_received = Signal(str)    # stderr
    _stdout_line = Signal(str)      # internal: marshal stdout to main thread
    _stderr_line = Signal(str)      # internal: marshal stderr to main thread
    _finished_code = Signal(int)    # internal: marshal exit code to main thread

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process_service = ProcessService()
        self._current_command: list[str] = []
        self.init_ui()
        self.apply_preferences(TerminalPreferences())
        self._stdout_line.connect(self._append_output)
        self._stderr_line.connect(self._append_error)
        self._finished_code.connect(self._on_process_finished)

    def init_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout()

        # Command input section
        command_layout = QHBoxLayout()
        command_layout.addWidget(QLabel("Command:"))

        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("Command will be displayed here...")
        self.command_input.setFont(QFont("Courier", 9))
        command_layout.addWidget(self.command_input)

        self.copy_button = QPushButton("Copy")
        self.copy_button.setMaximumWidth(60)
        self.copy_button.clicked.connect(self._on_copy_command)
        command_layout.addWidget(self.copy_button)

        layout.addLayout(command_layout)

        # Output display
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setFont(QFont("Courier", 10))
        layout.addWidget(QLabel("Output:"))
        layout.addWidget(self.output_text)

        # Control buttons
        button_layout = QHBoxLayout()

        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_output)
        button_layout.addWidget(self.clear_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_process)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.stop_button)

        # Status label
        self.status_label = QLabel("Ready")
        button_layout.addWidget(self.status_label)
        button_layout.addStretch()

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def run_command(
        self,
        command: list[str],
        working_directory: str = None,
        env: dict = None
    ):
        """Execute a command and stream output to the terminal."""
        self.clear_output()
        self.set_command_list(command)
        self.status_label.setText("Running...")
        self.stop_button.setEnabled(True)

        self.process_service.execute_command(
            command=command,
            working_directory=working_directory,
            env=env,
            on_output=self._stdout_line.emit,
            on_error=self._stderr_line.emit,
            on_finished=self._finished_code.emit,
        )
        self.process_started.emit()

    def run_freqtrade_command(
        self,
        command: list[str],
        working_directory: str = None,
        env: dict = None
    ):
        """Run a freqtrade command - command should be pre-built by services."""
        self.run_command(command, working_directory=working_directory, env=env)

    def stop_process(self):
        """Stop the running process."""
        self.process_service.stop_process()
        self.status_label.setText("Stopped")
        self.stop_button.setEnabled(False)

    def clear_output(self):
        """Clear the output display."""
        self.output_text.clear()

    def append_output(self, text: str):
        """Append text to output (stdout) - public method."""
        self._append_output(text)

    def append_error(self, text: str):
        """Append text to output (stderr) - public method."""
        self._append_error(text)

    def set_command(self, command_str: str):
        """Update the command input field with a new command string."""
        self._current_command = []
        self.command_input.setText(command_str)

    def set_command_list(self, command: list[str]):
        """Update the command input field from a tokenized command."""
        self._current_command = list(command)
        self.command_input.setText(format_command_string(command))

    def get_command(self) -> str:
        """Get the current command from the input field."""
        return self.command_input.text()

    def get_command_list(self) -> list[str]:
        """Get the current tokenized command if available."""
        return list(self._current_command)

    def _on_copy_command(self):
        """Copy command to clipboard and show tooltip."""
        command = self.get_command()
        if command:
            clipboard = QApplication.clipboard()
            clipboard.setText(command)
            self.copy_button.setToolTip("Copied!")
            QTimer.singleShot(2000, lambda: self.copy_button.setToolTip(""))

    def _default_fmt(self) -> QTextCharFormat:
        """Return a char format using the current default text color."""
        fmt = QTextCharFormat()
        fmt.setForeground(self.output_text.palette().text().color())
        return fmt

    def _append_output(self, text: str):
        """Append stdout text, colorizing numeric cells in table rows."""
        cursor = self.output_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        default_fmt = self._default_fmt()

        for line in re.split(r"(\n)", text):
            if line == "\n":
                cursor.insertText("\n", default_fmt)
                continue
            if not line:
                continue
            for segment, color in _colorize_line(line):
                if color is not None:
                    fmt = QTextCharFormat()
                    fmt.setForeground(color)
                    cursor.insertText(segment, fmt)
                else:
                    cursor.insertText(segment, default_fmt)

        self.output_text.setTextCursor(cursor)
        self._scroll_to_bottom()
        self.output_received.emit(text)

    def _append_error(self, text: str):
        """Append text to output (stderr) - in red."""
        cursor = self.output_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#e74c3c"))
        cursor.insertText(text, fmt)
        self.output_text.setTextCursor(cursor)
        self._scroll_to_bottom()
        self.error_received.emit(text)

    def _scroll_to_bottom(self):
        """Scroll output to bottom."""
        cursor = self.output_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.output_text.setTextCursor(cursor)

    def _on_process_finished(self, exit_code: int):
        """Handle process completion."""
        if exit_code == 0:
            self.status_label.setText("Completed (exit 0)")
        else:
            self.status_label.setText(f"Completed (exit {exit_code})")
        self.stop_button.setEnabled(False)
        self.process_finished.emit(exit_code)

    def get_output(self) -> str:
        """Return all plain text currently in the output display."""
        return self.output_text.toPlainText()

    def get_full_output(self) -> tuple:
        """Get full captured output (stdout, stderr)."""
        return self.process_service.get_full_output()

    def apply_preferences(self, prefs: TerminalPreferences):
        """Apply terminal appearance preferences."""
        font = QFont(prefs.font_family, prefs.font_size)
        self.output_text.setFont(font)
        self.command_input.setFont(QFont(prefs.font_family, max(prefs.font_size - 1, 7)))
        self.output_text.setStyleSheet(
            f"background-color: {prefs.background_color}; color: {prefs.text_color};"
        )

    def is_running(self) -> bool:
        """Check if a process is running."""
        return self.process_service.is_running()
