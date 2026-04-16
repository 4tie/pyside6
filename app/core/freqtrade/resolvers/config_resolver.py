from pathlib import Path
from typing import Optional

from app.core.utils.app_logger import get_logger

_log = get_logger("resolvers.config")


def resolve_config_file(user_data: Path, strategy_name: Optional[str] = None) -> Path:
    """Resolve the freqtrade config.json to use for a run.

    Resolution order:
    1. Sidecar config next to strategy: strategies/{strategy_name}_config.json
    2. Default: user_data/config.json

    Args:
        user_data: Resolved user_data directory Path.
        strategy_name: Optional strategy name for sidecar lookup.

    Returns:
        Absolute Path to the config file.

    Raises:
        FileNotFoundError: If no config file is found.
    """
    if strategy_name:
        sidecar = user_data / "strategies" / f"{strategy_name}_config.json"
        if sidecar.exists():
            _log.debug("Using sidecar config: %s", sidecar)
            return sidecar

    default = user_data / "config.json"
    if default.exists():
        _log.debug("Using default config: %s", default)
        return default

    raise FileNotFoundError(
        f"No config.json found in {user_data}. "
        "Create user_data/config.json or a strategy-specific sidecar."
    )
