"""
Unit tests for backtest_tools.py AI tools.

Tests:
  - get_latest_backtest_result
  - load_run_history
  - compare_runs
"""
from unittest.mock import patch

import pytest

from app.core.ai.tools.backtest_tools import (
    compare_runs,
    get_latest_backtest_result,
    load_run_history,
)


# ---------------------------------------------------------------------------
# get_latest_backtest_result
# ---------------------------------------------------------------------------

def test_get_latest_backtest_result_no_user_data_path():
    """Calling with settings=None returns an error dict."""
    result = get_latest_backtest_result(settings=None)
    assert result.get("error") == "user_data_path not configured"


# ---------------------------------------------------------------------------
# load_run_history
# ---------------------------------------------------------------------------

def test_load_run_history_no_user_data_path():
    """Calling with settings=None returns an error dict."""
    result = load_run_history("TestStrategy", settings=None)
    assert result.get("error") == "user_data_path not configured"


def test_load_run_history_no_results():
    """When IndexStore.get_strategy_runs returns [], output message is returned."""
    mock_settings = type("S", (), {"user_data_path": "/fake/user_data"})()

    with patch(
        "app.core.ai.tools.backtest_tools.IndexStore.get_strategy_runs",
        return_value=[],
    ):
        result = load_run_history("TestStrategy", settings=mock_settings)

    assert result.get("error") is None
    assert result.get("output") == "No results found for strategy: TestStrategy"


# ---------------------------------------------------------------------------
# compare_runs
# ---------------------------------------------------------------------------

def test_compare_runs_no_user_data_path():
    """Calling with settings=None returns an error dict."""
    result = compare_runs("run_a", "run_b", settings=None)
    assert result.get("error") == "user_data_path not configured"


def test_compare_runs_run_not_found():
    """When IndexStore.load returns an empty index, error contains the run ID."""
    mock_settings = type("S", (), {"user_data_path": "/fake/user_data"})()
    empty_index = {"updated_at": "", "strategies": {}}

    with patch(
        "app.core.ai.tools.backtest_tools.IndexStore.load",
        return_value=empty_index,
    ):
        result = compare_runs("missing-run-id", "other-run-id", settings=mock_settings)

    assert "error" in result
    assert "missing-run-id" in result["error"]
