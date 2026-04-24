"""Thread-safe bridge between ProcessService callbacks and the SSE endpoint.

Connects background-thread subprocess output to the asyncio event loop
that drives the GET /api/process/stream SSE endpoint.
"""
import asyncio
import threading
from typing import Any, AsyncGenerator, Optional

from app.core.utils.app_logger import get_logger

_log = get_logger("web.process_output_bus")


class ProcessOutputBus:
    """Thread-safe bridge: background thread → asyncio SSE generator.

    Usage::

        bus = ProcessOutputBus()

        # In route handler (asyncio context):
        bus.attach(asyncio.get_event_loop())
        process_service.execute_command(
            command=cmd,
            on_output=bus.push_line,
            on_error=bus.push_line,
            on_finished=bus.push_finished,
        )

        # In SSE generator:
        async for event in bus.stream():
            yield event
    """

    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._queue: Optional[asyncio.Queue] = None
        self._finished: bool = False
        self._exit_code: Optional[int] = None
        self._lock = threading.Lock()

    def attach(self, loop: asyncio.AbstractEventLoop) -> None:
        """Bind to the running event loop. Called once from the SSE endpoint."""
        with self._lock:
            self._loop = loop
            self._queue = asyncio.Queue()
            self._finished = False
            self._exit_code = None
        _log.debug("ProcessOutputBus attached to event loop")

    def push_line(self, line: str) -> None:
        """Push a stdout/stderr line from the background thread (thread-safe)."""
        with self._lock:
            loop = self._loop
            queue = self._queue
        if loop and queue:
            loop.call_soon_threadsafe(queue.put_nowait, ("line", line))

    def push_finished(self, exit_code: int) -> None:
        """Signal process completion from the background thread (thread-safe)."""
        with self._lock:
            loop = self._loop
            queue = self._queue
        if loop and queue:
            loop.call_soon_threadsafe(queue.put_nowait, ("finished", exit_code))
        _log.info("Process finished with exit_code=%s", exit_code)

    async def stream(self) -> AsyncGenerator[dict, None]:
        """Async generator consumed by the SSE endpoint.

        Yields SSE event dicts with 'event' and 'data' keys.
        When no process is attached, yields a single idle status event.
        """
        if self._queue is None:
            yield {"event": "status", "data": '{"status": "idle"}'}
            return

        while True:
            kind, payload = await self._queue.get()
            if kind == "line":
                yield {"event": "output", "data": payload.rstrip("\n")}
            elif kind == "finished":
                yield {
                    "event": "complete",
                    "data": f'{{"exit_code": {payload}}}',
                }
                break
