from typing import List, Optional

from app.core.models.settings_models import AppSettings
from app.core.freqtrade.runners.base_runner import RunCommand, build_command
from app.core.freqtrade.resolvers.runtime_resolver import resolve_run_paths


def build_download_data_command(
    settings: AppSettings,
    timeframe: str,
    timerange: Optional[str] = None,
    pairs: Optional[List[str]] = None,
) -> RunCommand:
    """Build a freqtrade download-data command.

    Args:
        settings: AppSettings with paths configured.
        timeframe: Candle timeframe e.g. '5m', '1h'.
        timerange: Optional timerange e.g. '20240101-20241231'.
        pairs: Optional list of pairs.

    Returns:
        RunCommand ready for ProcessService.

    Raises:
        ValueError: If settings are incomplete.
    """
    paths = resolve_run_paths(settings)

    ft_args = [
        "download-data",
        "--user-data-dir", str(paths.user_data_dir),
        "--config", str(paths.config_file),
        "--timeframe", timeframe,
        "--prepend",
    ]
    if timerange:
        ft_args += ["--timerange", timerange]
    if pairs:
        ft_args += ["-p"] + list(pairs)

    return build_command(settings, *ft_args)
