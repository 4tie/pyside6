"""
client.py — Ollama HTTP client for 4tie.

Owns conversation history and all network calls.
No Tkinter dependency — fully testable in isolation.
"""

from __future__ import annotations

try:
    import requests
    import requests.exceptions
except ImportError:
    requests = None  # type: ignore[assignment]

from . import config
from .storage import MessageStore


class OllamaClient:
    """Stateful chat client backed by a local Ollama server."""

    def __init__(self, store: MessageStore | None = None) -> None:
        self.history: list[dict] = []
        self.store: MessageStore = store or MessageStore()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def health_check(self) -> tuple[bool, str]:
        """
        GET /api/tags to verify Ollama is reachable.
        Returns (ok, human-readable message). Never raises.
        """
        if requests is None:
            return False, f"Cannot reach Ollama: 'requests' not installed."

        url = f"{config.OLLAMA_BASE_URL}/api/tags"
        try:
            resp = requests.get(url, timeout=config.OLLAMA_TIMEOUT_HEALTH)
            if resp.status_code == 200:
                return True, f"Connected to Ollama. Model: {config.OLLAMA_MODEL}"
            return False, (
                f"Cannot reach Ollama at {config.OLLAMA_BASE_URL}: "
                f"HTTP {resp.status_code}"
            )
        except Exception as exc:
            return False, f"Cannot reach Ollama at {config.OLLAMA_BASE_URL}: {exc}"

    def chat(self, user_message: str) -> str:
        """
        Send user_message to Ollama with full conversation history.
        Saves both sides to MessageStore.
        Returns the assistant reply, or a human-readable error string.
        Never raises.
        """
        if requests is None:
            return "4tie: 'requests' library is not installed."

        self.history.append({"role": "user", "content": user_message})
        self.store.save("user", user_message)

        payload = {
            "model": config.OLLAMA_MODEL,
            "stream": False,
            "messages": [
                {"role": "system", "content": config.SYSTEM_PROMPT}
            ] + self.history,
        }

        try:
            resp = requests.post(
                f"{config.OLLAMA_BASE_URL}/api/chat",
                json=payload,
                timeout=config.OLLAMA_TIMEOUT_CHAT,
            )
            if resp.status_code != 200:
                return f"4tie: Ollama returned HTTP {resp.status_code}."

            reply: str = resp.json()["message"]["content"]
            self.history.append({"role": "assistant", "content": reply})
            self.store.save("assistant", reply)
            return reply

        except requests.exceptions.ConnectionError as exc:
            return f"4tie: Cannot connect to Ollama at {config.OLLAMA_BASE_URL}: {exc}"
        except requests.exceptions.Timeout:
            return f"4tie: Request timed out ({config.OLLAMA_BASE_URL})."
        except (KeyError, ValueError) as exc:
            return f"4tie: Unexpected response format: {exc}"
        except Exception as exc:
            return f"4tie: {exc}"

    def reset(self) -> None:
        """Clear conversation history (keeps the same store/session)."""
        self.history.clear()
