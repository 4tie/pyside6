"""Tests for IndexStore (global backtest index)."""
import json

import pytest

from app.core.backtests.results_index import IndexStore
from app.core.backtests.results_store import RunStore
from tests.conftest import SAMPLE_STRATEGY


def test_index_created_after_save(sample_results, strategy_results_dir, backtest_results_dir):
    # strategy_results_dir is inside backtest_results_dir
    strat_dir = backtest_results_dir / SAMPLE_STRATEGY
    strat_dir.mkdir(parents=True, exist_ok=True)

    RunStore.save(
        results=sample_results,
        strategy_results_dir=str(strat_dir),
    )

    index_path = backtest_results_dir / "index.json"
    assert index_path.exists()


def test_index_contains_strategy(sample_results, backtest_results_dir):
    strat_dir = backtest_results_dir / SAMPLE_STRATEGY
    strat_dir.mkdir(parents=True, exist_ok=True)

    RunStore.save(
        results=sample_results,
        strategy_results_dir=str(strat_dir),
    )

    index = IndexStore.load(str(backtest_results_dir))
    assert SAMPLE_STRATEGY in index["strategies"]


def test_get_strategy_runs_returns_entries(sample_results, backtest_results_dir):
    import time
    strat_dir = backtest_results_dir / SAMPLE_STRATEGY
    strat_dir.mkdir(parents=True, exist_ok=True)

    RunStore.save(results=sample_results, strategy_results_dir=str(strat_dir))
    time.sleep(1.1)
    RunStore.save(results=sample_results, strategy_results_dir=str(strat_dir))

    runs = IndexStore.get_strategy_runs(str(backtest_results_dir), SAMPLE_STRATEGY)
    assert len(runs) == 2


def test_index_run_entry_fields(sample_results, backtest_results_dir):
    strat_dir = backtest_results_dir / SAMPLE_STRATEGY
    strat_dir.mkdir(parents=True, exist_ok=True)

    RunStore.save(results=sample_results, strategy_results_dir=str(strat_dir))

    runs = IndexStore.get_strategy_runs(str(backtest_results_dir), SAMPLE_STRATEGY)
    entry = runs[0]
    assert entry["strategy"] == SAMPLE_STRATEGY
    assert "profit_total_pct" in entry
    assert "trades_count" in entry
    assert "run_id" in entry


def test_index_missing_strategy_returns_empty(backtest_results_dir):
    runs = IndexStore.get_strategy_runs(str(backtest_results_dir), "NonExistent")
    assert runs == []


def test_index_load_missing_file_returns_default(tmp_path):
    index = IndexStore.load(str(tmp_path / "no_such_dir"))
    assert index == {"updated_at": "", "strategies": {}}


def test_rebuild_reconstructs_from_disk(sample_results, backtest_results_dir):
    strat_dir = backtest_results_dir / SAMPLE_STRATEGY
    strat_dir.mkdir(parents=True, exist_ok=True)

    RunStore.save(results=sample_results, strategy_results_dir=str(strat_dir))

    # Delete index and rebuild
    (backtest_results_dir / "index.json").unlink()
    rebuilt = IndexStore.rebuild(str(backtest_results_dir))

    assert SAMPLE_STRATEGY in rebuilt["strategies"]
    assert len(rebuilt["strategies"][SAMPLE_STRATEGY]["runs"]) == 1


def test_get_all_strategies(sample_results, backtest_results_dir):
    strat_dir = backtest_results_dir / SAMPLE_STRATEGY
    strat_dir.mkdir(parents=True, exist_ok=True)
    RunStore.save(results=sample_results, strategy_results_dir=str(strat_dir))

    strategies = IndexStore.get_all_strategies(str(backtest_results_dir))
    assert SAMPLE_STRATEGY in strategies
