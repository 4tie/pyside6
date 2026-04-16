# Product Overview

## Purpose
Freqtrade GUI is a PySide6 desktop application that provides a graphical interface for the Freqtrade cryptocurrency trading bot framework. It eliminates the need for command-line interaction when running backtests, downloading data, and managing trading strategies.

## Key Features
- **Backtesting**: Run strategy backtests with configurable timeframes, pairs, wallet size, and trade limits; view results in Summary/Trades tabs
- **Data Download**: Download OHLCV market data for selected pairs and timeframes via Freqtrade's download-data command
- **Strategy Management**: Auto-discover strategies from `user_data/strategies/`, select and run them from the UI
- **Settings Management**: Configure venv path, Python/Freqtrade executables, and user_data directory; validate and persist settings
- **Terminal Output**: Live streaming of subprocess output with color-coded stdout/stderr
- **Backtest Results**: Browse historical backtest runs per strategy, view performance metrics and trade stats
- **Pair Selector**: Multi-select dialog for choosing trading pairs with favorites support

## Target Users
Freqtrade users who prefer a GUI workflow over CLI for strategy development and backtesting.

## Use Cases
1. Configure Freqtrade environment paths once, reuse across sessions
2. Run backtests with preset timerange buttons (7d, 14d, 30d, 90d, 120d, 360d) or custom ranges
3. Compare historical backtest runs per strategy
4. Download market data for specific pairs before backtesting
5. Monitor live command output without leaving the application
