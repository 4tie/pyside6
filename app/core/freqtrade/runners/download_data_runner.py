from typing import List, Optional

from app.core.models.settings_models import AppSettings
from app.core.models.command_models import DownloadDataRunCommand
from app.core.freqtrade.runners.base_runner import create_command
from app.core.freqtrade.resolvers.runtime_resolver import find_run_paths


def create_download_data_command(
    settings: AppSettings,
    timeframe: str,
    timerange: Optional[str] = None,
    pairs: Optional[List[str]] = None,
    prepend: bool = False,
    erase: bool = False,
) -> DownloadDataRunCommand:
    """Build a freqtrade download-data command.

    Args:
        settings: AppSettings with paths configured.
        timeframe: Candle timeframe e.g. '5m', '1h'.
        timerange: Optional timerange e.g. '20240101-20241231'.
        pairs: Optional list of pairs.
        prepend: When True, include --prepend flag to prepend new candles to
            existing data files rather than appending.
        erase: When True, include --erase flag to delete existing data files
            for the selected pairs and timeframe before downloading.

    Returns:
        DownloadDataRunCommand ready for ProcessService.

    Raises:
        ValueError: If settings are incomplete.
    """
    paths = find_run_paths(settings)

    ft_args = [
        "download-data",
        "--user-data-dir", str(paths.user_data_dir),
        "--config", str(paths.config_file),
        "--timeframe", timeframe,
    ]
    if prepend:
        ft_args.append("--prepend")
    if erase:
        ft_args.append("--erase")
    if timerange:
        ft_args += ["--timerange", timerange]
    if pairs:
        ft_args += ["-p"] + list(pairs)

    base = create_command(settings, *ft_args)
    return DownloadDataRunCommand(
        program=base.program,
        args=base.args,
        cwd=base.cwd,
        config_file=str(paths.config_file),
        strategy_file=str(paths.strategy_file) if paths.strategy_file is not None else None,
    )
