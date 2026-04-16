"""
results_index.py — IndexStore and StrategyIndexStore.

IndexStore      : manages backtest_results/index.json (all strategies)
StrategyIndexStore : manages backtest_results/{strategy}/index.json (per strategy)
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from app.core.backtests.results_models import BacktestResults
from app.core.utils.app_logger import get_logger

_log = get_logger("backtests.index")

_INDEX_FILE = "index.json"


# ─────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────

def _load_json(path: Path, default: dict) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default


def _save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _entry_from_results(run_id: str, run_dir: Path, results: BacktestResults,
                        relative_to: Path) -> Dict:
    s = results.summary
    return {
        "run_id":           run_id,
        "run_dir":          str(run_dir.relative_to(relative_to)),
        "strategy":         s.strategy,
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


def _upsert_run(runs: List[Dict], run_id: str, entry: Dict) -> None:
    for i, r in enumerate(runs):
        if r.get("run_id") == run_id:
            runs[i] = entry
            return
    runs.append(entry)


# ─────────────────────────────────────────────
# IndexStore — global index across all strategies
# ─────────────────────────────────────────────

class IndexStore:
    """Manages backtest_results/index.json — fast lookup across all strategies."""

    @staticmethod
    def update(backtest_results_dir: str, run_id: str,
               run_dir: Path, results: BacktestResults) -> None:
        """Add or update a run entry in the global index."""
        root = Path(backtest_results_dir)
        index_path = root / _INDEX_FILE
        index = _load_json(index_path, {"updated_at": "", "strategies": {}})

        entry = _entry_from_results(run_id, run_dir, results, root)
        strategy = results.summary.strategy
        strat_block = index.setdefault("strategies", {}).setdefault(strategy, {"runs": []})
        _upsert_run(strat_block["runs"], run_id, entry)
        strat_block["runs"].sort(key=lambda r: r.get("saved_at", ""), reverse=True)

        index["updated_at"] = datetime.now().isoformat()
        _save_json(index_path, index)
        _log.debug("Global index updated | strategy=%s | run_id=%s", strategy, run_id)

    @staticmethod
    def load(backtest_results_dir: str) -> dict:
        """Load the full global index."""
        return _load_json(
            Path(backtest_results_dir) / _INDEX_FILE,
            {"updated_at": "", "strategies": {}}
        )

    @staticmethod
    def get_strategy_runs(backtest_results_dir: str, strategy: str) -> List[Dict]:
        """Return all run entries for a strategy, newest first."""
        index = IndexStore.load(backtest_results_dir)
        return index.get("strategies", {}).get(strategy, {}).get("runs", [])

    @staticmethod
    def get_all_strategies(backtest_results_dir: str) -> List[str]:
        """Return sorted list of strategy names in the index."""
        return sorted(IndexStore.load(backtest_results_dir).get("strategies", {}).keys())

    @staticmethod
    def rebuild(backtest_results_dir: str) -> dict:
        """Rebuild global index by scanning all run folders."""
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

        _save_json(root / _INDEX_FILE, index)
        return index


# ─────────────────────────────────────────────
# StrategyIndexStore — per-strategy index
# ─────────────────────────────────────────────

class StrategyIndexStore:
    """Manages backtest_results/{strategy}/index.json — per-strategy run list."""

    @staticmethod
    def update(strategy_dir: Path, run_id: str,
               run_dir: Path, results: BacktestResults) -> None:
        """Add or update a run entry in the strategy-level index."""
        index_path = strategy_dir / _INDEX_FILE
        index = _load_json(index_path, {"strategy": results.summary.strategy,
                                        "updated_at": "", "runs": []})
        entry = _entry_from_results(run_id, run_dir, results, strategy_dir)
        entry["run_dir"] = run_dir.name   # relative to strategy dir
        _upsert_run(index["runs"], run_id, entry)
        index["runs"].sort(key=lambda r: r.get("saved_at", ""), reverse=True)
        index["updated_at"] = datetime.now().isoformat()
        _save_json(index_path, index)
        _log.debug("Strategy index updated | strategy=%s | run_id=%s",
                   results.summary.strategy, run_id)

    @staticmethod
    def load(strategy_dir: str, strategy: str) -> dict:
        """Load the strategy-level index."""
        return _load_json(
            Path(strategy_dir) / _INDEX_FILE,
            {"strategy": strategy, "updated_at": "", "runs": []}
        )

    @staticmethod
    def rebuild(strategy_dir: str, strategy: str) -> dict:
        """Rebuild strategy index by scanning run folders."""
        root = Path(strategy_dir)
        index: dict = {"strategy": strategy, "updated_at": datetime.now().isoformat(), "runs": []}

        for run_dir in sorted(root.iterdir(), reverse=True):
            meta_path = run_dir / "meta.json"
            if not run_dir.is_dir() or not meta_path.exists():
                continue
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                entry = {k: meta.get(k) for k in (
                    "run_id", "timeframe", "pairs", "timerange",
                    "backtest_start", "backtest_end", "profit_total_pct",
                    "profit_total_abs", "starting_balance", "final_balance",
                    "max_drawdown_pct", "max_drawdown_abs", "trades_count",
                    "wins", "losses", "win_rate_pct", "sharpe", "sortino",
                    "calmar", "profit_factor", "expectancy",
                )}
                entry["run_dir"] = run_dir.name
                entry["saved_at"] = meta.get("start_time", "")
                index["runs"].append(entry)
            except Exception:
                continue

        _save_json(root / _INDEX_FILE, index)
        _log.info("Strategy index rebuilt | strategy=%s | runs=%d", strategy, len(index["runs"]))
        return index
