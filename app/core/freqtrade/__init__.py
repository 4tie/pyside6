"""Central freqtrade module for all freqtrade-related operations.

This module provides a single entry point for all freqtrade operations
with proper wrappers, logging, and error handling.
"""
from app.core.freqtrade.parsing import (
    parse_backtest_zip,
)
from app.core.freqtrade.discovery import (
    list_strategies,
    find_config_file_safe,
    detect_strategy_timeframe_safe,
)
from app.core.freqtrade.commands import (
    create_backtest_command,
    create_optimize_command,
    create_download_data_command,
)
from app.core.models.command_models import (
    BacktestRunCommand,
    OptimizeRunCommand,
    DownloadDataRunCommand,
)

__all__ = [
    # Parsing
    "parse_backtest_zip",
    # Discovery
    "list_strategies",
    "find_config_file_safe",
    "detect_strategy_timeframe_safe",
    # Commands
    "create_backtest_command",
    "create_optimize_command",
    "create_download_data_command",
    # Command types
    "BacktestRunCommand",
    "OptimizeRunCommand",
    "DownloadDataRunCommand",
]
