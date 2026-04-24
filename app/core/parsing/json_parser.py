"""Centralized JSON parsing utilities with consistent error handling.

Provides unified JSON parsing and writing operations with:
- Consistent error handling via ParseError
- Atomic file writes
- UTF-8 encoding by default
- Clear error messages
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


class ParseError(Exception):
    """Base exception for all parsing errors."""

    def __init__(self, message: str, path: Optional[str] = None, original_error: Optional[Exception] = None):
        self.message = message
        self.path = path
        self.original_error = original_error
        if path:
            super().__init__(f"{message} (path: {path})")
        else:
            super().__init__(message)


def parse_json_file(file_path: Path | str) -> Dict[str, Any]:
    """Parse a JSON file and return the parsed dictionary.

    Args:
        file_path: Path to the JSON file to parse.

    Returns:
        Parsed dictionary from the JSON file.

    Raises:
        ParseError: If the file does not exist, cannot be read, or contains invalid JSON.
    """
    path = Path(file_path)
    if not path.exists():
        raise ParseError(f"File not found", str(path))

    try:
        content = path.read_text(encoding="utf-8")
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise ParseError(f"Invalid JSON", str(path), e)
    except Exception as e:
        raise ParseError(f"Failed to read file", str(path), e)


def parse_json_string(json_string: str) -> Dict[str, Any]:
    """Parse a JSON string and return the parsed dictionary.

    Args:
        json_string: JSON string to parse.

    Returns:
        Parsed dictionary from the JSON string.

    Raises:
        ParseError: If the string contains invalid JSON.
    """
    try:
        return json.loads(json_string)
    except json.JSONDecodeError as e:
        raise ParseError("Invalid JSON string", original_error=e)
    except Exception as e:
        raise ParseError("Failed to parse JSON string", original_error=e)


def write_json_file_atomic(
    file_path: Path | str,
    data: Dict[str, Any],
    indent: int = 2,
    encoding: str = "utf-8",
) -> None:
    """Write data to a JSON file atomically using a temp file + rename.

    Args:
        file_path: Target file path.
        data: Dictionary to serialize as JSON.
        indent: JSON indentation level (default: 2).
        encoding: File encoding (default: utf-8).

    Raises:
        ParseError: If the write operation fails.
    """
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = path.with_suffix(".tmp")
    try:
        tmp_path.write_text(json_dumps(data), encoding=encoding)
        os.replace(tmp_path, path)
    except Exception as e:
        tmp_path.unlink(missing_ok=True)
        raise ParseError(f"Failed to write file", str(path), e)


def json_dumps(data: Dict[str, Any]) -> str:
    """Serialize dict to JSON string with consistent formatting.

    Uses consistent formatting across the application:
    - indent=2: Readable output
    - ensure_ascii=False: Arabic/Unicode support
    - sort_keys=True: Stable diffs for versioning

    Args:
        data: Dictionary to serialize.

    Returns:
        JSON string.
    """
    return json.dumps(
        data,
        indent=2,
        ensure_ascii=False,
        sort_keys=True,
    )


def parse_json_with_default(
    file_path: Path | str,
    default: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Parse a JSON file, returning a default if the file doesn't exist or parsing fails.

    Args:
        file_path: Path to the JSON file to parse.
        default: Default dictionary to return if parsing fails (default: empty dict).

    Returns:
        Parsed dictionary or the default value.
    """
    if default is None:
        default = {}
    
    try:
        return parse_json_file(file_path)
    except ParseError:
        return default
