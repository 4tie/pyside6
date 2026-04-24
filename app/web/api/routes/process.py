"""API endpoints for process streaming via SSE.

Provides Server-Sent Events endpoint for streaming subprocess output
via ProcessOutputBus.
"""
import asyncio

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.web.dependencies import ProcessOutputBusDep

router = APIRouter()


@router.get("/process/stream")
async def stream_process_output(bus: ProcessOutputBusDep):
    """Stream process output via Server-Sent Events."""
    loop = asyncio.get_event_loop()
    bus.attach(loop)
    return EventSourceResponse(bus.stream())
