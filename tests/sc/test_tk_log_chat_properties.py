"""
Property-based tests for sc/tk_log_chat.py using Hypothesis.
"""
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

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


def _make_app():
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    with patch.object(tlc.ChatApp, "_health_check"):
        app = tlc.ChatApp(root, MagicMock())
    return root, app


# ---------------------------------------------------------------------------
# P1 — Non-empty input echoed with "You:" prefix
# Feature: tk-log-chat, Property 1: Non-empty input is echoed to Chat_Window with "You:" prefix
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _CAN_USE_TK, reason="no display or tkinter not installed")
@given(text=st.text(min_size=1).filter(lambda s: s.strip()))
@settings(max_examples=100)
def test_p1_nonempty_input_echoed_with_you_prefix(text):
    root, app = _make_app()
    try:
        app.input_area.insert("1.0", text)
        app._on_send()
        assert "You:" in app.chat_window.get("1.0", "end")
    finally:
        root.destroy()


# ---------------------------------------------------------------------------
# P2 — Whitespace-only input rejected
# Feature: tk-log-chat, Property 2: Whitespace-only input is rejected
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _CAN_USE_TK, reason="no display or tkinter not installed")
@given(text=st.text(alphabet=st.characters(whitelist_categories=("Zs", "Cc")), min_size=1))
@settings(max_examples=100)
def test_p2_whitespace_only_rejected(text):
    assume(text.strip() == "")
    root, app = _make_app()
    try:
        app.input_area.insert("1.0", text)
        app._on_send()
        assert "You:" not in app.chat_window.get("1.0", "end")
        app.client.chat.assert_not_called()
    finally:
        root.destroy()


# ---------------------------------------------------------------------------
# P3 — POST payload well-formed for any user message
# Feature: tk-log-chat, Property 3: POST payload is well-formed for any user message
# ---------------------------------------------------------------------------

@given(message=st.text(min_size=1).filter(lambda s: s.strip()))
@settings(max_examples=100)
def test_p3_post_payload_well_formed(message):
    client = tlc.OllamaClient()
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured.update(json or {})
        return _make_mock_response(200, {"message": {"role": "assistant", "content": "ok"}})

    with patch("requests.post", side_effect=fake_post):
        client.chat(message)

    assert captured.get("stream") is False
    assert captured.get("model") == tlc.OLLAMA_MODEL
    msgs = captured.get("messages", [])
    assert msgs[0]["role"] == "system"
    assert msgs[-1]["role"] == "user"
    assert msgs[-1]["content"] == message


# ---------------------------------------------------------------------------
# P4 — Full conversation history included in every request
# Feature: tk-log-chat, Property 4: Conversation history is fully included in every request
# ---------------------------------------------------------------------------

@given(
    pairs=st.lists(st.tuples(st.text(min_size=1), st.text(min_size=1)), min_size=1, max_size=10),
    new_msg=st.text(min_size=1),
)
@settings(max_examples=100)
def test_p4_full_history_in_every_request(pairs, new_msg):
    client = tlc.OllamaClient()
    for u, a in pairs:
        client.history.append({"role": "user", "content": u})
        client.history.append({"role": "assistant", "content": a})

    captured_msgs = []

    def fake_post(url, json=None, timeout=None):
        captured_msgs.extend(json.get("messages", []))
        return _make_mock_response(200, {"message": {"role": "assistant", "content": "reply"}})

    with patch("requests.post", side_effect=fake_post):
        client.chat(new_msg)

    non_system = [m for m in captured_msgs if m["role"] != "system"]
    for i, (u, a) in enumerate(pairs):
        assert non_system[i * 2]["content"] == u
        assert non_system[i * 2 + 1]["content"] == a


# ---------------------------------------------------------------------------
# P5 — Assistant content correctly extracted from any valid response
# Feature: tk-log-chat, Property 5: Assistant content is correctly extracted from any valid response
# ---------------------------------------------------------------------------

