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
    ) -> DownloadDataRunCommand:
        """Build a download-data command."""
        settings = self.settings_service.load_settings()
        return create_download_data_command(
            settings=settings,
            timeframe=timeframe,
            timerange=timerange,
            pairs=pairs or [],
        )
