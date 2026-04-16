"""
results_store.py — RunStore: saves a single backtest run as a structured folder.
Also provides load_run() for reconstructing BacktestResults from disk.
"""
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.core.backtests.results_models import BacktestResults, BacktestSummary, BacktestTrade
from app.core.backtests.results_index import IndexStore, StrategyIndexStore
from app.core.utils.app_logger import get_logger

_log = get_logger("backtests.store")


class RunStore:
    """Persists a backtest run as a structured folder and updates both indexes."""

    @staticmethod
    def save(
        results: BacktestResults,
        strategy_results_dir: str,
        config_path: Optional[str] = None,
        run_params: Optional[dict] = None,
    ) -> Path:
        """Save a backtest run and update indexes."""
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        short_hash = hashlib.md5(ts.encode()).hexdigest()[:6]
        run_id = f"run_{ts}_{short_hash}"

        run_dir = Path(strategy_results_dir) / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        s = results.summary
        _log.info("Saving run | id=%s | strategy=%s | trades=%d | profit=%.4f%%",
                  run_id, s.strategy, s.total_trades, s.total_profit)

        _write_meta(run_dir, run_id, results)
        _write_results(run_dir, results)
        _write_trades(run_dir, results)
        _write_config_snapshot(run_dir, config_path)
        _write_params(run_dir, run_params, results)

        backtest_results_dir = str(Path(strategy_results_dir).parent)
        IndexStore.update(backtest_results_dir, run_id, run_dir, results)
        StrategyIndexStore.update(Path(strategy_results_dir), run_id, run_dir, results)

        _log.info("Run saved → %s", run_dir)
        return run_dir

    @staticmethod
    def load_run(run_dir: Path) -> BacktestResults:
        """Reconstruct BacktestResults from a saved run folder.

        Args:
            run_dir: Path to the run folder containing results.json and trades.json.

        Returns:
            BacktestResults

        Raises:
            FileNotFoundError: If required files are missing.
            ValueError: If JSON is malformed.
        """
        results_file = run_dir / "results.json"
        trades_file = run_dir / "trades.json"

        if not results_file.exists():
            raise FileNotFoundError(f"results.json not found in {run_dir}")
        if not trades_file.exists():
            raise FileNotFoundError(f"trades.json not found in {run_dir}")

        try:
            r = json.loads(results_file.read_text(encoding="utf-8"))
            t_data = json.loads(trades_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse run files: {e}")

        summary = BacktestSummary(
            strategy=r.get("strategy", ""),
            timeframe=r.get("timeframe", ""),
            total_trades=r.get("total_trades", 0),
            wins=r.get("wins", 0),
            losses=r.get("losses", 0),
            draws=r.get("draws", 0),
            win_rate=r.get("win_rate_pct", 0.0),
            avg_profit=r.get("avg_profit_pct", 0.0),
            total_profit=r.get("total_profit_pct", 0.0),
            total_profit_abs=r.get("total_profit_abs", 0.0),
            sharpe_ratio=r.get("sharpe_ratio"),
            sortino_ratio=r.get("sortino_ratio"),
            calmar_ratio=r.get("calmar_ratio"),
            max_drawdown=r.get("max_drawdown_pct", 0.0),
            max_drawdown_abs=r.get("max_drawdown_abs", 0.0),
            trade_duration_avg=r.get("avg_duration_min", 0),
            starting_balance=r.get("starting_balance", 0.0),
            final_balance=r.get("final_balance", 0.0),
            timerange=r.get("timerange", ""),
            pairlist=r.get("pairs", []),
            backtest_start=r.get("backtest_start", ""),
            backtest_end=r.get("backtest_end", ""),
            expectancy=r.get("expectancy", 0.0),
            profit_factor=r.get("profit_factor", 0.0),
            max_consecutive_wins=r.get("max_consecutive_wins", 0),
            max_consecutive_losses=r.get("max_consecutive_losses", 0),
        )

        trades = [
            BacktestTrade(
                pair=t.get("pair", ""),
                stake_amount=float(t.get("stake_amount", 0)),
                amount=0.0,
                open_date=t.get("entry", ""),
                close_date=t.get("exit") or None,
                open_rate=float(t.get("entry_rate", 0)),
                close_rate=float(t.get("exit_rate", 0)) if t.get("exit_rate") else None,
                profit=float(t.get("profit_pct", 0)),
                profit_abs=float(t.get("profit_abs", 0)),
                duration=int(t.get("duration_min", 0)),
                is_open=bool(t.get("is_open", False)),
                exit_reason=t.get("reason", ""),
            )
            for t in t_data
        ]

        raw_data = {"result": {"trades": [{"exit_reason": t.get("reason", "")} for t in t_data]}}
        return BacktestResults(summary=summary, trades=trades, raw_data=raw_data)


# ─────────────────────────────────────────────
# Private writers
# ─────────────────────────────────────────────

def _write_meta(run_dir: Path, run_id: str, results: BacktestResults) -> None:
    s = results.summary
    meta = {
        "run_id":           run_id,
        "strategy":         s.strategy,
        "timeframe":        s.timeframe,
        "pairs":            s.pairlist,
        "start_time":       datetime.now().isoformat(),
        "timerange":        s.timerange,
        "backtest_start":   s.backtest_start,
        "backtest_end":     s.backtest_end,
        "status":           "completed",
        "profit_total_pct": round(s.total_profit, 4),
        "profit_total_abs": round(s.total_profit_abs, 4),
        "starting_balance": s.starting_balance,
        "final_balance":    round(s.final_balance, 4),
        "max_drawdown_pct": round(s.max_drawdown, 4),
        "max_drawdown_abs": round(s.max_drawdown_abs, 4),
        "trades_count":     s.total_trades,
        "wins":             s.wins,
        "losses":           s.losses,
        "win_rate_pct":     round(s.win_rate, 2),
        "sharpe":           round(s.sharpe_ratio, 4) if s.sharpe_ratio is not None else None,
        "sortino":          round(s.sortino_ratio, 4) if s.sortino_ratio is not None else None,
        "calmar":           round(s.calmar_ratio, 4) if s.calmar_ratio is not None else None,
        "profit_factor":    round(s.profit_factor, 4),
        "expectancy":       round(s.expectancy, 4),
    }
    (run_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _write_results(run_dir: Path, results: BacktestResults) -> None:
    s = results.summary
    data = {
        "strategy":               s.strategy,
        "timeframe":              s.timeframe,
        "timerange":              s.timerange,
        "backtest_start":         s.backtest_start,
        "backtest_end":           s.backtest_end,
        "pairs":                  s.pairlist,
        "total_trades":           s.total_trades,
        "wins":                   s.wins,
        "losses":                 s.losses,
        "draws":                  s.draws,
        "win_rate_pct":           round(s.win_rate, 4),
        "avg_profit_pct":         round(s.avg_profit, 6),
        "total_profit_pct":       round(s.total_profit, 6),
        "total_profit_abs":       round(s.total_profit_abs, 6),
        "starting_balance":       s.starting_balance,
        "final_balance":          round(s.final_balance, 6),
        "max_drawdown_pct":       round(s.max_drawdown, 4),
        "max_drawdown_abs":       round(s.max_drawdown_abs, 6),
        "avg_duration_min":       s.trade_duration_avg,
        "max_consecutive_wins":   s.max_consecutive_wins,
        "max_consecutive_losses": s.max_consecutive_losses,
        "sharpe_ratio":           round(s.sharpe_ratio, 4) if s.sharpe_ratio is not None else None,
        "sortino_ratio":          round(s.sortino_ratio, 4) if s.sortino_ratio is not None else None,
        "calmar_ratio":           round(s.calmar_ratio, 4) if s.calmar_ratio is not None else None,
        "profit_factor":          round(s.profit_factor, 4),
        "expectancy":             round(s.expectancy, 4),
    }
    (run_dir / "results.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _write_trades(run_dir: Path, results: BacktestResults) -> None:
    trades_out = [
        {
            "pair":         t.pair,
            "entry":        t.open_date,
            "exit":         t.close_date or "",
            "entry_rate":   t.open_rate,
            "exit_rate":    t.close_rate,
            "duration_min": t.duration,
            "reason":       t.exit_reason,
            "profit_pct":   round(t.profit, 6),
            "profit_abs":   round(t.profit_abs, 8),
            "stake_amount": t.stake_amount,
            "is_open":      t.is_open,
        }
        for t in results.trades
    ]
    (run_dir / "trades.json").write_text(
        json.dumps(trades_out, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _write_config_snapshot(run_dir: Path, config_path: Optional[str]) -> None:
    """Copy the config used for the run into the run folder when available."""
    if not config_path:
        return

    source = Path(config_path)
    if not source.exists() or not source.is_file():
        _log.warning("Config snapshot skipped, file not found: %s", source)
        return

    shutil.copy2(source, run_dir / "config.snapshot.json")


def _write_params(run_dir: Path, run_params: Optional[dict],
                  results: BacktestResults) -> None:
    if run_params:
        params = run_params
    else:
        sd = {}
        strategy_block = results.raw_data.get("strategy", {})
        if isinstance(strategy_block, dict):
            sd = strategy_block.get(results.summary.strategy, {})
        params = {
            "buy_params":  sd.get("buy_params", {}),
            "sell_params": sd.get("sell_params", {}),
            "minimal_roi": sd.get("minimal_roi", {}),
            "stoploss":    sd.get("stoploss"),
        }
    (run_dir / "params.json").write_text(
        json.dumps(params, indent=2, ensure_ascii=False), encoding="utf-8"
    )
