"""Centralized parsing module for all data parsing operations.

This module consolidates all parsing logic to ensure:
- Consistent error handling
- Single source of truth for parsing logic
- Reusable parsing utilities
- Clear separation of parsing concerns
"""

from app.core.parsing.json_parser import (
    parse_json_file,
    parse_json_string,
    write_json_file_atomic,
    json_dumps,
    ParseError,
)

from app.core.parsing.backtest_parser import (
    parse_backtest_results_from_zip,
    parse_backtest_results_from_json,
)

from app.core.parsing.strategy_parser import (
    parse_strategy_config,
    write_strategy_config,
)

__all__ = [
    # JSON parsing utilities
    "parse_json_file",
    "parse_json_string",
    "write_json_file_atomic",
    "json_dumps",
    "ParseError",
    # Backtest parsing
    "parse_backtest_results_from_zip",
    "parse_backtest_results_from_json",
    # Strategy parsing
    "parse_strategy_config",
    "write_strategy_config",
]
