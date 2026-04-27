"""
ui.py — Tkinter ChatApp for 4tie.

Owns all widgets. Delegates all AI/storage work to OllamaClient.
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk

from . import config
from .client import OllamaClient


class ChatApp:
    """Main application window."""

    def __init__(self, root: tk.Tk, client: OllamaClient) -> None:
        self.root = root
        self.client = client
        self._build_ui()
        self._start_health_check()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.root.title(config.APP_TITLE)
        self.root.minsize(config.WIN_MIN_W, config.WIN_MIN_H)

        self._build_chat_panel()
        self._build_input_panel()
        self._build_status_bar()

    def _build_chat_panel(self) -> None:
        frame = tk.Frame(self.root)
        frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=(6, 0))

        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.chat_window = tk.Text(
            frame,
            state=tk.DISABLED,
            wrap=tk.WORD,
            yscrollcommand=scrollbar.set,
        )
        self.chat_window.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.chat_window.yview)

        for role, color in config.COLORS.items():
            self.chat_window.tag_configure(role, foreground=color)

    def _build_input_panel(self) -> None:
        frame = tk.Frame(self.root)
        frame.pack(fill=tk.X, padx=6, pady=(4, 0))

        self.input_area = tk.Text(
            frame, height=config.INPUT_HEIGHT, wrap=tk.WORD
        )
        self.input_area.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.input_area.bind("<Control-Return>", self._on_send)

        btn_frame = tk.Frame(frame)
        btn_frame.pack(side=tk.RIGHT, padx=(6, 0))

        self.send_button = ttk.Button(
            btn_frame, text="Send", command=self._on_send
        )
        self.send_button.pack(pady=(0, 2))

        self.clear_button = ttk.Button(
            btn_frame, text="Clear", command=self._on_clear
        )
        self.clear_button.pack()

    def _build_status_bar(self) -> None:
        self._status_var = tk.StringVar(
            value=f"Session: {self.client.store.session_file}"
        )
        tk.Label(
            self.root,
            textvariable=self._status_var,
            anchor="w",
            fg="#888888",
            font=("TkDefaultFont", 8),
        ).pack(fill=tk.X, padx=6, pady=(2, 4))

    # ------------------------------------------------------------------
    # Chat flow
    # ------------------------------------------------------------------

    def _on_send(self, event=None) -> str:
        text = self.input_area.get("1.0", tk.END).strip()
        if not text:
            self.input_area.focus_set()
            return "break"

        self._append("user", text)
        self.input_area.delete("1.0", tk.END)
        self.send_button.config(state=tk.DISABLED)
        self.clear_button.config(state=tk.DISABLED)
        self._append("system", "Thinking…")

        threading.Thread(
            target=lambda: self.root.after(
                0, lambda: self._on_response(self.client.chat(text))
            ),
            daemon=True,
        ).start()
        return "break"

    def _on_response(self, reply: str) -> None:
        self._remove_thinking()
        self._append("ai", reply)
        self.send_button.config(state=tk.NORMAL)
        self.clear_button.config(state=tk.NORMAL)

    def _on_clear(self) -> None:
        """Clear the chat window and reset conversation history."""
        self.chat_window.config(state=tk.NORMAL)
        self.chat_window.delete("1.0", tk.END)
        self.chat_window.config(state=tk.DISABLED)
        self.client.reset()
        self._append("system", "Conversation cleared. New session started.")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _append(self, role: str, text: str) -> None:
        label = config.LABELS.get(role, role.capitalize())
        self.chat_window.config(state=tk.NORMAL)
        self.chat_window.insert(tk.END, f"{label}: {text}\n\n", role)
        self.chat_window.config(state=tk.DISABLED)
        self.chat_window.yview(tk.END)

    def _remove_thinking(self) -> None:
        pos = self.chat_window.search("Thinking…", "1.0", tk.END)
        if not pos:
            return
        self.chat_window.config(state=tk.NORMAL)
        line = int(pos.split(".")[0])
        self.chat_window.delete(f"{line}.0", f"{line + 1}.end+1c")
        self.chat_window.config(state=tk.DISABLED)

    def _start_health_check(self) -> None:
        def _check() -> None:
            ok, msg = self.client.health_check()
            self.root.after(0, lambda: self._append("system", msg))

        threading.Thread(target=_check, daemon=True).start()
