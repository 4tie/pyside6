"""Compatibility shim — re-exports backtest parsers from their canonical location."""
from app.core.parsing.backtest_parser import (
    parse_backtest_results_from_zip,
    parse_backtest_results_from_json,
)

__all__ = [
    "parse_backtest_results_from_zip",
    "parse_backtest_results_from_json",
]
