"""AiPanel — dockable AI chat panel wrapping AIChatDock.

Provides a QDockWidget that can be docked to the left or right dock areas
of the main window.  If the AIChatDock import fails (optional feature),
a placeholder label is shown instead.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QLabel, QWidget

from app.core.utils.app_logger import get_logger

_log = get_logger("ui.ai_panel")

try:
    from app.ui.widgets.ai_chat_dock import AIChatDock as _AIChatDock
    _AI_AVAILABLE = True
except Exception:  # noqa: BLE001
    _AIChatDock = None  # type: ignore[assignment,misc]
    _AI_AVAILABLE = False
    _log.warning("AIChatDock import failed — AI feature not available")


class AiPanel(QDockWidget):
    """Dockable AI chat panel wrapping AIChatDock."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("AI Assistant", parent)
        self.setAllowedAreas(
            Qt.DockWidgetArea.RightDockWidgetArea
            | Qt.DockWidgetArea.LeftDockWidgetArea
        )
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
        )

        if _AI_AVAILABLE:
            try:
                self.setWidget(_AIChatDock())
                _log.debug("AiPanel initialised with AIChatDock")
            except Exception as exc:  # noqa: BLE001
                _log.warning("Failed to instantiate AIChatDock: %s", exc)
                self.setWidget(QLabel("AI feature not available"))
        else:
            self.setWidget(QLabel("AI feature not available"))
            _log.debug("AiPanel initialised with placeholder label")
