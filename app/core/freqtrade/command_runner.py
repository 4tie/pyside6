from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from app.core.models.settings_models import AppSettings


@dataclass
class BacktestCommand:
    """Represents a backtest command with execution info and result paths."""
    program: str        # Python executable path
    args: List[str]     # Command arguments
    cwd: str            # Working directory
    export_dir: str     # Directory for results
    export_zip: str     # Full path to export zip file
    strategy_file: str  # Full path to strategy .py file


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
            *args: Freqtrade command arguments
            settings: AppSettings instance
            use_module: Override module execution setting

        Returns:
            Command list ready for QProcess
        """
        use_module = use_module if use_module is not None else settings.use_module_execution

        if use_module and settings.python_executable:
            return [settings.python_executable, "-m", "freqtrade", *args]
        elif settings.freqtrade_executable:
            return [settings.freqtrade_executable, *args]
        else:
            raise ValueError(
                "No valid freqtrade execution method: python_executable or "
                "freqtrade_executable must be set"
            )

    @staticmethod
    def build_download_command(
        settings: AppSettings,
        timeframe: str,
        timerange: Optional[str] = None,
        pairs: Optional[List[str]] = None,
    ) -> "BacktestCommand":
        """Build a freqtrade download-data command.

        Args:
            settings: AppSettings with paths configured
            timeframe: Timeframe like "5m", "1h"
            timerange: Optional timerange like "20240101-20241231"
            pairs: Optional list of pairs

        Returns:
            BacktestCommand with program, args, cwd

        Raises:
            ValueError: If settings are invalid
        """
        if not settings.python_executable:
            raise ValueError("python_executable is not configured in Settings")
        if not settings.user_data_path:
            raise ValueError("user_data_path is not configured in Settings")

        user_data = Path(settings.user_data_path).expanduser().resolve()

        args = [
            "-m", "freqtrade", "download-data",
            "--user-data-dir", str(user_data),
            "--timeframe", timeframe,
            "--prepend",
        ]

        if timerange:
            args.extend(["--timerange", timerange])

        if pairs:
            args.append("-p")
            args.extend(pairs)

        cwd = str(settings.project_path or user_data)

        return BacktestCommand(
            program=settings.python_executable,
            args=args,
            cwd=cwd,
            export_dir=str(user_data / "data"),
            export_zip="",
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
        """Build a backtest command with strategy validation and result export.

        Args:
            settings: AppSettings with paths configured
            strategy_name: Strategy name (must exist as .py file)
            timeframe: Timeframe like "5m", "1h"
            timerange: Optional timerange like "20240101-20241231"
            pairs: Optional list of pairs like ["BTC/USDT", "ETH/USDT"]
            max_open_trades: Optional max open trades limit
            dry_run_wallet: Optional dry run wallet amount
            extra_flags: Optional additional command flags

        Returns:
            BacktestCommand with program, args, paths
        """
        if not settings.python_executable:
            raise ValueError("python_executable is not configured in Settings")
        if not settings.user_data_path:
            raise ValueError("user_data_path is not configured in Settings")

        user_data = Path(settings.user_data_path).expanduser().resolve()
        strategies_dir = user_data / "strategies"
        strategy_file = strategies_dir / f"{strategy_name}.py"

        if not strategy_file.exists():
            raise FileNotFoundError(
                f"Strategy file not found: {strategy_file}"
            )

        export_dir = user_data / "backtest_results" / strategy_name
        export_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_zip = export_dir / f"{strategy_name}_{timestamp}.backtest.zip"

        args = [
            "-m", "freqtrade", "backtesting",
            "--user-data-dir", str(user_data),
            "--strategy-path", str(strategies_dir),
            "--strategy", strategy_name,
            "--timeframe", timeframe,
            "--export", "trades",
            "--export-filename", str(export_zip),
        ]

        if timerange:
            args.extend(["--timerange", timerange])

        if pairs:
            args.append("-p")
            args.extend(pairs)

        if max_open_trades is not None:
            args.extend(["--max-open-trades", str(max_open_trades)])

        if dry_run_wallet is not None:
            args.extend(["--dry-run-wallet", str(dry_run_wallet)])

        if extra_flags:
            args.extend(extra_flags)

        cwd = str(settings.project_path or user_data)

        return BacktestCommand(
            program=settings.python_executable,
            args=args,
            cwd=cwd,
            export_dir=str(export_dir),
            export_zip=str(export_zip),
            strategy_file=str(strategy_file),
        )
