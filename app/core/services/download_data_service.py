from typing import List, Optional

from app.core.freqtrade import DownloadDataRunCommand, create_download_data_command
from app.core.services.settings_service import SettingsService


class DownloadDataService:
    """Service for building download-data commands."""

    def __init__(self, settings_service: SettingsService):
        self.settings_service = settings_service

    def build_command(
        self,
        timeframe: str,
        timerange: Optional[str] = None,
        pairs: Optional[List[str]] = None,
        prepend: bool = False,
        erase: bool = False,
    ) -> DownloadDataRunCommand:
        """Build a download-data command.

        Args:
            timeframe: Candle timeframe e.g. '5m', '1h'.
            timerange: Optional timerange e.g. '20240101-20241231'.
            pairs: Optional list of trading pairs.
            prepend: When True, forward --prepend to the runner so new candles
                are prepended to existing data files.
            erase: When True, forward --erase to the runner so existing data
                files are deleted before downloading.

        Returns:
            DownloadDataRunCommand ready for ProcessService.
        """
        settings = self.settings_service.load_settings()
        return create_download_data_command(
            settings=settings,
            timeframe=timeframe,
            timerange=timerange,
            pairs=pairs or [],
            prepend=prepend,
            erase=erase,
        )
