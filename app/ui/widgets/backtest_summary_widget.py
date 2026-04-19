# Backward-compatibility shim — BacktestSummaryWidget is BacktestStatsWidget
from app.ui.widgets.backtest_stats_widget import BacktestStatsWidget as BacktestSummaryWidget

__all__ = ["BacktestSummaryWidget"]
