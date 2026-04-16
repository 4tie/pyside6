import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.core.services.backtest_results_service import BacktestResults
from app.core.utils.app_logger import get_logger

_log = get_logger("run_store")


class StrategyIndexStore:
    """Manages user_data/backtest_results/<strategy>/index.json.

    Scoped to a single strategy — run_dir paths are relative to the strategy folder.

    Structure:
    {
      "strategy": "MultiMeee",
      "updated_at": "...",
      "runs": [
        {
          "run_id": "run_2026-04-16_14-32-10_6098ac",
          "run_dir": "run_2026-04-16_14-32-10_6098ac",
          "timeframe": "5m",
          "pairs": ["ADA/USDT", "ETH/USDT"],
          "timerange": "20250421-20260416",
          "backtest_start": "...",
          "backtest_end": "...",
          "saved_at": "...",
          "profit_total_pct": -4.651,
          "profit_total_abs": -3.7208,
          "starting_balance": 80.0,
          "final_balance": 76.279,
          "max_drawdown_pct": 9.9,
          "trades_count": 231,
          "wins": 84,
          "losses": 147,
          "win_rate_pct": 36.36,
          "sharpe": -0.3,
          "profit_factor": 0.93
        },
        ...
      ]
    }
    """

    INDEX_FILENAME = "index.json"

    @staticmethod
    def update(strategy_dir: Path, run_id: str, run_dir: Path, results: BacktestResults):
        """Add or update a run entry in the strategy-level index.

        Args:
            strategy_dir: Strategy results dir, e.g. backtest_results/MultiMeee
            run_id: The run identifier string
            run_dir: Absolute path to the run folder
            results: Parsed BacktestResults for this run
        """
        index_path = strategy_dir / StrategyIndexStore.INDEX_FILENAME
        index = StrategyIndexStore._load(index_path, results.summary.strategy)

        s = results.summary
        entry = {
            "run_id":           run_id,
            "run_dir":          run_dir.name,          # just the folder name, e.g. run_2026-...
            "timeframe":        s.timeframe,
            "pairs":            s.pairlist,
            "timerange":        s.timerange,
            "backtest_start":   s.backtest_start,
            "backtest_end":     s.backtest_end,
            "saved_at":         datetime.now().isoformat(),
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

        runs = index["runs"]
        for i, r in enumerate(runs):
            if r.get("run_id") == run_id:
                runs[i] = entry
                break
        else:
            runs.append(entry)

        runs.sort(key=lambda r: r.get("saved_at", ""), reverse=True)
        index["updated_at"] = datetime.now().isoformat()
        StrategyIndexStore._save(index_path, index)
        _log.debug("Strategy index updated | strategy=%s | run_id=%s | path=%s",
                   s.strategy, run_id, index_path)

    @staticmethod
    def load(strategy_dir: str, strategy: str) -> dict:
        """Load the strategy-level index.

        Args:
            strategy_dir: Strategy results dir path
            strategy: Strategy name (used to initialise if missing)

        Returns:
            Index dict
        """
        return StrategyIndexStore._load(
            Path(strategy_dir) / StrategyIndexStore.INDEX_FILENAME, strategy
        )

    @staticmethod
    def rebuild(strategy_dir: str, strategy: str) -> dict:
        """Rebuild the strategy index by scanning run folders.

        Args:
            strategy_dir: Strategy results dir path
            strategy: Strategy name

        Returns:
            Rebuilt index dict
        """
        root = Path(strategy_dir)
        index: dict = {
            "strategy":   strategy,
            "updated_at": datetime.now().isoformat(),
            "runs":       [],
        }
        for run_dir in sorted(root.iterdir(), reverse=True):
            meta_path = run_dir / "meta.json"
            if not run_dir.is_dir() or not meta_path.exists():
                continue
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                entry = {
                    "run_id":           meta.get("run_id", run_dir.name),
                    "run_dir":          run_dir.name,
                    "timeframe":        meta.get("timeframe", ""),
                    "pairs":            meta.get("pairs", []),
                    "timerange":        meta.get("timerange", ""),
                    "backtest_start":   meta.get("backtest_start", ""),
                    "backtest_end":     meta.get("backtest_end", ""),
                    "saved_at":         meta.get("start_time", ""),
                    "profit_total_pct": meta.get("profit_total_pct", 0),
                    "profit_total_abs": meta.get("profit_total_abs", 0),
                    "starting_balance": meta.get("starting_balance", 0),
                    "final_balance":    meta.get("final_balance", 0),
                    "max_drawdown_pct": meta.get("max_drawdown_pct", 0),
                    "max_drawdown_abs": meta.get("max_drawdown_abs", 0),
                    "trades_count":     meta.get("trades_count", 0),
                    "wins":             meta.get("wins", 0),
                    "losses":           meta.get("losses", 0),
                    "win_rate_pct":     meta.get("win_rate_pct", 0),
                    "sharpe":           meta.get("sharpe"),
                    "sortino":          meta.get("sortino"),
                    "calmar":           meta.get("calmar"),
                    "profit_factor":    meta.get("profit_factor", 0),
                    "expectancy":       meta.get("expectancy", 0),
                }
                index["runs"].append(entry)
            except Exception:
                continue

        StrategyIndexStore._save(root / StrategyIndexStore.INDEX_FILENAME, index)
        _log.info("Strategy index rebuilt | strategy=%s | runs=%d", strategy, len(index["runs"]))
        return index

    @staticmethod
    def _load(path: Path, strategy: str = "") -> dict:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"strategy": strategy, "updated_at": "", "runs": []}

    @staticmethod
    def _save(path: Path, index: dict):
        path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")


