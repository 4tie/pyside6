"""Central freqtrade parsing operations with proper wrappers."""
from pathlib import Path
from app.core.parsing.backtest_parser import parse_backtest_results_from_zip
from app.core.parsing.json_parser import parse_json_file
from app.core.backtests.results_models import BacktestResults
from app.core.utils.app_logger import get_logger

_log = get_logger("freqtrade.parsing")

def parse_backtest_zip(zip_path: str | Path) -> BacktestResults:
    """Parse backtest results from zip file with logging and error handling."""
    _log.debug("Parsing backtest zip: %s", zip_path)
    try:
        return parse_backtest_results_from_zip(str(zip_path))
    except Exception as e:
        _log.error("Failed to parse backtest zip %s: %s", zip_path, e)
        raise

def parse_json_file_safe(path: Path) -> dict:
    """Parse JSON file with logging and error handling."""
    _log.debug("Parsing JSON file: %s", path)
    try:
        return parse_json_file(path)
    except Exception as e:
        _log.error("Failed to parse JSON file %s: %s", path, e)
        raise
