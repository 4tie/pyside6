"""Qt desktop adapter for ProcessRun.

Bridges a ProcessRun's stdout/stderr queues to Qt signals so UI pages
can consume live subprocess output on the main thread without touching
subprocess logic directly.
"""

import queue

from PySide6.QtCore import QObject, QTimer, Signal

from app.core.models.run_models import ProcessRun, RunStatus
from app.core.utils.app_logger import get_logger

_log = get_logger("ui.adapters.process_run_adapter")

_TERMINAL_STATUSES = {RunStatus.FINISHED, RunStatus.FAILED, RunStatus.CANCELLED}


class ProcessRunAdapter(QObject):
    """Thin Qt adapter that polls a ProcessRun's queues via a QTimer.

    Emits Qt signals on the main thread as output arrives and when the
    run reaches a terminal state. Does NOT start or stop the subprocess.

    Signals:
        stdout_received: Emitted with each stdout line from the run.
        stderr_received: Emitted with each stderr line from the run.
        run_finished: Emitted with the exit code (or -1) when the run
            reaches a terminal state and both queues are drained.
    """

    stdout_received = Signal(str)
    stderr_received = Signal(str)
    run_finished = Signal(int)

    def __init__(self, run: ProcessRun, parent: QObject = None) -> None:
        """Initialise the adapter.

        Args:
            run: The ProcessRun to observe.
            parent: Optional Qt parent object.
        """
        super().__init__(parent)
        self._run = run
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._connected = False

    def start(self) -> None:
        """Start polling the run's queues.

        Connects the timer's timeout signal to the _poll slot and starts
        the timer.
        """
        if not self._connected:
            self._timer.timeout.connect(self._poll)
            self._connected = True
        self._timer.start()
        _log.debug("ProcessRunAdapter started for run %s", self._run.run_id)

    def stop(self) -> None:
        """Stop polling.

        Stops the timer and disconnects the timeout signal. Safe to call
        even if the adapter was never started.
        """
        self._timer.stop()
        if self._connected:
            try:
                self._timer.timeout.disconnect(self._poll)
            except RuntimeError:
                pass
            self._connected = False
        _log.debug("ProcessRunAdapter stopped for run %s", self._run.run_id)

    def _poll(self) -> None:
        """Drain queues and emit signals.

        Called by the QTimer on the main thread every 50 ms. Drains
        stdout_queue and stderr_queue, emitting the corresponding signals
        for each line. When the run has reached a terminal status and both
        queues are empty, emits run_finished and stops the timer.
        """
        # Drain stdout queue
        while True:
            try:
                line = self._run.stdout_queue.get_nowait()
                self.stdout_received.emit(line)
            except queue.Empty:
                break

        # Drain stderr queue
        while True:
            try:
                line = self._run.stderr_queue.get_nowait()
                self.stderr_received.emit(line)
            except queue.Empty:
                break

        # Check for terminal state with both queues empty
        if self._run.status in _TERMINAL_STATUSES:
            stdout_empty = self._run.stdout_queue.empty()
            stderr_empty = self._run.stderr_queue.empty()
            if stdout_empty and stderr_empty:
                exit_code = self._run.exit_code if self._run.exit_code is not None else -1
                _log.debug(
                    "Run %s finished with exit_code=%d, emitting run_finished",
                    self._run.run_id,
                    exit_code,
                )
                self.run_finished.emit(exit_code)
                self.stop()
