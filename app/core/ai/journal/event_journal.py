from datetime import datetime

from app.core.utils.app_logger import get_logger
from app.core.models.ai_models import EventRecord

_log = get_logger("services.event_journal")


class EventJournal:
    MAX_CAPACITY: int = 200

    def __init__(self) -> None:
        self._events: list[EventRecord] = []

    def record(self, event_type: str, source: str, payload: dict) -> None:
        """Append a new event record, discarding the oldest if over capacity."""
        self._events.append(
            EventRecord(
                timestamp=datetime.now(),
                event_type=event_type,
                source=source,
                payload=payload,
            )
        )
        if len(self._events) > self.MAX_CAPACITY:
            self._events.pop(0)

    def get_recent(self, n: int = 50) -> list[EventRecord]:
        """Return the last n events in chronological order (oldest first)."""
        if n == 0:
            return []
        if n < len(self._events):
            return self._events[-n:]
        return list(self._events)
