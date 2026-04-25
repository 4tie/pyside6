from typing import Optional

from PySide6.QtCore import QObject, Signal

from app.core.models.settings_models import AppSettings, SettingsValidationResult
from app.core.services.settings_service import SettingsService


class SettingsState(QObject):
    """Manages application settings state with Qt signals."""

    # Signals
    settings_loaded = Signal(AppSettings)
    settings_saved = Signal(AppSettings)
    settings_validated = Signal(SettingsValidationResult)
    settings_changed = Signal(AppSettings)
    ai_settings_changed = Signal(object)
    favorites_changed = Signal(list)

    def __init__(self):
        super().__init__()
        self.settings_service = SettingsService()
        self.current_settings: Optional[AppSettings] = None
        self.last_validation: Optional[SettingsValidationResult] = None

    def load_settings(self) -> AppSettings:
        """Load settings from disk."""
        self.current_settings = self.settings_service.load_settings()
        self.settings_loaded.emit(self.current_settings)
        return self.current_settings

    def save_settings(self, settings: AppSettings) -> bool:
        """Save settings to disk."""
        ai_changed = self.current_settings is None or self.current_settings.ai != settings.ai
        success = self.settings_service.save_settings(settings)
        if success:
            self.current_settings = settings
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
        preferences = self.settings_service.update_preferences(section, **kwargs)
        self.current_settings = self.settings_service.settings
        if self.current_settings:
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
