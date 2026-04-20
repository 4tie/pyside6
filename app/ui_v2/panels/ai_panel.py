"""AiPanel — dockable AI chat panel wrapping AIChatDock.

Requirements: 15.1, 15.5
"""


from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget

from app.app_state.settings_state import SettingsState
from app.core.utils.app_logger import get_logger
from app.ui.widgets.ai_chat_dock import AIChatDock

_log = get_logger("ui_v2.ai_panel")


class AiPanel(QDockWidget):
    """Dockable AI chat panel that wraps :class:`AIChatDock` unchanged.

    Allowed dock areas: right and left only.
    Features: closable and movable (no floating).

    Args:
        settings_state: Application settings state passed through to
            :class:`AIChatDock`.
        parent: Optional parent widget.
        ai_service: Optional AI service instance forwarded to
            :class:`AIChatDock`.
    """

    def __init__(
        self,
        settings_state: SettingsState,
        parent=None,
        ai_service=None,
    ) -> None:
        super().__init__("AI Chat", parent)
        self.setObjectName("AiPanel")
        self.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        self.setFeatures(
            QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable
        )

        self._chat_dock = AIChatDock(
            settings_state=settings_state,
            parent=self,
            ai_service=ai_service,
        )
        # AIChatDock is itself a QDockWidget; extract its inner widget so we
        # don't nest dock widgets, which Qt does not support.
        inner = self._chat_dock.widget()
        self.setWidget(inner)

        _log.debug("AiPanel initialised (ai_service=%s)", ai_service is not None)
