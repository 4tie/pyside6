"""
tk_log_chat.py — Standalone Tkinter chat app for explaining error messages and log output
using a local Ollama AI model.

Usage:
    python sc/tk_log_chat.py

Dependencies: requests, python-dotenv (both in project requirements.txt)
"""

import os
import json
import threading
import tkinter as tk
from tkinter import ttk
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Module-level configuration (populated by load_env())
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL: str = "http://localhost:11434"
OLLAMA_MODEL: str = "llama3"

SYSTEM_PROMPT = (
    "You are a senior developer. Explain the following error or log output in plain "
    "language and provide numbered fix steps."
)

# Storage paths
CHAT_DATA_DIR = Path("data/chat_history")
CHAT_LOG_FILE = CHAT_DATA_DIR / "conversations.jsonl"
CHAT_SESSIONS_DIR = CHAT_DATA_DIR / "sessions"


def load_env() -> None:
    """Load .env file (if python-dotenv is available) and read config into module globals."""
    global OLLAMA_BASE_URL, OLLAMA_MODEL

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")


def ensure_data_dirs() -> None:
    """Create chat history directories if they don't exist."""
    CHAT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    CHAT_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# OllamaClient
# ---------------------------------------------------------------------------

class MessageStore:
    """Persists chat messages to disk in JSONL + per-session JSON formats."""

    def __init__(self) -> None:
        ensure_data_dirs()
        self.session_id: str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_file: Path = CHAT_SESSIONS_DIR / f"session_{self.session_id}.json"
        self._session_messages: list[dict] = []

    def save(self, role: str, content: str) -> None:
        """Append a message to both the global log and the session file."""
        entry = {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "model": OLLAMA_MODEL,
            "role": role,
            "content": content,
        }
        try:
            with open(CHAT_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            pass

        self._session_messages.append(entry)
        try:
            with open(self.session_file, "w", encoding="utf-8") as f:
                json.dump(
                    {"session_id": self.session_id, "messages": self._session_messages},
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
        except OSError:
            pass


class OllamaClient:
    def __init__(self) -> None:
        self.history: list[dict] = []
        self.store = MessageStore()

    def health_check(self) -> tuple[bool, str]:
        """GET {OLLAMA_BASE_URL}/api/tags. Returns (ok, message). Never raises."""
        if requests is None:
            return False, f"Cannot reach Ollama at {OLLAMA_BASE_URL}: 'requests' library not installed"
        try:
            resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
            if resp.status_code == 200:
                return True, f"Connected to Ollama. Model: {OLLAMA_MODEL}"
            return False, f"Cannot reach Ollama at {OLLAMA_BASE_URL}: HTTP {resp.status_code}"
        except Exception as exc:
            return False, f"Cannot reach Ollama at {OLLAMA_BASE_URL}: {exc}"

    def chat(self, user_message: str) -> str:
        """
        Append user_message to history, POST /api/chat with full history,
        append assistant reply to history, return reply string.
        On any error return a human-readable error string without raising.
        """
        if requests is None:
            return "Error: 'requests' library is not installed."

        self.history.append({"role": "user", "content": user_message})
        self.store.save("user", user_message)

        payload = {
            "model": OLLAMA_MODEL,
            "stream": False,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + self.history,
        }

        try:
            resp = requests.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json=payload,
                timeout=120,
            )
            if resp.status_code != 200:
                return f"Error: Ollama returned HTTP {resp.status_code}."
            data = resp.json()
            reply: str = data["message"]["content"]
            self.history.append({"role": "assistant", "content": reply})
            self.store.save("assistant", reply)
            return reply
        except requests.exceptions.ConnectionError as exc:
            return f"Error: Cannot connect to Ollama at {OLLAMA_BASE_URL}: {exc}"
        except requests.exceptions.Timeout:
            return f"Error: Request to Ollama timed out ({OLLAMA_BASE_URL})."
        except (KeyError, ValueError) as exc:
            return f"Error: Unexpected response format from Ollama: {exc}"
        except Exception as exc:
            return f"Error: {exc}"


# ---------------------------------------------------------------------------
# ChatApp
# ---------------------------------------------------------------------------

class ChatApp:
    def __init__(self, root: tk.Tk, client: OllamaClient) -> None:
        self.root = root
        self.client = client
        self._build_ui()
        threading.Thread(target=self._health_check, daemon=True).start()

    def _build_ui(self) -> None:
        self.root.title("4tie — Log & Error Chat")
        self.root.minsize(700, 500)

        # --- Top frame: Chat_Window + scrollbar ---
        top_frame = tk.Frame(self.root)
        top_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=(6, 0))

        scrollbar = tk.Scrollbar(top_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.chat_window = tk.Text(
            top_frame,
            state=tk.DISABLED,
            wrap=tk.WORD,
            yscrollcommand=scrollbar.set,
        )
        self.chat_window.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.chat_window.yview)

        # Color tags
        self.chat_window.tag_configure("user", foreground="#1a73e8")
        self.chat_window.tag_configure("ai", foreground="#2e7d32")
        self.chat_window.tag_configure("system", foreground="#757575")

        # --- Bottom frame: Input_Area + Send_Button ---
        bottom_frame = tk.Frame(self.root)
        bottom_frame.pack(fill=tk.X, padx=6, pady=(4, 0))

        self.input_area = tk.Text(bottom_frame, height=5, wrap=tk.WORD)
        self.input_area.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.send_button = ttk.Button(bottom_frame, text="Send", command=self._on_send)
        self.send_button.pack(side=tk.RIGHT, padx=(6, 0))

        self.input_area.bind("<Control-Return>", self._on_send)

        # --- Status bar ---
        session_path = str(self.client.store.session_file)
        self._status_var = tk.StringVar(value=f"Session: {session_path}")
        status_bar = tk.Label(
            self.root,
            textvariable=self._status_var,
            anchor="w",
            fg="#888888",
            font=("TkDefaultFont", 8),
        )
        status_bar.pack(fill=tk.X, padx=6, pady=(2, 4))

    def _append_message(self, role: str, text: str) -> None:
        label_map = {"user": "You", "ai": "AI", "system": "System"}
        label = label_map.get(role, role.capitalize())

        self.chat_window.config(state=tk.NORMAL)
        self.chat_window.insert(tk.END, f"{label}: {text}\n\n", role)
        self.chat_window.config(state=tk.DISABLED)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self) -> None:
        self.chat_window.yview(tk.END)

    def _health_check(self) -> None:
        ok, msg = self.client.health_check()
        self.root.after(0, lambda: self._append_message("system", msg))

    def _on_send(self, event=None):
        text = self.input_area.get("1.0", tk.END).strip()
        if not text:
            self.input_area.focus_set()
            return "break"

        self._append_message("user", text)
        self.input_area.delete("1.0", tk.END)
        self.send_button.config(state=tk.DISABLED)
        self._append_message("system", "Thinking…")

        threading.Thread(
            target=self._do_chat,
            args=(text,),
            daemon=True,
        ).start()
        return "break"

    def _do_chat(self, message: str) -> None:
        reply = self.client.chat(message)
        self.root.after(0, lambda: self._on_response(reply))

    def _on_response(self, reply: str) -> None:
        self._remove_thinking()
        self._append_message("ai", reply)
        self.send_button.config(state=tk.NORMAL)

    def _remove_thinking(self) -> None:
        pos = self.chat_window.search("Thinking…", "1.0", tk.END)
        if pos:
            self.chat_window.config(state=tk.NORMAL)
            line_start = f"{pos.split('.')[0]}.0"
            line_end = f"{pos.split('.')[0]}.end+1c"
            # Delete the line and the following blank line if present
            next_line = f"{int(pos.split('.')[0]) + 1}.0"
            next_line_end = f"{int(pos.split('.')[0]) + 1}.end+1c"
            # Remove "System: Thinking…\n\n" (two lines)
            self.chat_window.delete(line_start, next_line_end)
            self.chat_window.config(state=tk.DISABLED)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    load_env()
    ensure_data_dirs()
    root = tk.Tk()
    app = ChatApp(root, OllamaClient())
    root.mainloop()
