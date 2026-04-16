"""AIService — single integration point for the AI subsystem.

Wires together EventJournal, ToolRegistry, context providers, journal
adapters, and ConversationRuntime into one cohesive service.
"""
from __future__ import annotations

from typing import List, Optional

from app.core.ai.context.app_state_context import AppStateContextProvider
from app.core.ai.context.backtest_context import BacktestContextProvider
from app.core.ai.context.context_provider import AppContextProvider
from app.core.ai.context.strategy_context import StrategyContextProvider
from app.core.ai.journal.backtest_adapter import BacktestJournalAdapter
from app.core.ai.journal.event_journal import EventJournal
from app.core.ai.journal.settings_adapter import SettingsJournalAdapter
from app.core.ai.runtime.agent_policy import default_policy
from app.core.ai.runtime.conversation_runtime import ConversationRuntime
from app.core.ai.tools.app_tools import register_app_tools
from app.core.ai.tools.backtest_tools import register_backtest_tools
from app.core.ai.tools.strategy_tools import register_strategy_tools
from app.core.ai.tools.tool_registry import ToolRegistry
from app.core.models.settings_models import AISettings
from app.core.utils.app_logger import get_logger

_log = get_logger("services.ai_service")


class AIService:
    """Wires the full AI subsystem and exposes a ready-to-use runtime factory.

    Args:
        settings_state: The application :class:`SettingsState` instance.
    """

    def __init__(self, settings_state=None) -> None:
        self._settings_state = settings_state

        # Shared journal — records backtest and settings events
        self.journal: EventJournal = EventJournal()

        # Journal adapters — connect signals to journal recording
        self.settings_adapter = SettingsJournalAdapter(
            self.journal, settings_state
        )
        self.backtest_adapter = BacktestJournalAdapter(self.journal)

        _log.info("AIService initialised")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def connect_backtest_service(self, backtest_service) -> None:
        """Wire the BacktestJournalAdapter to a BacktestService instance.

        Args:
            backtest_service: Service with ``process_started`` /
                ``process_finished`` signals.
        """
        self.backtest_adapter._connect(backtest_service)
        _log.debug("BacktestJournalAdapter connected to BacktestService")

    def get_runtime(self, ai_settings: Optional[AISettings] = None) -> ConversationRuntime:
        """Build and return a fully wired :class:`ConversationRuntime`.

        Creates a fresh :class:`ToolRegistry` with all tools registered and
        assembles the three context providers.  A new runtime is returned on
        every call so that settings changes are fully applied.

        Args:
            ai_settings: AI configuration to use.  Falls back to current
                settings from ``settings_state``, then to defaults.

        Returns:
            A :class:`ConversationRuntime` ready to send messages.
        """
        if ai_settings is None:
            if self._settings_state is not None:
                s = self._settings_state.current_settings
                ai_settings = s.ai if s else AISettings()
            else:
                ai_settings = AISettings()

        settings = None
        if self._settings_state is not None:
            settings = self._settings_state.current_settings

        # Build tool registry
        registry = ToolRegistry()
        register_app_tools(registry, settings=settings, event_journal=self.journal)
        register_backtest_tools(registry, settings=settings)
        register_strategy_tools(registry, settings=settings)
        _log.debug("ToolRegistry built with %d tools", len(registry._tools))

        # Build context providers
        backtest_prefs = (
            settings.backtest_preferences if settings else None
        )
        context_providers: List[AppContextProvider] = [
            AppStateContextProvider(self._settings_state),
            BacktestContextProvider(backtest_prefs),
            StrategyContextProvider(),
        ]

        runtime = ConversationRuntime(
            ai_settings=ai_settings,
            agent_policy=default_policy(),
            tool_registry=registry,
            context_providers=context_providers,
        )
        _log.info(
            "ConversationRuntime created: provider=%s model=%s tools=%s",
            ai_settings.provider,
            ai_settings.chat_model,
            ai_settings.tools_enabled,
        )
        return runtime
