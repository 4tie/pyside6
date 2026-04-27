"""
tk_log_chat.py — Entry point for 4tie.

Run from project root:
    python sc/tk_log_chat.py
"""

import sys
from pathlib import Path

# Make sc/ importable when run directly
sys.path.insert(0, str(Path(__file__).parent))

import tkinter as tk

from fourties import config
from fourties.client import OllamaClient
from fourties.ui import ChatApp


def main() -> None:
    config.load()
    config.ensure_dirs()
    root = tk.Tk()
    ChatApp(root, OllamaClient())
    root.mainloop()


if __name__ == "__main__":
    main()
