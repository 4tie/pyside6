from pathlib import Path
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
        """Build a download-data command.

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

        if not settings.python_executable:
            raise ValueError("python_executable is not configured in Settings")
        if not settings.user_data_path:
            raise ValueError("user_data_path is not configured in Settings")

        user_data = Path(settings.user_data_path).expanduser().resolve()

        # Resolve config file (same logic as backtest)
        config_file: Optional[Path] = None
        if settings.project_path:
            default_config = Path(settings.project_path) / "config.json"
            if default_config.exists():
                config_file = default_config

        if config_file is None:
            default_config = user_data / "config.json"
            if default_config.exists():
                config_file = default_config

        if config_file is None or not config_file.exists():
            raise FileNotFoundError(
                f"No config file found.\n"
                f"Checked: {user_data / 'config.json'}\n"
                f"Please create a config.json in user_data/ or project path."
            )

        # Build download-data command using CommandRunner
        cmd_list = CommandRunner.build_download_command(
            settings=settings,
            config_file=str(config_file),
            exchange="binance",
            timeframe=timeframe,
            timerange=timerange,
            prepend=True,  # --prepend flag
            pairs=pairs or [],
        )

        cwd = str(settings.project_path or user_data)

        return BacktestCommand(
            program=cmd_list[0],
            args=cmd_list[1:],
            cwd=cwd,
            export_dir=str(user_data / "data"),
            export_zip="",
            strategy_file="",
            config_file=str(config_file),
        )
