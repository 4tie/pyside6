# Project Structure

## Directory Layout

```
t:\ae\pyside6/
├── main.py                          # Entry point: creates QApplication, SettingsState, MainWindow
├── requirements.txt                 # PySide6>=6.6.0, pydantic>=2.0.0, freqtrade
├── app/
│   ├── app_state/
│   │   └── settings_state.py        # QObject with Qt Signals; bridges settings service to UI
│   ├── core/
│   │   ├── ai/
│   │   │   ├── models/              # AI model definitions (in development)
│   │   │   └── prompts/             # AI prompt templates (in development)
│   │   ├── freqtrade/
│   │   │   └── command_runner.py    # Builds CLI command lists; BacktestCommand dataclass
│   │   ├── models/
│   │   │   └── settings_models.py   # Pydantic models: AppSettings, BacktestPreferences, etc.
│   │   ├── services/
│   │   │   ├── backtest_service.py  # Delegates to CommandRunner.build_backtest_command
│   │   │   ├── dd_service.py        # Delegates to CommandRunner.build_download_command
│   │   │   ├── backtest_results_service.py  # Reads/parses backtest result files
│   │   │   ├── process_service.py   # Manages QProcess execution
│   │   │   └── settings_service.py  # Loads/saves AppSettings to JSON on disk
│   │   └── utils/
│   │       └── date_utils.py        # Date/timerange helpers
│   └── ui/
│       ├── main_window.py           # QMainWindow with Settings/Backtest/Terminal tabs
│       ├── pages/
│       │   ├── settings_page.py     # Settings form page
│       │   └── backtest_page.py     # Backtest configuration and run page
│       ├── widgets/
│       │   ├── terminal_widget.py   # Embedded terminal with live process output
│       │   └── backtest_results_widget.py  # Results browser/viewer
│       └── dialogs/
│           └── pairs_selector_dialog.py    # Multi-select pairs dialog with favorites
├── tests/
│   ├── core/                        # Core logic tests
│   └── ui/                          # UI tests
└── user_data/                       # Freqtrade user data (strategies, results, configs, data)
    ├── strategies/                  # .py strategy files
    ├── backtest_results/            # Per-strategy result subdirectories
    ├── config/                      # Per-strategy config JSON files
    ├── data/binance/                # Downloaded OHLCV data
    └── config.json                  # Default Freqtrade config
```

## Core Components and Relationships

```
main.py
  └── SettingsState (QObject)         ← wraps SettingsService, emits Qt Signals
        └── SettingsService           ← reads/writes AppSettings JSON
              └── AppSettings         ← Pydantic model (validated paths)

MainWindow (QMainWindow)
  ├── SettingsPage                    ← reads/writes via SettingsState
  ├── BacktestPage
  │     ├── BacktestService           ← calls CommandRunner.build_backtest_command
  │     ├── DownloadDataService       ← calls CommandRunner.build_download_command
  │     ├── BacktestResultsWidget     ← reads result files via BacktestResultsService
  │     └── PairsSelectorDialog       ← returns selected pairs list
  └── TerminalWidget                  ← runs QProcess, streams stdout/stderr
```

## Architectural Patterns

- **Service Layer**: Business logic lives in `core/services/`; UI pages instantiate services directly
- **Command Builder Pattern**: `CommandRunner` is a static-method-only class that constructs CLI argument lists; services call it and return `BacktestCommand` dataclasses to the UI
- **State Object with Signals**: `SettingsState` is a `QObject` that holds `current_settings` and emits typed Qt Signals (`settings_loaded`, `settings_saved`, `settings_changed`) so UI components can react reactively
- **Pydantic for Data Models**: All data structures (`AppSettings`, `BacktestPreferences`, `ProcessOutput`) are Pydantic `BaseModel` subclasses with field validators for path normalization
- **Separation of Command Building vs Execution**: `CommandRunner` only builds `List[str]` commands; `TerminalWidget`/`ProcessService` handles actual `QProcess` execution
