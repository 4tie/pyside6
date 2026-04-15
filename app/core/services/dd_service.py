from typing import List, Optional

from app.core.freqtrade.command_runner import BacktestCommand, CommandRunner
from app.core.services.settings_service import SettingsService


class DownloadDataService:
    """Service for building download-data commands."""

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
        """Build a download-data command.

        Args:
            timeframe: Timeframe (e.g., "5m", "1h")
            timerange: Optional timerange
            pairs: Optional list of pairs

        Returns:
            BacktestCommand with all necessary info

        Raises:
            ValueError: If settings are invalid or incomplete
            FileNotFoundError: If config file not found
        """
        settings = self.settings_service.load_settings()
        return CommandRunner.build_download_command(
            settings=settings,
            timeframe=timeframe,
            timerange=timerange,
            pairs=pairs or [],
        )
