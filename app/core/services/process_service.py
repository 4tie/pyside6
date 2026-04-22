import os
import subprocess
import threading
from pathlib import Path
from typing import Callable, Optional, Sequence

from app.core.utils.app_logger import get_logger

_log = get_logger("process")


class ProcessService:
    """Manages process execution with streaming output support (framework-agnostic)."""

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.output_buffer_stdout = ""
        self.output_buffer_stderr = ""
        self._output_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def execute_command(
        self,
        command: Sequence[str],
        on_output: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_finished: Optional[Callable[[int], None]] = None,
        working_directory: Optional[str] = None,
        env: Optional[dict] = None
    ) -> subprocess.Popen:
        """Execute a command and stream output.

        Args:
            command: Tokenized command sequence (e.g., ["python", "-m", "pytest"])
            on_output: Callback for stdout chunks
            on_error: Callback for stderr chunks
            on_finished: Callback with exit code when process completes
            working_directory: Directory to run command in
            env: Environment variables dict

        Returns:
            subprocess.Popen instance

        Raises:
            TypeError: If command is a string or empty
        """
        if isinstance(command, str) or not command:
            raise TypeError("command must be a non-empty tokenized sequence, not a string")

        command_parts = [str(part) for part in command]

        self.output_buffer_stdout = ""
        self.output_buffer_stderr = ""
        self._stop_event.clear()

        # Prepare environment
        process_env = dict(env) if env else None

        # Start process
        self.process = subprocess.Popen(
            command_parts,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            cwd=working_directory,
            env=process_env,
            text=True,
            bufsize=1,  # Line buffered
        )

        _log.info(
            "Process started | cmd=%s | cwd=%s | pid=%s",
            " ".join(command_parts),
            working_directory or "(default)",
            self.process.pid,
        )

        # Start output streaming thread
        if on_output or on_error:
            self._output_thread = threading.Thread(
                target=self._stream_output,
                args=(on_output, on_error, on_finished),
                daemon=True,
            )
            self._output_thread.start()
        elif on_finished:
            # If no streaming needed, just wait and call on_finished
            self._output_thread = threading.Thread(
                target=self._wait_for_completion,
                args=(on_finished,),
                daemon=True,
            )
            self._output_thread.start()

        return self.process

    def _stream_output(
        self,
        on_output: Optional[Callable[[str], None]],
        on_error: Optional[Callable[[str], None]],
        on_finished: Optional[Callable[[int], None]],
    ):
        """Stream output from process in background thread."""
        if not self.process:
            return

        # Stream stdout
        if on_output and self.process.stdout:
            for line in iter(self.process.stdout.readline, ""):
                if self._stop_event.is_set():
                    break
                if line:
                    self.output_buffer_stdout += line
                    _log.debug("stdout chunk: %d bytes", len(line))
                    on_output(line)

        # Stream stderr
        if on_error and self.process.stderr:
            for line in iter(self.process.stderr.readline, ""):
                if self._stop_event.is_set():
                    break
                if line:
                    self.output_buffer_stderr += line
                    _log.debug("stderr chunk: %d bytes", len(line))
                    on_error(line)

        # Wait for process completion
        if on_finished:
            self.process.wait()
            on_finished(self.process.returncode)

    def _wait_for_completion(self, on_finished: Callable[[int], None]):
        """Wait for process completion without streaming."""
        if not self.process:
            return
        self.process.wait()
        on_finished(self.process.returncode)

    def stop_process(self):
        """Stop the running process."""
        if self.process and self.process.poll() is None:
            _log.info("Terminating process (pid=%s)", self.process.pid)
            self._stop_event.set()
            self.process.terminate()
            try:
                self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                _log.warning("Process did not terminate gracefully — killing (pid=%s)", self.process.pid)
                self.process.kill()
                self.process.wait()

    def get_full_output(self) -> tuple[str, str]:
        """Get full captured output."""
        return self.output_buffer_stdout, self.output_buffer_stderr

    @staticmethod
    def build_environment(venv_path: str, base_env: Optional[dict] = None) -> dict:
        """Build environment dict with venv activated.

        Args:
            venv_path: Path to virtual environment
            base_env: Base environment dict (defaults to os.environ)

        Returns:
            Environment dict with VIRTUAL_ENV set and PATH updated
        """
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
        return self.process is not None and self.process.poll() is None
