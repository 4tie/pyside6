"""Integration tests for EventJournal adapters.

Validates Requirements 13.5, 13.6, 13.7
"""

import pytest

from app.core.ai.journal.event_journal import EventJournal
from app.core.ai.journal.backtest_adapter import BacktestJournalAdapter
from app.core.ai.journal.settings_adapter import SettingsJournalAdapter


def test_backtest_started_recorded():
    journal = EventJournal()
    adapter = BacktestJournalAdapter(journal)

    adapter.on_backtest_started(strategy="MyStrategy", timeframe="5m")

    events = journal.get_recent()
    assert len(events) == 1
    assert events[0].event_type == "backtest_started"
    assert events[0].payload["strategy"] == "MyStrategy"
    assert events[0].payload["timeframe"] == "5m"


def test_backtest_finished_recorded():
    journal = EventJournal()
    adapter = BacktestJournalAdapter(journal)

    adapter.on_backtest_finished(exit_code=0, result_summary="ok")

    events = journal.get_recent()
    assert len(events) == 1
    assert events[0].event_type == "backtest_finished"
    assert events[0].payload["exit_code"] == 0
    assert events[0].payload["result_summary"] == "ok"


def test_settings_saved_recorded():
    journal = EventJournal()
    adapter = SettingsJournalAdapter(journal, settings_state=None)

    adapter._on_settings_saved()

    events = journal.get_recent()
    assert len(events) == 1
    assert events[0].event_type == "settings_saved"
