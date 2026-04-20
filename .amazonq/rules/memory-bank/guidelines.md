# guidelines.md — Development Standards and Patterns

## Code Quality Standards

### Module-level logger pattern
Every module that logs uses a module-level private logger:
```python
from app.core.utils.app_logger import get_logger
_log = get_logger("services.backtest")  # or "backtest", "services.loop", etc.
```

### Logging conventions
- Use `%s` / `%d` / `%.4f` style formatting (not f-strings) in log calls
- Use `_log.info(...)`, `_log.warning(...)`, `_log.debug(...)`, `_log.error(...)`
- Log key parameters at entry points: `_log.info("Backtest requested | strategy=%s | ...", strategy, ...)`
- Log results at exit points: `_log.info("Parsed | strategy=%s | trades=%d | profit=%.4f%%", ...)`

### Pydantic models (v2)
All data models use Pydantic v2 BaseModel:
```python
from pydantic import BaseModel, Field, field_validator, model_validator

class MyModel(BaseModel):
    field_name: str = Field("default", description="Human-readable description")
    optional_field: Optional[str] = Field(None, description="...")
    list_field: list[str] = Field(default_factory=list, description="...")
```
- Always include `description=` in every `Field()`
- Use `@field_validator` with `@classmethod` for single-field validation
- Use `@model_validator(mode="before")` with `@classmethod` for migration/cross-field logic
- Validators must return the (possibly modified) value

### Type annotations
- Always annotate function parameters and return types
- Use `Optional[T]` for nullable values (not `T | None`)
- Use `List[T]`, `Dict[K, V]`, `Tuple[...]` from `typing` (not built-in generics in older code)
- Use `from __future__ import annotations` in complex service files

### Path handling
- Always use `Path(...).expanduser().resolve()` for user-provided paths
- Never hardcode absolute paths
- Use `pathlib.Path` throughout, not `os.path`

---

## Structural Conventions

### Service class pattern
Services are plain classes (no Qt inheritance) with injected dependencies:
```python
class BacktestService:
    def __init__(self, settings_service: SettingsService):
        self.settings_service = settings_service

    def do_something(self, ...) -> ReturnType:
        """Docstring."""
        settings = self.settings_service.load_settings()
        ...
```
- Services never import UI code
- Services receive dependencies via constructor injection
- Public methods have docstrings

### UI page pattern
Pages inherit from `QWidget` and follow this init order:
```python
class BacktestPage(QWidget):
    def __init__(self, settings_state: SettingsState, parent=None):
        super().__init__(parent)
        # 1. Store dependencies
        self.settings_state = settings_state
        # 2. Create service instances
        self.backtest_service = BacktestService(...)
        # 3. Initialize state variables
        self._initializing: bool = True
        # 4. Build UI
        self.init_ui()
        # 5. Connect signals
        self._connect_signals()
        # 6. Load initial data
        self._load_preferences()
        self._initializing = False
```

### Signal blocking during load
Always block signals when programmatically setting widget values:
```python
self.strategy_combo.blockSignals(True)
self.strategy_combo.clear()
self.strategy_combo.addItems(strategies)
self.strategy_combo.blockSignals(False)
```

### Private method naming
- `_method_name` for private/internal methods
- `_on_event_name` for event handlers (e.g., `_on_settings_changed`, `_on_select_pairs`)
- `_refresh_*` for data refresh methods
- `_update_*` for UI update methods
- `_load_*` / `_save_*` for persistence methods

---

## Semantic Patterns

### Callback injection (UI ↔ Service decoupling)
Services expose callback setters instead of importing UI:
```python
def set_callbacks(
    self,
    on_iteration_complete: Callable[[LoopIteration], None],
    on_loop_complete: Callable[[LoopResult], None],
    on_status: Callable[[str], None],
) -> None:
    self._on_iteration_complete = on_iteration_complete
    ...
```

### Defensive None/NaN handling
Always guard against None and NaN before arithmetic:
```python
def _is_nan_or_none(v) -> bool:
    if v is None:
        return True
    try:
        return math.isnan(float(v))
    except (TypeError, ValueError):
        return False
```

### copy.deepcopy for mutable state
Use `copy.deepcopy()` when storing or passing mutable dicts/objects that must not be mutated:
```python
self._current_params = copy.deepcopy(initial_params)
iteration.params_before = copy.deepcopy(self._current_params)
```

### Exception handling in services
Catch specific exceptions, log with `_log.warning(...)`, and return a safe fallback:
```python
try:
    results = parse_backtest_zip(str(zip_path))
except Exception as e:
    _log.warning("Failed to import zip %s: %s", zip_path.name, e)
    # continue or return None
```

### Lazy imports inside methods
Import heavy or circular-risk modules inside methods when needed:
```python
def _some_method(self):
    from pathlib import Path as _Path
    from app.core.freqtrade.runners.optimize_runner import build_optimize_command
    ...
```

### SPACING constants for UI layout
Use the `SPACING` dict from `app.ui.theme` for consistent margins/spacing:
```python
from app.ui.theme import SPACING
layout.setContentsMargins(SPACING["md"], SPACING["md"], SPACING["md"], SPACING["md"])
layout.setSpacing(SPACING["sm"])
```

### QTimer for periodic UI updates
```python
self._preview_timer = QTimer(self)
self._preview_timer.setInterval(1000)
self._preview_timer.timeout.connect(self._update_command_preview)
self._preview_timer.start()
```

---

## Architecture Enforcement Rules

- `app/core/**` must NEVER import from `app/ui/**`
- `app/ui/**` must NEVER build freqtrade commands directly
- All freqtrade command construction goes through `app/core/freqtrade/`
- All business logic goes in `app/core/services/`
- AI layer (`app/core/ai/`) must remain optional — core app works without it
- No hardcoded absolute paths anywhere in the codebase
- No duplicated command building across multiple files

## Testing Patterns

- Property-based tests use `hypothesis` library
- Qt widget tests use `pytest-qt`
- Test files mirror the source structure: `tests/core/services/` mirrors `app/core/services/`
- All `__init__.py` files in test directories are empty (namespace packages)
- Shared fixtures in `tests/conftest.py`
