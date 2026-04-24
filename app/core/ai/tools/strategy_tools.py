"""
strategy_tools.py — AI tools for reading strategy files and parameters.

Provides three tools:
  - list_strategies: list all strategy names in the strategies directory
  - read_strategy_code: return the source code of a named strategy
  - read_strategy_params: return buy/sell params and ROI table from a strategy's JSON file
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from app.core.ai.tools.tool_registry import ToolDefinition, ToolRegistry
from app.core.utils.app_logger import get_logger

_log = get_logger("services.strategy_tools")

_MAX_CODE_BYTES = 50 * 1024  # 50 KB


def list_available_strategies(settings=None) -> Dict[str, Any]:
    """Return the names of all strategies in the strategies directory.

    Args:
        settings: Optional ``AppSettings`` instance. Must have a
            ``user_data_path`` attribute.

    Returns:
        Dict with a ``strategies`` list of strategy names (without ``.py``),
        or an error dict if ``user_data_path`` is not configured.
    """
    if settings is None or getattr(settings, "user_data_path", None) is None:
        _log.warning("list_strategies: user_data_path not configured")
        return {"error": "user_data_path not configured"}

    strategies_dir = Path(settings.user_data_path) / "strategies"
    if not strategies_dir.exists():
        _log.info("list_strategies: strategies directory does not exist: %s", strategies_dir)
        return {"strategies": []}

    names = [p.stem for p in sorted(strategies_dir.glob("*.py"))]
    _log.debug("list_strategies: found %d strategies", len(names))
    return {"strategies": names}


def read_strategy_source_code(strategy_name: str, settings=None) -> Dict[str, Any]:
    """Return the source code of a named strategy file.

    Args:
        strategy_name: Name of the strategy (without ``.py`` extension).
        settings: Optional ``AppSettings`` instance. Must have a
            ``user_data_path`` attribute.

    Returns:
        Dict with ``code`` and ``strategy_name`` keys, or an error dict if
        the file is missing or ``user_data_path`` is not configured.
        Files larger than 50 KB are truncated with a notice appended.
    """
    if settings is None or getattr(settings, "user_data_path", None) is None:
        _log.warning("read_strategy_code: user_data_path not configured")
        return {"error": "user_data_path not configured"}

    strategy_file = Path(settings.user_data_path) / "strategies" / f"{strategy_name}.py"
    if not strategy_file.exists():
        _log.warning("read_strategy_code: file not found: %s", strategy_file)
        return {"error": f"Strategy file not found: {strategy_name}"}

    try:
        raw = strategy_file.read_bytes()
        if len(raw) > _MAX_CODE_BYTES:
            content = raw[:_MAX_CODE_BYTES].decode("utf-8", errors="replace")
            content += "\n[Note: file truncated at 50 KB]"
            _log.debug("read_strategy_code: %s truncated at 50 KB", strategy_name)
        else:
            content = raw.decode("utf-8", errors="replace")
        return {"code": content, "strategy_name": strategy_name}
    except OSError as exc:
        _log.error("read_strategy_code: failed to read %s: %s", strategy_file, exc)
        return {"error": f"Failed to read strategy file: {exc}"}


def read_strategy_parameters(strategy_name: str, settings=None) -> Dict[str, Any]:
    """Return buy/sell params and ROI table from a strategy's JSON params file.

    Args:
        strategy_name: Name of the strategy (without ``.json`` extension).
        settings: Optional ``AppSettings`` instance. Must have a
            ``user_data_path`` attribute.

    Returns:
        Dict with ``buy_params``, ``sell_params``, ``minimal_roi``, and
        ``stoploss`` keys if the params file exists, an output dict if the
        file is absent, or an error dict if ``user_data_path`` is not configured.
    """
    if settings is None or getattr(settings, "user_data_path", None) is None:
        _log.warning("read_strategy_params: user_data_path not configured")
        return {"error": "user_data_path not configured"}

    params_file = Path(settings.user_data_path) / "strategies" / f"{strategy_name}.json"
    if not params_file.exists():
        _log.info("read_strategy_params: no params file for strategy: %s", strategy_name)
        return {"output": f"No params file found for strategy: {strategy_name}", "error": None}

    try:
        data = json.loads(params_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _log.error("read_strategy_params: failed to parse %s: %s", params_file, exc)
        return {"error": f"Failed to read params file: {exc}"}

    _log.debug("read_strategy_params: loaded params for %s", strategy_name)
    return {
        "buy_params": data.get("buy_params"),
        "sell_params": data.get("sell_params"),
        "minimal_roi": data.get("minimal_roi"),
        "stoploss": data.get("stoploss"),
    }


def register_strategy_tools(registry: ToolRegistry, settings=None) -> None:
    """Register all strategy tools into the given registry.

    Args:
        registry: The :class:`ToolRegistry` to register tools into.
        settings: Optional ``AppSettings`` instance forwarded to each tool.
    """
    registry.register(ToolDefinition(
        name="list_strategies",
        description=(
            "List all available strategy names from the user_data/strategies directory. "
            "Returns strategy names without the .py extension."
        ),
        parameters_schema={"type": "object", "properties": {}, "required": []},
        callable=lambda: list_available_strategies(settings),
    ))

    registry.register(ToolDefinition(
        name="read_strategy_code",
        description=(
            "Read the full source code of a strategy file by name. "
            "Files larger than 50 KB are truncated with a notice. "
            "Returns an error if the strategy file does not exist."
        ),
        parameters_schema={
            "type": "object",
            "properties": {
                "strategy_name": {
                    "type": "string",
                    "description": "Strategy name without the .py extension",
                },
            },
            "required": ["strategy_name"],
        },
        callable=lambda strategy_name: read_strategy_source_code(strategy_name, settings),
    ))

    registry.register(ToolDefinition(
        name="read_strategy_params",
        description=(
            "Read buy/sell parameters, minimal ROI table, and stoploss from a "
            "strategy's JSON params file. Returns an informational message if no "
            "params file exists for the strategy."
        ),
        parameters_schema={
            "type": "object",
            "properties": {
                "strategy_name": {
                    "type": "string",
                    "description": "Strategy name without the .json extension",
                },
            },
            "required": ["strategy_name"],
        },
        callable=lambda strategy_name: read_strategy_parameters(strategy_name, settings),
    ))

    _log.debug("Strategy tools registered: list_strategies, read_strategy_code, read_strategy_params")
