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
        success = self.settings_service.save_settings(settings)
        if success:
            self.current_settings = settings
            self.settings_saved.emit(settings)
            self.settings_changed.emit(settings)
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

    def validate_current_settings(self) -> SettingsValidationResult:
        """Validate current settings."""
        if not self.current_settings:
            self.current_settings = AppSettings()

        self.last_validation = self.settings_service.validate_settings(self.current_settings)
        self.settings_validated.emit(self.last_validation)
        return self.last_validation

    def is_valid(self) -> bool:
        """Check if current settings are valid."""
        if self.last_validation:
            return self.last_validation.valid
        return False
