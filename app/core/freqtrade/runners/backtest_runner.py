from dataclasses import dataclass
from typing import List, Optional

from app.core.models.settings_models import AppSettings
from app.core.freqtrade.runners.base_runner import RunCommand, build_command
from app.core.freqtrade.resolvers.runtime_resolver import resolve_run_paths


@dataclass
class BacktestRunCommand(RunCommand):
    """RunCommand extended with backtest-specific paths."""
    export_dir: str
    config_file: str
    strategy_file: str


def build_backtest_command(
    settings: AppSettings,
    strategy_name: str,
    timeframe: str,
    timerange: Optional[str] = None,
    pairs: Optional[List[str]] = None,
    max_open_trades: Optional[int] = None,
    dry_run_wallet: Optional[float] = None,
    extra_flags: Optional[List[str]] = None,
) -> BacktestRunCommand:
    """Build a freqtrade backtesting command.

    Args:
        settings: AppSettings with paths configured.
        strategy_name: Strategy class name (must exist as .py file).
        timeframe: Candle timeframe e.g. '5m', '1h'.
        timerange: Optional timerange e.g. '20240101-20241231'.
        pairs: Optional list of pairs.
        max_open_trades: Optional trade limit.
        dry_run_wallet: Optional starting wallet.
        extra_flags: Optional additional CLI flags.

    Returns:
        BacktestRunCommand ready for ProcessService.

    Raises:
        ValueError: If settings are incomplete.
        FileNotFoundError: If strategy file does not exist.
    """
    paths = resolve_run_paths(settings, strategy_name=strategy_name)

    export_dir = paths.user_data_dir / "backtest_results"
    export_dir.mkdir(parents=True, exist_ok=True)

    ft_args = [
        "backtesting",
        "--user-data-dir", str(paths.user_data_dir),
        "--config", str(paths.config_file),
        "--strategy-path", str(paths.strategies_dir),
        "--strategy", strategy_name,
        "--timeframe", timeframe,
        "--export", "trades",
    ]
    if timerange:
        ft_args += ["--timerange", timerange]
    if pairs:
        ft_args += ["-p"] + list(pairs)
    if max_open_trades is not None:
        ft_args += ["--max-open-trades", str(max_open_trades)]
    if dry_run_wallet is not None:
        ft_args += ["--dry-run-wallet", str(dry_run_wallet)]
    if extra_flags:
        ft_args += list(extra_flags)

    base = build_command(settings, *ft_args)
    return BacktestRunCommand(
        program=base.program,
        args=base.args,
        cwd=base.cwd,
        export_dir=str(export_dir),
        config_file=str(paths.config_file),
        strategy_file=str(paths.strategy_file),
    )
