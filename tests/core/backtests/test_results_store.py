"""
Tests for exit-reason key fix in results_store.py.

Covers:
  - Unit: _write_trades() uses "exit_reason" key (C1 write fix)
  - Unit: load_run() reads canonical "exit_reason" key (C2 read fix)
  - Unit: load_run() backward-compat fallback for legacy "reason" key (C1 read fix)
  - PBT:  round-trip save → load_run preserves exit_reason (Preservation)
  - PBT:  load_run on "exit_reason" records (C2 fix checking)
  - PBT:  load_run on legacy "reason" records (C1 fix checking)
"""
import json
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import List

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.core.backtests.results_models import BacktestResults, BacktestSummary, BacktestTrade
from app.core.backtests.results_store import RunStore, _write_trades


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _minimal_summary() -> BacktestSummary:
    return BacktestSummary(
        strategy="TestStrategy",
        timeframe="5m",
        total_trades=0,
        wins=0,
        losses=0,
        draws=0,
        win_rate=0.0,
        avg_profit=0.0,
        total_profit=0.0,
        total_profit_abs=0.0,
        sharpe_ratio=None,
        sortino_ratio=None,
        calmar_ratio=None,
        max_drawdown=0.0,
        max_drawdown_abs=0.0,
        trade_duration_avg=0,
    )


def _make_trade(exit_reason: str = "roi") -> BacktestTrade:
    return BacktestTrade(
        pair="BTC/USDT",
        stake_amount=100.0,
        amount=0.01,
        open_date="2026-01-01 00:00:00",
        close_date="2026-01-01 01:00:00",
        open_rate=10000.0,
        close_rate=10500.0,
        profit=0.05,
        profit_abs=5.0,
        duration=60,
        is_open=False,
        exit_reason=exit_reason,
    )


def _make_results(trades: List[BacktestTrade]) -> BacktestResults:
    summary = replace(_minimal_summary(), total_trades=len(trades))
    return BacktestResults(summary=summary, trades=trades, raw_data={})


def _write_trades_json(tmp_path: Path, trades: List[BacktestTrade]) -> List[dict]:
    """Call _write_trades() and return the parsed JSON list."""
    results = _make_results(trades)
    _write_trades(tmp_path, results)
    return json.loads((tmp_path / "trades.json").read_text(encoding="utf-8"))


def _make_run_dir_with_trades(tmp_path: Path, trade_records: List[dict]) -> Path:
    """Write a minimal run folder with the given raw trade records."""
    run_dir = tmp_path / "run_test"
    run_dir.mkdir()
    summary = _minimal_summary()
    results_data = {
        "strategy": summary.strategy,
        "timeframe": summary.timeframe,
        "total_trades": 0,
        "wins": 0, "losses": 0, "draws": 0,
        "win_rate_pct": 0.0, "avg_profit_pct": 0.0,
        "total_profit_pct": 0.0, "total_profit_abs": 0.0,
        "starting_balance": 0.0, "final_balance": 0.0,
        "max_drawdown_pct": 0.0, "max_drawdown_abs": 0.0,
        "avg_duration_min": 0,
    }
    (run_dir / "results.json").write_text(json.dumps(results_data), encoding="utf-8")
    (run_dir / "trades.json").write_text(json.dumps(trade_records), encoding="utf-8")
    return run_dir


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests
# ─────────────────────────────────────────────────────────────────────────────

def test_write_trades_uses_exit_reason_key(tmp_path):
    """_write_trades() must write 'exit_reason', never 'reason' (C1 write fix)."""
    records = _write_trades_json(tmp_path, [_make_trade("roi"), _make_trade("stop_loss")])
    for record in records:
        assert "exit_reason" in record, "expected 'exit_reason' key in written trade"
        assert "reason" not in record, "unexpected legacy 'reason' key in written trade"


