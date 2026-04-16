"""Unit tests for AIWorker signals.

Verifies that token_received, response_complete, and error_occurred signals
are emitted with correct payloads.

Validates: Requirements 19.1, 19.2
"""
import sys
import threading
from unittest.mock import MagicMock

from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication

from app.core.ai.providers.provider_base import AIResponse, StreamToken
from app.core.ai.runtime.conversation_runtime import AIWorker
from app.core.models.settings_models import AISettings

# Ensure a QApplication exists for Qt-based tests
_app = QApplication.instance() or QApplication(sys.argv)

_MESSAGES = [{"role": "user", "content": "hello"}]
_MODEL = "llama3"


def _make_worker(stream_enabled: bool = True) -> AIWorker:
    """Create an AIWorker with a fresh cancel flag and settings."""
    ai_settings = AISettings(stream_enabled=stream_enabled)
    cancel_flag = threading.Event()
    mock_provider = MagicMock()
    return AIWorker(mock_provider, cancel_flag, ai_settings), mock_provider


def test_run_chat_streaming_emits_token_received():
    """stream_chat() tokens are forwarded via token_received signal."""
    worker, mock_provider = _make_worker(stream_enabled=True)

    tokens = [
        StreamToken(delta="Hello", finish_reason=None),
        StreamToken(delta=" world", finish_reason="stop"),
    ]
    mock_provider.stream_chat.return_value = iter(tokens)

    spy = QSignalSpy(worker.token_received)
    worker.run_chat(_MESSAGES, _MODEL)

    assert spy.count() == 2, f"Expected 2 token_received emissions, got {spy.count()}"
    assert spy.at(0)[0].delta == "Hello"
    assert spy.at(1)[0].delta == " world"


def test_run_chat_non_streaming_emits_response_complete():
    """Non-streaming chat() result is forwarded via response_complete signal."""
    worker, mock_provider = _make_worker(stream_enabled=False)

    expected_response = AIResponse(content="Hi there", model=_MODEL, finish_reason="stop")
    mock_provider.chat.return_value = expected_response

    spy = QSignalSpy(worker.response_complete)
    worker.run_chat(_MESSAGES, _MODEL)

    assert spy.count() == 1, f"Expected 1 response_complete emission, got {spy.count()}"
    assert spy.at(0)[0].content == "Hi there"


def test_run_chat_error_emits_error_occurred():
    """Provider exception is caught and forwarded via error_occurred signal."""
    worker, mock_provider = _make_worker(stream_enabled=True)

    mock_provider.stream_chat.side_effect = RuntimeError("connection refused")

    spy = QSignalSpy(worker.error_occurred)
    worker.run_chat(_MESSAGES, _MODEL)

    assert spy.count() == 1, f"Expected 1 error_occurred emission, got {spy.count()}"
    assert "connection refused" in spy.at(0)[0]
