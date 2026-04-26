"""Backtest results parsing module.

Handles parsing of freqtrade backtest results from both zip files and JSON files.
"""

import json
import zipfile
from pathlib import Path
from typing import Any, Dict, List

from app.core.models.backtest_models import BacktestResults, BacktestSummary, BacktestTrade
from app.core.parsing.json_parser import ParseError
from app.core.utils.app_logger import get_logger

_log = get_logger("parsing.backtest")


def parse_backtest_results_from_zip(zip_path: str) -> BacktestResults:
    """Parse a freqtrade backtest zip and return structured results.

    Args:
        zip_path: Path to the .zip file written by freqtrade.

    Returns:
        BacktestResults

    Raises:
        ParseError: If zip does not exist or JSON is malformed.
    """
    path = Path(zip_path)
    if not path.exists():
        raise FileNotFoundError(f"Backtest zip not found: {path}")

    try:
        with zipfile.ZipFile(path) as zf:
            json_files = [n for n in zf.namelist()
                          if n.endswith(".json") and "_config" not in n]
            if not json_files:
                raise ValueError(f"No result JSON found in zip: {path}")
            _log.debug("Parsing zip: %s | entry=%s", path.name, json_files[0])
            data = json.loads(zf.read(json_files[0]).decode("utf-8"))
    except (FileNotFoundError, ValueError):
        raise
    except json.JSONDecodeError as e:
        _log.error("JSON decode error in %s: %s", path.name, e)
        raise ValueError(f"Failed to parse backtest JSON in {path}") from e
    except Exception as e:
        _log.error("Failed to open zip %s: %s", path.name, e)
        raise ValueError(f"Failed to parse backtest zip {path}: {e}") from e

    result = _parse_results_data(data)
    _log.info("Parsed | strategy=%s | trades=%d | profit=%.4f%%",
              result.summary.strategy, result.summary.total_trades, result.summary.total_profit)
    return result


def parse_backtest_results_from_json(json_path: str) -> BacktestResults:
    """Parse a bt-*.result.json file directly.

    Args:
        json_path: Path to the result JSON file.

    Returns:
        BacktestResults

    Raises:
        ParseError: If file does not exist or JSON is malformed.
    """
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"Result file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return _parse_results_data(data)
    except FileNotFoundError:
        raise
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse result JSON {path}") from e
    except Exception as e:
        raise ValueError(f"Failed to parse result file {path}: {e}") from e


def _parse_results_data(data: Dict[str, Any]) -> BacktestResults:
    """Parse freqtrade result JSON (zip format or bt-*.result.json format).

    Zip format:  {"strategy": {"<Name>": {"trades": [...], "total_trades": N, ...}}}
    File format: {"strategy": "<Name>", "result": {"trades": [...]}, ...}
    """
    strategy_block = data.get("strategy", {})

    if isinstance(strategy_block, dict):
        strategy_name = next(iter(strategy_block), "Unknown")
        sd = strategy_block[strategy_name]
        trades_data = sd.get("trades", [])
    else:
        strategy_name = str(strategy_block)
        sd = {}
        trades_data = data.get("result", {}).get("trades", [])

    trades = _parse_trades_data(trades_data)
    summary = _build_backtest_summary(strategy_name, sd, trades)
    return BacktestResults(summary=summary, trades=trades, raw_data=data)


def _parse_trades_data(trades_data: List[Dict]) -> List[BacktestTrade]:
    trades = []
    for t in trades_data:
        try:
            trades.append(BacktestTrade(
                pair=t.get("pair", ""),
                stake_amount=float(t.get("stake_amount", 0)),
                amount=float(t.get("amount", 0)),
                open_date=str(t.get("open_date", "")),
                close_date=str(t.get("close_date", "")) or None,
                open_rate=float(t.get("open_rate", 0)),
                close_rate=float(t.get("close_rate", 0)) if t.get("close_rate") else None,
                profit=float(t.get("profit_ratio", 0)) * 100,
                profit_abs=float(t.get("profit_abs", 0)),
                duration=int(t.get("trade_duration", 0)),
                is_open=bool(t.get("is_open", False)),
                exit_reason=str(t.get("exit_reason", "")),
            ))
        except (ValueError, KeyError):
            continue
    return trades


def _build_backtest_summary(strategy_name: str, sd: Dict, trades: List[BacktestTrade]) -> BacktestSummary:
    total = len(trades)
    wins   = int(sd.get("wins",   sum(1 for t in trades if t.profit > 0)))
    losses = int(sd.get("losses", sum(1 for t in trades if t.profit < 0)))
    draws  = int(sd.get("draws",  sum(1 for t in trades if t.profit == 0)))

    avg_s = float(sd.get("holding_avg_s", 0.0))
    avg_min = int(avg_s / 60) if avg_s else (
        int(sum(t.duration for t in trades) / total) if total else 0
    )

    return BacktestSummary(
        strategy=strategy_name,
        timeframe=str(sd.get("timeframe", "")),
        total_trades=int(sd.get("total_trades", total)),
        wins=wins,
        losses=losses,
        draws=draws,
        win_rate=float(sd.get("winrate", wins / total if total else 0.0)) * 100,
        avg_profit=float(sd.get("profit_mean", sum(t.profit for t in trades) / total if total else 0.0)) * 100,
        total_profit=float(sd.get("profit_total", 0.0)) * 100,
        total_profit_abs=float(sd.get("profit_total_abs", sum(t.profit_abs for t in trades))),
        sharpe_ratio=float(sd["sharpe"]) if sd.get("sharpe") is not None else None,
        sortino_ratio=float(sd["sortino"]) if sd.get("sortino") is not None else None,
        calmar_ratio=float(sd["calmar"]) if sd.get("calmar") is not None else None,
        max_drawdown=float(sd.get("max_relative_drawdown", sd.get("max_drawdown_account", 0.0))) * 100,
        max_drawdown_abs=float(sd.get("max_drawdown_abs", 0.0)),
        trade_duration_avg=avg_min,
        starting_balance=float(sd.get("starting_balance", sd.get("dry_run_wallet", 0.0))),
        final_balance=float(sd.get("final_balance", 0.0)),
        timerange=str(sd.get("timerange", "")),
        pairlist=list(sd.get("pairlist", [])),
        backtest_start=str(sd.get("backtest_start", "")),
        backtest_end=str(sd.get("backtest_end", "")),
        expectancy=float(sd.get("expectancy", 0.0)),
        profit_factor=float(sd.get("profit_factor", 0.0)),
        max_consecutive_wins=int(sd.get("max_consecutive_wins", 0)),
        max_consecutive_losses=int(sd.get("max_consecutive_losses", 0)),
    )
