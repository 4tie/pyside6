import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

from app.core.utils.app_logger import get_logger

_log = get_logger("strategy_config")

_KNOWN_SECTIONS = {"roi", "stoploss", "trailing", "buy", "sell"}


class StrategyConfigService:
    """Stateless service for reading and writing strategy parameter JSON files."""

    @staticmethod
    def get_strategy_json_files(strategies_dir: str) -> List[Path]:
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
        if not json_path.exists():
            raise FileNotFoundError(f"Strategy JSON not found: {json_path}")
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            _log.debug("Loaded strategy JSON: %s", json_path.name)
            return data
        except json.JSONDecodeError as e:
            _log.error("JSON decode error in %s: %s", json_path.name, e)
            raise ValueError(f"Failed to parse {json_path.name}: {e}")
        except Exception as e:
            _log.error("Failed to load %s: %s", json_path.name, e)
            raise ValueError(f"Failed to load {json_path.name}: {e}")

    @staticmethod
    def save(json_path: Path, data: dict) -> None:
        """Atomically write a strategy JSON file.

        Args:
            json_path: Destination path
            data: Full strategy dict to serialise

        Raises:
            ValueError: If the write fails
        """
        tmp = json_path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            os.replace(tmp, json_path)
            _log.info("Saved strategy JSON: %s", json_path.name)
        except Exception as e:
            tmp.unlink(missing_ok=True)
            _log.error("Failed to save %s: %s", json_path.name, e)
            raise ValueError(f"Failed to save {json_path.name}: {e}")

    @staticmethod
    def get_known_sections(params: dict) -> Tuple[Dict, Dict]:
        """Split params into known (editable) and unknown (preserved) sections.

        Args:
            params: The params dict from a strategy JSON

        Returns:
            Tuple of (known_sections, unknown_sections)
        """
        known = {k: v for k, v in params.items() if k in _KNOWN_SECTIONS}
        unknown = {k: v for k, v in params.items() if k not in _KNOWN_SECTIONS}
        return known, unknown
