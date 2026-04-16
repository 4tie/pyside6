# Development Guidelines

## Code Quality Standards

### Module-level logger pattern (used in every non-trivial module)
```python
from app.core.utils.app_logger import get_logger
_log = get_logger("module_name")  # private, underscore-prefixed
```
Log levels: `_log.debug` for data details, `_log.info` for lifecycle events, `_log.warning` for recoverable issues, `_log.error` for failures.

### Docstrings
All public classes and methods have Google-style docstrings with Args/Returns/Raises sections. Private helpers (`_handle_stdout`, `_resolve_python_from_venv`) have one-line docstrings only.

### Type hints
All function signatures use full type hints including `Optional`, `List`, `Dict`, `Callable`, `tuple`. Use `from typing import ...` (not `collections.abc`).

### `__init__.py` files
All package `__init__.py` files are empty — no re-exports. Import directly from the module file.

---

## Structural Conventions

### Service classes
- Stateless logic → `@staticmethod` methods (e.g., `CommandRunner`, `BacktestResultsService`)
- Stateful services hold instance state and accept dependencies via `__init__` (e.g., `BacktestService(settings_service)`, `ProcessService()`)
- Services never import UI code

### Dataclasses vs Pydantic
- `@dataclass` for internal data transfer objects (e.g., `BacktestCommand`, `BacktestTrade`, `BacktestSummary`)
- `pydantic.BaseModel` for user-facing settings and validation (e.g., `AppSettings`, `BacktestPreferences`)
- Pydantic models use `Field(default, description="...")` on every field
- Path normalization via `@field_validator(..., mode="before")` with `Path.expanduser().resolve()`

### Qt patterns
- State objects extend `QObject` and declare `Signal(ModelType)` class attributes
- UI pages receive `SettingsState` via constructor — never instantiate state themselves
- `QProcess` is managed by `ProcessService`; UI widgets connect via callbacks (`on_output`, `on_error`, `on_finished`)
- `MainWindow` wires signals to slots in `__init__` (e.g., `settings_state.settings_saved.connect(self._on_settings_saved)`)

### Command building
Always return a `BacktestCommand` dataclass (never a raw list) from service-level builders. The dataclass carries `program`, `args`, `cwd`, `export_dir`, `export_zip`, `strategy_file`.

```python
# Correct pattern
cmd = BacktestCommand(program=..., args=[...], cwd=..., export_dir=..., export_zip=..., strategy_file=...)
# Then execute via ProcessService
process_service.execute_command([cmd.program] + cmd.args, cwd=cmd.cwd, ...)
```

---

## Naming Conventions
- Classes: `PascalCase`
- Methods/functions: `snake_case`; private methods prefixed with `_`
- Module-level logger: always `_log`
- Constants/module-level private: underscore prefix
- Qt signal names: `noun_past_tense` (e.g., `settings_saved`, `settings_loaded`)

---

## Error Handling Patterns
- Raise `ValueError` for configuration/logic errors (missing settings, invalid params)
- Raise `FileNotFoundError` for missing files (strategy .py, zip files)
- Catch broad `Exception` only in persistence/IO methods; log with `_log.error` and re-raise as `ValueError` with a user-friendly message
- Never silently swallow exceptions in service layer

```python
# Standard IO error pattern
try:
    ...
except json.JSONDecodeError as e:
    _log.error("JSON decode error in %s: %s", filename, e)
    raise ValueError(f"Failed to parse: {e}")
except Exception as e:
    _log.error("Failed: %s", e)
    raise ValueError(f"Operation failed: {e}")
```

---

## Path Handling
- Always use `pathlib.Path` — never string concatenation for paths
- Resolve paths: `Path(x).expanduser().resolve()`
- Platform branching: `if os.name == "nt":` for Windows `Scripts/` vs Unix `bin/`
- `mkdir(parents=True, exist_ok=True)` before writing files

---

## Semantic Patterns

### Fallback execution strategy
```python
if use_module and settings.python_executable:
    return [settings.python_executable, "-m", "freqtrade", *args]
elif settings.freqtrade_executable:
    return [settings.freqtrade_executable, *args]
else:
    raise ValueError("No valid freqtrade execution method")
```

### Optional list parameters default to empty list at call site
```python
def build_command(self, pairs: Optional[List[str]] = None, extra_flags: Optional[List[str]] = None):
    ...
    pairs=pairs or [],
    extra_flags=extra_flags or [],
```

### Prefer pre-computed values, fall back to computing from raw data
```python
wins = int(sd.get('wins', sum(1 for t in trades if t.profit > 0)))
```

### Format display data in a dedicated method returning `Dict[str, str]`
Service methods like `format_summary_for_display` return plain dicts of formatted strings — UI widgets consume these without knowing the model structure.

### Environment injection for subprocesses
Never rely on shell activation. Inject `VIRTUAL_ENV` and prepend venv `bin/Scripts` to `PATH` explicitly via `QProcessEnvironment`.
