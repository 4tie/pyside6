# PATHS.md

## Runtime Paths

| Path | Description |
|------|-------------|
| `~/.freqtrade_gui/settings.json` | Persisted app settings |
| `{user_data_path}/strategies/` | Strategy `.py` files |
| `{user_data_path}/backtest_results/{strategy}/` | Per-strategy backtest zip exports |
| `{user_data_path}/data/binance/` | Downloaded OHLCV data |
| `{user_data_path}/config.json` | Freqtrade config |
| `{user_data_path}/logs/app.log` | Application log file |

## Project Paths

| Path | Description |
|------|-------------|
| `main.py` | Entry point |
| `app/app_state/settings_state.py` | Qt reactive state |
| `app/core/models/settings_models.py` | Pydantic models |
| `app/core/freqtrade/command_runner.py` | Command building + `BacktestCommand` dataclass |
| `app/core/services/` | All service classes |
| `app/core/utils/app_logger.py` | `get_logger()` factory |
| `app/core/utils/date_utils.py` | Date/timerange helpers |
| `app/ui/main_window.py` | `QMainWindow` with tab bar |
| `app/ui/pages/` | `settings_page`, `backtest_page`, `dd_page` |
| `app/ui/widgets/` | `terminal_widget`, `backtest_results_widget`, `data_status_widget` |
| `app/ui/dialogs/pairs_selector_dialog.py` | Multi-select pairs dialog |
| `tools/` | MCP server scripts |
| `docs/` | Agent and developer documentation |
| `logs/` | Local log output |
| `.amazonq/rules/memory-bank/` | Pinned context rules for Amazon Q |

## Venv Resolution (Windows)

```
{venv_path}/Scripts/python.exe   → python_executable
{venv_path}/Scripts/freqtrade.exe → freqtrade_executable
```

## Venv Resolution (Unix)

```
{venv_path}/bin/python   → python_executable
{venv_path}/bin/freqtrade → freqtrade_executable
```
