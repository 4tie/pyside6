# PATHS.md

## Runtime Paths

| Path | Description |
|------|-------------|
| `~/.freqtrade_gui/settings.json` | Persisted app settings |
| `{user_data_path}/strategies/` | Strategy `.py` files |
| `{user_data_path}/backtest_results/{strategy}/` | Per-strategy backtest zip exports |
| `{user_data_path}/data/binance/` | Downloaded OHLCV data |
| `{user_data_path}/config.json` | Freqtrade config |
| `data/log/app.log` | Application log file |
| `data/memory/project_facts.json` | Persistent agent memory |

## Project Source Paths

| Path | Description |
|------|-------------|
| `main.py` | Entry point |
| `app/app_state/settings_state.py` | Qt reactive state |
| `app/core/models/settings_models.py` | Pydantic models |
| `app/core/freqtrade/command_runner.py` | Command building + `BacktestCommand` |
| `app/core/services/` | All service classes |
| `app/core/utils/app_logger.py` | `get_logger()` factory |
| `app/core/utils/date_utils.py` | Date/timerange helpers |
| `app/ui/main_window.py` | `QMainWindow` with tab bar |
| `app/ui/pages/` | `settings_page`, `backtest_page`, `dd_page` |
| `app/ui/widgets/` | `terminal_widget`, `backtest_results_widget`, `data_status_widget` |
| `app/ui/dialogs/pairs_selector_dialog.py` | Multi-select pairs dialog |

## data/ Layout

| Path | Description |
|------|-------------|
| `data/tools/` | MCP server scripts |
| `data/docs/app_docs/` | App architecture, agents, paths, rules |
| `data/docs/freqtrade_docs/` | Freqtrade-specific references |
| `data/rules/` | guidelines, product, structure, tech |
| `data/memory/` | `project_facts.json` — persistent agent memory |
| `data/log/` | `app.log` |

## Venv Resolution

**Windows:**
```
{venv_path}/Scripts/python.exe      → python_executable
{venv_path}/Scripts/freqtrade.exe   → freqtrade_executable
```

**Unix:**
```
{venv_path}/bin/python      → python_executable
{venv_path}/bin/freqtrade   → freqtrade_executable
```
