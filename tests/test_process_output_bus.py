"""Tests for ProcessOutputBus — unit tests and property-based tests.

Covers:
- Lines pushed from a thread appear in stream() in order
- push_finished terminates the stream with the correct exit code
- Calling push_line before attach() does not raise
- Property 8: SSE delivers correct exit code
"""
import asyncio
import threading

import pytest
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from app.web.process_output_bus import ProcessOutputBus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_stream(bus: ProcessOutputBus) -> list:
    """Drain bus.stream() synchronously and return all events."""
    loop = asyncio.new_event_loop()
    try:
        async def _drain():
            events = []
            async for event in bus.stream():
                events.append(event)
            return events
        return loop.run_until_complete(_drain())
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

class TestProcessOutputBusUnit:
    def test_lines_appear_in_order(self):
        bus = ProcessOutputBus()
        loop = asyncio.new_event_loop()
        bus.attach(loop)

        lines = ["line one\n", "line two\n", "line three\n"]

        def _push():
            for line in lines:
                bus.push_line(line)
            bus.push_finished(0)

        t = threading.Thread(target=_push, daemon=True)

        async def _collect():
            events = []
            async for event in bus.stream():
                events.append(event)
            return events

        try:
            t.start()
            events = loop.run_until_complete(_collect())
        finally:
            loop.close()
            t.join(timeout=2)

        output_events = [e for e in events if e["event"] == "output"]
        assert [e["data"] for e in output_events] == [l.rstrip("\n") for l in lines]

    def test_push_finished_terminates_stream_with_exit_code(self):
        bus = ProcessOutputBus()
        loop = asyncio.new_event_loop()
        bus.attach(loop)

        def _push():
            bus.push_finished(42)

        t = threading.Thread(target=_push, daemon=True)

        async def _collect():
            events = []
            async for event in bus.stream():
                events.append(event)
            return events

        try:
            t.start()
            events = loop.run_until_complete(_collect())
        finally:
            loop.close()
            t.join(timeout=2)

        assert events[-1]["event"] == "complete"
        assert "42" in events[-1]["data"]

    def test_push_line_before_attach_does_not_raise(self):
        bus = ProcessOutputBus()
        # Should silently drop — no exception
        bus.push_line("some line\n")
        bus.push_finished(0)

    def test_stream_without_attach_yields_idle(self):
        bus = ProcessOutputBus()
        events = _collect_stream(bus)
        assert len(events) == 1
        assert events[0]["event"] == "status"
        assert "idle" in events[0]["data"]


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------

# Feature: web-layer-architecture, Property 8: SSE delivers correct exit code
@given(st.integers(min_value=-255, max_value=255))
@h_settings(max_examples=100)
def test_sse_exit_code(exit_code):
    """Property 8: Final SSE event is 'complete' and contains the integer exit code."""
    bus = ProcessOutputBus()
    loop = asyncio.new_event_loop()
    bus.attach(loop)

    def _push():
        bus.push_finished(exit_code)

    t = threading.Thread(target=_push, daemon=True)

    async def _collect():
        events = []
        async for event in bus.stream():
            events.append(event)
        return events

    try:
        t.start()
        events = loop.run_until_complete(_collect())
    finally:
        loop.close()
        t.join(timeout=2)

    assert events[-1]["event"] == "complete"
    assert str(exit_code) in events[-1]["data"]
