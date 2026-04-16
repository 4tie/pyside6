from pathlib import Path
from typing import List

from app.core.utils.app_logger import get_logger

_log = get_logger("resolvers.strategy")


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
