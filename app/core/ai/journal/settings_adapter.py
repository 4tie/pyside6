from app.core.ai.journal.event_journal import EventJournal
from app.core.utils.app_logger import get_logger

_log = get_logger("services.settings_adapter")


class SettingsJournalAdapter:
    """Connects SettingsState.settings_saved signal to EventJournal recording.

    Adapters import from services/state — services never import from journal.
    """

    def __init__(self, journal: EventJournal, settings_state=None) -> None:
        self._journal = journal
        if settings_state is not None:
            settings_state.settings_saved.connect(self._on_settings_saved)

    def _on_settings_saved(self, settings=None) -> None:
        """Slot connected to SettingsState.settings_saved signal."""
        _log.debug("Recording settings_saved")
        self._journal.record("settings_saved", "settings_state", {})
