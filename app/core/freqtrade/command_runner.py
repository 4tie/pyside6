from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from app.core.models.settings_models import AppSettings


@dataclass
class BacktestCommand:
    """Represents a backtest command with execution info and result paths."""
    program: str                     # Python executable path
    args: List[str]                  # Command arguments
    cwd: str                         # Working directory
    export_dir: str                  # Directory for results
    export_zip: str                  # Full path to export zip file
    strategy_file: str               # Full path to strategy .py file
    config_file: str                 # Full path to config file


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
            FileNotFoundError: If config file not found
        """
        if not settings.python_executable:
            raise ValueError("python_executable is not configured in Settings")
        if not settings.user_data_path:
            raise ValueError("user_data_path is not configured in Settings")

        user_data = Path(settings.user_data_path).expanduser().resolve()

        config_file: Optional[Path] = None
        if settings.project_path:
            candidate = Path(settings.project_path) / "config.json"
            if candidate.exists():
                config_file = candidate
        if config_file is None:
            candidate = user_data / "config.json"
            if candidate.exists():
                config_file = candidate
        if config_file is None:
            raise FileNotFoundError(
                f"No config file found. Checked: {user_data / 'config.json'}"
            )

        args = [
            "-m", "freqtrade", "download-data",
            "--config", str(config_file),
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
            config_file=str(config_file),
        )

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
        strategy_name: str,
        timeframe: str,
        timerange: Optional[str] = None,
        pairs: Optional[List[str]] = None,
        max_open_trades: Optional[int] = None,
        dry_run_wallet: Optional[float] = None,
        extra_flags: Optional[List[str]] = None
    ) -> BacktestCommand:
        """Build a backtest command with strategy validation and result export.

        Args:
            settings: AppSettings with paths configured
            strategy_name: Strategy name (must exist as .py file)
            timeframe: Timeframe like "5m", "1h"
            timerange: Optional timerange like "20240101-20241231"
            pairs: Optional list of pairs like ["BTC/USDT", "ETH/USDT"]
            stake_currency: Optional stake currency
            stake_amount: Optional stake amount
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

        # Validate strategy file exists
        if not strategy_file.exists():
            raise FileNotFoundError(
                f"Strategy file not found: {strategy_file}\n"
                f"Available strategies directory: {strategies_dir}"
            )

        # Resolve config file (in order of preference)
        config_file: Optional[Path] = None
        sidecar_json = strategies_dir / f"{strategy_name}.json"

        if sidecar_json.exists():
            config_file = sidecar_json
        elif settings.project_path:
            # Try explicit project config
            default_config = Path(settings.project_path) / "config.json"
            if default_config.exists():
                config_file = default_config

        # Fallback to user_data config
        if config_file is None:
            default_config = user_data / "config.json"
            if default_config.exists():
                config_file = default_config

        if config_file is None or not config_file.exists():
            raise FileNotFoundError(
                f"No config file found for strategy '{strategy_name}'.\n"
                f"Checked: {sidecar_json} and {user_data / 'config.json'}\n"
                f"Please create a config.json in user_data/ or a sidecar."
            )

        # Create export directory
        export_dir = user_data / "backtest_results" / strategy_name
        export_dir.mkdir(parents=True, exist_ok=True)

        # Generate timestamped zip filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_zip = export_dir / f"{strategy_name}_{timestamp}.backtest.zip"

        # Build command arguments
        args = [
            "-m", "freqtrade", "backtesting",
            "--user-data-dir", str(user_data),
            "--strategy-path", str(strategies_dir),
            "--strategy", strategy_name,
            "--config", str(config_file),
            "--timeframe", timeframe,
            "--export", "trades",
            "--export-filename", str(export_zip),
        ]

        # Optional: timerange
        if timerange:
            args.extend(["--timerange", timerange])

        # Optional: pairs
        if pairs:
            args.append("-p")
            args.extend(pairs)

        # Optional: trading limits
        if max_open_trades is not None:
            args.extend(["--max-open-trades", str(max_open_trades)])

        # Optional: dry run wallet
        if dry_run_wallet is not None:
            args.extend(["--dry-run-wallet", str(dry_run_wallet)])

        # Optional: extra flags
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
            config_file=str(config_file),
        )
