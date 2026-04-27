"""Thread-safe bridge for process output streaming callbacks."""

import asyncio
import threading
from typing import AsyncGenerator, Optional

from app.core.utils.app_logger import get_logger

_log = get_logger("web.process_output_bus")


class ProcessOutputBus:
    """Bridge background process callbacks into an asyncio stream."""

    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._queue: Optional[asyncio.Queue] = None
        self._lock = threading.Lock()

    def attach(self, loop: asyncio.AbstractEventLoop) -> None:
        with self._lock:
            self._loop = loop
            self._queue = asyncio.Queue()
        _log.debug("ProcessOutputBus attached")

    def push_line(self, line: str) -> None:
        with self._lock:
            loop = self._loop
            queue = self._queue
        if loop and queue:
            loop.call_soon_threadsafe(queue.put_nowait, ("line", line))

    def push_finished(self, exit_code: int) -> None:
        with self._lock:
            loop = self._loop
            queue = self._queue
        if loop and queue:
            loop.call_soon_threadsafe(queue.put_nowait, ("finished", exit_code))
        _log.info("Process finished with exit_code=%s", exit_code)

    async def stream(self) -> AsyncGenerator[dict, None]:
        if self._queue is None:
            yield {"event": "status", "data": '{"status": "idle"}'}
            return
        while True:
            kind, payload = await self._queue.get()
            if kind == "line":
                yield {"event": "output", "data": str(payload).rstrip("\n")}
            elif kind == "finished":
                yield {"event": "complete", "data": f'{{"exit_code": {payload}}}'}
                break
