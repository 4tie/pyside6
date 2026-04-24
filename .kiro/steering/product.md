# Product

Freqtrade GUI is a desktop application that provides a graphical interface for the [freqtrade](https://www.freqtrade.io/) cryptocurrency trading bot framework. It wraps freqtrade's CLI tooling in a PySide6 desktop app and also exposes a FastAPI web server for browser-based access.

## Core Capabilities

- **Backtesting**: Run and visualize freqtrade backtests with configurable strategies, timeframes, and pair lists
- **Strategy Lab (Loop)**: Automated iterative optimization loop — runs backtest → diagnose → suggest → apply → repeat until profit targets are met
- **Hyperopt**: Hyperparameter optimization via freqtrade's built-in hyperopt engine
- **Results & Comparison**: Parse, store, and compare backtest result files (JSON/ZIP)
- **Data Download**: Download OHLCV market data for selected pairs and timeframes
- **AI Advisor**: Conversational AI assistant (Ollama or OpenRouter) with tool-calling support for strategy analysis and backtest triggering
- **Rollback**: Version-controlled strategy parameter snapshots with restore capability
- **Web UI**: Parallel FastAPI + vanilla JS web interface served at port 8000

## Key Domain Concepts

- Strategies live in `user_data/strategies/` as Python files with `.json` params sidecar files
- Backtest results are stored as freqtrade ZIP/JSON files under `user_data/backtest_results/`
- Settings (paths, AI config, preferences) are persisted to `data/settings.json`
- The "robust score" is a composite metric (profitability + consistency + stability − fragility) used to rank loop iterations
