# Development Guidelines

## Code Quality Standards

### Typing
- Always use full type annotations on method signatures: `def build_command(self, strategy_name: str, timeframe: str, timerange: Optional[str] = None) -> BacktestCommand:`
- Use `Optional[X]` (not `X | None`) for optional parameters — consistent throughout codebase
- Use built-in generics for collections: `list[str]`, `tuple[str, str]` (Python 3.10+ style)
- Import `Optional`, `List` from `typing` for function signatures; use built-in `list[str]` in Pydantic models

### Docstrings
- Every class and public method has a docstring
- Use Google-style docstrings with `Args:`, `Returns:`, `Raises:` sections
- Example:
  ```python
  def build_command(self, strategy_name: str, timeframe: str) -> BacktestCommand:
      """Build a backtest command.

      Args:
          strategy_name: Strategy name
          timeframe: Timeframe (e.g., "5m", "1h")

      Returns:
          BacktestCommand with all necessary info

      Raises:
          ValueError: If settings are invalid or incomplete
          FileNotFoundError: If strategy or config files don't exist
      """
  ```

### Naming Conventions
- Classes: PascalCase (`BacktestService`, `SettingsState`, `CommandRunner`)
- Methods: snake_case; private methods prefixed with `_` (`_append_error`, `_refresh_strategies`)
- Qt signal handlers: `_on_<event>` pattern (`_on_settings_changed`, `_on_select_pairs`, `_on_copy_command`)
- UI init method: always named `init_ui(self)`
- Signal connection method: always named `_connect_signals(self)`

### Error Handling
- Raise `ValueError` for configuration/input errors, `FileNotFoundError` for missing files
- UI methods catch `(ValueError, FileNotFoundError)` and show `QMessageBox.critical()`
- Broad `except Exception as e` used only in service-layer I/O (settings load/save) with `print(f"Failed to ...: {e}")`
- Never silently swallow exceptions in command-building logic

---

## Architectural Patterns

### Service Layer Pattern
Services are plain Python classes (not QObjects) that accept a `SettingsService` in `__init__` and expose a `build_command()` method:
```python
class BacktestService:
    def __init__(self, settings_service: SettingsService):
        self.settings_service = settings_service

    def build_command(self, ...) -> BacktestCommand:
        settings = self.settings_service.load_settings()
        return CommandRunner.build_backtest_command(settings=settings, ...)
```

### Command Builder Pattern
`CommandRunner` is a static-method-only class. It never holds state. All methods return `List[str]` or `BacktestCommand`:
```python
class CommandRunner:
    @staticmethod
    def build_freqtrade_command(*args: str, settings: AppSettings, use_module: Optional[bool] = None) -> List[str]:
        ...
```

### Qt State Object Pattern
`SettingsState` is a `QObject` subclass that wraps a service and exposes typed Qt Signals. UI components connect to these signals for reactive updates:
```python
class SettingsState(QObject):
    settings_loaded = Signal(AppSettings)
    settings_saved = Signal(AppSettings)
    settings_changed = Signal(AppSettings)
```

### UI Page Initialization Pattern
Every QWidget page follows this exact constructor sequence:
```python
def __init__(self, settings_state: SettingsState, parent=None):
    super().__init__(parent)
    # 1. Store dependencies
    self.settings_state = settings_state
    self.settings_service = SettingsService()
    self.backtest_service = BacktestService(self.settings_service)
    # 2. Initialize state flags
    self._initializing: bool = True
    # 3. Build UI
    self.init_ui()
    # 4. Wire signals
    self._connect_signals()
    # 5. Load data
    self._refresh_strategies()
    self._load_preferences()
    # 6. Release init guard and trigger preview
    self._initializing = False
    self._update_command_preview()
```

### Signal Blocking During Bulk Load
When loading saved preferences into multiple widgets, block all signals first, set values, then unblock:
```python
self.strategy_combo.blockSignals(True)
self.timeframe_input.blockSignals(True)
# ... set values ...
self.strategy_combo.blockSignals(False)
self.timeframe_input.blockSignals(False)
```

---

## Pydantic Model Conventions

- All data models extend `pydantic.BaseModel`
- Use `Field(default, description="...")` for every field
- Path fields use `@field_validator(..., mode="before")` with `@classmethod` to normalize via `Path(v).expanduser().resolve()`
- Nested models use `Field(default_factory=NestedModel)` pattern
- Serialize with `model.model_dump()` (Pydantic v2 API, not `.dict()`)

---

## Qt Process Execution

- Use `ProcessService.execute_command()` with callback parameters (`on_output`, `on_error`, `on_finished`)
- Never block the UI thread — all process I/O is async via Qt signals
- Termination sequence: `process.terminate()` → `waitForFinished(1000)` → `process.kill()`
- Decode bytes with `data.decode("utf-8", errors="replace")`
- stderr is displayed in red using `QTextCursor` + `charFormat().setForeground(Qt.red)`

---

## File and Path Conventions

- Always use `pathlib.Path` for path manipulation, never string concatenation
- Resolve paths: `Path(settings.user_data_path).expanduser().resolve()`
- Config resolution priority: strategy sidecar JSON → project `config.json` → `user_data/config.json`
- Create output directories with `export_dir.mkdir(parents=True, exist_ok=True)`
- Cross-platform venv paths: check `os.name == "nt"` for `Scripts/` vs `bin/`

---

## Freqtrade Command Conventions

- Preferred invocation: `python -m freqtrade <subcommand>` (controlled by `settings.use_module_execution`)
- Fallback: direct `freqtrade` executable path
- Always pass `--user-data-dir`, `--strategy-path`, `--config` explicitly
- Download data always uses `--prepend` flag
- Export backtest results with `--export trades --export-filename <timestamped_path>`
