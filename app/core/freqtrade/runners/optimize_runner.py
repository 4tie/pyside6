from dataclasses import dataclass
from typing import List, Optional

from app.core.freqtrade.resolvers.runtime_resolver import find_run_paths
from app.core.freqtrade.runners.base_runner import RunCommand, create_command
from app.core.models.settings_models import AppSettings


@dataclass
class OptimizeRunCommand(RunCommand):
    """RunCommand extended with optimize-specific paths."""

    config_file: str
    strategy_file: str


def create_optimize_command(
    settings: AppSettings,
    strategy_name: str,
    timeframe: str,
    epochs: int,
    timerange: Optional[str] = None,
    pairs: Optional[List[str]] = None,
    spaces: Optional[List[str]] = None,
    hyperopt_loss: Optional[str] = None,
    extra_flags: Optional[List[str]] = None,
) -> OptimizeRunCommand:
    """Build a freqtrade hyperopt command."""
    paths = find_run_paths(settings, strategy_name=strategy_name)

    ft_args = [
        "hyperopt",
        "--user-data-dir", str(paths.user_data_dir),
        "--config", str(paths.config_file),
        "--strategy-path", str(paths.strategies_dir),
        "--strategy", strategy_name,
        "--timeframe", timeframe,
        "-e", str(epochs),
    ]
    if timerange:
        ft_args += ["--timerange", timerange]
    if pairs:
        ft_args += ["-p"] + list(pairs)
    if spaces:
        ft_args += ["--spaces", *spaces]
    if hyperopt_loss:
        ft_args += ["--hyperopt-loss", hyperopt_loss]
    if extra_flags:
        ft_args += list(extra_flags)

    base = create_command(settings, *ft_args)
    return OptimizeRunCommand(
        program=base.program,
        args=base.args,
        cwd=base.cwd,
        config_file=str(paths.config_file),
        strategy_file=str(paths.strategy_file),
    )
