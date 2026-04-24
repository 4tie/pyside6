"""Command models for freqtrade operations.

These dataclasses represent executable commands for freqtrade subprocesses.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence
import os
import shlex
import subprocess


@dataclass(frozen=True)
class ResolvedRunPaths:
    """Resolved filesystem paths needed to build a freqtrade command."""
    project_dir: Path
    user_data_dir: Path
    config_file: Path
    strategies_dir: Path
    strategy_file: Optional[Path] = None


@dataclass
class RunCommand:
    """Executable command ready for ProcessService."""
    program: str
    args: List[str]
    cwd: str

    def as_list(self) -> List[str]:
        """Return the command as a flat token list."""
        return [self.program, *self.args]

    def to_display_string(self) -> str:
        """Return a shell-safe display string for the current platform."""
        return format_command_string(self.as_list())


def format_command_string(command: Sequence[str]) -> str:
    """Render a tokenized command for display/copy without re-splitting it later."""
    command_parts = [str(part) for part in command if part is not None]
    if os.name == "nt":
        return subprocess.list2cmdline(command_parts)
    return shlex.join(command_parts)


@dataclass
class BacktestRunCommand(RunCommand):
    """RunCommand extended with backtest-specific paths."""
    export_dir: str
    config_file: str
    strategy_file: str


@dataclass
class OptimizeRunCommand(RunCommand):
    """RunCommand extended with hyperopt-specific paths."""
    export_dir: str
    config_file: str
    strategy_file: str


@dataclass
class DownloadDataRunCommand(RunCommand):
    """RunCommand extended with download-data-specific paths."""
    config_file: str
    strategy_file: Optional[str] = None
