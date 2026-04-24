import os
import shlex
import subprocess
from pathlib import Path
from typing import List, Sequence

from app.core.models.settings_models import AppSettings
from app.core.models.command_models import RunCommand, format_command_string


def create_command(settings: AppSettings, *ft_args: str) -> RunCommand:
    """Build a freqtrade command using python -m freqtrade or direct executable.

    Args:
        settings: AppSettings with python/freqtrade paths configured.
        *ft_args: freqtrade subcommand and flags.

    Returns:
        RunCommand(program, args, cwd)

    Raises:
        ValueError: If no valid execution method is configured.
    """
    if settings.project_path:
        cwd = str(Path(settings.project_path).expanduser().resolve())
    elif settings.user_data_path:
        cwd = str(Path(settings.user_data_path).expanduser().resolve())
    else:
        cwd = str(Path.cwd())

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
