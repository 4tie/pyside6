# ARCHITECTURE.md

## Layered Architecture

```
UI Layer          app/ui/pages/, app/ui/widgets/, app/ui/dialogs/
    ↓
State Layer       app/app_state/settings_state.py  (QObject + Signals)
    ↓
Service Layer     app/core/services/               (business logic)
    ↓
Model Layer       app/core/models/                 (Pydantic)
    ↓
Infrastructure    app/core/freqtrade/, app/core/utils/
```

## Services

| Service | Responsibility |
|---------|---------------|
| `SettingsService` | JSON persistence + path validation |
| `BacktestService` | Build backtest commands, list strategies |
| `BacktestResultsService` | Parse zip results → `BacktestResults` |
| `DownloadDataService` | Build download-data commands |
| `ProcessService` | QProcess wrapper, live stdout/stderr streaming |
| `RunStore` | Persist backtest run metadata |

## Command Flow

```
BacktestService.build_command()
    → CommandRunner.build_backtest_command()
    → BacktestCommand(program, args, cwd, export_dir, export_zip, strategy_file)
    → ProcessService.execute_command()
    → TerminalWidget streams output
    → on exit 0: BacktestResultsService.parse_backtest_zip()
    → BacktestResultsWidget.display()
```

## State

- `SettingsState` — QObject holding `AppSettings`
- Signals: `settings_saved`, `settings_loaded`, `settings_changed`, `settings_validated`
- Pages receive `SettingsState` via constructor — never instantiate it themselves

## Settings Persistence

- Stored: `~/.freqtrade_gui/settings.json`
- Model: `AppSettings` (Pydantic, path normalization via `field_validator`)
- Nested: `BacktestPreferences`, `DownloadPreferences`, `TerminalPreferences`

## Freqtrade Execution

- Preferred: `python -m freqtrade <cmd>` (venv Python)
- Fallback: direct `freqtrade` executable
- Environment: `VIRTUAL_ENV` + `PATH` injected into `QProcessEnvironment` — no shell activation
