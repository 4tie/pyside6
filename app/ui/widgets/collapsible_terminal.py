"""Collapsible terminal widget with a toggle header button."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton

from app.core.models.settings_models import TerminalPreferences
from app.core.utils.app_logger import get_logger
from app.ui.widgets.terminal_widget import TerminalWidget

_log = get_logger("ui.collapsible_terminal")


class CollapsibleTerminal(QWidget):
    """A TerminalWidget wrapped in a collapsible toggle header.

    The terminal is hidden by default. Clicking the header button toggles
    visibility. The widget exposes the inner TerminalWidget as `.terminal`
    for callers that need to call run_command() etc.

    Attributes:
        LABEL_COLLAPSED: Button label when the terminal is hidden.
        LABEL_EXPANDED: Button label when the terminal is visible.
    """

    LABEL_COLLAPSED = "Terminal Output ▶"
    LABEL_EXPANDED = "Terminal Output ▼"

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialise the collapsible terminal widget.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._expanded: bool = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._toggle_btn = QPushButton(self.LABEL_COLLAPSED)
        self._toggle_btn.clicked.connect(self.toggle)
        layout.addWidget(self._toggle_btn)

        self._terminal = TerminalWidget()
        self._terminal.setVisible(False)
        layout.addWidget(self._terminal)

        _log.debug("CollapsibleTerminal initialised (collapsed)")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def terminal(self) -> TerminalWidget:
        """The inner TerminalWidget."""
        return self._terminal

    def is_expanded(self) -> bool:
        """Return True if the terminal is currently visible.

        Returns:
            Current expanded state.
        """
        return self._expanded

    def show_terminal(self) -> None:
        """Expand the terminal (e.g. when a run starts)."""
        self._expanded = True
        self._terminal.setVisible(True)
        self._toggle_btn.setText(self.LABEL_EXPANDED)
        _log.debug("CollapsibleTerminal expanded")

    def hide_terminal(self) -> None:
        """Collapse the terminal."""
        self._expanded = False
        self._terminal.setVisible(False)
        self._toggle_btn.setText(self.LABEL_COLLAPSED)
        _log.debug("CollapsibleTerminal collapsed")

    def toggle(self) -> None:
        """Toggle visibility between expanded and collapsed."""
        if self._expanded:
            self.hide_terminal()
        else:
            self.show_terminal()

    def apply_preferences(self, prefs: TerminalPreferences) -> None:
        """Delegate terminal appearance preferences to the inner widget.

        Args:
            prefs: Terminal appearance preferences to apply.
        """
        self._terminal.apply_preferences(prefs)
