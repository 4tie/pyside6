# Development Guidelines

## General Principles
- Prefer small, safe, incremental changes — don't mix refactors with behavior changes
- Reuse existing services and pages before adding new parallel systems
- Core backtest/results/settings behavior takes priority over AI or provider complexity

## Logging
Every non-trivial module declares a module-level private logger:
```python
from app.core.utils.app_logger import get_logger
_log = get_logger("section.module")  # e.g. "services.backtest", "ui.backtest_page"
```
Levels: `debug` for data details, `info` for lifecycle events, `warning` for recoverable issues, `error` for failures. Custom `CMD` level (25) is used for freqtrade command execution.

## Type Hints & Docstrings
- All function signatures use full type hints: `Optional`, `List`, `Dict`, `Callable` from `typing`
- Public classes and methods: Google-style docstrings with Args/Returns/Raises
- Private helpers: one-line docstrings only

## Models: Dataclass vs Pydantic
- `@dataclass` for internal DTOs: `RunCommand`, `BacktestRunCommand`, `BacktestTrade`, `BacktestResults`
- `pydantic.BaseModel` for user-facing settings: `AppSettings`, `BacktestPreferences`, etc.
  - Every field uses `Field(default, description="...")`
  - Path fields normalized via `@field_validator(..., mode="before")` with `Path.expanduser().resolve()`

## Command Building Pattern
Runners return a `RunCommand` or `BacktestRunCommand` dataclass — never a raw list:
```python
# Build
cmd = build_backtest_command(settings, strategy_name=..., timeframe=...)
# Execute
process_service.execute_command(cmd.as_list(), cwd=cmd.cwd, ...)
```
`BacktestRunCommand` extends `RunCommand` with `export_dir`, `config_file`, `strategy_file`.

## Service Conventions
- Stateless logic → `@staticmethod` methods (e.g. `CommandRunner`, `IndexStore`, `RunStore`)
- Stateful services hold instance state and accept dependencies via `__init__`
- Services **never** import UI code
- `ProcessService` is the only place `QProcess` is created and managed

## Qt / UI Patterns
- State objects extend `QObject` and declare `Signal(ModelType)` class attributes
- Pages receive `SettingsState` via constructor — never instantiate state themselves
- Signal names use `noun_past_tense`: `settings_saved`, `settings_loaded`, `settings_changed`
- `MainWindow` wires all signals to slots in `__init__`
- Block widget signals during bulk UI loads: `widget.blockSignals(True) / False`

## Error Handling
- `ValueError` for config/logic errors; `FileNotFoundError` for missing files
- Catch broad `Exception` only in IO/persistence — log with `_log.error`, re-raise as `ValueError`
- Never silently swallow exceptions in the service layer

```python
try:
    ...
except json.JSONDecodeError as e:
    _log.error("Parse error in %s: %s", filename, e)
    raise ValueError(f"Failed to parse: {e}")
```

## Path Handling
- Always use `pathlib.Path` — never string concatenation
- Resolve all user-supplied paths: `Path(x).expanduser().resolve()`
- `mkdir(parents=True, exist_ok=True)` before writing files
- Platform branching: `if os.name == "nt":` for `Scripts/` vs `bin/`

## Freqtrade Execution
```python
# Preferred (use_module_execution=True)
[settings.python_executable, "-m", "freqtrade", *ft_args]
# Fallback
[settings.freqtrade_executable, *ft_args]
```
Never rely on shell activation — inject `VIRTUAL_ENV` and prepend venv bin to `PATH` via `QProcessEnvironment` or `ProcessService.build_environment()`.

## Backtest Results Storage
Each run is saved as a folder under `{user_data}/backtest_results/{strategy}/run_{ts}_{hash}/`:
- `meta.json` — summary metrics for index display
- `results.json` — full `BacktestSummary` fields
- `trades.json` — list of `BacktestTrade` records
- `params.json` — strategy buy/sell params and ROI
- `config.snapshot.json` — copy of the config used

Two indexes are maintained automatically by `RunStore.save()`:
- `backtest_results/index.json` — global across all strategies (`IndexStore`)
- `backtest_results/{strategy}/index.json` — per-strategy (`StrategyIndexStore`)

## Naming Conventions
| Thing | Convention |
|-------|-----------|
| Classes | `PascalCase` |
| Methods / functions | `snake_case` |
| Private methods / vars | `_snake_case` |
| Module-level logger | `_log` |
| Qt signals | `noun_past_tense` |
| `__init__.py` | Empty — no re-exports |
