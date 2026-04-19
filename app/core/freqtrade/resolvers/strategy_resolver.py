from pathlib import Path
from typing import List, Optional
import re

from app.core.utils.app_logger import get_logger

_log = get_logger("resolvers.strategy")


def detect_strategy_timeframe(strategy_path: Path) -> str:
    """Detect the timeframe from a strategy file.

    Args:
        strategy_path: Path to the strategy .py file.

    Returns:
        Detected timeframe string (e.g. "5m", "1h"), defaults to "5m" if not found.
    """
    try:
        content = strategy_path.read_text(encoding="utf-8")
        
        # Look for timeframe = "..." or timeframe: str = "..."
        # Common patterns in freqtrade strategies
        patterns = [
            r'timeframe\s*=\s*["\'](\w+)["\']',  # timeframe = "5m"
            r'timeframe\s*:\s*str\s*=\s*["\'](\w+)["\']',  # timeframe: str = "5m"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                timeframe = match.group(1)
                _log.debug("Detected timeframe '%s' from %s", timeframe, strategy_path.name)
                return timeframe
        
        _log.debug("No timeframe found in %s, defaulting to '5m'", strategy_path.name)
        return "5m"
    except Exception as exc:
        _log.warning("Failed to detect timeframe from %s: %s", strategy_path, exc)
        return "5m"


def resolve_strategy_file(user_data: Path, strategy_name: str) -> Path:
    """Resolve the absolute path to a strategy .py file.

    Args:
        user_data: Resolved user_data directory Path.
        strategy_name: Strategy class name without .py extension.

    Returns:
        Absolute Path to the strategy file.

    Raises:
        FileNotFoundError: If the strategy file does not exist.
    """
    path = user_data / "strategies" / f"{strategy_name}.py"
    if not path.exists():
        raise FileNotFoundError(f"Strategy file not found: {path}")
    _log.debug("Strategy resolved: %s", path)
    return path


def list_strategies(user_data: Path) -> List[str]:
    """List available strategy names from user_data/strategies/.

    Args:
        user_data: Resolved user_data directory Path.

    Returns:
        Sorted list of strategy names (without .py extension).
    """
    strategies_dir = user_data / "strategies"
    if not strategies_dir.exists():
        return []
    return sorted(
        f.stem
        for f in strategies_dir.glob("*.py")
        if f.is_file() and not f.name.startswith("_")
    )
