"""API endpoints for process streaming via SSE.

Provides Server-Sent Events endpoint for streaming subprocess output.
"""
import asyncio
import queue
from typing import Optional

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app.web.dependencies import ProcessServiceDep
from app.core.services.process_service import ProcessService

router = APIRouter()

# Global queue for streaming process output
_output_queue: queue.Queue = Optional[None]
_current_process: Optional[dict] = None


def set_output_queue(q: queue.Queue):
    """Set the global output queue for the current process."""
    global _output_queue
    _output_queue = q


def set_current_process(info: dict):
    """Set information about the currently running process."""
    global _current_process
    _current_process = info


async def event_generator():
    """Generate SSE events from process output."""
    global _output_queue, _current_process
    
    if _current_process is None:
        # No process running, send idle status
        yield {
            "event": "status",
            "data": '{"status": "idle", "message": "No process running"}'
        }
        return
    
    try:
        while True:
            if _output_queue and not _output_queue.empty():
                try:
                    line = _output_queue.get_nowait()
                    yield {
                        "event": "output",
                        "data": line
                    }
                except queue.Empty:
                    pass
            else:
                # Check if process is still running
                if _current_process.get("finished", False):
                    # Send final exit code and close
                    yield {
                        "event": "complete",
                        "data": f'{{"exit_code": {_current_process.get("exit_code", 0)}}}'
                    }
                    break
                await asyncio.sleep(0.1)  # Small delay to prevent busy loop
    except asyncio.CancelledError:
        # Client disconnected
        pass


@router.get("/process/stream")
async def stream_process_output():
    """Stream process output via Server-Sent Events."""
    return EventSourceResponse(event_generator())
