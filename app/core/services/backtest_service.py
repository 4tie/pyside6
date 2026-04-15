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

    def build_download_data_command(
        self,
        timeframe: str,
        timerange: Optional[str] = None,
        pairs: Optional[List[str]] = None,
    ) -> BacktestCommand:
        """Build a download-data command using backtest config.

        Args:
            timeframe: Timeframe (e.g., "5m", "1h")
            timerange: Optional timerange
            pairs: Optional list of pairs

        Returns:
            BacktestCommand with all necessary info
        """
        settings = self.settings_service.load_settings()

        # Get config file path from backtest command
        bt_cmd = CommandRunner.build_backtest_command(
            settings=settings,
            strategy_name="dummy",  # Not needed for download
            timeframe=timeframe,
            timerange=timerange,
            pairs=pairs or [],
            extra_flags=[],
        )
        config_file = bt_cmd.config_file

        # Build download-data command
        cmd_list = CommandRunner.build_freqtrade_command(
            "download-data", settings=settings
        )
        cmd_list.extend(["--config", config_file, "--exchange", "binance"])

        if pairs:
            for pair in pairs:
                cmd_list.extend(["--pairs", pair])

        if timeframe:
            cmd_list.extend(["--timeframe", timeframe])

        if timerange:
            cmd_list.extend(["--timerange", timerange])

        cmd_list.append("--prepend")

        # Create BacktestCommand-like object
        result = BacktestCommand(
            program=cmd_list[0],
            args=cmd_list[1:],
            config_file=config_file,
            strategy_file="",
            export_zip="",
            cwd=bt_cmd.cwd,
        )
        return result

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
