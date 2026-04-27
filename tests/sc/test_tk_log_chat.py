"""
Unit tests for sc/tk_log_chat.py
"""
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock

import pytest

# Display detection — also requires tkinter to actually be importable
_HAS_DISPLAY = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY") or os.name == "nt")


def _check_real_tkinter():
    try:
        import _tkinter  # noqa: F401
        return True
    except ImportError:
        return False


_HAS_TKINTER = _check_real_tkinter()
_CAN_USE_TK = _HAS_DISPLAY and _HAS_TKINTER

if not _HAS_TKINTER:
    sys.modules.setdefault("tkinter", Mock())
    sys.modules.setdefault("tkinter.ttk", Mock())

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import sc.tk_log_chat as tlc


def _make_mock_response(status_code: int, json_data=None):
    mock = MagicMock()
    mock.status_code = status_code
    if json_data is not None:
        mock.json.return_value = json_data
    return mock


def _chat_window_text(app) -> str:
    return app.chat_window.get("1.0", "end")


# ---------------------------------------------------------------------------
# 4.1  OllamaClient.health_check
# ---------------------------------------------------------------------------

class TestHealthCheck:
    def test_200_returns_true_and_connected_message(self):
        client = tlc.OllamaClient()
        with patch("requests.get", return_value=_make_mock_response(200)):
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
        with patch("requests.get", return_value=_make_mock_response(503)):
            ok, msg = client.health_check()
        assert ok is False

    def test_never_raises(self):
        client = tlc.OllamaClient()
        for exc in [ConnectionError("x"), OSError("y"), RuntimeError("z")]:
            with patch("requests.get", side_effect=exc):
                try:
                    client.health_check()
                except Exception as e:
                    pytest.fail(f"health_check raised: {e}")


# ---------------------------------------------------------------------------
# 4.2  OllamaClient.chat
# ---------------------------------------------------------------------------

class TestOllamaClientChat:
    def test_200_returns_assistant_content(self):
        client = tlc.OllamaClient()
        resp = _make_mock_response(200, {"message": {"role": "assistant", "content": "Hello!"}})
        with patch("requests.post", return_value=resp):
            assert client.chat("hi") == "Hello!"

    def test_connection_error_returns_string(self):
        client = tlc.OllamaClient()
        with patch("requests.post", side_effect=tlc.requests.exceptions.ConnectionError("x")):
            result = client.chat("hi")
        assert isinstance(result, str) and result

    def test_connection_error_does_not_raise(self):
        client = tlc.OllamaClient()
        with patch("requests.post", side_effect=tlc.requests.exceptions.ConnectionError("x")):
            try:
                client.chat("hi")
            except Exception as e:
                pytest.fail(f"chat raised: {e}")

    def test_500_returns_string(self):
        client = tlc.OllamaClient()
        with patch("requests.post", return_value=_make_mock_response(500)):
            result = client.chat("hi")
        assert isinstance(result, str) and result

    def test_malformed_json_returns_string(self):
        client = tlc.OllamaClient()
        resp = _make_mock_response(200, {"unexpected": "data"})
        with patch("requests.post", return_value=resp):
            result = client.chat("hi")
        assert isinstance(result, str) and result

    def test_history_updated_after_success(self):
        client = tlc.OllamaClient()
        resp = _make_mock_response(200, {"message": {"role": "assistant", "content": "Reply"}})
        with patch("requests.post", return_value=resp):
            client.chat("Hello")
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

    def test_empty_input_no_change(self):
        before = _chat_window_text(self.app)
        self.app._on_send()
        assert _chat_window_text(self.app) == before

    def test_empty_input_no_http_call(self):
        self.app._on_send()
        self.client.chat.assert_not_called()

    def test_whitespace_no_you_prefix(self):
        self.app.input_area.insert("1.0", "   \n\t  ")
        self.app._on_send()
        assert "You:" not in _chat_window_text(self.app)

    def test_whitespace_no_http_call(self):
        self.app.input_area.insert("1.0", "   \n\t  ")
        self.app._on_send()
        self.client.chat.assert_not_called()

    def test_valid_text_you_prefix_in_chat(self):
        self.app.input_area.insert("1.0", "some error log")
        self.app._on_send()
        assert "You:" in _chat_window_text(self.app)

    def test_valid_text_clears_input(self):
        self.app.input_area.insert("1.0", "some error log")
        self.app._on_send()
        assert self.app.input_area.get("1.0", "end").strip() == ""

    def test_valid_text_disables_send_button(self):
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
        self.app.input_area.insert("1.0", "test message")
        self.app._on_send()

    def teardown_method(self):
        self.root.destroy()

    def test_send_button_re_enabled(self):
        self.app._on_response("test reply")
        assert str(self.app.send_button["state"]) == "normal"

    def test_ai_prefix_in_chat(self):
        self.app._on_response("test reply")
        assert "AI:" in _chat_window_text(self.app)

    def test_thinking_removed(self):
        self.app._on_response("test reply")
        assert "Thinking" not in _chat_window_text(self.app)


# ---------------------------------------------------------------------------
# 4.5  UI configuration
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _CAN_USE_TK, reason="no display or tkinter not installed")
class TestUIConfiguration:
    def setup_method(self):
        import tkinter as tk
        self.root = tk.Tk()
        self.root.withdraw()
        with patch.object(tlc.ChatApp, "_health_check"):
            self.app = tlc.ChatApp(self.root, MagicMock())

    def teardown_method(self):
        self.root.destroy()

    def test_window_title(self):
        assert self.root.title() == "Log & Error Chat"

    def test_minsize(self):
        w, h = self.root.minsize()
        assert w == 700 and h == 500

    def test_chat_window_disabled(self):
        assert str(self.app.chat_window["state"]) == "disabled"

    def test_ctrl_enter_binding(self):
        assert self.app.input_area.bind("<Control-Return>")


# ---------------------------------------------------------------------------
# 4.6  .env loading
# ---------------------------------------------------------------------------

class TestEnvLoading:
    def test_defaults_when_vars_absent(self, monkeypatch):
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        monkeypatch.delenv("OLLAMA_MODEL", raising=False)
        with patch("dotenv.load_dotenv"):
            tlc.load_env()
        assert tlc.OLLAMA_BASE_URL == "http://localhost:11434"
        assert tlc.OLLAMA_MODEL == "llama3"

    def test_reads_env_vars(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://custom:8888")
        monkeypatch.setenv("OLLAMA_MODEL", "mistral")
        with patch("dotenv.load_dotenv"):
            tlc.load_env()
        assert tlc.OLLAMA_BASE_URL == "http://custom:8888"
        assert tlc.OLLAMA_MODEL == "mistral"
