from typing import List, Optional

from app.core.freqtrade.command_runner import BacktestCommand, CommandRunner
from app.core.services.settings_service import SettingsService


class DownloadDataService:
    """Service for building and managing download-data commands."""

    def __init__(self, settings_service: SettingsService):
        """Initialize with a SettingsService instance.

        Args:
            settings_service: SettingsService for loading settings
        """
        self.settings_service = settings_service

    def build_command(
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

        Raises:
            ValueError: If settings are invalid or incomplete
        """
        settings = self.settings_service.load_settings()

        # Get config file path from backtest command (uses same config)
        bt_cmd = CommandRunner.build_backtest_command(
            settings=settings,
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
