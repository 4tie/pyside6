from typing import List, Optional

from app.core.freqtrade.runners.backtest_runner import BacktestRunCommand, build_backtest_command
from app.core.freqtrade.runners.base_runner import build_command
from app.core.freqtrade.runners.download_data_runner import build_download_data_command
from app.core.models.settings_models import AppSettings


BacktestCommand = BacktestRunCommand


class CommandRunner:
    """Backward-compatible wrapper over the new runner modules."""

    @staticmethod
    def build_freqtrade_command(
        *args: str,
        settings: AppSettings,
        use_module: Optional[bool] = None
    ) -> List[str]:
        """Build a freqtrade command with proper fallback logic.

        Args:
            *args: Freqtrade command arguments
            settings: AppSettings instance
            use_module: Override module execution setting

        Returns:
            Command list ready for QProcess
        """
        if use_module is not None and use_module != settings.use_module_execution:
            settings = settings.model_copy(update={"use_module_execution": use_module})
        return build_command(settings, *args).as_list()

    @staticmethod
    def build_download_command(
        settings: AppSettings,
        timeframe: str,
        timerange: Optional[str] = None,
        pairs: Optional[List[str]] = None,
    ) -> "BacktestCommand":
        """Backward-compatible download-data builder."""
        run = build_download_data_command(
            settings=settings,
            timeframe=timeframe,
            timerange=timerange,
            pairs=pairs,
        )
        return BacktestCommand(
            program=run.program,
            args=run.args,
            cwd=run.cwd,
            export_dir="",
            config_file="",
            strategy_file="",
        )

    @staticmethod
    def build_python_version_command(settings: AppSettings) -> List[str]:
        """Build command to check Python version."""
        if not settings.python_executable:
            raise ValueError("python_executable not set")
        return [settings.python_executable, "--version"]

    @staticmethod
    def build_backtest_command(
        settings: AppSettings,
        strategy_name: str,
        timeframe: str,
        timerange: Optional[str] = None,
        pairs: Optional[List[str]] = None,
        max_open_trades: Optional[int] = None,
        dry_run_wallet: Optional[float] = None,
        extra_flags: Optional[List[str]] = None
    ) -> "BacktestCommand":
        """Backward-compatible backtesting builder."""
        return build_backtest_command(
            settings=settings,
            strategy_name=strategy_name,
            timeframe=timeframe,
            timerange=timerange,
            pairs=pairs,
            max_open_trades=max_open_trades,
            dry_run_wallet=dry_run_wallet,
            extra_flags=extra_flags,
        )
