"""
storage.py — Persists chat messages to disk.

Two formats:
  - conversations.jsonl  : global append-only log across all sessions
  - sessions/<id>.json   : full session context per run
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from . import config


class MessageStore:
    """Saves every message to the global JSONL log and a per-session JSON file."""

    def __init__(self) -> None:
        config.ensure_dirs()
        self.session_id: str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_file: Path = (
            config.CHAT_SESSIONS_DIR / f"session_{self.session_id}.json"
        )
        self._messages: list[dict] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(self, role: str, content: str) -> None:
        """Persist a single message entry."""
        entry = self._make_entry(role, content)
        self._append_jsonl(entry)
        self._write_session(entry)

    def all_messages(self) -> list[dict]:
        """Return a copy of all messages saved this session."""
        return list(self._messages)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _make_entry(self, role: str, content: str) -> dict:
        return {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "model": config.OLLAMA_MODEL,
            "role": role,
            "content": content,
        }

    def _append_jsonl(self, entry: dict) -> None:
        try:
            with open(config.CHAT_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _write_session(self, entry: dict) -> None:
        self._messages.append(entry)
        try:
            with open(self.session_file, "w", encoding="utf-8") as f:
                json.dump(
                    {"session_id": self.session_id, "messages": self._messages},
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
        except OSError:
            pass
