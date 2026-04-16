from typing import Optional

from app.core.ai.context.context_provider import AppContextProvider


class AppStateContextProvider(AppContextProvider):
    """Provides AI context from current application settings state."""

    def __init__(self, settings_state=None):
        """Initialize with an optional SettingsState instance.

        Args:
            settings_state: Optional SettingsState; if None, defaults are used.
        """
        self._settings_state = settings_state

    def get_context(self) -> dict:
        """Return current AI settings as context.

        Returns:
            Dict with provider, selected_model, tools_enabled, active_tab.
        """
        ai = None
        if self._settings_state is not None:
            settings = getattr(self._settings_state, "current_settings", None)
            if settings is not None:
                ai = getattr(settings, "ai", None)

        return {
            "provider": getattr(ai, "provider", "") if ai is not None else "",
            "selected_model": getattr(ai, "chat_model", "") if ai is not None else "",
            "tools_enabled": getattr(ai, "tools_enabled", False) if ai is not None else False,
            "active_tab": "",
        }
