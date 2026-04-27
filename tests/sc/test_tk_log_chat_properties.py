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

# Display detection — also requires tkinter to actually be importable
_HAS_DISPLAY = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY") or os.name == "nt")
try:
    import tkinter as _tk_check
    _HAS_TKINTER = True
except ImportError:
    _HAS_TKINTER = False
    _tk_stub = Mock()
    sys.modules['tkinter'] = _tk_stub
    sys.modules['tkinter.ttk'] = Mock()

_CAN_USE_TK = _HAS_DISPLAY and _HAS_TKINTER

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
    return app.chat_window.get("1.0", "end")


def _make_app():
    """Create a ChatApp with a hidden Tk root. Caller must destroy root."""
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    client = MagicMock()
    with patch.object(tlc.ChatApp, "_health_check"):
        app = tlc.ChatApp(root, client)
    return root, app


# ---------------------------------------------------------------------------
# P1 — Non-empty input echoed with "You:" prefix
# Feature: tk-log-chat, Property 1: Non-empty input is echoed to Chat_Window with "You:" prefix
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _CAN_USE_TK, reason="no display or tkinter not installed")
@given(text=st.text(min_size=1).filter(lambda s: s.strip()))
@settings(max_examples=100)
def test_p1_nonempty_input_echoed_with_you_prefix(text):
    """Validates: Requirements 2.1, 2.3"""
    root, app = _make_app()
    try:
        app.input_area.insert("1.0", text)
        app._on_send()
        content = _chat_window_text(app)
        assert "You:" in content
    finally:
        root.destroy()


# ---------------------------------------------------------------------------
# P2 — Whitespace-only input rejected
# Feature: tk-log-chat, Property 2: Whitespace-only input is rejected
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _CAN_USE_TK, reason="no display or tkinter not installed")
@given(text=st.text(alphabet=st.characters(whitelist_categories=("Zs", "Cc")), min_size=1))
@settings(max_examples=100)
def test_p2_whitespace_only_input_rejected(text):
    """Validates: Requirements 2.2"""
    assume(text.strip() == "")
    root, app = _make_app()
    try:
        app.input_area.insert("1.0", text)
        app._on_send()
        content = _chat_window_text(app)
        assert "You:" not in content
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
    """Validates: Requirements 3.1"""
    client = tlc.OllamaClient()
    captured_payload = {}

    def fake_post(url, json=None, timeout=None):
        captured_payload.update(json or {})
        return _make_mock_response(200, {"message": {"role": "assistant", "content": "ok"}})

    with patch("requests.post", side_effect=fake_post):
        client.chat(message)

    assert captured_payload.get("stream") is False
    assert captured_payload.get("model") == tlc.OLLAMA_MODEL
    messages = captured_payload.get("messages", [])
    assert messages[0]["role"] == "system"
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == message


# ---------------------------------------------------------------------------
# P4 — Full conversation history included in every request
# Feature: tk-log-chat, Property 4: Conversation history is fully included in every request
# ---------------------------------------------------------------------------

@given(
    pairs=st.lists(
        st.tuples(st.text(min_size=1), st.text(min_size=1)),
        min_size=1,
        max_size=10,
    ),
    new_msg=st.text(min_size=1),
)
@settings(max_examples=100)
def test_p4_full_history_in_every_request(pairs, new_msg):
    """Validates: Requirements 3.2"""
    client = tlc.OllamaClient()
    # Manually populate history with prior pairs
    for user_msg, asst_msg in pairs:
        client.history.append({"role": "user", "content": user_msg})
        client.history.append({"role": "assistant", "content": asst_msg})

    captured_messages = []

    def fake_post(url, json=None, timeout=None):
        captured_messages.extend(json.get("messages", []))
        return _make_mock_response(200, {"message": {"role": "assistant", "content": "reply"}})

    with patch("requests.post", side_effect=fake_post):
        client.chat(new_msg)

    # Skip system message (index 0), then check all prior pairs appear in order
    non_system = [m for m in captured_messages if m["role"] != "system"]
    for i, (user_msg, asst_msg) in enumerate(pairs):
        assert non_system[i * 2]["role"] == "user"
        assert non_system[i * 2]["content"] == user_msg
        assert non_system[i * 2 + 1]["role"] == "assistant"
        assert non_system[i * 2 + 1]["content"] == asst_msg


# ---------------------------------------------------------------------------
# P5 — Assistant content correctly extracted from any valid response
# Feature: tk-log-chat, Property 5: Assistant content is correctly extracted from any valid response
# ---------------------------------------------------------------------------

@given(content=st.text())
@settings(max_examples=100)
def test_p5_assistant_content_extracted_correctly(content):
    """Validates: Requirements 3.3"""
    client = tlc.OllamaClient()
    mock_resp = _make_mock_response(200, {"message": {"role": "assistant", "content": content}})
    with patch("requests.post", return_value=mock_resp):
        result = client.chat("any message")
    assert result == content


