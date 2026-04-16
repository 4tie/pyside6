# Project Structure

## Directory Layout
```
main.py                          # Entry point: QApplication, logging setup, MainWindow
requirements.txt                 # PySide6, pydantic, freqtrade
app/
├── app_state/
│   └── settings_state.py        # QObject + Qt signals for reactive settings
├── core/
│   ├── freqtrade/
│   │   ├── command_runner.py    # Backward-compat CommandRunner wrapper
│   │   ├── resolvers/           # config_resolver, strategy_resolver, runtime_resolver
│   │   └── runners/             # backtest_runner, download_data_runner, optimize_runner, base_runner
│   ├── models/
│   │   └── settings_models.py   # Pydantic: AppSettings, BacktestPreferences, etc.
│   ├── services/
│   │   ├── settings_service.py
│   │   ├── backtest_service.py
│   │   ├── backtest_results_service.py
│   │   ├── download_data_service.py
│   │   ├── optimize_service.py
│   │   ├── process_service.py   # QProcess wrapper
│   │   └── run_store.py
│   └── utils/
│       ├── app_logger.py        # get_logger() factory
│       └── date_utils.py
└── ui/
    ├── main_window.py
    ├── dialogs/
    │   └── pairs_selector_dialog.py
    ├── pages/
    │   ├── settings_page.py
    │   ├── backtest_page.py
    │   ├── optimize_page.py
    │   ├── download_data_page.py
    │   └── strategy_config_page.py
    └── widgets/
        ├── terminal_widget.py
        ├── backtest_results_widget.py
        ├── backtest_stats_widget.py
        ├── backtest_summary_widget.py
        ├── backtest_trades_widget.py
        └── data_status_widget.py
data/
├── docs/app_docs/               # ARCHITECTURE.md, PATHS.md, AGENTS.md
├── docs/freqtrade_docs/         # Freqtrade reference docs
├── rules/                       # guidelines.md, product.md, structure.md, tech.md
├── memory/                      # project_facts.json — persistent agent memory
├── tools/                       # MCP server scripts
└── log/                         # app.log, ui.log, services.log, process.log
```

## Layered Architecture
```
UI Layer       app/ui/pages/, app/ui/widgets/, app/ui/dialogs/
    ↓
State Layer    app/app_state/settings_state.py  (QObject + Signals)
    ↓
Service Layer  app/core/services/               (business logic, no UI imports)
    ↓
Model Layer    app/core/models/                 (Pydantic)
    ↓
Infra Layer    app/core/freqtrade/, app/core/utils/
```

## Key Conventions

### Naming
- Classes: `PascalCase` | Methods/functions: `snake_case` | Private: `_snake_case`
- Module-level logger: always `_log = get_logger("section.module")`
- Qt signals: `noun_past_tense` (e.g. `settings_saved`, `settings_loaded`)

### Models
- `@dataclass` for internal DTOs (e.g. `BacktestRunCommand`, `BacktestTrade`)
- `pydantic.BaseModel` for user-facing settings — every field uses `Field(default, description="...")`
- Path fields normalized via `@field_validator(..., mode="before")` using `Path.expanduser().resolve()`

### Services
- Stateless logic → `@staticmethod` methods
- Stateful services accept dependencies via `__init__`
- Services never import UI code

### Qt Patterns
- Pages receive `SettingsState` via constructor — never instantiate it themselves
- `QProcess` managed exclusively by `ProcessService`
- `__init__.py` files are empty — import directly from module files

### Error Handling
- `ValueError` for config/logic errors, `FileNotFoundError` for missing files
- Catch broad `Exception` only in IO/persistence; log with `_log.error` then re-raise as `ValueError`
- Never silently swallow exceptions in the service layer

### Path Handling
- Always use `pathlib.Path` — never string concatenation
- `Path(x).expanduser().resolve()` for all user-supplied paths
- `mkdir(parents=True, exist_ok=True)` before writing files
