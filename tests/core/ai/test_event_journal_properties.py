# Feature: ai-chat-panel, Property 10: EventJournal never exceeds capacity
# Feature: ai-chat-panel, Property 11: EventJournal get_recent returns chronological order
"""Property-based tests for EventJournal.

Uses Hypothesis to verify correctness properties across arbitrary inputs.
"""
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.ai.journal.event_journal import EventJournal


# ---------------------------------------------------------------------------
# Property 10: EventJournal never exceeds capacity
# Validates: Requirements 13.2
# ---------------------------------------------------------------------------

@given(st.integers(min_value=1, max_value=500))
@settings(max_examples=100)
def test_property_10_event_journal_never_exceeds_capacity(num_events: int):
    # Feature: ai-chat-panel, Property 10: EventJournal never exceeds capacity
    # Validates: Requirements 13.2
    journal = EventJournal()

    for i in range(num_events):
        journal.record(event_type="test_event", source="test", payload={"index": i})

    assert len(journal._events) <= EventJournal.MAX_CAPACITY

    # Retained entries must be the most recently recorded
    expected_count = min(num_events, EventJournal.MAX_CAPACITY)
    assert len(journal._events) == expected_count

    # The last recorded event's payload index should match the last recorded index
    if num_events > 0:
        assert journal._events[-1].payload["index"] == num_events - 1

    # If more than capacity was recorded, the first retained event should be
    # the one recorded at position (num_events - MAX_CAPACITY)
    if num_events > EventJournal.MAX_CAPACITY:
        expected_first_index = num_events - EventJournal.MAX_CAPACITY
        assert journal._events[0].payload["index"] == expected_first_index


# ---------------------------------------------------------------------------
# Property 11: EventJournal get_recent returns chronological order
# Validates: Requirements 13.4
# ---------------------------------------------------------------------------

@given(
    num_events=st.integers(min_value=0, max_value=300),
    n=st.integers(min_value=0, max_value=300),
)
@settings(max_examples=100)
def test_property_11_event_journal_get_recent_chronological_order(num_events: int, n: int):
    # Feature: ai-chat-panel, Property 11: EventJournal get_recent returns chronological order
    # Validates: Requirements 13.4
    journal = EventJournal()

    for i in range(num_events):
        journal.record(event_type="test_event", source="test", payload={"index": i})

    result = journal.get_recent(n)

    # Result must contain at most n events
    assert len(result) <= n

    # Timestamps must be in ascending (chronological) order
    for i in range(len(result) - 1):
        assert result[i].timestamp <= result[i + 1].timestamp
