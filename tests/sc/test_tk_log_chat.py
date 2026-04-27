"""
Unit tests for sc/tk_log_chat.py
"""
import os
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock

import pytest

# Display detection — also requires tkinter to actually be importable
_HAS_DISPLAY = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY") or os.name == "nt")

# Check for real tkinter BEFORE any mocking
def _check_real_tkinter():
    """Return True only if the real tkinter C extension is available."""
    try:
        import _tkinter  # noqa: F401 — the C extension that backs tkinter
        return True
    except ImportError:
        return False

_HAS_TKINTER = _check_real_tkinter()
_CAN_USE_TK = _HAS_DISPLAY and _HAS_TKINTER

# Stub tkinter so sc/tk_log_chat.py can be imported for non-UI tests
if not _HAS_TKINTER:
    _tk_stub = Mock()
    sys.modules.setdefault('tkinter', _tk_stub)
    sys.modules.setdefault('tkinter.ttk', Mock())

# Ensure sc/ is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import sc.tk_log_chat as tlc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_response(status_code: int, json_data=None):
    mock = MagicMock()
    mock.status_code = status_code
    if json_data is not None:
        mock.json.return_value = json_data
    return mock


def _chat_window_text(app) -> str:
    """Read all text from the chat_window widget."""
    return app.chat_window.get("1.0", "end")


# ---------------------------------------------------------------------------
# 4.1  OllamaClient.health_check
# ---------------------------------------------------------------------------

class TestHealthCheck:
    def test_200_returns_true_and_connected_message(self):
        client = tlc.OllamaClient()
        mock_resp = _make_mock_response(200)
        with patch("requests.get", return_value=mock_resp):
            ok, msg = client.health_check()
        assert ok is True
        assert "Connected" in msg

    def test_connection_error_returns_false_with_url(self):
        client = tlc.OllamaClient()
        url = tlc.OLLAMA_BASE_URL
        with patch("requests.get", side_effect=ConnectionError("refused")):
            ok, msg = client.health_check()
        assert ok is False
        assert url in msg

    def test_non_200_returns_false(self):
        client = tlc.OllamaClient()
        mock_resp = _make_mock_response(503)
        with patch("requests.get", return_value=mock_resp):
            ok, msg = client.health_check()
        assert ok is False

    def test_never_raises_on_any_error(self):
        client = tlc.OllamaClient()
        for exc in [ConnectionError("x"), OSError("y"), RuntimeError("z")]:
            with patch("requests.get", side_effect=exc):
                try:
                    client.health_check()
                except Exception as e:
                    pytest.fail(f"health_check raised unexpectedly: {e}")


# ---------------------------------------------------------------------------
# 4.2  OllamaClient.chat
# ---------------------------------------------------------------------------

class TestOllamaClientChat:
    def test_200_returns_assistant_content(self):
        client = tlc.OllamaClient()
        mock_resp = _make_mock_response(200, {"message": {"role": "assistant", "content": "Hello!"}})
        with patch("requests.post", return_value=mock_resp):
            result = client.chat("hi")
        assert result == "Hello!"

    def test_connection_error_returns_error_string(self):
        client = tlc.OllamaClient()
        with patch("requests.post", side_effect=tlc.requests.exceptions.ConnectionError("refused")):
            result = client.chat("hi")
        assert isinstance(result, str)
        assert result  # non-empty

    def test_connection_error_does_not_raise(self):
        client = tlc.OllamaClient()
        with patch("requests.post", side_effect=tlc.requests.exceptions.ConnectionError("x")):
            try:
                client.chat("hi")
            except Exception as e:
                pytest.fail(f"chat raised unexpectedly: {e}")

    def test_500_returns_error_string(self):
        client = tlc.OllamaClient()
        mock_resp = _make_mock_response(500)
        with patch("requests.post", return_value=mock_resp):
            result = client.chat("hi")
        assert isinstance(result, str)
        assert result

    def test_malformed_json_missing_message_key_returns_error_string(self):
        client = tlc.OllamaClient()
        mock_resp = _make_mock_response(200, {"unexpected": "data"})
        with patch("requests.post", return_value=mock_resp):
            result = client.chat("hi")
        assert isinstance(result, str)
        assert result

    def test_history_updated_after_successful_chat(self):
        client = tlc.OllamaClient()
        mock_resp = _make_mock_response(200, {"message": {"role": "assistant", "content": "Reply"}})
        with patch("requests.post", return_value=mock_resp):
            client.chat("Hello")
        assert len(client.history) == 2
        assert client.history[0] == {"role": "user", "content": "Hello"}
        assert client.history[1] == {"role": "assistant", "content": "Reply"}


