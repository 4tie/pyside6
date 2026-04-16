# Project Structure

## Directory Layout
```
pyside6/
├── main.py                          # Entry point: QApplication, logging setup, MainWindow
├── requirements.txt                 # PySide6, pydantic, freqtrade
├── app/
│   ├── app_state/
│   │   └── settings_state.py        # QObject with Qt signals for reactive settings
│   ├── core/
│   │   ├── ai/
│   │   │   ├── models/__init__.py   # AI model definitions (placeholder)
│   │   │   ├── prompts/__init__.py  # AI prompt templates (placeholder)
│   │   │   └── __init__.py
│   │   ├── freqtrade/
│   │   │   └── command_runner.py    # BacktestCommand dataclass + CommandRunner static methods
│   │   ├── models/
│   │   │   └── settings_models.py   # Pydantic models: AppSettings, BacktestPreferences, etc.
│   │   ├── services/
│   │   │   ├── backtest_service.py  # BacktestService: build_command, get_available_strategies
│   │   │   ├── backtest_results_service.py  # Load/index historical backtest results
│   │   │   ├── dd_service.py        # DownloadDataService: build download commands
│   │   │   ├── process_service.py   # QProcess wrapper for subprocess execution
│   │   │   ├── run_store.py         # Persistent store for backtest run metadata
│   │   │   └── settings_service.py  # JSON persistence + validation of AppSettings
│   │   └── utils/
│   │       ├── app_logger.py        # Logging setup (file + console handlers)
│   │       └── date_utils.py        # Date/timerange helpers
│   └── ui/
│       ├── main_window.py           # QMainWindow with tab bar (Settings|Backtest|Download|Terminal)
│       ├── dialogs/
│       │   └── pairs_selector_dialog.py  # Multi-select pairs dialog
│       ├── pages/
│       │   ├── settings_page.py     # Settings form with venv/path pickers
│       │   ├── backtest_page.py     # Backtest runner UI with results panel
│       │   └── dd_page.py           # Download data UI
│       └── widgets/
│           ├── terminal_widget.py   # Live output display with stop/clear controls
│           ├── backtest_results_widget.py  # Results browser (Summary/Trades tabs)
│           └── data_status_widget.py       # Data availability status display
├── user_data/                       # Freqtrade user data (strategies, data, results)
│   ├── strategies/                  # .py strategy files
│   ├── data/binance/                # Downloaded OHLCV data
│   ├── backtest_results/            # Per-strategy run directories with JSON results
│   └── config.json                  # Freqtrade config
└── tests/                           # Test stubs (core/ and ui/ subdirs)
```

## Core Architectural Patterns

### Layered Architecture
```
UI Layer (pages, widgets, dialogs)
    ↓ uses
State Layer (app_state/settings_state.py — QObject + Signals)
    ↓ uses
Service Layer (core/services/ — business logic)
    ↓ uses
Model Layer (core/models/ — Pydantic data models)
    ↓ uses
Infrastructure (core/freqtrade/command_runner.py, core/utils/)
```

### State Management
- `SettingsState` (QObject) holds `current_settings: AppSettings` and emits signals (`settings_loaded`, `settings_saved`, `settings_changed`, `settings_validated`) for reactive UI updates
- Pages receive `SettingsState` via constructor injection

### Command Execution Flow
1. Service builds a `BacktestCommand` (dataclass with program, args, cwd, export paths)
2. UI passes command to `ProcessService` (QProcess wrapper)
3. `TerminalWidget` connects to `ProcessService` signals for live output streaming

### Settings Persistence
- Stored at `~/.freqtrade_gui/settings.json` as JSON
- Loaded into `AppSettings` (Pydantic model with path normalization validators)
- Nested preference models: `BacktestPreferences`, `DownloadPreferences`, `TerminalPreferences`
