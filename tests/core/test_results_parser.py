"""Tests for the backtest results parser."""
import json
import zipfile

import pytest

from app.core.backtests.results_parser import parse_backtest_zip, parse_result_json_file
from tests.conftest import SAMPLE_STRATEGY


def test_parse_zip_returns_results(backtest_zip):
    results = parse_backtest_zip(str(backtest_zip))
    assert results.summary.strategy == SAMPLE_STRATEGY
    assert results.summary.total_trades == 2


def test_parse_zip_summary_fields(backtest_zip):
    results = parse_backtest_zip(str(backtest_zip))
    s = results.summary
    assert s.wins == 1
    assert s.losses == 1
    assert s.total_profit == pytest.approx(0.8, rel=0.01)
    assert s.max_drawdown == pytest.approx(5.0, rel=0.01)
    assert s.sharpe_ratio == pytest.approx(1.2, rel=0.01)


def test_parse_zip_trades_populated(backtest_zip):
    results = parse_backtest_zip(str(backtest_zip))
    assert len(results.trades) == 2


def test_parse_zip_trade_exit_reason(backtest_zip):
    """exit_reason must be parsed from freqtrade's raw trade data."""
    results = parse_backtest_zip(str(backtest_zip))
    reasons = {t.exit_reason for t in results.trades}
    assert "roi" in reasons
    assert "stop_loss" in reasons


def test_parse_zip_trade_fields(backtest_zip):
    results = parse_backtest_zip(str(backtest_zip))
    t = results.trades[0]
    assert t.pair in ("ADA/USDT", "ETH/USDT")
    assert t.profit != 0
    assert t.duration == 60
    assert t.exit_reason != ""


def test_parse_zip_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        parse_backtest_zip(str(tmp_path / "nonexistent.zip"))


def test_parse_zip_empty_zip_raises(tmp_path):
    empty_zip = tmp_path / "empty.zip"
    with zipfile.ZipFile(empty_zip, "w"):
        pass
    with pytest.raises(ValueError):
        parse_backtest_zip(str(empty_zip))


def test_parse_json_file(backtest_json):
    results = parse_result_json_file(str(backtest_json))
    assert results.summary.strategy == SAMPLE_STRATEGY
    assert results.summary.total_trades == 2


def test_parse_json_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        parse_result_json_file(str(tmp_path / "no.json"))