def test_load_run_reads_canonical_exit_reason_key(tmp_path):
    """load_run() must populate exit_reason from 'exit_reason' key (C2 read fix)."""
    trade_records = [
        {"pair": "BTC/USDT", "exit_reason": "stop_loss", "stake_amount": 100.0,
         "entry": "2026-01-01 00:00:00", "exit": "2026-01-01 01:00:00",
         "entry_rate": 10000.0, "exit_rate": 9500.0, "profit_pct": -0.05,
         "profit_abs": -5.0, "duration_min": 60, "is_open": False},
    ]
    run_dir = _make_run_dir_with_trades(tmp_path, trade_records)
    loaded = RunStore.load_run(run_dir)
    assert loaded.trades[0].exit_reason == "stop_loss"


def test_load_run_legacy_reason_key_fallback(tmp_path):
    """load_run() must populate exit_reason from legacy 'reason' key (C1 backward compat)."""
    trade_records = [
        {"pair": "ETH/USDT", "reason": "roi", "stake_amount": 50.0,
         "entry": "2026-01-01 00:00:00", "exit": "2026-01-01 02:00:00",
         "entry_rate": 2000.0, "exit_rate": 2100.0, "profit_pct": 0.05,
         "profit_abs": 2.5, "duration_min": 120, "is_open": False},
    ]
    run_dir = _make_run_dir_with_trades(tmp_path, trade_records)
    loaded = RunStore.load_run(run_dir)
    assert loaded.trades[0].exit_reason == "roi"


# ─────────────────────────────────────────────────────────────────────────────
# Property-based tests (Hypothesis)
# ─────────────────────────────────────────────────────────────────────────────

_exit_reason_st = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_"),
    max_size=30,
)

_trade_st = st.builds(
    _make_trade,
    exit_reason=_exit_reason_st,
)


@given(trades=st.lists(_trade_st, min_size=0, max_size=10))
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_round_trip_preserves_exit_reason(tmp_path, trades):
    """Property 4 — Preservation: save → load_run must preserve exit_reason for all trades."""
    results = _make_results(trades)
    with tempfile.TemporaryDirectory() as td:
        strategy_dir = Path(td) / "backtest_results" / "TestStrategy"
        strategy_dir.mkdir(parents=True, exist_ok=True)
        run_dir = RunStore.save(results=results, strategy_results_dir=str(strategy_dir))
        loaded = RunStore.load_run(run_dir)
    assert len(loaded.trades) == len(trades)
    for original, loaded_trade in zip(trades, loaded.trades):
        assert loaded_trade.exit_reason == original.exit_reason


@given(exit_reason=_exit_reason_st)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_load_run_canonical_key_arbitrary_values(tmp_path, exit_reason):
    """Property 2 — Fix Checking Read Defect: load_run on 'exit_reason' records works for any string."""
    trade_records = [
        {"pair": "BTC/USDT", "exit_reason": exit_reason, "stake_amount": 100.0,
         "entry": "2026-01-01 00:00:00", "exit": "2026-01-01 01:00:00",
         "entry_rate": 10000.0, "exit_rate": 10500.0, "profit_pct": 0.05,
         "profit_abs": 5.0, "duration_min": 60, "is_open": False},
    ]
    with tempfile.TemporaryDirectory() as td:
        run_dir = _make_run_dir_with_trades(Path(td), trade_records)
        loaded = RunStore.load_run(run_dir)
    assert loaded.trades[0].exit_reason == exit_reason


@given(exit_reason=_exit_reason_st)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_load_run_legacy_key_arbitrary_values(tmp_path, exit_reason):
    """Property 3 — Fix Checking Write Defect: load_run on legacy 'reason' records migrates correctly."""
    trade_records = [
        {"pair": "ETH/USDT", "reason": exit_reason, "stake_amount": 50.0,
         "entry": "2026-01-01 00:00:00", "exit": "2026-01-01 02:00:00",
         "entry_rate": 2000.0, "exit_rate": 2100.0, "profit_pct": 0.05,
         "profit_abs": 2.5, "duration_min": 120, "is_open": False},
    ]
    with tempfile.TemporaryDirectory() as td:
        run_dir = _make_run_dir_with_trades(Path(td), trade_records)
        loaded = RunStore.load_run(run_dir)
    assert loaded.trades[0].exit_reason == exit_reason
