from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QDialogButtonBox,
    QScrollArea,
    QWidget,
)

from app.app_state.settings_state import SettingsState
from app.ui.pages.settings_page import SettingsPage
from app.core.utils.app_logger import get_logger

_log = get_logger("ui.settings_dialog")


class SettingsDialog(QDialog):
    """Modal dialog wrapping SettingsPage with a scrollable content area."""

    def __init__(self, settings_state: SettingsState, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(640, 720)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(0)

        # Wrap SettingsPage in a scroll area so it doesn't get cut off
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        self.settings_page = SettingsPage(settings_state)
        scroll.setWidget(self.settings_page)
        layout.addWidget(scroll, 1)

        # Close button at bottom
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.setContentsMargins(8, 0, 8, 0)
        btn_box.rejected.connect(self.close)
        layout.addWidget(btn_box)

        _log.debug("SettingsDialog created")
