"""
Shared pytest fixtures for the entire test suite.
All paths are relative to tmp_path — no hardcoded machine paths.
"""
import json
import zipfile
from datetime import datetime
from pathlib import Path

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Minimal sample data that mirrors real freqtrade output shapes
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_STRATEGY = "TestStrategy"

SAMPLE_TRADE = {
    "pair": "ADA/USDT",
    "stake_amount": 40.0,
    "max_stake_amount": 40.0,
    "amount": 100.0,
    "open_date": "2026-01-01 00:00:00",
    "close_date": "2026-01-01 01:00:00",
    "open_rate": 0.40,
    "close_rate": 0.42,
    "fee_open": 0.001,
    "fee_close": 0.001,
    "trade_duration": 60,
    "profit_ratio": 0.05,
    "profit_abs": 2.0,
    "exit_reason": "roi",
    "is_open": False,
    "enter_tag": "buy",
    "leverage": 1.0,
    "is_short": False,
    "open_timestamp": 1735689600000,
    "close_timestamp": 1735693200000,
}

SAMPLE_LOSING_TRADE = {
    **SAMPLE_TRADE,
    "pair": "ETH/USDT",
    "profit_ratio": -0.03,
    "profit_abs": -1.2,
    "exit_reason": "stop_loss",
    "close_rate": 0.388,
}

SAMPLE_STRATEGY_DATA = {
    "trades": [SAMPLE_TRADE, SAMPLE_LOSING_TRADE],
    "total_trades": 2,
    "wins": 1,
    "losses": 1,
    "draws": 0,
    "winrate": 0.5,
    "profit_mean": 0.01,
    "profit_total": 0.008,
    "profit_total_abs": 0.8,
    "holding_avg_s": 3600.0,
    "max_relative_drawdown": 0.05,
    "max_drawdown_abs": 2.0,
    "sharpe": 1.2,
    "sortino": 1.5,
    "calmar": 0.8,
    "starting_balance": 80.0,
    "final_balance": 80.8,
    "timeframe": "5m",
    "timerange": "20260101-20260201",
    "backtest_start": "2026-01-01 00:00:00",
    "backtest_end": "2026-02-01 00:00:00",
    "pairlist": ["ADA/USDT", "ETH/USDT"],
    "expectancy": 0.4,
    "profit_factor": 1.67,
    "max_consecutive_wins": 1,
    "max_consecutive_losses": 1,
}


def _make_backtest_json(strategy: str = SAMPLE_STRATEGY) -> dict:
    """Return a dict matching freqtrade's backtest result JSON structure."""
    return {"strategy": {strategy: SAMPLE_STRATEGY_DATA}}


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def backtest_json(tmp_path: Path) -> Path:
    """Write a minimal freqtrade backtest result JSON and return its path."""
    data = _make_backtest_json()
    p = tmp_path / "backtest-result-test.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


@pytest.fixture()
def backtest_zip(tmp_path: Path) -> Path:
    """Write a minimal freqtrade backtest result ZIP and return its path."""
    data = _make_backtest_json()
    json_name = "backtest-result-test.json"
    zip_path = tmp_path / "backtest-result-test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(json_name, json.dumps(data))
    return zip_path


@pytest.fixture()
def strategy_results_dir(tmp_path: Path) -> Path:
    """Return a fresh per-strategy backtest results directory."""
    d = tmp_path / "backtest_results" / SAMPLE_STRATEGY
    d.mkdir(parents=True)
    return d


@pytest.fixture()
def backtest_results_dir(tmp_path: Path) -> Path:
    """Return a fresh top-level backtest results directory (no sub-dirs created)."""
    d = tmp_path / "br_root"
    d.mkdir(parents=True)
    return d


@pytest.fixture()
def sample_results(backtest_zip):
    """Return parsed BacktestResults from the sample zip fixture."""
    from app.core.backtests.results_parser import parse_backtest_zip
    return parse_backtest_zip(str(backtest_zip))
