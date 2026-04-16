"""
backtest_tools.py — AI tools for querying backtest results.

Provides three tools:
  - get_latest_backtest_result: most recent run summary for the current strategy
  - load_run_history: list of run summaries for a named strategy
  - compare_runs: side-by-side metric comparison of two runs by ID
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.backtests.results_index import IndexStore
from app.core.backtests.results_store import RunStore
from app.core.ai.tools.tool_registry import ToolDefinition, ToolRegistry
from app.core.utils.app_logger import get_logger

_log = get_logger("services.backtest_tools")

# Keys extracted for run summaries
_SUMMARY_KEYS = (
    "run_id",
    "strategy",
    "saved_at",
    "profit_factor",
    "win_rate_pct",
    "trades_count",
    "profit_total_pct",
    "max_drawdown_pct",
    "sharpe",
)

# Keys used in side-by-side comparison
_COMPARE_KEYS = (
    "run_id",
    "strategy",
    "timeframe",
    "timerange",
    "trades_count",
    "win_rate_pct",
    "profit_total_pct",
    "profit_total_abs",
    "profit_factor",
    "max_drawdown_pct",
    "sharpe",
    "sortino",
    "calmar",
    "expectancy",
    "saved_at",
)


def _backtest_results_dir(user_data_path: str) -> str:
    """Return the backtest_results directory path string."""
    return str(Path(user_data_path) / "backtest_results")


def _find_run_entry(backtest_results_dir: str, run_id: str) -> Optional[Dict]:
    """Search the global index for a run entry by run_id."""
    index = IndexStore.load(backtest_results_dir)
    for _strategy, block in index.get("strategies", {}).items():
        for entry in block.get("runs", []):
            if entry.get("run_id") == run_id:
                return entry
    return None


def get_latest_backtest_result(settings=None) -> Dict[str, Any]:
    """Return the most recent backtest run summary across all strategies.

    Args:
        settings: Optional ``AppSettings`` instance. Must have a
            ``user_data_path`` attribute.

    Returns:
        Dict with summary metrics, or an error/output dict if unavailable.
    """
    if settings is None or getattr(settings, "user_data_path", None) is None:
        _log.warning("get_latest_backtest_result: user_data_path not configured")
        return {"error": "user_data_path not configured"}

    results_dir = _backtest_results_dir(settings.user_data_path)
    index = IndexStore.load(results_dir)

    # Collect all runs across all strategies and find the newest
    all_runs: List[Dict] = []
    for block in index.get("strategies", {}).values():
        all_runs.extend(block.get("runs", []))

    if not all_runs:
        _log.info("get_latest_backtest_result: no results found")
        return {"output": "No results found", "error": None}

    # Sort by saved_at descending; entries without saved_at sort last
    all_runs.sort(key=lambda r: r.get("saved_at", ""), reverse=True)
    latest = all_runs[0]

    summary = {k: latest.get(k) for k in _SUMMARY_KEYS}
    _log.debug("get_latest_backtest_result: returning run_id=%s", summary.get("run_id"))
    return summary


def load_run_history(strategy: str, settings=None) -> Dict[str, Any]:
    """Return a list of run summaries for the given strategy.

    Args:
        strategy: Strategy name to look up.
        settings: Optional ``AppSettings`` instance. Must have a
            ``user_data_path`` attribute.

    Returns:
        Dict with a ``runs`` list, or an error/output dict if unavailable.
    """
    if settings is None or getattr(settings, "user_data_path", None) is None:
        _log.warning("load_run_history: user_data_path not configured")
        return {"error": "user_data_path not configured"}

    results_dir = _backtest_results_dir(settings.user_data_path)
    runs = IndexStore.get_strategy_runs(results_dir, strategy)

    if not runs:
        _log.info("load_run_history: no results for strategy=%s", strategy)
        return {"output": f"No results found for strategy: {strategy}", "error": None}

    summaries = [
        {
            "date": r.get("saved_at", ""),
            "profit_factor": r.get("profit_factor"),
            "win_rate": r.get("win_rate_pct"),
            "total_trades": r.get("trades_count"),
            "run_id": r.get("run_id"),
            "profit_total_pct": r.get("profit_total_pct"),
            "max_drawdown_pct": r.get("max_drawdown_pct"),
        }
        for r in runs
    ]
    _log.debug("load_run_history: strategy=%s runs=%d", strategy, len(summaries))
    return {"runs": summaries}


def compare_runs(run_id_a: str, run_id_b: str, settings=None) -> Dict[str, Any]:
    """Return a side-by-side metric comparison of two runs.

    Args:
        run_id_a: ID of the first run.
        run_id_b: ID of the second run.
        settings: Optional ``AppSettings`` instance. Must have a
            ``user_data_path`` attribute.

    Returns:
        Dict with ``run_a`` and ``run_b`` sub-dicts, or an error dict if
        either run is not found or ``user_data_path`` is not configured.
    """
    if settings is None or getattr(settings, "user_data_path", None) is None:
        _log.warning("compare_runs: user_data_path not configured")
        return {"error": "user_data_path not configured"}

    results_dir = _backtest_results_dir(settings.user_data_path)

    entry_a = _find_run_entry(results_dir, run_id_a)
    if entry_a is None:
        _log.warning("compare_runs: run not found: %s", run_id_a)
        return {"error": f"Run not found: {run_id_a}"}

    entry_b = _find_run_entry(results_dir, run_id_b)
    if entry_b is None:
        _log.warning("compare_runs: run not found: %s", run_id_b)
        return {"error": f"Run not found: {run_id_b}"}

    def _extract(entry: Dict) -> Dict:
        return {k: entry.get(k) for k in _COMPARE_KEYS}

    _log.debug("compare_runs: comparing %s vs %s", run_id_a, run_id_b)
    return {
        "run_a": _extract(entry_a),
        "run_b": _extract(entry_b),
    }


def register_backtest_tools(registry: ToolRegistry, settings=None) -> None:
    """Register all backtest tools into the given registry.

    Args:
        registry: The :class:`ToolRegistry` to register tools into.
        settings: Optional ``AppSettings`` instance forwarded to each tool.
    """
    registry.register(ToolDefinition(
        name="get_latest_backtest_result",
        description=(
            "Return the most recent backtest run summary across all strategies. "
            "Includes profit factor, win rate, total trades, drawdown, and Sharpe ratio."
        ),
        parameters_schema={"type": "object", "properties": {}, "required": []},
        callable=lambda: get_latest_backtest_result(settings),
    ))

    registry.register(ToolDefinition(
        name="load_run_history",
        description=(
            "Return a list of backtest run summaries for a specific strategy, "
            "ordered newest first. Each entry includes date, profit factor, "
            "win rate, and total trades."
        ),
        parameters_schema={
            "type": "object",
            "properties": {
                "strategy": {
                    "type": "string",
                    "description": "Strategy name to retrieve run history for",
                },
            },
            "required": ["strategy"],
        },
        callable=lambda strategy: load_run_history(strategy, settings),
    ))

    registry.register(ToolDefinition(
        name="compare_runs",
        description=(
            "Compare two backtest runs side-by-side by their run IDs. "
            "Returns key metrics for both runs for direct comparison."
        ),
        parameters_schema={
            "type": "object",
            "properties": {
                "run_id_a": {
                    "type": "string",
                    "description": "ID of the first run to compare",
                },
                "run_id_b": {
                    "type": "string",
                    "description": "ID of the second run to compare",
                },
            },
            "required": ["run_id_a", "run_id_b"],
        },
        callable=lambda run_id_a, run_id_b: compare_runs(run_id_a, run_id_b, settings),
    ))

    _log.debug("Backtest tools registered: get_latest_backtest_result, load_run_history, compare_runs")
