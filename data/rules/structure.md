# Project Structure

## Directory Layout
```
pyside6/
├── main.py                          # Entry point: QApplication, logging setup, MainWindow
├── requirements.txt                 # PySide6, pydantic, freqtrade
├── data/
│   ├── docs/
│   │   ├── app_docs/                # App architecture, agents, paths, rules
│   │   └── freqtrade_docs/          # Freqtrade-specific references
│   ├── rules/                       # guidelines, product, structure, tech
│   ├── memory/                      # project_facts.json — persistent agent memory
│   ├── tools/                       # MCP server scripts
│   └── log/                         # app.log
├── tools/                           # MCP servers (symlinked from data/tools)
├── app/
│   ├── app_state/
│   │   └── settings_state.py        # QObject with Qt signals for reactive settings
│   ├── core/
│   │   ├── freqtrade/
│   │   │   └── command_runner.py    # BacktestCommand dataclass + CommandRunner
│   │   ├── models/
│   │   │   └── settings_models.py   # Pydantic models: AppSettings, BacktestPreferences
│   │   ├── services/
│   │   │   ├── backtest_service.py
│   │   │   ├── backtest_results_service.py
│   │   │   ├── dd_service.py
│   │   │   ├── process_service.py
│   │   │   ├── run_store.py
│   │   │   └── settings_service.py
│   │   └── utils/
│   │       ├── app_logger.py
│   │       └── date_utils.py
│   └── ui/
│       ├── main_window.py
│       ├── dialogs/
│       │   └── pairs_selector_dialog.py
│       ├── pages/
│       │   ├── settings_page.py
│       │   ├── backtest_page.py
│       │   └── dd_page.py
│       └── widgets/
│           ├── terminal_widget.py
│           ├── backtest_results_widget.py
│           └── data_status_widget.py
├── user_data/
│   ├── strategies/
│   ├── data/binance/
│   ├── backtest_results/
│   └── config.json
└── tests/
```

## Core Architectural Patterns

### Layered Architecture
```
UI Layer (pages, widgets, dialogs)
    ↓
State Layer (app_state/settings_state.py — QObject + Signals)
    ↓
Service Layer (core/services/ — business logic)
    ↓
Model Layer (core/models/ — Pydantic)
    ↓
Infrastructure (core/freqtrade/, core/utils/)
```

### State Management
- `SettingsState` (QObject) holds `current_settings: AppSettings`
- Emits: `settings_loaded`, `settings_saved`, `settings_changed`, `settings_validated`
- Pages receive `SettingsState` via constructor injection

### Command Execution Flow
1. Service builds `BacktestCommand` (dataclass: program, args, cwd, export paths)
2. UI passes to `ProcessService` (QProcess wrapper)
3. `TerminalWidget` connects to `ProcessService` signals for live streaming

### Settings Persistence
- Stored at `~/.freqtrade_gui/settings.json`
- Loaded into `AppSettings` (Pydantic with path normalization validators)
- Nested: `BacktestPreferences`, `DownloadPreferences`, `TerminalPreferences`