class IndexStore:
    """Manages user_data/backtest_results/index.json.

    The index is a fast lookup file — no need to open individual run folders.

    Structure:
    {
      "updated_at": "...",
      "strategies": {
        "MultiMeee": {
          "runs": [
            {
              "run_id": "run_2026-04-16_14-32-10_6098ac",
              "run_dir": "MultiMeee/run_2026-04-16_14-32-10_6098ac",
              "strategy": "MultiMeee",
              "timeframe": "5m",
              "pairs": ["ADA/USDT", "ETH/USDT"],
              "timerange": "20250421-20260416",
              "backtest_start": "...",
              "backtest_end": "...",
              "saved_at": "...",
              "profit_total_pct": -4.651,
              "profit_total_abs": -3.7208,
              "starting_balance": 80.0,
              "final_balance": 76.279,
              "max_drawdown_pct": 9.9,
              "trades_count": 231,
              "wins": 84,
              "losses": 147,
              "win_rate_pct": 36.36,
              "sharpe": -0.3,
              "profit_factor": 0.93
            },
            ...
          ]
        }
      }
    }
    """

    INDEX_FILENAME = "index.json"

    @staticmethod
    def update(backtest_results_dir: str, run_id: str, run_dir: Path, results: BacktestResults):
        """Add or update a run entry in the index.

        Args:
            backtest_results_dir: Root dir, e.g. user_data/backtest_results
            run_id: The run identifier string
            run_dir: Absolute path to the run folder
            results: Parsed BacktestResults for this run
        """
        index_path = Path(backtest_results_dir) / IndexStore.INDEX_FILENAME
        index = IndexStore._load(index_path)

        s = results.summary
        strategy = s.strategy

        entry = {
            "run_id":           run_id,
            "run_dir":          str(run_dir.relative_to(Path(backtest_results_dir))),
            "strategy":         strategy,
            "timeframe":        s.timeframe,
            "pairs":            s.pairlist,
            "timerange":        s.timerange,
            "backtest_start":   s.backtest_start,
            "backtest_end":     s.backtest_end,
            "saved_at":         datetime.now().isoformat(),
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
            "profit_factor":    round(s.profit_factor, 4),
            "expectancy":       round(s.expectancy, 4),
        }

        strategies = index.setdefault("strategies", {})
        strat_block = strategies.setdefault(strategy, {"runs": []})

        # Replace existing entry for same run_id, otherwise append
        runs = strat_block["runs"]
        for i, r in enumerate(runs):
            if r.get("run_id") == run_id:
                runs[i] = entry
                break
        else:
            runs.append(entry)

        # Keep runs sorted newest-first
        runs.sort(key=lambda r: r.get("saved_at", ""), reverse=True)

        index["updated_at"] = datetime.now().isoformat()
        IndexStore._save(index_path, index)
        _log.debug("Index updated | strategy=%s | run_id=%s", strategy, run_id)

    @staticmethod
    def load(backtest_results_dir: str) -> dict:
        """Load the full index.

        Args:
            backtest_results_dir: Root dir, e.g. user_data/backtest_results

        Returns:
            Index dict (empty structure if file doesn't exist)
        """
        return IndexStore._load(Path(backtest_results_dir) / IndexStore.INDEX_FILENAME)

    @staticmethod
    def get_strategy_runs(backtest_results_dir: str, strategy: str) -> list[dict]:
        """Return all run entries for a strategy, newest first.

        Args:
            backtest_results_dir: Root dir
            strategy: Strategy name

        Returns:
            List of run entry dicts
        """
        index = IndexStore.load(backtest_results_dir)
        return index.get("strategies", {}).get(strategy, {}).get("runs", [])

    @staticmethod
    def get_all_strategies(backtest_results_dir: str) -> list[str]:
        """Return all strategy names present in the index.

        Args:
            backtest_results_dir: Root dir

        Returns:
            Sorted list of strategy names
        """
        index = IndexStore.load(backtest_results_dir)
        return sorted(index.get("strategies", {}).keys())

    @staticmethod
    def rebuild(backtest_results_dir: str) -> dict:
        """Rebuild the index by scanning all run folders on disk.

        Reads only meta.json from each run folder — does not open trades or results.

        Args:
            backtest_results_dir: Root dir, e.g. user_data/backtest_results

        Returns:
            The rebuilt index dict
        """
        root = Path(backtest_results_dir)
        index: dict = {"updated_at": datetime.now().isoformat(), "strategies": {}}

        for strategy_dir in sorted(root.iterdir()):
            if not strategy_dir.is_dir():
                continue
            runs = []
            for run_dir in sorted(strategy_dir.iterdir(), reverse=True):
                meta_path = run_dir / "meta.json"
                if not run_dir.is_dir() or not meta_path.exists():
                    continue
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    meta["run_dir"] = str(run_dir.relative_to(root))
                    runs.append(meta)
                except Exception:
                    continue
            if runs:
                index["strategies"][strategy_dir.name] = {"runs": runs}

        IndexStore._save(root / IndexStore.INDEX_FILENAME, index)
        return index

    # ------------------------------------------------------------------ #

    @staticmethod
    def _load(path: Path) -> dict:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"updated_at": "", "strategies": {}}

    @staticmethod
    def _save(path: Path, index: dict):
        path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")