# ---------------------------------------------------------------------------
# 4.3  ChatApp._on_send
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _CAN_USE_TK, reason="no display or tkinter not installed")
class TestOnSend:
    def setup_method(self):
        import tkinter as tk
        self.root = tk.Tk()
        self.root.withdraw()
        self.client = MagicMock()
        with patch.object(tlc.ChatApp, "_health_check"):
            self.app = tlc.ChatApp(self.root, self.client)

    def teardown_method(self):
        self.root.destroy()

    def test_empty_input_does_not_change_chat_window(self):
        before = _chat_window_text(self.app)
        self.app._on_send()
        after = _chat_window_text(self.app)
        assert before == after

    def test_empty_input_makes_no_http_call(self):
        self.app._on_send()
        self.client.chat.assert_not_called()

    def test_whitespace_only_does_not_change_chat_window(self):
        self.app.input_area.insert("1.0", "   \n\t  ")
        before = _chat_window_text(self.app)
        self.app._on_send()
        after = _chat_window_text(self.app)
        # Chat window should not have gained a "You:" line
        assert "You:" not in after

    def test_whitespace_only_makes_no_http_call(self):
        self.app.input_area.insert("1.0", "   \n\t  ")
        self.app._on_send()
        self.client.chat.assert_not_called()

    def test_valid_text_appears_in_chat_window_with_you_prefix(self):
        self.app.input_area.insert("1.0", "some error log")
        self.app._on_send()
        content = _chat_window_text(self.app)
        assert "You:" in content

    def test_valid_text_clears_input_area(self):
        self.app.input_area.insert("1.0", "some error log")
        self.app._on_send()
        remaining = self.app.input_area.get("1.0", "end").strip()
        assert remaining == ""

    def test_valid_text_disables_send_button(self):
        import tkinter as tk
        self.app.input_area.insert("1.0", "some error log")
        self.app._on_send()
        assert str(self.app.send_button["state"]) == "disabled"


# ---------------------------------------------------------------------------
# 4.4  ChatApp._on_response
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _CAN_USE_TK, reason="no display or tkinter not installed")
class TestOnResponse:
    def setup_method(self):
        import tkinter as tk
        self.root = tk.Tk()
        self.root.withdraw()
        self.client = MagicMock()
        with patch.object(tlc.ChatApp, "_health_check"):
            self.app = tlc.ChatApp(self.root, self.client)
        # Simulate a send so Thinking… is present and button is disabled
        self.app.input_area.insert("1.0", "test message")
        self.app._on_send()

    def teardown_method(self):
        self.root.destroy()

    def test_send_button_re_enabled(self):
        self.app._on_response("test reply")
        assert str(self.app.send_button["state"]) == "normal"

    def test_ai_prefix_in_chat_window(self):
        self.app._on_response("test reply")
        content = _chat_window_text(self.app)
        assert "AI:" in content

    def test_thinking_removed_from_chat_window(self):
        self.app._on_response("test reply")
        content = _chat_window_text(self.app)
        assert "Thinking" not in content


# ---------------------------------------------------------------------------
# 4.5  UI configuration
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _CAN_USE_TK, reason="no display or tkinter not installed")
class TestUIConfiguration:
    def setup_method(self):
        import tkinter as tk
        self.root = tk.Tk()
        self.root.withdraw()
        self.client = MagicMock()
        with patch.object(tlc.ChatApp, "_health_check"):
            self.app = tlc.ChatApp(self.root, self.client)

    def teardown_method(self):
        self.root.destroy()

    def test_window_title(self):
        assert self.root.title() == "Log & Error Chat"

    def test_minsize(self):
        w, h = self.root.minsize()
        assert w == 700
        assert h == 500

    def test_chat_window_state_is_disabled(self):
        import tkinter as tk
        assert str(self.app.chat_window["state"]) == "disabled"

    def test_ctrl_enter_binding_exists_on_input_area(self):
        bindings = self.app.input_area.bind("<Control-Return>")
        assert bindings  # non-empty string means binding exists


# ---------------------------------------------------------------------------
# 4.6  .env loading
# ---------------------------------------------------------------------------

class TestEnvLoading:
    def test_load_env_reads_custom_values(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("OLLAMA_BASE_URL=http://test:9999\nOLLAMA_MODEL=testmodel\n")

        # Remove any existing values so fallback doesn't interfere
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        monkeypatch.delenv("OLLAMA_MODEL", raising=False)

        with patch("dotenv.load_dotenv", lambda: env_file.read_text() and
                   (monkeypatch.setenv("OLLAMA_BASE_URL", "http://test:9999"),
                    monkeypatch.setenv("OLLAMA_MODEL", "testmodel"))):
            tlc.load_env()

        assert tlc.OLLAMA_BASE_URL == "http://test:9999"
        assert tlc.OLLAMA_MODEL == "testmodel"

    def test_load_env_uses_defaults_when_vars_absent(self, monkeypatch):
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        monkeypatch.delenv("OLLAMA_MODEL", raising=False)

        with patch("dotenv.load_dotenv"):
            tlc.load_env()

        assert tlc.OLLAMA_BASE_URL == "http://localhost:11434"
        assert tlc.OLLAMA_MODEL == "llama3"
