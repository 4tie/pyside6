# Backward-compatibility shim — import from new location
from app.core.backtests.results_models import BacktestTrade, BacktestSummary, BacktestResults
from app.core.parsing.backtest_parser import parse_backtest_results_from_zip, parse_backtest_results_from_json

__all__ = [
    "BacktestTrade", "BacktestSummary", "BacktestResults",
    "parse_backtest_results_from_zip", "parse_backtest_results_from_json",
    "BacktestResultsService",
]


class BacktestResultsService:
    """Deprecated — use app.core.backtests.results_parser directly."""
    parse_backtest_results_from_zip = staticmethod(parse_backtest_results_from_zip)
    parse_backtest_results_from_json = staticmethod(parse_backtest_results_from_json)
