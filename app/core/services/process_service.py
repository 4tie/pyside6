import os
from pathlib import Path
from typing import Optional, Callable, List

from PySide6.QtCore import QProcess, QProcessEnvironment

from app.core.utils.app_logger import get_logger

_log = get_logger("process")


class ProcessService:
    """Manages process execution with streaming output support."""

    def __init__(self):
        self.process: Optional[QProcess] = None
        self.output_buffer_stdout = ""
        self.output_buffer_stderr = ""

    def execute_command(
        self,
        command: List[str],
        on_output: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_finished: Optional[Callable[[int], None]] = None,
        working_directory: Optional[str] = None,
        env: Optional[dict] = None
    ) -> QProcess:
        """Execute a command and stream output."""
        self.process = QProcess()
        self.output_buffer_stdout = ""
        self.output_buffer_stderr = ""

        # Set working directory if provided
        if working_directory:
            self.process.setWorkingDirectory(working_directory)

        # Set environment variables
        if env:
            q_env = QProcessEnvironment()
            for key, value in env.items():
                q_env.insert(key, str(value))
            self.process.setProcessEnvironment(q_env)

        # Connect signals
        if on_output:
            self.process.readyReadStandardOutput.connect(
                lambda: self._handle_stdout(on_output)
            )

        if on_error:
            self.process.readyReadStandardError.connect(
                lambda: self._handle_stderr(on_error)
            )

        if on_finished:
            self.process.finished.connect(on_finished)

        # Start the process
        self.process.start(command[0], command[1:])
        _log.info("Process started | cmd=%s | cwd=%s", " ".join(command), working_directory or "(default)")
        return self.process

    def _handle_stdout(self, callback: Callable[[str], None]):
        """Handle stdout data."""
        if self.process:
            data = self.process.readAllStandardOutput().data().decode("utf-8", errors="replace")
            self.output_buffer_stdout += data
            _log.debug("stdout chunk: %d bytes", len(data))
            callback(data)

    def _handle_stderr(self, callback: Callable[[str], None]):
        """Handle stderr data."""
        if self.process:
            data = self.process.readAllStandardError().data().decode("utf-8", errors="replace")
            self.output_buffer_stderr += data
            _log.debug("stderr chunk: %d bytes", len(data))
            callback(data)

    def stop_process(self):
        """Stop the running process."""
        if self.process and self.process.state() == QProcess.Running:
            _log.info("Terminating process (pid=%s)", self.process.processId())
            self.process.terminate()
            if not self.process.waitForFinished(1000):
                _log.warning("Process did not terminate gracefully — killing (pid=%s)",
                             self.process.processId())
                self.process.kill()

    def get_full_output(self) -> tuple[str, str]:
        """Get full captured output."""
        return self.output_buffer_stdout, self.output_buffer_stderr

    @staticmethod
    def build_environment(venv_path: str, base_env: Optional[dict] = None) -> dict:
        """Build environment dict with venv activated."""
        env = dict(base_env or os.environ)
        venv = Path(venv_path)

        if os.name == "nt":
            bin_dir = venv / "Scripts"
        else:
            bin_dir = venv / "bin"

        env["VIRTUAL_ENV"] = str(venv)
        env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")

        return env

    def is_running(self) -> bool:
        """Check if process is still running."""
        return self.process is not None and self.process.state() == QProcess.Running
