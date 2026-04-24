"""Unit tests for ProcessRunManager lifecycle with real subprocesses.

Feature: process-run-manager
"""

import sys
import time
from typing import List

import pytest

from app.core.models.command_models import RunCommand
from app.core.models.run_models import ProcessRun, RunStatus
from app.core.services.process_run_manager import ProcessRunManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cmd(python_args: str, cwd: str = ".") -> RunCommand:
    """Build a RunCommand that runs a short Python snippet."""
    return RunCommand(
        program=sys.executable,
        args=["-c", python_args],
        cwd=cwd,
    )


def wait_for_status(
    run: ProcessRun,
    expected: RunStatus,
    timeout: float = 5.0,
    poll_interval: float = 0.1,
) -> bool:
    """Poll until run.status == expected or timeout expires.

    Returns:
        True if the expected status was reached, False on timeout.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if run.status == expected:
            return True
        time.sleep(poll_interval)
    return False


# ---------------------------------------------------------------------------
# Test 1: start_run → RUNNING, started_at set, retrievable via get_run
# Property 3 — Validates: Requirements 2.1, 2.2, 2.8
# ---------------------------------------------------------------------------


def test_start_run_returns_running_run() -> None:
    """start_run must return a ProcessRun with RUNNING status, started_at set,
    and the run must be retrievable via get_run.

    Property 3 — **Validates: Requirements 2.1, 2.2, 2.8**
    """
    manager = ProcessRunManager()
    cmd = _make_cmd("import time; time.sleep(2)")

    run = manager.start_run(cmd)

    try:
        assert run.status == RunStatus.RUNNING, f"Expected RUNNING, got {run.status}"
        assert run.started_at is not None, "started_at must be set after start_run"
        assert run.run_id, "run_id must be non-empty"

        # Must be retrievable via get_run
        retrieved = manager.get_run(run.run_id)
        assert retrieved is run, "get_run must return the same ProcessRun object"
    finally:
        # Clean up: stop the long-running process
        try:
            manager.stop_run(run.run_id)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Test 2: exit code 0 → FINISHED, exit_code == 0, finished_at set
# Property 5 — Validates: Requirements 2.6
# ---------------------------------------------------------------------------


def test_exit_code_zero_sets_finished_status() -> None:
    """A subprocess that exits with code 0 must set status=FINISHED,
    exit_code=0, and finished_at.

    Property 5 — **Validates: Requirements 2.6**
    """
    manager = ProcessRunManager()
    cmd = _make_cmd("import sys; sys.exit(0)")

    run = manager.start_run(cmd)

    reached = wait_for_status(run, RunStatus.FINISHED)
    assert reached, f"Run did not reach FINISHED within timeout (status={run.status})"
    assert run.exit_code == 0, f"Expected exit_code=0, got {run.exit_code}"
    assert run.finished_at is not None, "finished_at must be set after process exits"


# ---------------------------------------------------------------------------
# Test 3: non-zero exit → FAILED, exit_code matches
# Property 5 — Validates: Requirements 2.7
# ---------------------------------------------------------------------------


def test_nonzero_exit_sets_failed_status() -> None:
    """A subprocess that exits with a non-zero code must set status=FAILED
    and exit_code to the actual return code.

    Property 5 — **Validates: Requirements 2.7**
    """
    manager = ProcessRunManager()
    cmd = _make_cmd("import sys; sys.exit(42)")

    run = manager.start_run(cmd)

    reached = wait_for_status(run, RunStatus.FAILED)
    assert reached, f"Run did not reach FAILED within timeout (status={run.status})"
    assert run.exit_code == 42, f"Expected exit_code=42, got {run.exit_code}"
    assert run.finished_at is not None, "finished_at must be set after process exits"


# ---------------------------------------------------------------------------
# Test 4: stop_run on running process → CANCELLED
# Validates: Requirements 2.3, 2.4
# ---------------------------------------------------------------------------


def test_stop_run_cancels_running_process() -> None:
    """stop_run on a RUNNING process must terminate it and set status=CANCELLED.

    **Validates: Requirements 2.3, 2.4**
    """
    manager = ProcessRunManager()
    cmd = _make_cmd("import time; time.sleep(60)")

    run = manager.start_run(cmd)
    assert run.status == RunStatus.RUNNING

    manager.stop_run(run.run_id)

    assert run.status == RunStatus.CANCELLED, (
        f"Expected CANCELLED after stop_run, got {run.status}"
    )


# ---------------------------------------------------------------------------
# Test 5: get_run round-trip after terminal state
# Property 6 — Validates: Requirements 2.8, 8.3
# ---------------------------------------------------------------------------


def test_get_run_round_trip_after_terminal_state() -> None:
    """get_run must return the same ProcessRun object after it has reached
    a terminal state.

    Property 6 — **Validates: Requirements 2.8, 8.3**
    """
    manager = ProcessRunManager()
    cmd = _make_cmd("import sys; sys.exit(0)")

    run = manager.start_run(cmd)
    wait_for_status(run, RunStatus.FINISHED)

    retrieved = manager.get_run(run.run_id)
    assert retrieved is run, "get_run must return the same object after terminal state"
    assert retrieved.status == RunStatus.FINISHED


# ---------------------------------------------------------------------------
# Test 6: on_run_finished callback invoked exactly once per terminal transition
# Property 10 — Validates: Requirements 6.4
# ---------------------------------------------------------------------------


def test_on_run_finished_callback_invoked_once_on_finish() -> None:
    """on_run_finished must be called exactly once when a run reaches FINISHED.

    Property 10 — **Validates: Requirements 6.4**
    """
    finished_runs: List[ProcessRun] = []

    def callback(run: ProcessRun) -> None:
        finished_runs.append(run)

    manager = ProcessRunManager(on_run_finished=callback)
    cmd = _make_cmd("import sys; sys.exit(0)")

    run = manager.start_run(cmd)
    wait_for_status(run, RunStatus.FINISHED)
    # Give the callback a moment to be invoked
    time.sleep(0.2)

    assert len(finished_runs) == 1, (
        f"Expected callback to be called exactly once, got {len(finished_runs)}"
    )
    assert finished_runs[0] is run


def test_on_run_finished_callback_invoked_once_on_cancel() -> None:
    """on_run_finished must be called exactly once when a run is CANCELLED.

    Property 10 — **Validates: Requirements 6.4**
    """
    finished_runs: List[ProcessRun] = []

    def callback(run: ProcessRun) -> None:
        finished_runs.append(run)

    manager = ProcessRunManager(on_run_finished=callback)
    cmd = _make_cmd("import time; time.sleep(60)")

    run = manager.start_run(cmd)
    manager.stop_run(run.run_id)
    # Give the callback a moment to be invoked
    time.sleep(0.2)

    assert len(finished_runs) == 1, (
        f"Expected callback to be called exactly once on cancel, got {len(finished_runs)}"
    )
    assert finished_runs[0] is run
    assert finished_runs[0].status == RunStatus.CANCELLED


def test_on_run_finished_callback_invoked_once_on_failure() -> None:
    """on_run_finished must be called exactly once when a run reaches FAILED.

    Property 10 — **Validates: Requirements 6.4**
    """
    finished_runs: List[ProcessRun] = []

    def callback(run: ProcessRun) -> None:
        finished_runs.append(run)

    manager = ProcessRunManager(on_run_finished=callback)
    cmd = _make_cmd("import sys; sys.exit(1)")

    run = manager.start_run(cmd)
    wait_for_status(run, RunStatus.FAILED)
    time.sleep(0.2)

    assert len(finished_runs) == 1, (
        f"Expected callback to be called exactly once on failure, got {len(finished_runs)}"
    )
    assert finished_runs[0] is run
    assert finished_runs[0].status == RunStatus.FAILED


# ---------------------------------------------------------------------------
# Test 7 (sub-task 2.5): stdout/stderr buffer accumulation
# Property 9 — Validates: Requirements 3.1, 3.2, 3.4, 3.5
# ---------------------------------------------------------------------------


def test_stdout_stderr_buffer_accumulation() -> None:
    """After a run reaches terminal state, stdout_buffer and stderr_buffer must
    contain exactly the lines produced by the subprocess, in order.

    Property 9 — **Validates: Requirements 3.1, 3.2, 3.4, 3.5**
    """
    stdout_lines = ["stdout line 1", "stdout line 2", "stdout line 3"]
    stderr_lines = ["stderr line A", "stderr line B"]

    # Build a Python snippet that prints known lines to stdout and stderr
    script = (
        "import sys\n"
        + "".join(f"print({line!r})\n" for line in stdout_lines)
        + "".join(f"print({line!r}, file=sys.stderr)\n" for line in stderr_lines)
        + "sys.stdout.flush()\n"
        + "sys.stderr.flush()\n"
    )

    manager = ProcessRunManager()
    cmd = RunCommand(program=sys.executable, args=["-c", script], cwd=".")

    run = manager.start_run(cmd)

    # Wait for the run to reach a terminal state
    reached = wait_for_status(run, RunStatus.FINISHED)
    assert reached, f"Run did not reach FINISHED within timeout (status={run.status})"

    # stdout_buffer must contain exactly the expected lines (with trailing newlines)
    actual_stdout = [line.rstrip("\n") for line in run.stdout_buffer]
    assert actual_stdout == stdout_lines, (
        f"stdout_buffer mismatch.\nExpected: {stdout_lines}\nActual:   {actual_stdout}"
    )

    # stderr_buffer must contain exactly the expected lines (with trailing newlines)
    actual_stderr = [line.rstrip("\n") for line in run.stderr_buffer]
    assert actual_stderr == stderr_lines, (
        f"stderr_buffer mismatch.\nExpected: {stderr_lines}\nActual:   {actual_stderr}"
    )


def test_stdout_stderr_buffer_accumulation_large_output() -> None:
    """Buffer accumulation works correctly for larger output volumes.

    Property 9 — **Validates: Requirements 3.1, 3.2, 3.4, 3.5**
    """
    n_stdout = 20
    n_stderr = 15

    script = (
        "import sys\n"
        + f"for i in range({n_stdout}): print(f'out{{i}}')\n"
        + f"for i in range({n_stderr}): print(f'err{{i}}', file=sys.stderr)\n"
        + "sys.stdout.flush()\n"
        + "sys.stderr.flush()\n"
    )

    manager = ProcessRunManager()
    cmd = RunCommand(program=sys.executable, args=["-c", script], cwd=".")

    run = manager.start_run(cmd)
    reached = wait_for_status(run, RunStatus.FINISHED)
    assert reached, f"Run did not reach FINISHED within timeout (status={run.status})"

    actual_stdout = [line.rstrip("\n") for line in run.stdout_buffer]
    actual_stderr = [line.rstrip("\n") for line in run.stderr_buffer]

    expected_stdout = [f"out{i}" for i in range(n_stdout)]
    expected_stderr = [f"err{i}" for i in range(n_stderr)]

    assert actual_stdout == expected_stdout, (
        f"stdout_buffer mismatch: expected {n_stdout} lines, got {len(actual_stdout)}"
    )
    assert actual_stderr == expected_stderr, (
        f"stderr_buffer mismatch: expected {n_stderr} lines, got {len(actual_stderr)}"
    )
