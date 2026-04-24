from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.core.freqtrade.resolvers.config_resolver import find_config_file_path
from app.core.freqtrade.resolvers.strategy_resolver import find_strategy_file_path
from app.core.models.settings_models import AppSettings


@dataclass(frozen=True)
class ResolvedRunPaths:
    """Resolved filesystem paths needed to build a freqtrade command."""

    project_dir: Path
    user_data_dir: Path
    config_file: Path
    strategies_dir: Path
    strategy_file: Optional[Path] = None


def find_user_data_directory(settings: AppSettings) -> Path:
    """Resolve and validate the configured user_data directory."""
    if not settings.user_data_path:
        raise ValueError("user_data_path is not configured in Settings")

    user_data_dir = Path(settings.user_data_path).expanduser().resolve()
    if not user_data_dir.exists():
        raise FileNotFoundError(f"user_data directory not found: {user_data_dir}")
    return user_data_dir


def find_project_directory(settings: AppSettings, user_data_dir: Path) -> Path:
    """Resolve the working directory used for freqtrade execution."""
    if settings.project_path:
        return Path(settings.project_path).expanduser().resolve()
    return user_data_dir


def find_run_paths(
    settings: AppSettings,
    strategy_name: Optional[str] = None,
) -> ResolvedRunPaths:
    """Resolve user_data, config, and optional strategy paths for a freqtrade run."""
    user_data_dir = find_user_data_directory(settings)
    project_dir = find_project_directory(settings, user_data_dir)
    strategies_dir = user_data_dir / "strategies"
    strategy_file = (
        find_strategy_file_path(user_data_dir, strategy_name)
        if strategy_name
        else None
    )
    config_file = find_config_file_path(user_data_dir, strategy_name=strategy_name)

    return ResolvedRunPaths(
        project_dir=project_dir,
        user_data_dir=user_data_dir,
        config_file=config_file,
        strategies_dir=strategies_dir,
        strategy_file=strategy_file,
    )
