from typing import Optional

from PySide6.QtCore import QFileSystemWatcher, QObject, QTimer, Signal

from app.core.models.settings_models import AppSettings, SettingsValidationResult
from app.core.services.settings_service import SettingsService
from app.core.utils.app_logger import get_logger

_log = get_logger("settings_state")


class SettingsState(QObject):
    """Manages application settings state with Qt signals."""

    # Signals
    settings_loaded = Signal(AppSettings)
    settings_saved = Signal(AppSettings)
    settings_validated = Signal(SettingsValidationResult)
    settings_changed = Signal(AppSettings)
    ai_settings_changed = Signal(object)
    favorites_changed = Signal(list)
    # Emitted when settings.json changes on disk from an external source
    preferences_reloaded = Signal(AppSettings)

    # How long (ms) to wait after a file-change event before reloading,
    # to coalesce rapid successive writes (e.g. atomic rename + fsync).
    _FILE_RELOAD_DEBOUNCE_MS = 300
    # How long (ms) after our own save before we re-arm the watcher guard.
    _SAVE_GUARD_MS = 600

    def __init__(self):
        super().__init__()
        self.settings_service = SettingsService()
        self.current_settings: Optional[AppSettings] = None
        self.last_validation: Optional[SettingsValidationResult] = None

        # File-watching infrastructure
        self._file_watcher = QFileSystemWatcher(self)
        self._file_watcher.fileChanged.connect(self._on_settings_file_changed)

        # Debounce timer: coalesces rapid file-change events before reloading
        self._reload_debounce = QTimer(self)
        self._reload_debounce.setSingleShot(True)
        self._reload_debounce.setInterval(self._FILE_RELOAD_DEBOUNCE_MS)
        self._reload_debounce.timeout.connect(self._reload_from_disk)

        # Guard flag: True while we are writing so we ignore our own file events
        self._saving: bool = False
        self._save_guard_timer = QTimer(self)
        self._save_guard_timer.setSingleShot(True)
        self._save_guard_timer.setInterval(self._SAVE_GUARD_MS)
        self._save_guard_timer.timeout.connect(self._clear_saving_guard)

    def load_settings(self) -> AppSettings:
        """Load settings from disk."""
        self.current_settings = self.settings_service.load_settings()
        self._arm_file_watcher()
        self.settings_loaded.emit(self.current_settings)
        return self.current_settings

    def save_settings(self, settings: AppSettings) -> bool:
        """Save settings to disk."""
        ai_changed = self.current_settings is None or self.current_settings.ai != settings.ai
        # Suppress the file-change event triggered by our own write
        self._saving = True
        self._save_guard_timer.start()
        success = self.settings_service.save_settings(settings)
        if success:
            self.current_settings = settings
            self._arm_file_watcher()
            self.settings_saved.emit(settings)
            self.settings_changed.emit(settings)
            if ai_changed:
                self.ai_settings_changed.emit(settings.ai)
        return success

    def update_settings(self, **kwargs) -> AppSettings:
        """Update specific settings fields."""
        if not self.current_settings:
            self.current_settings = AppSettings()

        # Update fields
        for key, value in kwargs.items():
            if hasattr(self.current_settings, key):
                setattr(self.current_settings, key, value)

        self.settings_changed.emit(self.current_settings)
        return self.current_settings

    def update_preferences(self, section: str, **kwargs):
        """Update and save a nested preference section."""
        if not self.current_settings:
            self.current_settings = self.settings_service.load_settings()
        previous_ai = self.current_settings.ai
        # Suppress the file-change event triggered by our own write
        self._saving = True
        self._save_guard_timer.start()
        preferences = self.settings_service.update_preferences(section, **kwargs)
        self.current_settings = self.settings_service.settings
        if self.current_settings:
            self._arm_file_watcher()
            self.settings_saved.emit(self.current_settings)
            self.settings_changed.emit(self.current_settings)
            if previous_ai != self.current_settings.ai:
                self.ai_settings_changed.emit(self.current_settings.ai)
        return preferences

    def validate_current_settings(self) -> SettingsValidationResult:
        """Validate current settings."""
        if not self.current_settings:
            self.current_settings = AppSettings()

        self.last_validation = self.settings_service.validate_settings(self.current_settings)
        self.settings_validated.emit(self.last_validation)
        return self.last_validation

    def toggle_favorite_pair(self, pair: str) -> None:
        """Add pair to favorites if absent, remove if present; save and emit.

        Args:
            pair: The trading pair string to toggle (e.g. "BTC/USDT").
        """
        if not self.current_settings:
            return
        favs = list(self.current_settings.favorite_pairs)
        if pair in favs:
            favs.remove(pair)
        else:
            favs.append(pair)
        self.current_settings.favorite_pairs = favs
        self.save_settings(self.current_settings)
        self.favorites_changed.emit(favs)

    def is_valid(self) -> bool:
        """Check if current settings are valid."""
        if self.last_validation:
            return self.last_validation.valid
        return False

    # ── File-watching helpers ─────────────────────────────────────────

    def _arm_file_watcher(self) -> None:
        """Ensure the settings file is being watched (re-arm after atomic rename)."""
        path = str(self.settings_service.settings_file)
        watched = self._file_watcher.files()
        if path not in watched:
            if self.settings_service.settings_file.exists():
                self._file_watcher.addPath(path)
                _log.debug("File watcher armed for %s", path)

    def _on_settings_file_changed(self, path: str) -> None:
        """Slot called by QFileSystemWatcher when the settings file changes."""
        if self._saving:
            _log.debug("Ignoring file-change event (our own write): %s", path)
            # Re-arm in case atomic write replaced the inode
            self._arm_file_watcher()
            return
        _log.debug("External settings file change detected: %s — scheduling reload", path)
        # Re-arm watcher (atomic writes can remove the watch)
        self._arm_file_watcher()
        # Debounce: reset the timer so rapid events collapse into one reload
        self._reload_debounce.start()

    def _reload_from_disk(self) -> None:
        """Reload settings from disk and emit preferences_reloaded."""
        try:
            new_settings = self.settings_service.load_settings()
            self.current_settings = new_settings
            _log.info("Settings reloaded from disk (external change)")
            self.preferences_reloaded.emit(new_settings)
            self.settings_changed.emit(new_settings)
        except Exception as exc:
            _log.warning("Failed to reload settings from disk: %s", exc)

    def _clear_saving_guard(self) -> None:
        """Re-arm the file watcher after our own save has settled."""
        self._saving = False
        self._arm_file_watcher()
        _log.debug("Save guard cleared — file watcher re-armed")
