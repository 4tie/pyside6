from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QLabel,
    QLineEdit, QApplication
)
from PySide6.QtGui import QFont, QTextCursor

from app.core.services.process_service import ProcessService
from app.core.freqtrade.command_runner import CommandRunner
from app.core.models.settings_models import AppSettings


class TerminalWidget(QWidget):
    """Terminal widget for command execution and output display."""

    process_started = Signal()
    process_finished = Signal(int)  # exit code
    output_received = Signal(str)   # stdout
    error_received = Signal(str)    # stderr

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process_service = ProcessService()
        self.init_ui()

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
        command: list,
        working_directory: str = None,
        env: dict = None
    ):
        """Execute a command and stream output to the terminal."""
        self.clear_output()
        self.status_label.setText("Running...")
        self.stop_button.setEnabled(True)

        self.process_service.execute_command(
            command=command,
            working_directory=working_directory,
            env=env,
            on_output=self._append_output,
            on_error=self._append_error,
            on_finished=self._on_process_finished
        )
        self.process_started.emit()

    def run_freqtrade_command(
        self,
        *args: str,
        settings: AppSettings,
        working_directory: str = None
    ):
        """Run a freqtrade command."""
        try:
            command = CommandRunner.build_freqtrade_command(*args, settings=settings)
            env = ProcessService.build_environment(
                settings.venv_path or settings.python_executable,
                base_env=None
            ) if settings.venv_path else None
            self.run_command(command, working_directory=working_directory, env=env)
        except Exception as e:
            self._append_error(f"Error building command: {str(e)}\n")

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
        self.command_input.setText(command_str)

    def get_command(self) -> str:
        """Get the current command from the input field."""
        return self.command_input.text()

    def _on_copy_command(self):
        """Copy command to clipboard and show tooltip."""
        command = self.get_command()
        if command:
            clipboard = QApplication.clipboard()
            clipboard.setText(command)
            self.copy_button.setToolTip("Copied!")
            QTimer.singleShot(2000, lambda: self.copy_button.setToolTip(""))

    def _append_output(self, text: str):
        """Append text to output (stdout)."""
        self.output_text.insertPlainText(text)
        self._scroll_to_bottom()
        self.output_received.emit(text)

    def _append_error(self, text: str):
        """Append text to output (stderr) - in red."""
        cursor = self.output_text.textCursor()
        cursor.movePosition(QTextCursor.End)

        # Format error text in red
        fmt = cursor.charFormat()
        fmt.setForeground(Qt.red)
        cursor.setCharFormat(fmt)
        cursor.insertText(text)

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

    def get_full_output(self) -> tuple:
        """Get full captured output (stdout, stderr)."""
        return self.process_service.get_full_output()

    def is_running(self) -> bool:
        """Check if a process is running."""
        return self.process_service.is_running()
