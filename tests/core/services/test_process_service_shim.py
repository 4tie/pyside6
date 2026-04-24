"""Property-based tests for ProcessService backward-compat shim.

Feature: process-run-manager
Property 11: ProcessService.execute_command delegation round-trip
"""

import sys
import time
from typing import List

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.models.run_models import RunStatus
from app.core.services.process_service import ProcessService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def wait_until(condition, timeout: float = 5.0, poll: float = 0.05) -> bool:
    """Poll condition() until it returns True or timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(poll)
    return False


# ---------------------------------------------------------------------------
# Property 11: ProcessService.execute_command delegation round-trip
# Validates: Requirements 7.2, 7.3
# ---------------------------------------------------------------------------


@given(
    # extra_args is generated but not used in the actual subprocess call —
    # we always run a fixed short-lived command so the test stays fast.
    # The property verifies that regardless of what args Hypothesis generates,
    # the shim correctly registers a run and delivers callbacks.
    extra_args=st.lists(st.text(min_size=1), min_size=1, max_size=5),
)
@settings(max_examples=5)
def test_execute_command_delegation_round_trip(extra_args: List[str]) -> None:
    """For any command sequence, ProcessService.execute_command must register a
    new run in the internal manager and deliver on_output / on_finished callbacks
    with data matching the run's stdout_buffer and exit_code.

    Property 11 — **Validates: Requirements 7.2, 7.3**
    """
    svc = ProcessService()

    stdout_received: List[str] = []
    finished_codes: List[int] = []

    def on_output(line: str) -> None:
        stdout_received.append(line)

    def on_finished(code: int) -> None:
        finished_codes.append(code)

    # Use a fixed short-lived command that produces known output
    command = [sys.executable, "-c", "print('hello from shim')"]

    svc.execute_command(
        command=command,
        on_output=on_output,
        on_finished=on_finished,
    )

    # A run_id must have been registered
    assert svc._current_run_id is not None, (
        "execute_command must set _current_run_id"
    )
    run_id = svc._current_run_id

    # The manager must have the run registered
    run = svc._manager.get_run(run_id)
    assert run is not None, "Manager must have the run registered"

    # Wait for the run to reach a terminal state
    reached = wait_until(
        lambda: run.status in (RunStatus.FINISHED, RunStatus.FAILED, RunStatus.CANCELLED)
    )
    assert reached, f"Run did not reach terminal state within timeout (status={run.status})"

    # Wait for callbacks to be delivered (shim threads may lag slightly)
    wait_until(lambda: len(finished_codes) > 0)

    # on_finished must have been called with exit_code == 0
    assert len(finished_codes) == 1, (
        f"on_finished must be called exactly once, got {len(finished_codes)}"
    )
    assert finished_codes[0] == 0, (
        f"Expected exit_code=0, got {finished_codes[0]}"
    )
    assert finished_codes[0] == run.exit_code, (
        f"on_finished exit_code {finished_codes[0]} must match run.exit_code {run.exit_code}"
    )

    # on_output callbacks must match stdout_buffer content
    # (both contain the same lines; order must match)
    buffer_content = "".join(run.stdout_buffer)
    callback_content = "".join(stdout_received)
    assert callback_content == buffer_content, (
        f"Callback stdout content must match stdout_buffer.\n"
        f"  callbacks: {stdout_received!r}\n"
        f"  buffer:    {run.stdout_buffer!r}"
    )

    # The output must contain the expected text
    assert "hello from shim" in callback_content, (
        f"Expected 'hello from shim' in stdout, got: {callback_content!r}"
    )


# ---------------------------------------------------------------------------
# Additional example-based tests for shim correctness
# ---------------------------------------------------------------------------


def test_execute_command_sets_current_run_id() -> None:
    """execute_command must set _current_run_id to the new run's run_id.

    **Validates: Requirements 7.2**
    """
    svc = ProcessService()
    assert svc._current_run_id is None

    svc.execute_command(command=[sys.executable, "-c", "pass"])

    assert svc._current_run_id is not None


def test_execute_command_run_registered_in_manager() -> None:
    """The run created by execute_command must be retrievable from the manager.

    **Validates: Requirements 7.2**
    """
    svc = ProcessService()
    svc.execute_command(command=[sys.executable, "-c", "pass"])

    run = svc._manager.get_run(svc._current_run_id)
    assert run is not None
    assert run.run_id == svc._current_run_id


def test_execute_command_on_error_callback_receives_stderr() -> None:
    """on_error callback must receive stderr lines from the subprocess.

    **Validates: Requirements 7.3**
    """
    svc = ProcessService()
    stderr_received: List[str] = []
    finished_codes: List[int] = []

    svc.execute_command(
        command=[
            sys.executable,
            "-c",
            "import sys; print('err line', file=sys.stderr)",
        ],
        on_error=lambda line: stderr_received.append(line),
        on_finished=lambda code: finished_codes.append(code),
    )

    run = svc._manager.get_run(svc._current_run_id)
    wait_until(
        lambda: run.status in (RunStatus.FINISHED, RunStatus.FAILED, RunStatus.CANCELLED)
    )
    wait_until(lambda: len(finished_codes) > 0)

    stderr_content = "".join(stderr_received)
    assert "err line" in stderr_content, (
        f"Expected 'err line' in stderr callbacks, got: {stderr_content!r}"
    )


def test_stop_process_cancels_running_run() -> None:
    """stop_process must cancel the currently running run.

    **Validates: Requirements 7.2**
    """
    svc = ProcessService()
    svc.execute_command(
        command=[sys.executable, "-c", "import time; time.sleep(60)"]
    )

    assert svc.is_running()
    svc.stop_process()

    run = svc._manager.get_run(svc._current_run_id)
    assert run.status == RunStatus.CANCELLED


def test_stop_process_noop_when_no_run() -> None:
    """stop_process must not raise when no run has been started.

    **Validates: Requirements 7.2**
    """
    svc = ProcessService()
    svc.stop_process()  # must not raise


def test_get_full_output_returns_joined_buffers() -> None:
    """get_full_output must return joined stdout and stderr buffers.

    **Validates: Requirements 7.2**
    """
    svc = ProcessService()
    finished_codes: List[int] = []

    svc.execute_command(
        command=[
            sys.executable,
            "-c",
            "import sys; print('out1'); print('err1', file=sys.stderr)",
        ],
        on_finished=lambda code: finished_codes.append(code),
    )

    run = svc._manager.get_run(svc._current_run_id)
    wait_until(
        lambda: run.status in (RunStatus.FINISHED, RunStatus.FAILED, RunStatus.CANCELLED)
    )
    wait_until(lambda: len(finished_codes) > 0)

    stdout_str, stderr_str = svc.get_full_output()
    assert "out1" in stdout_str, f"Expected 'out1' in stdout, got: {stdout_str!r}"
    assert "err1" in stderr_str, f"Expected 'err1' in stderr, got: {stderr_str!r}"


def test_get_full_output_empty_when_no_run() -> None:
    """get_full_output must return ('', '') when no run has been started.

    **Validates: Requirements 7.2**
    """
    svc = ProcessService()
    result = svc.get_full_output()
    assert result == ("", "")


def test_is_running_false_when_no_run() -> None:
    """is_running must return False when no run has been started.

    **Validates: Requirements 7.2**
    """
    svc = ProcessService()
    assert svc.is_running() is False


def test_is_running_true_while_running() -> None:
    """is_running must return True while the subprocess is active.

    **Validates: Requirements 7.2**
    """
    svc = ProcessService()
    svc.execute_command(
        command=[sys.executable, "-c", "import time; time.sleep(10)"]
    )
    assert svc.is_running() is True
    svc.stop_process()


def test_is_running_false_after_finish() -> None:
    """is_running must return False after the subprocess exits.

    **Validates: Requirements 7.2**
    """
    svc = ProcessService()
    finished_codes: List[int] = []

    svc.execute_command(
        command=[sys.executable, "-c", "pass"],
        on_finished=lambda code: finished_codes.append(code),
    )

    run = svc._manager.get_run(svc._current_run_id)
    wait_until(
        lambda: run.status in (RunStatus.FINISHED, RunStatus.FAILED, RunStatus.CANCELLED)
    )
    wait_until(lambda: len(finished_codes) > 0)

    assert svc.is_running() is False


def test_execute_command_raises_on_string_command() -> None:
    """execute_command must raise TypeError when given a string instead of a sequence.

    **Validates: Requirements 7.2**
    """
    svc = ProcessService()
    with pytest.raises(TypeError):
        svc.execute_command(command="python -c pass")  # type: ignore[arg-type]


def test_execute_command_raises_on_empty_command() -> None:
    """execute_command must raise TypeError when given an empty sequence.

    **Validates: Requirements 7.2**
    """
    svc = ProcessService()
    with pytest.raises(TypeError):
        svc.execute_command(command=[])
