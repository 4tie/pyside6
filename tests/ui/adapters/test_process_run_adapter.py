"""Integration tests for ProcessRunAdapter Qt signals.

Validates: Requirements 4.2, 4.3, 4.4, 4.5
"""

import sys

import pytest
from PySide6.QtWidgets import QApplication

from app.core.models.run_models import ProcessRun, RunStatus
from app.ui.adapters.process_run_adapter import ProcessRunAdapter


# ---------------------------------------------------------------------------
# Session-scoped QApplication fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def qt_app():
    """Create (or reuse) a QApplication for the test session."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    return app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run(**kwargs) -> ProcessRun:
    """Return a ProcessRun with sensible defaults for testing."""
    defaults = {"command": ["echo", "test"]}
    defaults.update(kwargs)
    return ProcessRun(**defaults)


def _process_events(qt_app, iterations: int = 10) -> None:
    """Process Qt events multiple times to allow timer callbacks to fire."""
    for _ in range(iterations):
        qt_app.processEvents()


# ---------------------------------------------------------------------------
# Test 1: stdout_received / stderr_received signals emitted from queues
# ---------------------------------------------------------------------------


def test_stdout_received_signal_emitted(qt_app):
    """Adapter emits stdout_received for each line in stdout_queue."""
    run = _make_run()
    run.stdout_queue.put("line one")
    run.stdout_queue.put("line two")

    received = []
    adapter = ProcessRunAdapter(run)
    adapter.stdout_received.connect(received.append)
    adapter.start()

    # Force the timer to fire by processing events; use waitSignal via qtbot
    # is not available here so we process events and then manually call _poll.
    adapter._poll()
    adapter.stop()

    assert received == ["line one", "line two"]


def test_stderr_received_signal_emitted(qt_app):
    """Adapter emits stderr_received for each line in stderr_queue."""
    run = _make_run()
    run.stderr_queue.put("err one")
    run.stderr_queue.put("err two")

    received = []
    adapter = ProcessRunAdapter(run)
    adapter.stderr_received.connect(received.append)
    adapter.start()

    adapter._poll()
    adapter.stop()

    assert received == ["err one", "err two"]


def test_both_queues_drained_in_single_poll(qt_app):
    """Adapter drains both stdout and stderr in a single _poll call."""
    run = _make_run()
    run.stdout_queue.put("stdout line")
    run.stderr_queue.put("stderr line")

    stdout_lines = []
    stderr_lines = []
    adapter = ProcessRunAdapter(run)
    adapter.stdout_received.connect(stdout_lines.append)
    adapter.stderr_received.connect(stderr_lines.append)
    adapter.start()

    adapter._poll()
    adapter.stop()

    assert stdout_lines == ["stdout line"]
    assert stderr_lines == ["stderr line"]


# ---------------------------------------------------------------------------
# Test 2: run_finished emitted and timer stopped on terminal state
# ---------------------------------------------------------------------------


def test_run_finished_emitted_when_finished(qt_app):
    """Adapter emits run_finished with exit_code when run is FINISHED."""
    run = _make_run()
    run.status = RunStatus.FINISHED
    run.exit_code = 0

    finished_codes = []
    adapter = ProcessRunAdapter(run)
    adapter.run_finished.connect(finished_codes.append)
    adapter.start()

    adapter._poll()

    assert finished_codes == [0]
    assert not adapter._timer.isActive()


def test_run_finished_emitted_when_failed(qt_app):
    """Adapter emits run_finished with non-zero exit_code when run is FAILED."""
    run = _make_run()
    run.status = RunStatus.FAILED
    run.exit_code = 1

    finished_codes = []
    adapter = ProcessRunAdapter(run)
    adapter.run_finished.connect(finished_codes.append)
    adapter.start()

    adapter._poll()

    assert finished_codes == [1]
    assert not adapter._timer.isActive()


def test_run_finished_emits_minus_one_for_cancelled(qt_app):
    """Adapter emits run_finished(-1) when run is CANCELLED (no exit_code)."""
    run = _make_run()
    run.status = RunStatus.CANCELLED
    run.exit_code = None

    finished_codes = []
    adapter = ProcessRunAdapter(run)
    adapter.run_finished.connect(finished_codes.append)
    adapter.start()

    adapter._poll()

    assert finished_codes == [-1]
    assert not adapter._timer.isActive()


def test_run_finished_not_emitted_while_running(qt_app):
    """Adapter does NOT emit run_finished while run is still RUNNING."""
    run = _make_run()
    run.status = RunStatus.RUNNING

    finished_codes = []
    adapter = ProcessRunAdapter(run)
    adapter.run_finished.connect(finished_codes.append)
    adapter.start()

    adapter._poll()
    adapter.stop()

    assert finished_codes == []


def test_run_finished_emitted_after_draining_queues(qt_app):
    """Adapter drains queues and emits run_finished in the same poll cycle.

    When the run is already terminal and has pending output, a single _poll
    call drains all output AND emits run_finished (because the drain empties
    the queues before the terminal check).
    """
    run = _make_run()
    run.status = RunStatus.FINISHED
    run.exit_code = 0
    run.stdout_queue.put("pending line")

    finished_codes = []
    stdout_lines = []
    adapter = ProcessRunAdapter(run)
    adapter.run_finished.connect(finished_codes.append)
    adapter.stdout_received.connect(stdout_lines.append)
    adapter.start()

    # Single poll: drains stdout then sees empty queues + terminal status
    adapter._poll()
    assert stdout_lines == ["pending line"]
    assert finished_codes == [0]


def test_timer_stopped_after_run_finished(qt_app):
    """Timer is inactive after run_finished is emitted."""
    run = _make_run()
    run.status = RunStatus.FINISHED
    run.exit_code = 0

    adapter = ProcessRunAdapter(run)
    adapter.start()
    assert adapter._timer.isActive()

    adapter._poll()

    assert not adapter._timer.isActive()


# ---------------------------------------------------------------------------
# Test 3: Adapter has no subprocess management methods
# ---------------------------------------------------------------------------


def test_adapter_has_no_start_run_method(qt_app):
    """ProcessRunAdapter must not expose start_run."""
    run = _make_run()
    adapter = ProcessRunAdapter(run)
    assert not hasattr(adapter, "start_run")


def test_adapter_has_no_stop_run_method(qt_app):
    """ProcessRunAdapter must not expose stop_run."""
    run = _make_run()
    adapter = ProcessRunAdapter(run)
    assert not hasattr(adapter, "stop_run")


def test_adapter_has_no_execute_command_method(qt_app):
    """ProcessRunAdapter must not expose execute_command."""
    run = _make_run()
    adapter = ProcessRunAdapter(run)
    assert not hasattr(adapter, "execute_command")


# ---------------------------------------------------------------------------
# Test 4: stop() is safe to call before start()
# ---------------------------------------------------------------------------


def test_stop_before_start_does_not_raise(qt_app):
    """Calling stop() before start() must not raise an exception."""
    run = _make_run()
    adapter = ProcessRunAdapter(run)
    adapter.stop()  # Should not raise


def test_stop_twice_does_not_raise(qt_app):
    """Calling stop() twice must not raise an exception."""
    run = _make_run()
    adapter = ProcessRunAdapter(run)
    adapter.start()
    adapter.stop()
    adapter.stop()  # Second stop — disconnect already gone, must not raise
