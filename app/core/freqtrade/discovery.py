"""Central freqtrade discovery operations with proper wrappers."""
from pathlib import Path
from app.core.freqtrade.resolvers.config_resolver import find_config_file_path
from app.core.freqtrade.resolvers.strategy_resolver import (
    list_available_strategies,
    detect_strategy_timeframe,
)
from app.core.utils.app_logger import get_logger

_log = get_logger("freqtrade.discovery")

def find_config_file_safe(user_data_dir: Path, strategy_name: str) -> Path:
    """Find config file path with logging and error handling."""
    _log.debug("Finding config file for strategy: %s", strategy_name)
    try:
        return find_config_file_path(user_data_dir, strategy_name=strategy_name)
    except Exception as e:
        _log.error("Failed to find config file for %s: %s", strategy_name, e)
        raise

def list_strategies(user_data_dir: Path) -> list[str]:
    """List available strategies with logging and error handling."""
    _log.debug("Listing strategies from: %s", user_data_dir)
    try:
        return list_available_strategies(user_data_dir)
    except Exception as e:
        _log.error("Failed to list strategies: %s", e)
        raise

def detect_strategy_timeframe_safe(strategy_path: Path) -> str:
    """Detect strategy timeframe with logging and error handling."""
    _log.debug("Detecting timeframe for strategy: %s", strategy_path)
    try:
        return detect_strategy_timeframe(strategy_path)
    except Exception as e:
        _log.warning("Failed to detect timeframe for %s, using default: %s", strategy_path, e)
        return "5m"  # fallback
