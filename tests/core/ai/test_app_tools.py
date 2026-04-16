"""Unit tests for Phase 3 app tools (get_app_status, read_recent_logs, list_recent_events).

Validates: Requirements 15.1, 15.2, 15.4, 15.6
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.ai.tools.app_tools import get_app_status, list_recent_events, read_recent_logs
from app.core.models.settings_models import AISettings, AppSettings


# ---------------------------------------------------------------------------
# get_app_status
# ---------------------------------------------------------------------------


def test_get_app_status_returns_expected_keys():
    """Calling with settings=None returns a dict with the four required keys."""
    result = get_app_status(settings=None)
    assert "provider" in result
    assert "chat_model" in result
    assert "tools_enabled" in result
    assert "status" in result


def test_get_app_status_with_settings():
    """Values from AppSettings are reflected in the returned dict."""
    settings = AppSettings(ai=AISettings(provider="ollama", chat_model="llama3", tools_enabled=True))
    result = get_app_status(settings=settings)
    assert result["provider"] == "ollama"
    assert result["chat_model"] == "llama3"
    assert result["tools_enabled"] is True


# ---------------------------------------------------------------------------
# read_recent_logs
# ---------------------------------------------------------------------------


def test_read_recent_logs_clamps_lines_over_200(tmp_path: Path):
    """Requesting more than 200 lines appends the clamping note."""
    log_file = tmp_path / "app.log"
    log_file.write_text("\n".join(f"line {i}" for i in range(10)), encoding="utf-8")

    with patch(
        "app.core.ai.tools.app_tools.LogPathResolver.get_log_path",
        return_value=log_file,
    ):
        result = read_recent_logs(lines=300)

    assert "[Note: output clamped to 200 lines]" in result


def test_read_recent_logs_missing_file():
    """Returns an error message when the log file does not exist."""
    missing = Path("/nonexistent/path/app.log")
    with patch(
        "app.core.ai.tools.app_tools.LogPathResolver.get_log_path",
        return_value=missing,
    ):
        result = read_recent_logs()

    assert result.startswith("Log file not found:")


# ---------------------------------------------------------------------------
# list_recent_events
# ---------------------------------------------------------------------------


def test_list_recent_events_no_journal():
    """Returns an empty JSON array when no journal is provided."""
    result = list_recent_events(event_journal=None)
    assert result == "[]"


def test_list_recent_events_with_journal():
    """Returns a valid JSON array with the correct number of items."""
    from datetime import datetime

    def _make_record(n: int):
        rec = MagicMock()
        rec.timestamp = datetime(2024, 1, 1, 0, 0, n)
        rec.event_type = f"event_{n}"
        rec.source = "test"
        rec.payload = {"n": n}
        return rec

    journal = MagicMock()
    journal.get_recent.return_value = [_make_record(1), _make_record(2)]

    result = list_recent_events(event_journal=journal)
    parsed = json.loads(result)

    assert isinstance(parsed, list)
    assert len(parsed) == 2
