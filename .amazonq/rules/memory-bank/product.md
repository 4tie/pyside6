# Product Overview

## Purpose
A PySide6 desktop GUI application that wraps the Freqtrade algorithmic trading framework, providing a user-friendly interface for running backtests, downloading market data, and managing trading strategy configurations without needing to use the command line.

## Key Features
- **Backtest Runner**: Configure and launch Freqtrade backtests with strategy selection, timeframe, timerange, and pair selection
- **Download Data**: Download historical OHLCV market data from exchanges (Binance) for specified pairs and timeframes
- **Backtest Results Viewer**: Browse, compare, and inspect backtest result files (JSON/ZIP) organized by strategy
- **Settings Management**: Configure paths to Python venv, Freqtrade executable, user_data directory, and project root
- **Embedded Terminal**: Run ad-hoc Freqtrade commands and view live process output with colored stdout/stderr
- **Pairs Selector Dialog**: Multi-select trading pairs with favorites support
- **AI Integration**: Placeholder AI module for prompt/model management (in development)

## Target Users
- Algorithmic traders using Freqtrade who want a GUI workflow
- Developers backtesting and iterating on trading strategies (MultiMa, MohsBaseline, etc.)
- Users who prefer not to manage CLI commands manually

## Use Cases
- Run backtests on strategies with custom timeframes and pair lists
- Download fresh market data before backtesting
- Compare backtest results across strategy versions
- Quickly switch between strategy configurations via saved settings
