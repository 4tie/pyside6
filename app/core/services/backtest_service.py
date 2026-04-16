from pathlib import Path
from typing import List, Optional

from app.core.freqtrade.runners.backtest_runner import BacktestRunCommand, build_backtest_command
from app.core.freqtrade.resolvers.strategy_resolver import list_strategies
from app.core.services.settings_service import SettingsService


class BacktestService:
    """Service for building backtest commands and listing strategies."""

    def __init__(self, settings_service: SettingsService):
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
    ) -> BacktestRunCommand:
        """Build a backtest command."""
        settings = self.settings_service.load_settings()
        return build_backtest_command(
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
        """List available strategy names from user_data/strategies/."""
        settings = self.settings_service.load_settings()
        if not settings.user_data_path:
            return []
        return list_strategies(Path(settings.user_data_path).expanduser().resolve())
