from typing import List, Optional

from app.core.freqtrade.command_runner import BacktestCommand, CommandRunner
from app.core.services.settings_service import SettingsService


class BacktestService:
    """Service for building and managing backtest commands."""

    def __init__(self, settings_service: SettingsService):
        """Initialize with a SettingsService instance.

        Args:
            settings_service: SettingsService for loading settings
        """
        self.settings_service = settings_service

    def build_command(
        self,
        strategy_name: str,
        timeframe: str,
        timerange: Optional[str] = None,
        pairs: Optional[List[str]] = None,
        max_open_trades: Optional[int] = None,
        dry_run_wallet: Optional[float] = None,
        extra_flags: Optional[List[str]] = None,
    ) -> BacktestCommand:
        """Build a backtest command.

        Args:
            strategy_name: Strategy name
            timeframe: Timeframe (e.g., "5m", "1h")
            timerange: Optional timerange (e.g., "20240101-20241231")
            pairs: Optional list of pairs
            max_open_trades: Optional max open trades
            dry_run_wallet: Optional dry run wallet
            extra_flags: Optional extra flags

        Returns:
            BacktestCommand with all necessary info

        Raises:
            ValueError: If settings are invalid or incomplete
            FileNotFoundError: If strategy or config files don't exist
        """
        settings = self.settings_service.load_settings()

        return CommandRunner.build_backtest_command(
            settings=settings,
            strategy_name=strategy_name,
            timeframe=timeframe,
            timerange=timerange,
            pairs=pairs or [],
            max_open_trades=max_open_trades,
            dry_run_wallet=dry_run_wallet,
            extra_flags=extra_flags or [],
        )

    def get_available_strategies(self) -> List[str]:
        """Get list of available strategies from user_data/strategies/.

        Returns:
            List of strategy names (without .py extension)
        """
        from pathlib import Path

        settings = self.settings_service.load_settings()
        if not settings.user_data_path:
            return []

        strategies_dir = Path(settings.user_data_path) / "strategies"
        if not strategies_dir.exists():
            return []

        strategies = [
            f.stem
            for f in strategies_dir.glob("*.py")
            if f.is_file() and not f.name.startswith("_")
        ]
        return sorted(strategies)
