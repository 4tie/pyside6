from typing import Optional

from app.core.ai.context.context_provider import AppContextProvider


class BacktestContextProvider(AppContextProvider):
    """Provides AI context from the current backtest tab configuration."""

    def __init__(self, backtest_preferences=None, backtest_page=None):
        """Initialize with optional BacktestPreferences and live BacktestPage.

        Args:
            backtest_preferences: Optional BacktestPreferences for saved prefs.
            backtest_page: Optional live BacktestPage instance for current UI state.
        """
        self._prefs = backtest_preferences
        self._backtest_page = backtest_page

    def get_context(self) -> dict:
        """Return current backtest tab configuration as context.

        Returns:
            Dict with strategy, timeframe, timerange, pairs, dry_run_wallet,
            max_open_trades from the live UI if available, else from saved prefs.
        """
        # Prefer live UI state
        if self._backtest_page is not None:
            try:
                return self._backtest_page.get_current_config()
            except Exception:
                pass

        # Fall back to saved preferences
        prefs = self._prefs
        return {
            "strategy": getattr(prefs, "last_strategy", "") if prefs is not None else "",
            "timeframe": getattr(prefs, "default_timeframe", "") if prefs is not None else "",
            "timerange": getattr(prefs, "default_timerange", "") if prefs is not None else "",
            "pairs": [],
            "dry_run_wallet": getattr(prefs, "dry_run_wallet", 80.0) if prefs is not None else 80.0,
            "max_open_trades": getattr(prefs, "max_open_trades", 2) if prefs is not None else 2,
        }
