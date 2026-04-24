"""Strategy configuration parsing module.

Handles parsing and writing of strategy parameter JSON files.
"""

from pathlib import Path
from typing import Dict, Tuple

from app.core.parsing.json_parser import ParseError, parse_json_file, write_json_file_atomic
from app.core.utils.app_logger import get_logger

_log = get_logger("parsing.strategy")

_KNOWN_SECTIONS = {"roi", "stoploss", "trailing", "buy", "sell"}


def parse_strategy_config(json_path: Path | str) -> Dict:
    """Read and parse a strategy JSON file.

    Args:
        json_path: Path to the strategy .json file

    Returns:
        Parsed dict with strategy_name and params

    Raises:
        ParseError: If the file does not exist or cannot be parsed
    """
    path = Path(json_path)
    try:
        data = parse_json_file(path)
        _log.debug("Loaded strategy JSON: %s", path.name)
        return data
    except ParseError as e:
        _log.error("Failed to load strategy JSON %s: %s", path.name, e)
        raise


def write_strategy_config(json_path: Path | str, data: Dict) -> None:
    """Atomically write a strategy JSON file.

    Args:
        json_path: Destination path
        data: Full strategy dict to serialise

    Raises:
        ParseError: If the write fails
    """
    path = Path(json_path)
    try:
        write_json_file_atomic(path, data)
        _log.info("Saved strategy JSON: %s", path.name)
    except ParseError as e:
        _log.error("Failed to save strategy JSON %s: %s", path.name, e)
        raise


def get_strategy_json_files(strategies_dir: str) -> list[Path]:
    """Return sorted list of .json files that have a matching .py strategy file.

    Args:
        strategies_dir: Path to user_data/strategies/

    Returns:
        Sorted list of Path objects for valid strategy JSON files
    """
    root = Path(strategies_dir)
    if not root.exists():
        return []
    return sorted(
        p for p in root.glob("*.json")
        if (root / f"{p.stem}.py").exists()
    )


def get_known_sections(params: Dict) -> Tuple[Dict, Dict]:
    """Split params into known (editable) and unknown (preserved) sections.

    Args:
        params: The params dict from a strategy JSON

    Returns:
        Tuple of (known_sections, unknown_sections)
    """
    known = {k: v for k, v in params.items() if k in _KNOWN_SECTIONS}
    unknown = {k: v for k, v in params.items() if k not in _KNOWN_SECTIONS}
    return known, unknown
