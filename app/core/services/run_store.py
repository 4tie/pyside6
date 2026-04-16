# Backward-compatibility shim — import from new location
from app.core.backtests.results_store import RunStore
from app.core.backtests.results_index import IndexStore, StrategyIndexStore

__all__ = ["RunStore", "IndexStore", "StrategyIndexStore"]
