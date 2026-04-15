# Technology Stack

## Languages and Versions
- Python 3.10+ (uses `list[str]` built-in generics, `tuple[str, str]` return types)
- No JavaScript/TypeScript — pure Python desktop app

## Core Dependencies
| Package | Version | Purpose |
|---|---|---|
| PySide6 | >=6.6.0 | Qt6 GUI framework (widgets, signals, QProcess) |
| pydantic | >=2.0.0 | Data models, validation, settings serialization |
| freqtrade | latest | Algorithmic trading framework (invoked as subprocess) |

## Key Qt Modules Used
- `PySide6.QtWidgets` — QMainWindow, QTabWidget, QProcess, dialogs, form widgets
- `PySide6.QtCore` — QObject, Signal, QProcess, QProcessEnvironment
- `PySide6.QtGui` — (minimal, for terminal coloring)

## Settings Persistence
- Settings stored at `~/.freqtrade_gui/settings.json`
- Serialized via `pydantic model.model_dump()` → `json.dump(..., indent=2)`
- Deserialized via `AppSettings(**data)` with automatic path normalization via `@field_validator`

## Process Execution
- Freqtrade is invoked as a subprocess via `QProcess` (not Python import)
- Preferred invocation: `python -m freqtrade <subcommand>` (controlled by `use_module_execution` flag)
- Fallback: direct `freqtrade` executable path
- stdout/stderr streamed via `readyReadStandardOutput` / `readyReadStandardError` signals
- Process termination: `terminate()` → wait 1s → `kill()`

## Linting / Formatting
- Ruff (`.ruff_cache/` present, version 0.15.10)
- No pyproject.toml or setup.cfg found — Ruff likely configured via `ruff.toml` or defaults

## Development Commands
```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py

# Lint with ruff
ruff check .
ruff format .
```

## File Conventions
- Settings JSON: `~/.freqtrade_gui/settings.json`
- Strategy files: `user_data/strategies/<StrategyName>.py`
- Strategy sidecar config: `user_data/strategies/<StrategyName>.json` (optional, takes priority)
- Default config: `user_data/config.json`
- Backtest results: `user_data/backtest_results/<StrategyName>/`
- Downloaded data: `user_data/data/binance/`
