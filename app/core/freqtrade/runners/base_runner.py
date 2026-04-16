from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from app.core.models.settings_models import AppSettings


@dataclass
class RunCommand:
    """Executable command ready for ProcessService."""
    program: str
    args: List[str]
    cwd: str


def build_command(settings: AppSettings, *ft_args: str) -> RunCommand:
    """Build a freqtrade command using python -m freqtrade or direct executable.

    Args:
        settings: AppSettings with python/freqtrade paths configured.
        *ft_args: freqtrade subcommand and flags.

    Returns:
        RunCommand(program, args, cwd)

    Raises:
        ValueError: If no valid execution method is configured.
    """
    if not settings.user_data_path:
        raise ValueError("user_data_path is not configured in Settings")

    cwd = str(
        Path(settings.project_path).expanduser().resolve()
        if settings.project_path
        else Path(settings.user_data_path).expanduser().resolve()
    )

    if settings.use_module_execution and settings.python_executable:
        return RunCommand(
            program=settings.python_executable,
            args=["-m", "freqtrade", *ft_args],
            cwd=cwd,
        )
    if settings.freqtrade_executable:
        return RunCommand(
            program=settings.freqtrade_executable,
            args=list(ft_args),
            cwd=cwd,
        )
    raise ValueError(
        "No valid freqtrade execution method: set python_executable or freqtrade_executable"
    )
