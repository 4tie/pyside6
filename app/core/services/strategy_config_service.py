from pathlib import Path
from typing import Dict, List, Tuple

from app.core.parsing.strategy_parser import (
    parse_strategy_config,
    write_strategy_config,
    get_strategy_json_files,
    get_known_sections,
)
from app.core.utils.app_logger import get_logger

_log = get_logger("strategy_config")


class StrategyConfigService:
    """Stateless service for reading and writing strategy parameter JSON files.
    
    DEPRECATED: Use app.core.parsing.strategy_parser functions directly.
    This service is kept for backward compatibility.
    """

    @staticmethod
    def get_strategy_json_files(strategies_dir: str) -> List[Path]:
        """Return sorted list of .json files that have a matching .py strategy file.

        Args:
            strategies_dir: Path to user_data/strategies/

        Returns:
            Sorted list of Path objects for valid strategy JSON files
        """
        return get_strategy_json_files(strategies_dir)

    @staticmethod
    def load(json_path: Path) -> dict:
        """Read and parse a strategy JSON file.

        Args:
            json_path: Path to the strategy .json file

        Returns:
            Parsed dict with strategy_name and params

        Raises:
            FileNotFoundError: If the file does not exist
            ValueError: If the file cannot be parsed
        """
        return parse_strategy_config(json_path)

    @staticmethod
    def save(json_path: Path, data: dict) -> None:
        """Atomically write a strategy JSON file.

        Args:
            json_path: Destination path
            data: Full strategy dict to serialise

        Raises:
            ValueError: If the write fails
        """
        write_strategy_config(json_path, data)

    @staticmethod
    def get_known_sections(params: dict) -> Tuple[Dict, Dict]:
        """Split params into known (editable) and unknown (preserved) sections.

        Args:
            params: The params dict from a strategy JSON

        Returns:
            Tuple of (known_sections, unknown_sections)
        """
        return get_known_sections(params)
