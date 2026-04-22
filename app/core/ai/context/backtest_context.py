from typing import Optional

from app.core.ai.context.context_provider import AppContextProvider


class BacktestContextProvider(AppContextProvider):
    """Provides AI context from backtest preferences."""

    def __init__(self, backtest_preferences=None):
        """Initialize with optional BacktestPreferences.

        Args:
            backtest_preferences: Optional BacktestPreferences for saved prefs.
        """
        self._prefs = backtest_preferences

    def get_context(self) -> dict:
        """Return backtest configuration as context.

        Returns:
            Dict with strategy, timeframe, timerange, pairs, dry_run_wallet,
            max_open_trades from saved preferences.
        """
        prefs = self._prefs
        return {
            "strategy": getattr(prefs, "last_strategy", "") if prefs is not None else "",
            "timeframe": getattr(prefs, "default_timeframe", "") if prefs is not None else "",
            "timerange": getattr(prefs, "default_timerange", "") if prefs is not None else "",
            "pairs": [],
            "dry_run_wallet": getattr(prefs, "dry_run_wallet", 80.0) if prefs is not None else 80.0,
            "max_open_trades": getattr(prefs, "max_open_trades", 2) if prefs is not None else 2,
        }
