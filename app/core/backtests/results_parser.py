"""DEPRECATED: Use app.core.parsing.backtest_parser instead.

This module is kept for backward compatibility. All new code should use:
    from app.core.parsing.backtest_parser import (
        parse_backtest_results_from_zip,
        parse_backtest_results_from_json,
    )
"""

import warnings

from app.core.parsing.backtest_parser import (
    parse_backtest_results_from_zip as _parse_backtest_results_from_zip,
    parse_backtest_results_from_json as _parse_backtest_results_from_json,
)
from app.core.backtests.results_models import BacktestResults

warnings.warn(
    "app.core.backtests.results_parser is deprecated. "
    "Use app.core.parsing.backtest_parser instead.",
    DeprecationWarning,
    stacklevel=2
)


def parse_backtest_results_from_zip(zip_path: str) -> BacktestResults:
    """DEPRECATED: Use app.core.parsing.backtest_parser.parse_backtest_results_from_zip instead."""
    return _parse_backtest_results_from_zip(zip_path)


def parse_backtest_results_from_json(json_path: str) -> BacktestResults:
    """DEPRECATED: Use app.core.parsing.backtest_parser.parse_backtest_results_from_json instead."""
    return _parse_backtest_results_from_json(json_path)