class RunStore:
    """Persists a single backtest run as a structured folder under the strategy results dir.

    Layout:
        user_data/backtest_results/<strategy>/
        └── run_<YYYY-MM-DD_HH-MM-SS>_<hash>/
            ├── meta.json
            ├── results.json
            ├── trades.json
            └── params.json

    Also updates user_data/backtest_results/index.json automatically.
    """

    @staticmethod
    def save(
        results: BacktestResults,
        strategy_results_dir: str,
        run_params: Optional[dict] = None,
    ) -> Path:
        """Save a backtest run to a timestamped folder and update the index.

        Args:
            results: Parsed BacktestResults
            strategy_results_dir: Base dir, e.g. user_data/backtest_results/MultiMeee
            run_params: Optional strategy knobs / hyperopt params dict

        Returns:
            Path to the created run folder
        """
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        short_hash = hashlib.md5(ts.encode()).hexdigest()[:6]
        run_id = f"run_{ts}_{short_hash}"

        run_dir = Path(strategy_results_dir) / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        _log.info("Saving run | id=%s | strategy=%s | trades=%d | profit=%.4f%%",
                  run_id, results.summary.strategy,
                  results.summary.total_trades, results.summary.total_profit)

        RunStore._write_meta(run_dir, run_id, results)
        RunStore._write_results(run_dir, results)
        RunStore._write_trades(run_dir, results)
        RunStore._write_params(run_dir, run_params, results)

        backtest_results_dir = str(Path(strategy_results_dir).parent)
        IndexStore.update(backtest_results_dir, run_id, run_dir, results)
        StrategyIndexStore.update(Path(strategy_results_dir), run_id, run_dir, results)
        _log.info("Run saved → %s", run_dir)
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
    def _write_params(run_dir: Path, run_params: Optional[dict], results: BacktestResults):
        """Write params.json — strategy knobs / hyperopt params."""
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
