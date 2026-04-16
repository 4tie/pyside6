# Product Overview

Freqtrade GUI is a PySide6 desktop application that provides a graphical interface for the [Freqtrade](https://www.freqtrade.io/) cryptocurrency trading bot framework — eliminating the need for CLI interaction when running backtests, downloading data, and managing strategies.

## Key Features
- **Backtesting** — run strategy backtests with configurable timeframes, pairs, wallet size, and trade limits; view results in Summary/Trades tabs
- **Hyperopt (Optimize)** — run hyperparameter optimization jobs via Freqtrade's hyperopt engine
- **Data Download** — download OHLCV market data for selected pairs/timeframes
- **Strategy Management** — auto-discover strategies from `user_data/strategies/`
- **Settings** — configure venv path, Python/Freqtrade executables, and `user_data` directory; validate and persist
- **Terminal Output** — live streaming of subprocess stdout/stderr with color coding
- **Backtest Results Browser** — browse historical runs per strategy, view metrics and trade stats
- **Pair Selector** — multi-select dialog with favorites support

## Target Users
Freqtrade users who prefer a GUI workflow over CLI for strategy development and backtesting.
