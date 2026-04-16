"""Unit tests for AI context providers.

Validates: Requirements 14.2, 14.3, 14.4, 14.5
"""

import time
from unittest.mock import MagicMock

from app.core.ai.context.app_state_context import AppStateContextProvider
from app.core.ai.context.backtest_context import BacktestContextProvider
from app.core.ai.context.strategy_context import StrategyContextProvider


class TestAppStateContextProvider:
    def test_app_state_context_returns_expected_keys(self):
        provider = AppStateContextProvider(settings_state=None)
        result = provider.get_context()
        assert "provider" in result
        assert "selected_model" in result
        assert "tools_enabled" in result
        assert "active_tab" in result

    def test_app_state_context_with_settings(self):
        ai_settings = MagicMock()
        ai_settings.provider = "openrouter"
        ai_settings.chat_model = "gpt-4"
        ai_settings.tools_enabled = True

        current_settings = MagicMock()
        current_settings.ai = ai_settings

        settings_state = MagicMock()
        settings_state.current_settings = current_settings

        provider = AppStateContextProvider(settings_state=settings_state)
        result = provider.get_context()

        assert result["provider"] == "openrouter"
        assert result["selected_model"] == "gpt-4"
        assert result["tools_enabled"] is True


class TestBacktestContextProvider:
    def test_backtest_context_returns_expected_keys(self):
        provider = BacktestContextProvider(backtest_preferences=None)
        result = provider.get_context()
        assert "last_strategy" in result
        assert "last_timeframe" in result
        assert "last_timerange" in result
        assert "last_exit_code" in result
        assert "last_result_summary" in result


class TestStrategyContextProvider:
    def test_strategy_context_returns_expected_keys(self):
        provider = StrategyContextProvider()
        result = provider.get_context()
        assert "last_strategy_name" in result
        assert "last_strategy_path" in result

    def test_strategy_context_with_values(self):
        provider = StrategyContextProvider(
            strategy_name="MyStrategy",
            strategy_path="/path/to/MyStrategy.py",
        )
        result = provider.get_context()
        assert result["last_strategy_name"] == "MyStrategy"
        assert result["last_strategy_path"] == "/path/to/MyStrategy.py"


class TestProviderPerformance:
    def test_all_providers_complete_within_100ms(self):
        providers = [
            AppStateContextProvider(settings_state=None),
            BacktestContextProvider(backtest_preferences=None),
            StrategyContextProvider(),
        ]
        for provider in providers:
            start = time.perf_counter()
            provider.get_context()
            elapsed_ms = (time.perf_counter() - start) * 1000
            assert elapsed_ms < 100, (
                f"{provider.__class__.__name__}.get_context() took {elapsed_ms:.2f}ms, expected < 100ms"
            )
