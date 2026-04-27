"""
config.py — Runtime configuration for 4tie.

All tuneable values live here. Load once at startup via load().
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------
APP_NAME = "4tie"
APP_TITLE = "4tie — Log & Error Chat"

SYSTEM_PROMPT = (
    "Your name is 4tie. You are not an AI, not a human, not a language model — "
    "you are 4tie. If anyone asks who you are or what you are, say you are 4tie. "
    "Never refer to yourself as an AI, assistant, LLM, or any other label. "
    "Just 4tie. You are a senior developer who specialises in diagnosing errors "
    "and log output. Explain issues in plain language and provide numbered fix "
    "steps. When you refer to yourself in responses, always use the name 4tie."
)

# ---------------------------------------------------------------------------
# Ollama connection
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL: str = "http://localhost:11434"
OLLAMA_MODEL: str = "llama3"
OLLAMA_TIMEOUT_HEALTH: int = 5
OLLAMA_TIMEOUT_CHAT: int = 120

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
DATA_DIR = Path("data")
CHAT_DATA_DIR = DATA_DIR / "chat_history"
CHAT_LOG_FILE = CHAT_DATA_DIR / "conversations.jsonl"
CHAT_SESSIONS_DIR = CHAT_DATA_DIR / "sessions"

# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
WIN_MIN_W = 700
WIN_MIN_H = 500
INPUT_HEIGHT = 5

COLORS = {
    "user": "#1a73e8",    # blue
    "ai": "#2e7d32",      # green
    "system": "#757575",  # grey
}

LABELS = {
    "user": "You",
    "ai": "4tie",
    "system": "System",
}


def load() -> None:
    """Read env vars (after dotenv) into module-level constants."""
    global OLLAMA_BASE_URL, OLLAMA_MODEL

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", OLLAMA_BASE_URL)
    OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", OLLAMA_MODEL)


def ensure_dirs() -> None:
    """Create required data directories."""
    CHAT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    CHAT_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