# ---------------------------------------------------------------------------
# P6 — Any AI_Client failure returns a string, never raises
# Feature: tk-log-chat, Property 6: Any AI_Client failure returns a string, never raises
# ---------------------------------------------------------------------------

@given(
    status_code=st.integers(min_value=400, max_value=599),
    error_msg=st.text(min_size=1),
)
@settings(max_examples=100)
def test_p6_failure_returns_string_never_raises(status_code, error_msg):
    """Validates: Requirements 3.4"""
    client = tlc.OllamaClient()

    # Test non-200 HTTP status
    mock_resp = _make_mock_response(status_code)
    with patch("requests.post", return_value=mock_resp):
        try:
            result = client.chat("msg")
        except Exception as e:
            pytest.fail(f"chat raised on HTTP {status_code}: {e}")
    assert isinstance(result, str)
    assert result

    # Test connection error
    client2 = tlc.OllamaClient()
    with patch("requests.post", side_effect=tlc.requests.exceptions.ConnectionError(error_msg)):
        try:
            result2 = client2.chat("msg")
        except Exception as e:
            pytest.fail(f"chat raised on ConnectionError: {e}")
    assert isinstance(result2, str)
    assert result2


# ---------------------------------------------------------------------------
# P7 — Assistant reply echoed with "AI:" prefix
# Feature: tk-log-chat, Property 7: Assistant reply is echoed to Chat_Window with "AI:" prefix
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _CAN_USE_TK, reason="no display or tkinter not installed")
@given(reply=st.text(min_size=1))
@settings(max_examples=100)
def test_p7_assistant_reply_echoed_with_ai_prefix(reply):
    """Validates: Requirements 4.1"""
    root, app = _make_app()
    try:
        app._on_response(reply)
        content = _chat_window_text(app)
        assert "AI:" in content
    finally:
        root.destroy()


# ---------------------------------------------------------------------------
# P8 — Health check failure shows attempted URL
# Feature: tk-log-chat, Property 8: Health check failure always shows a warning containing the attempted URL
# ---------------------------------------------------------------------------

@given(base_url=st.text(min_size=1))
@settings(max_examples=100)
def test_p8_health_check_failure_shows_url(base_url):
    """Validates: Requirements 5.2"""
    client = tlc.OllamaClient()
    original_url = tlc.OLLAMA_BASE_URL
    try:
        tlc.OLLAMA_BASE_URL = base_url
        with patch("requests.get", side_effect=ConnectionError("refused")):
            ok, msg = client.health_check()
        assert ok is False
        assert base_url in msg
    finally:
        tlc.OLLAMA_BASE_URL = original_url


# ---------------------------------------------------------------------------
# P9 — Health check success shows model name
# Feature: tk-log-chat, Property 9: Health check success shows the configured model name
# ---------------------------------------------------------------------------

@given(model=st.text(min_size=1))
@settings(max_examples=100)
def test_p9_health_check_success_shows_model_name(model):
    """Validates: Requirements 5.3"""
    client = tlc.OllamaClient()
    original_model = tlc.OLLAMA_MODEL
    try:
        tlc.OLLAMA_MODEL = model
        mock_resp = _make_mock_response(200)
        with patch("requests.get", return_value=mock_resp):
            ok, msg = client.health_check()
        assert ok is True
        assert model in msg
    finally:
        tlc.OLLAMA_MODEL = original_model


# ---------------------------------------------------------------------------
# P10 — Environment variable fallback correctness
# Feature: tk-log-chat, Property 10: Environment variable fallback correctness
# ---------------------------------------------------------------------------

@given(
    url=st.one_of(st.none(), st.text(min_size=1, alphabet=st.characters(blacklist_characters='\x00'))),
    model=st.one_of(st.none(), st.text(min_size=1, alphabet=st.characters(blacklist_characters='\x00'))),
)
@settings(max_examples=100)
def test_p10_env_var_fallback_correctness(url, model):
    """Validates: Requirements 6.2"""
    env_patch = {}
    if url is not None:
        env_patch["OLLAMA_BASE_URL"] = url
    if model is not None:
        env_patch["OLLAMA_MODEL"] = model

    # Build a clean env without the two keys, then add back only what we want
    clean_env = {k: v for k, v in os.environ.items()
                 if k not in ("OLLAMA_BASE_URL", "OLLAMA_MODEL")}
    clean_env.update(env_patch)

    with patch.dict(os.environ, clean_env, clear=True):
        with patch("dotenv.load_dotenv"):
            tlc.load_env()

    expected_url = url if url is not None else "http://localhost:11434"
    expected_model = model if model is not None else "llama3"

    assert tlc.OLLAMA_BASE_URL == expected_url
    assert tlc.OLLAMA_MODEL == expected_model
