"""command_palette.py — Ctrl+P command palette overlay for the Freqtrade GUI.

Provides a frameless dialog with a search input and a filtered list of
registered commands. Supports fuzzy (substring) matching.
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from app.core.utils.app_logger import get_logger
from app.ui.theme import FONT, PALETTE, SPACING

_log = get_logger("ui.command_palette")

_PALETTE_WIDTH = 500


def _fuzzy_match(query: str, label: str) -> bool:
    """Return True if every character in *query* appears in *label* in order.

    Case-insensitive substring containment is used for simplicity and speed.

    Args:
        query: The search string typed by the user.
        label: The command label to match against.

    Returns:
        True if label contains all characters of query in order.
    """
    if not query:
        return True
    q = query.lower()
    label_lower = label.lower()
    # Simple case: substring containment (covers the spec requirement)
    return q in label_lower


class CommandPalette(QDialog):
    """Ctrl+P command palette overlay with fuzzy search.

    Args:
        commands: List of command dicts, each with keys:
            - id (str): Unique command identifier.
            - label (str): Human-readable command name.
            - shortcut (str): Keyboard shortcut string (may be empty).
            - action (Callable): Zero-argument callable to invoke.
        parent: Optional parent widget used for centering.

    Signals:
        command_selected(str): Emitted with the command id when a command is executed.
    """

    command_selected = Signal(str)

    def __init__(self, commands: list[dict], parent=None) -> None:
        super().__init__(
            parent,
            Qt.FramelessWindowHint | Qt.Popup,
        )
        self.setObjectName("command_palette")
        self._commands = commands
        self._build_ui()
        self._populate_list(query="")
        self._center_on_parent()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Build the search input + results list layout."""
        self.setFixedWidth(_PALETTE_WIDTH)
        self.setMinimumHeight(300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Search input
        self._search_edit = QLineEdit()
        self._search_edit.setObjectName("command_palette_search")
        self._search_edit.setPlaceholderText("Type a command...")
        self._search_edit.setAccessibleName("Command search")
        self._search_edit.setToolTip("Type to filter commands")
        self._search_edit.setStyleSheet(
            f"font-size: {FONT['size_lg']}px;"
            f"padding: {SPACING['sm']}px {SPACING['md']}px;"
            "border: none;"
            f"border-bottom: 1px solid {PALETTE['border']};"
            "border-radius: 0;"
        )
        self._search_edit.textChanged.connect(self._on_search_changed)
        layout.addWidget(self._search_edit)

        # Results list
        self._list_widget = QListWidget()
        self._list_widget.setObjectName("command_palette_list")
        self._list_widget.setStyleSheet(
            "border: none;"
            f"font-size: {FONT['size_base']}px;"
        )
        self._list_widget.itemActivated.connect(self._on_item_activated)
        self._list_widget.itemDoubleClicked.connect(self._on_item_activated)
        layout.addWidget(self._list_widget)

        # Install key press filter on the search box to handle Enter/arrow keys
        self._search_edit.installEventFilter(self)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _populate_list(self, query: str) -> None:
        """Rebuild the list widget with commands matching *query*.

        Args:
            query: Current search string.
        """
        self._list_widget.clear()
        for cmd in self._commands:
            if _fuzzy_match(query, cmd.get("label", "")):
                shortcut = cmd.get("shortcut", "")
                display = cmd["label"]
                if shortcut:
                    display = f"{cmd['label']}    {shortcut}"
                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, cmd)
                self._list_widget.addItem(item)

        if self._list_widget.count() > 0:
            self._list_widget.setCurrentRow(0)

    def _execute_selected(self) -> None:
        """Execute the currently selected command and close the palette."""
        item = self._list_widget.currentItem()
        if item is None:
            return
        cmd = item.data(Qt.UserRole)
        if cmd is None:
            return

        cmd_id: str = cmd.get("id", "")
        action: Callable | None = cmd.get("action")

        _log.info("CommandPalette executing command: %r", cmd_id)
        self.command_selected.emit(cmd_id)
        self.accept()

        if callable(action):
            try:
                action()
            except Exception:
                _log.exception("Error executing command %r", cmd_id)

    def _center_on_parent(self) -> None:
        """Position the palette centered on the parent widget."""
        parent = self.parent()
        if parent is not None and isinstance(parent, __import__("PySide6.QtWidgets", fromlist=["QWidget"]).QWidget):
            parent_geo = parent.geometry()
            parent_center = parent.mapToGlobal(
                __import__("PySide6.QtCore", fromlist=["QPoint"]).QPoint(
                    parent_geo.width() // 2,
                    parent_geo.height() // 3,
                )
            )
            x = parent_center.x() - _PALETTE_WIDTH // 2
            y = parent_center.y()
            self.move(x, y)

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def eventFilter(self, obj, event) -> bool:  # noqa: ANN001
        """Handle keyboard navigation from the search input."""
        from PySide6.QtCore import QEvent

        if obj is self._search_edit and event.type() == QEvent.KeyPress:
            key = event.key()
            if key in (Qt.Key_Return, Qt.Key_Enter):
                self._execute_selected()
                return True
            if key == Qt.Key_Down:
                row = self._list_widget.currentRow()
                if row < self._list_widget.count() - 1:
                    self._list_widget.setCurrentRow(row + 1)
                return True
            if key == Qt.Key_Up:
                row = self._list_widget.currentRow()
                if row > 0:
                    self._list_widget.setCurrentRow(row - 1)
                return True
            if key == Qt.Key_Escape:
                self.reject()
                return True
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_search_changed(self, text: str) -> None:
        """Re-filter the list when the search text changes."""
        self._populate_list(query=text)

    def _on_item_activated(self, item: QListWidgetItem) -> None:
        """Execute the command when an item is activated (Enter or double-click)."""
        self._execute_selected()
