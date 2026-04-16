"""Tests for RunStore.save() and RunStore.load_run()."""
import json
from pathlib import Path

import pytest

from app.core.backtests.results_store import RunStore
from tests.conftest import SAMPLE_STRATEGY


def test_save_creates_expected_files(sample_results, strategy_results_dir):
    run_dir = RunStore.save(
        results=sample_results,
        strategy_results_dir=str(strategy_results_dir),
    )
    assert run_dir.exists()
    assert (run_dir / "meta.json").exists()
    assert (run_dir / "results.json").exists()
    assert (run_dir / "trades.json").exists()
    assert (run_dir / "params.json").exists()


def test_save_meta_fields(sample_results, strategy_results_dir):
    run_dir = RunStore.save(
        results=sample_results,
        strategy_results_dir=str(strategy_results_dir),
    )
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["strategy"] == SAMPLE_STRATEGY
    assert meta["trades_count"] == 2
    assert meta["wins"] == 1
    assert meta["losses"] == 1
    assert "run_id" in meta
    assert meta["version_id"] is None


def test_save_with_version_id(sample_results, strategy_results_dir):
    run_dir = RunStore.save(
        results=sample_results,
        strategy_results_dir=str(strategy_results_dir),
        version_id="test-version-123",
    )
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["version_id"] == "test-version-123"


def test_save_trades_contain_exit_reason(sample_results, strategy_results_dir):
    run_dir = RunStore.save(
        results=sample_results,
        strategy_results_dir=str(strategy_results_dir),
    )
    trades = json.loads((run_dir / "trades.json").read_text(encoding="utf-8"))
    assert len(trades) == 2
    reasons = {t["exit_reason"] for t in trades}
    assert "roi" in reasons
    assert "stop_loss" in reasons


def test_load_run_round_trip(sample_results, strategy_results_dir):
    run_dir = RunStore.save(
        results=sample_results,
        strategy_results_dir=str(strategy_results_dir),
    )
    loaded = RunStore.load_run(run_dir)
    assert loaded.summary.strategy == SAMPLE_STRATEGY
    assert loaded.summary.total_trades == 2
    assert len(loaded.trades) == 2


def test_load_run_trades_have_exit_reason(sample_results, strategy_results_dir):
    run_dir = RunStore.save(
        results=sample_results,
        strategy_results_dir=str(strategy_results_dir),
    )
    loaded = RunStore.load_run(run_dir)
    reasons = {t.exit_reason for t in loaded.trades}
    assert "roi" in reasons
    assert "stop_loss" in reasons


def test_load_run_missing_results_raises(tmp_path):
    empty_dir = tmp_path / "empty_run"
    empty_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        RunStore.load_run(empty_dir)


def test_save_run_id_format(sample_results, strategy_results_dir):
    run_dir = RunStore.save(
        results=sample_results,
        strategy_results_dir=str(strategy_results_dir),
    )
    assert run_dir.name.startswith("run_")
