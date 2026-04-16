from typing import Optional

from app.core.ai.context.context_provider import AppContextProvider


class BacktestContextProvider(AppContextProvider):
    """Provides AI context from the last backtest run preferences."""

    def __init__(self, backtest_preferences=None):
        """Initialize with an optional BacktestPreferences instance.

        Args:
            backtest_preferences: Optional BacktestPreferences; if None, defaults are used.
        """
        self._prefs = backtest_preferences

    def get_context(self) -> dict:
        """Return last backtest run info as context.

        Returns:
            Dict with last_strategy, last_timeframe, last_timerange,
            last_exit_code, last_result_summary.
        """
        prefs = self._prefs
        return {
            "last_strategy": getattr(prefs, "last_strategy", "") if prefs is not None else "",
            "last_timeframe": getattr(prefs, "default_timeframe", "") if prefs is not None else "",
            "last_timerange": getattr(prefs, "default_timerange", "") if prefs is not None else "",
            "last_exit_code": None,
            "last_result_summary": "",
        }
