import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.core.services.backtest_results_service import BacktestResults


class RunStore:
    """Persists a single backtest run as a structured folder under the strategy results dir.

    Layout:
        user_data/backtest_results/<strategy>/
        └── run_<YYYY-MM-DD_HH-MM-SS>_<hash>/
            ├── meta.json
            ├── results.json
            ├── trades.json
            ├── config.snapshot.json
            └── params.json
    """

    @staticmethod
    def save(
        results: BacktestResults,
        strategy_results_dir: str,
        config_path: Optional[str] = None,
        run_params: Optional[dict] = None,
    ) -> Path:
        """Save a backtest run to a timestamped folder.

        Args:
            results: Parsed BacktestResults
            strategy_results_dir: Base dir, e.g. user_data/backtest_results/MultiMeee
            config_path: Path to the config file used for this run (for snapshot)
            run_params: Optional strategy knobs / hyperopt params dict

        Returns:
            Path to the created run folder
        """
        s = results.summary
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        short_hash = hashlib.md5(ts.encode()).hexdigest()[:6]
        run_id = f"run_{ts}_{short_hash}"

        run_dir = Path(strategy_results_dir) / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        RunStore._write_meta(run_dir, run_id, results)
        RunStore._write_results(run_dir, results)
        RunStore._write_trades(run_dir, results)
        RunStore._write_config_snapshot(run_dir, config_path, results)
        RunStore._write_params(run_dir, run_params, results)

        return run_dir

    # ------------------------------------------------------------------ #

    @staticmethod
    def _write_meta(run_dir: Path, run_id: str, results: BacktestResults):
        """Write meta.json — lightweight tracking record."""
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

    @staticmethod
    def _write_results(run_dir: Path, results: BacktestResults):
        """Write results.json — full summary stats."""
        s = results.summary
        data = {
            "strategy":              s.strategy,
            "timeframe":             s.timeframe,
            "timerange":             s.timerange,
            "backtest_start":        s.backtest_start,
            "backtest_end":          s.backtest_end,
            "pairs":                 s.pairlist,
            "total_trades":          s.total_trades,
            "wins":                  s.wins,
            "losses":                s.losses,
            "draws":                 s.draws,
            "win_rate_pct":          round(s.win_rate, 4),
            "avg_profit_pct":        round(s.avg_profit, 6),
            "total_profit_pct":      round(s.total_profit, 6),
            "total_profit_abs":      round(s.total_profit_abs, 6),
            "starting_balance":      s.starting_balance,
            "final_balance":         round(s.final_balance, 6),
            "max_drawdown_pct":      round(s.max_drawdown, 4),
            "max_drawdown_abs":      round(s.max_drawdown_abs, 6),
            "avg_duration_min":      s.trade_duration_avg,
            "max_consecutive_wins":  s.max_consecutive_wins,
            "max_consecutive_losses":s.max_consecutive_losses,
            "sharpe_ratio":          round(s.sharpe_ratio, 4) if s.sharpe_ratio is not None else None,
            "sortino_ratio":         round(s.sortino_ratio, 4) if s.sortino_ratio is not None else None,
            "calmar_ratio":          round(s.calmar_ratio, 4) if s.calmar_ratio is not None else None,
            "profit_factor":         round(s.profit_factor, 4),
            "expectancy":            round(s.expectancy, 4),
        }
        (run_dir / "results.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    @staticmethod
    def _write_trades(run_dir: Path, results: BacktestResults):
        """Write trades.json — one entry per trade."""
        raw_trades = (
            results.raw_data.get("strategy", {})
            .get(results.summary.strategy, {})
            .get("trades", [])
        ) if isinstance(results.raw_data.get("strategy"), dict) else (
            results.raw_data.get("result", {}).get("trades", [])
        )

        trades_out = []
        for i, t in enumerate(results.trades):
            raw = raw_trades[i] if i < len(raw_trades) else {}
            trades_out.append({
                "pair":         t.pair,
                "entry":        t.open_date,
                "exit":         t.close_date or "",
                "entry_rate":   t.open_rate,
                "exit_rate":    t.close_rate,
                "duration_min": t.duration,
                "reason":       raw.get("exit_reason", ""),
                "profit_pct":   round(t.profit, 6),
                "profit_abs":   round(t.profit_abs, 8),
                "stake_amount": t.stake_amount,
                "is_open":      t.is_open,
            })

        (run_dir / "trades.json").write_text(
            json.dumps(trades_out, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    @staticmethod
    def _write_config_snapshot(
        run_dir: Path,
        config_path: Optional[str],
        results: BacktestResults,
    ):
        """Write config.snapshot.json — config used at run time."""
        snapshot: dict = {}

        if config_path and Path(config_path).exists():
            try:
                snapshot = json.loads(Path(config_path).read_text(encoding="utf-8"))
            except Exception:
                pass

        # Enrich with runtime values from parsed results if available
        s = results.summary
        snapshot.setdefault("timeframe", s.timeframe)
        snapshot.setdefault("dry_run_wallet", s.starting_balance)

        (run_dir / "config.snapshot.json").write_text(
            json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    @staticmethod
    def _write_params(run_dir: Path, run_params: Optional[dict], results: BacktestResults):
        """Write params.json — strategy knobs / hyperopt params."""
        params: dict = {}

        if run_params:
            params = run_params
        else:
            # Try to extract buy/sell params from raw data
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
