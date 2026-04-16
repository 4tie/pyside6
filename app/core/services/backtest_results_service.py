# Backward-compatibility shim — import from new location
from app.core.backtests.results_models import BacktestTrade, BacktestSummary, BacktestResults
from app.core.backtests.results_parser import parse_backtest_zip, parse_result_json_file

__all__ = [
    "BacktestTrade", "BacktestSummary", "BacktestResults",
    "parse_backtest_zip", "parse_result_json_file",
    "BacktestResultsService",
]


class BacktestResultsService:
    """Deprecated — use app.core.backtests.results_parser directly."""
    parse_backtest_zip = staticmethod(parse_backtest_zip)
    parse_result_json_file = staticmethod(parse_result_json_file)
