"""download_data_page.py — Backward-compatibility alias for download_page.

Provides DownloadDataPage as a subclass of DownloadPage so that existing
tests and code that reference the old module name continue to work.
The PairsSelectorDialog is imported here so that test patches targeting
this module's namespace work correctly.
"""
from __future__ import annotations

from app.core.utils.app_logger import get_logger
from app.ui.dialogs.pairs_selector_dialog import PairsSelectorDialog
from app.ui.pages.download_page import DownloadPage

_log = get_logger("ui.download_data_page")


class DownloadDataPage(DownloadPage):
    """Backward-compatible alias for DownloadPage.

    Overrides _on_select_pairs to use the PairsSelectorDialog imported
    in this module's namespace, so that test patches work correctly.
    """

    def _on_select_pairs(self) -> None:
        """Open PairsSelectorDialog (uses this module's namespace for patchability)."""
        settings = self._settings_state.current_settings
        favorites: list = []
        if settings is not None:
            favorites = list(settings.favorite_pairs or [])

        selected = self.run_config_form.get_config().get("pairs", [])
        dlg = PairsSelectorDialog(
            favorites=favorites,
            selected=list(selected),
            settings_state=self._settings_state,
            parent=self,
        )
        if dlg.exec():
            new_pairs = dlg.get_selected_pairs()
            self.run_config_form.set_config({"pairs": new_pairs})


__all__ = ["DownloadDataPage", "PairsSelectorDialog"]
