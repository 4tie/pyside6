from app.core.ai.context.context_provider import AppContextProvider


class StrategyContextProvider(AppContextProvider):
    """Provides AI context about the currently active strategy."""

    def __init__(self, strategy_name: str = "", strategy_path: str = ""):
        """Initialize with optional strategy name and path.

        Args:
            strategy_name: Name of the last open strategy.
            strategy_path: File path of the last open strategy.
        """
        self._strategy_name = strategy_name
        self._strategy_path = strategy_path

    def get_context(self) -> dict:
        """Return current strategy info as context.

        Returns:
            Dict with last_strategy_name and last_strategy_path.
        """
        return {
            "last_strategy_name": self._strategy_name,
            "last_strategy_path": self._strategy_path,
        }
