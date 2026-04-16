"""Tests for StrategyIndexStore (per-strategy index)."""
import json

import pytest

from app.core.backtests.results_index import StrategyIndexStore
from app.core.backtests.results_store import RunStore
from tests.conftest import SAMPLE_STRATEGY


def test_strategy_index_created_after_save(sample_results, strategy_results_dir):
    RunStore.save(results=sample_results, strategy_results_dir=str(strategy_results_dir))
    assert (strategy_results_dir / "index.json").exists()


def test_strategy_index_contains_run(sample_results, strategy_results_dir):
    RunStore.save(results=sample_results, strategy_results_dir=str(strategy_results_dir))
    index = StrategyIndexStore.load(str(strategy_results_dir), SAMPLE_STRATEGY)
    assert len(index["runs"]) == 1
    assert index["strategy"] == SAMPLE_STRATEGY


def test_strategy_index_run_dir_is_folder_name_only(sample_results, strategy_results_dir):
    """run_dir in strategy index must be just the folder name, not a full path."""
    run_dir = RunStore.save(results=sample_results, strategy_results_dir=str(strategy_results_dir))
    index = StrategyIndexStore.load(str(strategy_results_dir), SAMPLE_STRATEGY)
    run_dir_field = index["runs"][0]["run_dir"]
    assert "/" not in run_dir_field
    assert "\\" not in run_dir_field
    assert run_dir_field == run_dir.name


def test_strategy_index_multiple_runs_sorted_newest_first(sample_results, strategy_results_dir):
    import time
    RunStore.save(results=sample_results, strategy_results_dir=str(strategy_results_dir))
    time.sleep(1.1)
    RunStore.save(results=sample_results, strategy_results_dir=str(strategy_results_dir))
    index = StrategyIndexStore.load(str(strategy_results_dir), SAMPLE_STRATEGY)
    assert len(index["runs"]) == 2
    # Newest first
    assert index["runs"][0]["saved_at"] >= index["runs"][1]["saved_at"]


def test_strategy_index_rebuild(sample_results, strategy_results_dir):
    import time
    RunStore.save(results=sample_results, strategy_results_dir=str(strategy_results_dir))
    time.sleep(1.1)
    RunStore.save(results=sample_results, strategy_results_dir=str(strategy_results_dir))

    # Delete index and rebuild
    (strategy_results_dir / "index.json").unlink()
    rebuilt = StrategyIndexStore.rebuild(str(strategy_results_dir), SAMPLE_STRATEGY)

    assert rebuilt["strategy"] == SAMPLE_STRATEGY
    assert len(rebuilt["runs"]) == 2


def test_strategy_index_load_missing_returns_default(tmp_path):
    index = StrategyIndexStore.load(str(tmp_path / "no_such"), "Ghost")
    assert index["runs"] == []
    assert index["strategy"] == "Ghost"
