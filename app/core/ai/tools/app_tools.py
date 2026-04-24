from __future__ import annotations

from pathlib import Path
from typing import Optional

from app.core.ai.tools.log_path_resolver import LogPathResolver
from app.core.ai.tools.tool_registry import ToolDefinition, ToolRegistry
from app.core.parsing.json_parser import json_dumps
from app.core.utils.app_logger import get_logger

_log = get_logger("services.app_tools")


def get_application_status(settings=None) -> dict:
    """Return current app status including provider, model, and tools state.

    Args:
        settings: Optional ``AppSettings`` instance. If ``None``, defaults
            are returned with empty strings.

    Returns:
        Dict with keys ``provider``, ``chat_model``, ``tools_enabled``, ``status``.
    """
    if settings is None:
        return {
            "provider": "",
            "chat_model": "",
            "tools_enabled": False,
            "status": "running",
        }
    ai = settings.ai
    return {
        "provider": ai.provider,
        "chat_model": ai.chat_model,
        "tools_enabled": ai.tools_enabled,
        "status": "running",
    }


def read_recent_log_lines(lines: int = 50) -> str:
    """Read the last N lines from the application log file.

    Args:
        lines: Number of lines to read. Clamped to a maximum of 200.

    Returns:
        Log content as a string, or an error message if the file is missing.
    """
    clamped = lines > 200
    effective_lines = min(lines, 200)

    log_path: Path = LogPathResolver.get_log_path("app.log")
    if not log_path.exists():
        return f"Log file not found: {log_path}"

    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
        all_lines = text.splitlines()
        tail = all_lines[-effective_lines:] if len(all_lines) > effective_lines else all_lines
        result = "\n".join(tail)
        if clamped:
            result += "\n[Note: output clamped to 200 lines]"
        return result
    except OSError as exc:
        _log.error("Failed to read log file %s: %s", log_path, exc)
        return f"Error reading log file: {exc}"


def get_most_recent_error() -> str:
    """Return the most recent ERROR line from the application log.

    Returns:
        The last line containing "ERROR", or ``"No recent errors found"`` if none.
    """
    log_path: Path = LogPathResolver.get_log_path("app.log")
    if not log_path.exists():
        return "No recent errors found"

    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
        for line in reversed(text.splitlines()):
            if "ERROR" in line:
                return line
        return "No recent errors found"
    except OSError as exc:
        _log.error("Failed to read log file %s: %s", log_path, exc)
        return "No recent errors found"


def list_recent_application_events(event_journal=None, n: int = 20) -> str:
    """Return the last N events from the event journal as a JSON array.

    Args:
        event_journal: Optional ``EventJournal`` instance. If ``None``,
            returns an empty JSON array.
        n: Number of recent events to return.

    Returns:
        JSON string representing a list of event records.
    """
    if event_journal is None:
        return "[]"

    try:
        records = event_journal.get_recent(n)
        serialized = [
            {
                "timestamp": r.timestamp.isoformat() if hasattr(r.timestamp, "isoformat") else str(r.timestamp),
                "event_type": r.event_type,
                "source": r.source,
                "payload": r.payload,
            }
            for r in records
        ]
        return json_dumps(serialized)
    except Exception as exc:
        _log.error("Failed to serialize event journal: %s", exc)
        return "[]"


def register_app_tools(
    registry: ToolRegistry,
    settings=None,
    event_journal=None,
) -> None:
    """Register all Phase 3 app tools into the given registry.

    Args:
        registry: The :class:`ToolRegistry` to register tools into.
        settings: Optional ``AppSettings`` instance passed to ``get_app_status``.
        event_journal: Optional ``EventJournal`` instance passed to
            ``list_recent_events``.
    """
    registry.register(ToolDefinition(
        name="get_app_status",
        description="Get current app status including provider, model, and tools state",
        parameters_schema={"type": "object", "properties": {}, "required": []},
        callable=lambda: get_application_status(settings),
    ))
    registry.register(ToolDefinition(
        name="read_recent_logs",
        description="Read recent application log lines",
        parameters_schema={
            "type": "object",
            "properties": {"lines": {"type": "integer", "default": 50}},
            "required": [],
        },
        callable=lambda lines=50: read_recent_log_lines(lines),
    ))
    registry.register(ToolDefinition(
        name="get_last_error",
        description="Get the most recent error from the application log",
        parameters_schema={"type": "object", "properties": {}, "required": []},
        callable=lambda: get_most_recent_error(),
    ))
    registry.register(ToolDefinition(
        name="list_recent_events",
        description="List recent application events from the event journal",
        parameters_schema={
            "type": "object",
            "properties": {"n": {"type": "integer", "default": 20}},
            "required": [],
        },
        callable=lambda n=20: list_recent_application_events(event_journal, n),
    ))
