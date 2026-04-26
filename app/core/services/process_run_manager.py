"""ProcessRunManager — framework-agnostic subprocess run registry.

Manages the full lifecycle of subprocess invocations: starting, tracking,
stopping, and providing access to per-run metadata and I/O buffers.

No PySide6, fastapi, or starlette imports are permitted in this module.
"""

import subprocess
import threading
from datetime import datetime, timezone
from typing import Callable, Optional

from app.core.models.command_models import RunCommand
from app.core.models.run_models import ProcessRun, RunStatus
from app.core.utils.app_logger import get_logger

_log = get_logger("services.process_run_manager")


class ProcessRunManager:
    """Central registry for subprocess runs.

    Each call to ``start_run`` creates a ``ProcessRun`` record, launches the
    subprocess, and starts daemon threads to stream stdout/stderr into the
    run's queues and buffers.  The manager is safe to use from multiple
    threads; all mutations to ``_runs`` and ``_processes`` are protected by
    ``_lock``.

    Args:
        on_run_finished: Optional callback invoked once when a run reaches a
            terminal state (``FINISHED``, ``FAILED``, or ``CANCELLED``).
            Called from a daemon thread — callers must handle thread safety.
    """

    def __init__(
        self,
        on_run_finished: Optional[Callable[[ProcessRun], None]] = None,
    ) -> None:
        self._runs: dict[str, ProcessRun] = {}
        self._processes: dict[str, subprocess.Popen] = {}
        self._lock = threading.Lock()
        self._on_run_finished = on_run_finished

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_run(self, command: RunCommand) -> ProcessRun:
        """Create a ``ProcessRun``, launch the subprocess, and return the run.

        Args:
            command: ``RunCommand`` describing the program, args, and cwd.

        Returns:
            The newly created ``ProcessRun`` in ``RUNNING`` state.

        Raises:
            ValueError: If ``command.as_list()`` is empty, or if the
                executable cannot be found / the OS refuses to launch it.
        """
        cmd_list = command.as_list()
        if not cmd_list:
            raise ValueError("command.as_list() must not be empty")

        run = ProcessRun(command=cmd_list, cwd=command.cwd or None)
        run.status = RunStatus.RUNNING
        run.started_at = datetime.now(timezone.utc)

        try:
            proc = subprocess.Popen(
                cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                cwd=command.cwd or None,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError as exc:
            run.status = RunStatus.FAILED
            run.exit_code = -1
            _log.error("Executable not found for run %s: %s", run.run_id, exc)
            raise ValueError(f"Executable not found: {exc}") from exc
        except OSError as exc:
            run.status = RunStatus.FAILED
            run.exit_code = -1
            _log.error("OSError launching run %s: %s", run.run_id, exc)
            raise ValueError(f"Failed to launch process: {exc}") from exc

        with self._lock:
            self._runs[run.run_id] = run
            self._processes[run.run_id] = proc

        _log.info(
            "Run started | run_id=%s | cmd=%s | cwd=%s | pid=%s",
            run.run_id,
            " ".join(cmd_list),
            command.cwd or "(default)",
            proc.pid,
        )

        # Start reader threads for stdout and stderr
        t_out = threading.Thread(
            target=self._reader_thread,
            args=(run, proc.stdout, run.stdout_queue, run.stdout_buffer, "stdout"),
            daemon=True,
            name=f"run-{run.run_id[:8]}-stdout",
        )
        t_err = threading.Thread(
            target=self._reader_thread,
            args=(run, proc.stderr, run.stderr_queue, run.stderr_buffer, "stderr"),
            daemon=True,
            name=f"run-{run.run_id[:8]}-stderr",
        )
        t_out.start()
        t_err.start()

        # Start waiter thread that sets terminal status after process exits
        t_wait = threading.Thread(
            target=self._waiter_thread,
            args=(run, proc, t_out, t_err),
            daemon=True,
            name=f"run-{run.run_id[:8]}-waiter",
        )
        t_wait.start()

        return run

    def stop_run(self, run_id: str) -> None:
        """Terminate the subprocess for the given run.

        Sends ``SIGTERM``, waits up to 3 seconds, then sends ``SIGKILL`` if
        the process has not exited.  Sets the run status to ``CANCELLED``.

        Args:
            run_id: The ``run_id`` of the run to stop.

        Raises:
            KeyError: If ``run_id`` is not registered.
            ValueError: If the run is not in ``RUNNING`` state.
        """
        with self._lock:
            if run_id not in self._runs:
                raise KeyError(run_id)
            run = self._runs[run_id]
            if run.status != RunStatus.RUNNING:
                raise ValueError(
                    f"Run '{run_id}' is not running (status: {run.status.value})"
                )
            proc = self._processes.get(run_id)

        # Mark as CANCELLED before sending signals so the waiter thread
        # sees the CANCELLED status and skips its own terminal transition.
        with self._lock:
            run.status = RunStatus.CANCELLED
            run.finished_at = datetime.now(timezone.utc)

        if proc is not None:
            _log.info("Stopping run %s (pid=%s) — sending SIGTERM", run_id, proc.pid)
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    _log.warning(
                        "Run %s did not exit after SIGTERM — sending SIGKILL", run_id
                    )
                    proc.kill()
                    proc.wait()
            except OSError as exc:
                _log.error("Error stopping run %s: %s", run_id, exc)

        _log.info("Run %s cancelled", run_id)

        if self._on_run_finished is not None:
            try:
                self._on_run_finished(run)
            except Exception:
                _log.exception("on_run_finished callback raised for run %s", run_id)

    def get_run(self, run_id: str) -> ProcessRun:
        """Return the ``ProcessRun`` for the given ``run_id``.

        Args:
            run_id: The unique identifier of the run.

        Returns:
            The ``ProcessRun`` instance.

        Raises:
            KeyError: If ``run_id`` is not registered.
        """
        with self._lock:
            if run_id not in self._runs:
                raise KeyError(run_id)
            return self._runs[run_id]

    def list_runs(self, status: Optional[RunStatus] = None) -> list[ProcessRun]:
        """Return all registered runs in insertion order.

        Args:
            status: If provided, only runs with this status are returned.

        Returns:
            List of ``ProcessRun`` instances in creation order.
        """
        with self._lock:
            runs = list(self._runs.values())
        if status is not None:
            runs = [r for r in runs if r.status == status]
        return runs

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _reader_thread(
        self,
        run: ProcessRun,
        pipe,
        q,
        buf: list,
        stream_name: str,
    ) -> None:
        """Read lines from *pipe* and append them to *q* and *buf*.

        Args:
            run: The ``ProcessRun`` this reader belongs to.
            pipe: The file-like pipe object (``proc.stdout`` or ``proc.stderr``).
            q: The ``queue.Queue`` to put lines into.
            buf: The list buffer to append lines to.
            stream_name: ``"stdout"`` or ``"stderr"`` — used for logging only.
        """
        try:
            if pipe is None:
                return
            for line in iter(pipe.readline, ""):
                if line:
                    buf.append(line)
                    q.put(line)
                    _log.debug("run %s %s: %r", run.run_id[:8], stream_name, line[:80])
        except Exception as exc:
            msg = f"[output reader error: {exc}]"
            _log.error("Reader thread error for run %s (%s): %s", run.run_id, stream_name, exc)
            buf.append(msg)
            q.put(msg)
        finally:
            try:
                if pipe is not None:
                    pipe.close()
            except Exception:
                pass

    def _waiter_thread(
        self,
        run: ProcessRun,
        proc: subprocess.Popen,
        t_out: threading.Thread,
        t_err: threading.Thread,
    ) -> None:
        """Wait for the subprocess to exit, then set the terminal status.

        Waits for both reader threads to finish (ensuring all output is
        captured) before updating the run status.

        Args:
            run: The ``ProcessRun`` to update.
            proc: The ``subprocess.Popen`` handle.
            t_out: The stdout reader thread.
            t_err: The stderr reader thread.
        """
        try:
            proc.wait()
            # Drain remaining output before marking terminal
            t_out.join()
            t_err.join()

            return_code = proc.returncode

            with self._lock:
                # If already CANCELLED (stop_run was called), don't overwrite
                if run.status == RunStatus.CANCELLED:
                    return

                run.exit_code = return_code
                run.finished_at = datetime.now(timezone.utc)
                if return_code == 0:
                    run.status = RunStatus.FINISHED
                else:
                    run.status = RunStatus.FAILED

            _log.info(
                "Run %s finished | status=%s | exit_code=%s",
                run.run_id,
                run.status.value,
                return_code,
            )

            if self._on_run_finished is not None:
                try:
                    self._on_run_finished(run)
                except Exception:
                    _log.exception(
                        "on_run_finished callback raised for run %s", run.run_id
                    )
        except Exception as exc:
            _log.error("Waiter thread error for run %s: %s", run.run_id, exc)
            with self._lock:
                if run.status == RunStatus.RUNNING:
                    run.status = RunStatus.FAILED
                    run.finished_at = datetime.now(timezone.utc)
