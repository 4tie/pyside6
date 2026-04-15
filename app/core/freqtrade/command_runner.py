from typing import List, Optional

from app.core.models.settings_models import AppSettings


class CommandRunner:
    """Builds and manages freqtrade command execution."""

    @staticmethod
    def build_freqtrade_command(
        *args: str,
        settings: AppSettings,
        use_module: Optional[bool] = None
    ) -> List[str]:
        """Build a freqtrade command with proper fallback logic.

        Args:
            *args: Freqtrade command arguments (e.g., "backtesting", "--config", "config.json")
            settings: AppSettings instance
            use_module: Override module execution setting. If None, use settings.use_module_execution

        Returns:
            Command list ready for QProcess
        """
        use_module = use_module if use_module is not None else settings.use_module_execution

        if use_module and settings.python_executable:
            # Preferred: python -m freqtrade
            return [settings.python_executable, "-m", "freqtrade", *args]
        elif settings.freqtrade_executable:
            # Fallback: direct freqtrade executable
            return [settings.freqtrade_executable, *args]
        else:
            raise ValueError(
                "No valid freqtrade execution method: python_executable or "
                "freqtrade_executable must be set"
            )

    @staticmethod
    def build_version_check_command(settings: AppSettings) -> List[str]:
        """Build command to check freqtrade version."""
        return CommandRunner.build_freqtrade_command("--version", settings=settings)

    @staticmethod
    def build_python_version_command(settings: AppSettings) -> List[str]:
        """Build command to check Python version."""
        if not settings.python_executable:
            raise ValueError("python_executable not set")
        return [settings.python_executable, "--version"]

    @staticmethod
    def build_backtest_command(
        settings: AppSettings,
        config_file: str,
        **options
    ) -> List[str]:
        """Build freqtrade backtesting command.

        Args:
            settings: AppSettings instance
            config_file: Path to strategy config
            **options: Additional backtest options (e.g., timerange="20200101-", stake_currency="USDT")

        Returns:
            Command list
        """
        cmd = CommandRunner.build_freqtrade_command(
            "backtesting",
            "--config", config_file,
            settings=settings
        )

        # Add additional options
        for key, value in options.items():
            flag = f"--{key.replace('_', '-')}"
            cmd.append(flag)
            if value is not True:  # True means flag only, no value
                cmd.append(str(value))

        return cmd

    @staticmethod
    def build_download_command(
        settings: AppSettings,
        config_file: str,
        **options
    ) -> List[str]:
        """Build freqtrade download-data command.

        Args:
            settings: AppSettings instance
            config_file: Path to strategy config
            **options: Additional download options

        Returns:
            Command list
        """
        cmd = CommandRunner.build_freqtrade_command(
            "download-data",
            "--config", config_file,
            settings=settings
        )

        for key, value in options.items():
            flag = f"--{key.replace('_', '-')}"
            cmd.append(flag)
            if value is not True:
                cmd.append(str(value))

        return cmd
