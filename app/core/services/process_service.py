"""ProcessService — backward-compatibility shim over ProcessRunManager.

Preserves the original public API (execute_command, stop_process,
get_full_output, is_running, build_environment) while delegating all
subprocess management to ProcessRunManager internally.

No PySide6 imports are permitted in this module.
"""

import os
import queue
import threading
from pathlib import Path
from typing import Callable, Optional, Sequence

from app.core.models.command_models import RunCommand
from app.core.models.run_models import ProcessRun, RunStatus
from app.core.services.process_run_manager import ProcessRunManager
from app.core.utils.app_logger import get_logger

_log = get_logger("process")


class _ShimAdapter:
    """Lightweight adapter that drains a ProcessRun's queues on daemon threads
    and calls the provided callbacks directly.

    This is the non-Qt equivalent of ProcessRunAdapter — it does NOT import
    PySide6 and calls callbacks from reader threads rather than via Qt signals.

    Args:
        run: The ProcessRun whose queues will be drained.
        on_output: Optional callback invoked with each stdout line.
        on_error: Optional callback invoked with each stderr line.
        on_finished: Optional callback invoked with the exit code when the run
            reaches a terminal state.
    """

    def __init__(
        self,
        run: ProcessRun,
        on_output: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_finished: Optional[Callable[[int], None]] = None,
    ) -> None:
        self._run = run
        self._on_output = on_output
        self._on_error = on_error
        self._on_finished = on_finished

    def start(self) -> None:
        """Start daemon threads that drain stdout_queue, stderr_queue, and
        watch for terminal status to fire on_finished."""
        t_out = threading.Thread(
            target=self._drain_stdout,
            daemon=True,
            name=f"shim-{self._run.run_id[:8]}-stdout",
        )
        t_err = threading.Thread(
            target=self._drain_stderr,
            daemon=True,
            name=f"shim-{self._run.run_id[:8]}-stderr",
        )
        t_watch = threading.Thread(
            target=self._watch_finished,
            args=(t_out, t_err),
            daemon=True,
            name=f"shim-{self._run.run_id[:8]}-watch",
        )
        t_out.start()
        t_err.start()
        t_watch.start()

    def _drain_stdout(self) -> None:
        """Drain stdout_queue and call on_output for each line."""
        if self._on_output is None:
            return
        run = self._run
        while True:
            # Check for terminal state with empty queue
            terminal = run.status in (
                RunStatus.FINISHED,
                RunStatus.FAILED,
                RunStatus.CANCELLED,
            )
            try:
                line = run.stdout_queue.get(timeout=0.05)
                self._on_output(line)
            except queue.Empty:
                if terminal:
                    break

    def _drain_stderr(self) -> None:
        """Drain stderr_queue and call on_error for each line."""
        if self._on_error is None:
            return
        run = self._run
        while True:
            terminal = run.status in (
                RunStatus.FINISHED,
                RunStatus.FAILED,
                RunStatus.CANCELLED,
            )
            try:
                line = run.stderr_queue.get(timeout=0.05)
                self._on_error(line)
            except queue.Empty:
                if terminal:
                    break

    def _watch_finished(
        self,
        t_out: threading.Thread,
        t_err: threading.Thread,
    ) -> None:
        """Wait for the run to reach a terminal state, then fire on_finished."""
        if self._on_finished is None:
            return
        run = self._run
        # Poll until terminal
        while run.status not in (
            RunStatus.FINISHED,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
        ):
            threading.Event().wait(0.05)

        # Wait for drain threads to finish so all output has been delivered
        t_out.join()
        t_err.join()

        exit_code = run.exit_code if run.exit_code is not None else -1
        try:
            self._on_finished(exit_code)
        except Exception:
            _log.exception(
                "on_finished callback raised for run %s", run.run_id
            )


class ProcessService:
    """Manages process execution with streaming output support (framework-agnostic).

    Backward-compatibility shim: delegates all subprocess management to an
    internal ProcessRunManager while preserving the original public API.
    """

    def __init__(self) -> None:
        self._manager: ProcessRunManager = ProcessRunManager()
        self._current_run_id: Optional[str] = None

    def execute_command(
        self,
        command: Sequence[str],
        on_output: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_finished: Optional[Callable[[int], None]] = None,
        working_directory: Optional[str] = None,
        env: Optional[dict] = None,
    ) -> None:
        """Execute a command and stream output.

        Builds a RunCommand from the supplied arguments, delegates to
        ProcessRunManager.start_run(), and wires the callbacks via _ShimAdapter.

        Args:
            command: Tokenized command sequence (e.g., ["python", "-m", "pytest"])
            on_output: Callback for stdout lines
            on_error: Callback for stderr lines
            on_finished: Callback with exit code when process completes
            working_directory: Directory to run command in
            env: Environment variables dict (currently unused by the manager;
                kept for API compatibility)

        Raises:
            TypeError: If command is a string or empty
        """
        if isinstance(command, str) or not command:
            raise TypeError(
                "command must be a non-empty tokenized sequence, not a string"
            )

        command_parts = [str(part) for part in command]

        run_command = RunCommand(
            program=command_parts[0],
            args=command_parts[1:],
            cwd=working_directory or ".",
        )

        run = self._manager.start_run(run_command)
        self._current_run_id = run.run_id

        adapter = _ShimAdapter(
            run=run,
            on_output=on_output,
            on_error=on_error,
            on_finished=on_finished,
        )
        adapter.start()

        _log.info(
            "ProcessService.execute_command delegated | run_id=%s | cmd=%s",
            run.run_id,
            " ".join(command_parts),
        )

    def stop_process(self) -> None:
        """Stop the currently running process.

        Calls ProcessRunManager.stop_run if a current run is set and RUNNING.
        Does nothing if no run is active or the run is not in RUNNING state.
        """
        if self._current_run_id is None:
            return
        try:
            run = self._manager.get_run(self._current_run_id)
        except KeyError:
            return
        if run.status != RunStatus.RUNNING:
            return
        try:
            self._manager.stop_run(self._current_run_id)
        except (KeyError, ValueError):
            pass

    def get_full_output(self) -> tuple:
        """Get full captured output as a tuple of (stdout, stderr) strings.

        Returns:
            Tuple of (stdout_str, stderr_str) where each is the joined buffer.
        """
        if self._current_run_id is None:
            return ("", "")
        try:
            run = self._manager.get_run(self._current_run_id)
        except KeyError:
            return ("", "")
        stdout_str = "".join(run.stdout_buffer)
        stderr_str = "".join(run.stderr_buffer)
        return (stdout_str, stderr_str)

    def is_running(self) -> bool:
        """Check if the current process is still running.

        Returns:
            True if the current run exists and has RUNNING status.
        """
        if self._current_run_id is None:
            return False
        try:
            run = self._manager.get_run(self._current_run_id)
        except KeyError:
            return False
        return run.status == RunStatus.RUNNING

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
