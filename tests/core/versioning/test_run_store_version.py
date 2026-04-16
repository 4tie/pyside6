"""Unit tests for RunStore.save() with version_id integration."""
import json
import pytest
from pathlib import Path

from app.core.backtests.results_models import BacktestResults, BacktestSummary
from app.core.backtests.results_store import RunStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_backtest_results(strategy="TestStrategy") -> BacktestResults:
    summary = BacktestSummary(
        strategy=strategy,
        timeframe="5m",
        total_trades=10,
        wins=6,
        losses=4,
        draws=0,
        win_rate=60.0,
        avg_profit=1.5,
        total_profit=15.0,
        total_profit_abs=150.0,
        sharpe_ratio=1.2,
        sortino_ratio=1.5,
        calmar_ratio=0.8,
        max_drawdown=5.0,
        max_drawdown_abs=50.0,
        trade_duration_avg=120,
        starting_balance=1000.0,
        final_balance=1150.0,
        timerange="20240101-20240201",
        pairlist=["BTC/USDT"],
        backtest_start="2024-01-01",
        backtest_end="2024-02-01",
        expectancy=0.9,
        profit_factor=1.5,
        max_consecutive_wins=3,
        max_consecutive_losses=2,
    )
    return BacktestResults(summary=summary, trades=[], raw_data={})


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_save_with_version_id_writes_to_meta(tmp_path):
    results = make_backtest_results()
    strategy_results_dir = str(tmp_path / "backtest_results" / "TestStrategy")

    run_dir = RunStore.save(results, strategy_results_dir, version_id="test-uuid-123")

    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["version_id"] == "test-uuid-123"


def test_save_without_version_id_writes_null(tmp_path):
    results = make_backtest_results()
    strategy_results_dir = str(tmp_path / "backtest_results" / "TestStrategy")

    run_dir = RunStore.save(results, strategy_results_dir)

    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["version_id"] is None


def test_save_meta_json_contains_version_id_key(tmp_path):
    """version_id key must always be present in meta.json (even when null)."""
    results = make_backtest_results()
    strategy_results_dir = str(tmp_path / "backtest_results" / "TestStrategy")

    run_dir = RunStore.save(results, strategy_results_dir)

    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    assert "version_id" in meta


def test_save_creates_run_dir(tmp_path):
    results = make_backtest_results()
    strategy_results_dir = str(tmp_path / "backtest_results" / "TestStrategy")

    run_dir = RunStore.save(results, strategy_results_dir, version_id="v-abc")

    assert run_dir.exists()
    assert run_dir.is_dir()


def test_save_meta_json_run_id_matches_dir_name(tmp_path):
    results = make_backtest_results()
    strategy_results_dir = str(tmp_path / "backtest_results" / "TestStrategy")

    run_dir = RunStore.save(results, strategy_results_dir)

    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["run_id"] == run_dir.name