@given(content=st.text())
@settings(max_examples=100)
def test_p5_assistant_content_extracted(content):
    client = tlc.OllamaClient()
    resp = _make_mock_response(200, {"message": {"role": "assistant", "content": content}})
    with patch("requests.post", return_value=resp):
        assert client.chat("msg") == content


# ---------------------------------------------------------------------------
# P6 — Any AI_Client failure returns a string, never raises
# Feature: tk-log-chat, Property 6: Any AI_Client failure returns a string, never raises
# ---------------------------------------------------------------------------

@given(status_code=st.integers(min_value=400, max_value=599))
@settings(max_examples=100)
def test_p6_failure_returns_string_never_raises(status_code):
    client = tlc.OllamaClient()
    with patch("requests.post", return_value=_make_mock_response(status_code)):
        try:
            result = client.chat("msg")
        except Exception as e:
            pytest.fail(f"chat raised on HTTP {status_code}: {e}")
    assert isinstance(result, str) and result


# ---------------------------------------------------------------------------
# P7 — Assistant reply echoed with "AI:" prefix
# Feature: tk-log-chat, Property 7: Assistant reply is echoed to Chat_Window with "AI:" prefix
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _CAN_USE_TK, reason="no display or tkinter not installed")
@given(reply=st.text(min_size=1))
@settings(max_examples=100)
def test_p7_assistant_reply_echoed_with_ai_prefix(reply):
    root, app = _make_app()
    try:
        app._on_response(reply)
        assert "AI:" in app.chat_window.get("1.0", "end")
    finally:
        root.destroy()


# ---------------------------------------------------------------------------
# P8 — Health check failure shows attempted URL
# Feature: tk-log-chat, Property 8: Health check failure always shows a warning containing the attempted URL
# ---------------------------------------------------------------------------

@given(base_url=st.text(min_size=1))
@settings(max_examples=100)
def test_p8_health_check_failure_shows_url(base_url):
    client = tlc.OllamaClient()
    original = tlc.OLLAMA_BASE_URL
    try:
        tlc.OLLAMA_BASE_URL = base_url
        with patch("requests.get", side_effect=ConnectionError("refused")):
            ok, msg = client.health_check()
        assert ok is False
        assert base_url in msg
    finally:
        tlc.OLLAMA_BASE_URL = original


# ---------------------------------------------------------------------------
# P9 — Health check success shows model name
# Feature: tk-log-chat, Property 9: Health check success shows the configured model name
# ---------------------------------------------------------------------------

@given(model=st.text(min_size=1))
@settings(max_examples=100)
def test_p9_health_check_success_shows_model(model):
    client = tlc.OllamaClient()
    original = tlc.OLLAMA_MODEL
    try:
        tlc.OLLAMA_MODEL = model
        with patch("requests.get", return_value=_make_mock_response(200)):
            ok, msg = client.health_check()
        assert ok is True
        assert model in msg
    finally:
        tlc.OLLAMA_MODEL = original


# ---------------------------------------------------------------------------
# P10 — Environment variable fallback correctness
# Feature: tk-log-chat, Property 10: Environment variable fallback correctness
# ---------------------------------------------------------------------------

_safe_str = st.text(
    min_size=1,
    alphabet=st.characters(blacklist_characters="\x00"),
)


@given(url=st.one_of(st.none(), _safe_str), model=st.one_of(st.none(), _safe_str))
@settings(max_examples=100)
def test_p10_env_var_fallback(url, model):
    env = {k: v for k, v in os.environ.items() if k not in ("OLLAMA_BASE_URL", "OLLAMA_MODEL")}
    if url is not None:
        env["OLLAMA_BASE_URL"] = url
    if model is not None:
        env["OLLAMA_MODEL"] = model

    with patch.dict(os.environ, env, clear=True):
        with patch("dotenv.load_dotenv"):
            tlc.load_env()

    assert tlc.OLLAMA_BASE_URL == (url if url is not None else "http://localhost:11434")
    assert tlc.OLLAMA_MODEL == (model if model is not None else "llama3")
