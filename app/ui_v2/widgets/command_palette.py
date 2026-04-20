"""CommandPalette widget for the v2 UI layer.

A frameless ``QDialog`` overlay that provides fuzzy-filtered command
search, triggered by ``Ctrl+P``.

Requirements: 11.1, 11.4
"""
from typing import Callable, Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from app.core.utils.app_logger import get_logger

_log = get_logger("ui_v2.command_palette")


def _fuzzy_match(query: str, text: str) -> bool:
    """Return ``True`` when every character of *query* appears in *text* in order.

    Case-insensitive.  An empty query matches everything.

    Args:
        query: The search string typed by the user.
        text:  The candidate string to test.

    Returns:
        ``True`` if *query* is a subsequence of *text*.
    """
    if not query:
        return True
    query = query.lower()
    text = text.lower()
    idx = 0
    for ch in text:
        if ch == query[idx]:
            idx += 1
            if idx == len(query):
                return True
    return False


class CommandPalette(QDialog):
    """Frameless command palette overlay.

    Args:
        commands: List of command dicts, each with keys:
                  ``id`` (str), ``label`` (str), ``shortcut`` (str),
                  ``action`` (Callable).
        parent:   Optional parent widget.

    Signals:
        command_selected(str): Emitted with the command ``id`` when a
                               command is executed.
    """

    command_selected = Signal(str)

    def __init__(
        self,
        commands: List[Dict],
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._commands = commands
        self._filtered: List[Dict] = list(commands)

        self.setObjectName("command_palette")
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setModal(True)
        self.setMinimumWidth(480)
        self.setMaximumWidth(640)

        self._build_ui()
        self._populate_list(self._commands)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construct the palette layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Search input
        self._search = QLineEdit()
        self._search.setPlaceholderText("Type a command…")
        self._search.setAccessibleName("Command search")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._on_search_changed)
        layout.addWidget(self._search)

        # Results list
        self._list = QListWidget()
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list.itemActivated.connect(self._on_item_activated)
        self._list.itemClicked.connect(self._on_item_activated)
        layout.addWidget(self._list)

        # Empty-state hint
        self._empty_label = QLabel("No matching commands")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setStyleSheet("color: #888; padding: 12px;")
        self._empty_label.hide()
        layout.addWidget(self._empty_label)

    def _populate_list(self, commands: List[Dict]) -> None:
        """Fill the list widget with the given command dicts.

        Args:
            commands: Filtered list of command dicts to display.
        """
        self._list.clear()
        for cmd in commands:
            label = cmd.get("label", cmd.get("id", ""))
            shortcut = cmd.get("shortcut", "")
            display = f"{label}  {shortcut}".strip() if shortcut else label
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, cmd)
            self._list.addItem(item)

        has_items = self._list.count() > 0
        self._list.setVisible(has_items)
        self._empty_label.setVisible(not has_items)

        if has_items:
            self._list.setCurrentRow(0)

        self.adjustSize()

    def _on_search_changed(self, text: str) -> None:
        """Filter the command list based on the current search text.

        Args:
            text: Current text in the search input.
        """
        self._filtered = [
            cmd for cmd in self._commands
            if _fuzzy_match(text, cmd.get("label", ""))
            or _fuzzy_match(text, cmd.get("id", ""))
        ]
        self._populate_list(self._filtered)

    def _on_item_activated(self, item: QListWidgetItem) -> None:
        """Execute the selected command and close the palette.

        Args:
            item: The activated list item.
        """
        cmd: Optional[Dict] = item.data(Qt.UserRole)
        if cmd is None:
            return
        cmd_id: str = cmd.get("id", "")
        action: Optional[Callable] = cmd.get("action")

        _log.info("CommandPalette: executing command '%s'", cmd_id)
        self.command_selected.emit(cmd_id)
        self.accept()

        if callable(action):
            try:
                action()
            except Exception as exc:
                _log.error("Command '%s' raised an exception: %s", cmd_id, exc)

    def _execute_selected(self) -> None:
        """Execute the currently highlighted item (keyboard Enter)."""
        item = self._list.currentItem()
        if item:
            self._on_item_activated(item)

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle keyboard navigation within the palette.

        Args:
            event: The key press event.
        """
        key = event.key()
        if key in (Qt.Key_Return, Qt.Key_Enter):
            self._execute_selected()
        elif key == Qt.Key_Escape:
            self.reject()
        elif key == Qt.Key_Down:
            row = self._list.currentRow()
            if row < self._list.count() - 1:
                self._list.setCurrentRow(row + 1)
        elif key == Qt.Key_Up:
            row = self._list.currentRow()
            if row > 0:
                self._list.setCurrentRow(row - 1)
        else:
            super().keyPressEvent(event)

    def showEvent(self, event) -> None:
        """Clear search and reset list when the palette is shown."""
        self._search.clear()
        self._populate_list(self._commands)
        self._search.setFocus()
        super().showEvent(event)
