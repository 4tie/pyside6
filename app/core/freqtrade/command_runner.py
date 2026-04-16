from dataclasses import dataclass
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
        """Build a freqtrade download-data command."""
        if not settings.user_data_path:
            raise ValueError("user_data_path is not configured in Settings")

        user_data = Path(settings.user_data_path).expanduser().resolve()

        ft_args = [
            "download-data",
            "--user-data-dir", str(user_data),
            "--timeframe", timeframe,
            "--prepend",
        ]
        if timerange:
            ft_args.extend(["--timerange", timerange])
        if pairs:
            ft_args += ["-p"] + list(pairs)

        full_cmd = CommandRunner.build_freqtrade_command(*ft_args, settings=settings)
        return BacktestCommand(
            program=full_cmd[0],
            args=full_cmd[1:],
            cwd=str(settings.project_path or user_data),
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
        """Build a backtest command with strategy validation and result export."""
        if not settings.user_data_path:
            raise ValueError("user_data_path is not configured in Settings")

        user_data = Path(settings.user_data_path).expanduser().resolve()
        strategies_dir = user_data / "strategies"
        strategy_file = strategies_dir / f"{strategy_name}.py"

        if not strategy_file.exists():
            raise FileNotFoundError(f"Strategy file not found: {strategy_file}")

        export_dir = user_data / "backtest_results"
        export_dir.mkdir(parents=True, exist_ok=True)

        ft_args = [
            "backtesting",
            "--user-data-dir", str(user_data),
            "--strategy-path", str(strategies_dir),
            "--strategy", strategy_name,
            "--timeframe", timeframe,
            "--export", "trades",
        ]
        if timerange:
            ft_args.extend(["--timerange", timerange])
        if pairs:
            ft_args += ["-p"] + list(pairs)
        if max_open_trades is not None:
            ft_args.extend(["--max-open-trades", str(max_open_trades)])
        if dry_run_wallet is not None:
            ft_args.extend(["--dry-run-wallet", str(dry_run_wallet)])
        if extra_flags:
            ft_args.extend(extra_flags)

        full_cmd = CommandRunner.build_freqtrade_command(*ft_args, settings=settings)
        return BacktestCommand(
            program=full_cmd[0],
            args=full_cmd[1:],
            cwd=str(settings.project_path or user_data),
            export_dir=str(export_dir),
            export_zip="",
            strategy_file=str(strategy_file),
        )
