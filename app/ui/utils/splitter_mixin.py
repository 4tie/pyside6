"""SplitterStateMixin — reusable splitter state persistence for page widgets."""
from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QSplitter, QWidget

from app.core.utils.app_logger import get_logger

_log = get_logger("ui.splitter_mixin")

_QSETTINGS_ORG = "FreqtradeGUI"
_QSETTINGS_APP = "ModernUI"


class SplitterStateMixin:
    """Mixin for pages with splitters that need state persistence.

    Requires the subclass to define:
        - self._splitter: QSplitter instance
        - self._splitter_key: str for QSettings key (e.g., "splitter/backtest")
        - self._splitter_default_sizes: list[int] (e.g., [300, 900])

    Automatically saves/restores splitter state via QSettings.
    Call _restore_state() in __init__ after building UI.
    """

    _splitter: QSplitter
    _splitter_key: str
    _splitter_default_sizes: list[int]

    def _restore_state(self) -> None:
        """Restore splitter state from QSettings, falling back to default sizes."""
        qs = QSettings(_QSETTINGS_ORG, _QSETTINGS_APP)
        state = qs.value(self._splitter_key)
        if state is not None:
            restored = self._splitter.restoreState(state)
            sizes = self._splitter.sizes()
            if not restored or not sizes or sizes[0] < 100:
                self._splitter.setSizes(self._splitter_default_sizes)

    def _save_state(self) -> None:
        """Persist splitter state to QSettings."""
        qs = QSettings(_QSETTINGS_ORG, _QSETTINGS_APP)
        qs.setValue(self._splitter_key, self._splitter.saveState())

    def hideEvent(self, event) -> None:  # noqa: N802
        """Save splitter state when page is hidden."""
        self._save_state()
        # Call parent's hideEvent if available
        if hasattr(super(), "hideEvent"):
            super().hideEvent(event)  # type: ignore[misc]
