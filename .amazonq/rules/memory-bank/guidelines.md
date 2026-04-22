# guidelines.md — Development Standards and Patterns

## Code Quality Standards

### Module-Level Docstrings
Every non-trivial module starts with a triple-quoted docstring describing its purpose:
```python
"""AIService — single integration point for the AI subsystem.

Wires together EventJournal, ToolRegistry, context providers, journal
adapters, and ConversationRuntime into one cohesive service.
"""
```

### Future Annotations
All service and model files use `from __future__ import annotations` at the top.

### Module-Level Logger
Every module that logs defines a module-level logger immediately after imports:
```python
_log = get_logger("services.loop")
```
Logger names follow the dotted path convention: `"services.loop"`, `"ui_v2.pages.backtest_page"`, `"backtests.store"`.

### Private Helpers as Module-Level Functions
Private utility functions are module-level with underscore prefix, not nested:
```python
def _norm(value: float, lo: float, hi: float) -> float: ...
def _write_meta(run_dir: Path, ...) -> None: ...
```

---

## Naming Conventions

- Classes: PascalCase (`BacktestPage`, `LoopService`, `RunStore`)
- Private attributes: `_snake_case` prefix (`self._config`, `self._running`)
- Module-level private: `_snake_case` (`_log`, `_SETTINGS_KEY`, `_NORM_NET_PROFIT_MIN`)
- Constants: `_UPPER_SNAKE_CASE` with underscore prefix when module-private
- Methods: `snake_case`; private methods prefixed with `_`
- UI section separators use dashed comment blocks:
  ```python
  # ------------------------------------------------------------------
  # UI Construction
  # ------------------------------------------------------------------
  ```

---

## Structural Conventions

### Class Organization Pattern
Classes follow a consistent section order:
1. Class-level constants
2. `__init__`
3. Public API (properties, then methods)
4. Private helpers (prefixed `_`)
5. UI sections use comment banners: `# -- UI Construction --`, `# -- Signal Wiring --`, `# -- Public API --`

### UI Page Pattern (QWidget subclasses)
```python
class BacktestPage(QWidget):
    loop_completed = Signal()  # Signals declared at class level

    def __init__(self, settings_state: SettingsState, parent=None) -> None:
        super().__init__(parent)
        # 1. Store dependencies
        # 2. Initialize state
        # 3. _build_ui()
        # 4. _connect_signals()
        # 5. _refresh_*() calls
        # 6. Restore persisted state

    def _build_ui(self) -> None: ...
    def _connect_signals(self) -> None: ...
    def _refresh_*(self) -> None: ...
    def get_*(self) -> ...: ...   # Public API
    def refresh(self) -> None: ...  # Called by parent window
```

### Service Pattern
Services are plain classes (no Qt inheritance) with:
- Constructor takes dependencies as arguments
- Public API methods with full docstrings
- Private helpers prefixed `_`
- Static methods for pure transformations (`RunStore.save`, `RunStore.load_run`)
- Callbacks registered via `set_callbacks()` rather than signals

### Pydantic Models
All domain models use Pydantic v2 `BaseModel`:
```python
class AppSettings(BaseModel):
    field: type = Field(default, description="...")
```
- Every field has a `Field(default, description="...")` annotation
- Validators use `@field_validator` and `@model_validator` decorators
- Migration logic lives in `@model_validator(mode="before")` for backward compat

---

## Architectural Patterns

### Layer Separation (enforced by CI)
- UI (`app/ui_v2/`, `app/ui/`) NEVER imports from each other's internals
- `app/core/**` NEVER imports from `app/ui*`
- Services import from domain models and freqtrade layer, not from UI
- No hardcoded absolute paths anywhere

### Dependency Injection
Services receive dependencies through constructor arguments:
```python
class LoopService:
    def __init__(self, improve_service: ImproveService) -> None: ...

class BacktestPage(QWidget):
    def __init__(self, settings_state: SettingsState, parent=None) -> None: ...
```

### Settings Access Pattern
Settings are always accessed via `SettingsState`, never read directly from disk:
```python
settings = self.settings_state.current_settings
if not settings or not settings.user_data_path:
    return
```

### Path Handling
Always use `pathlib.Path` with `.expanduser().resolve()`:
```python
backtest_results_dir = Path(settings.user_data_path).expanduser().resolve() / "backtest_results"
```

### Error Handling in UI
UI methods catch specific exceptions and show `QMessageBox`:
```python
try:
    results = RunStore.load_run(run_dir)
except (FileNotFoundError, ValueError) as e:
    _log.error("Failed to load run %s: %s", run_meta.get("run_id"), e)
    QMessageBox.critical(self, "Load Failed", str(e))
```

### Logging Style
Use `%s` format strings (not f-strings) in log calls:
```python
_log.info("Saving run | id=%s | strategy=%s | trades=%d | profit=%.4f%%",
          run_id, s.strategy, s.total_trades, s.total_profit)
_log.warning("Loop iter %d: hyperopt non-zero exit code %d", iteration.iteration_number, exit_code)
```

---

## Semantic Patterns

### Callback Registration Pattern
Services expose callbacks via a `set_callbacks()` method:
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

### Optional Dependency Pattern
Optional integrations (AI advisor, backtest page) are set post-construction:
```python
self._ai_advisor = None  # Set via set_ai_advisor()
self._backtest_page = None  # set via set_backtest_page() after UI is built
```

### State Machine Pattern (LoopService)
State transitions are explicit with `_running`, `_current_iteration`, `_best_score`.
Public methods check state guards before proceeding:
```python
def should_continue(self) -> bool:
    if not self._running: return False
    if self._config is None: return False
    if self._current_iteration >= self._config.max_iterations: return False
    return True
```

### Immutable Results Pattern
`copy.deepcopy()` is used consistently when storing params to prevent mutation:
```python
self._current_params = copy.deepcopy(initial_params)
iteration.params_before = copy.deepcopy(self._current_params)
```

### QSettings Persistence
Splitter states and UI preferences use `QSettings("FreqtradeGUI", "ModernUI")`:
```python
qs = QSettings("FreqtradeGUI", "ModernUI")
qs.setValue(_SETTINGS_KEY, self._splitter.saveState())
```

### Accessibility
All interactive widgets set `setAccessibleName()` and `setToolTip()`:
```python
self._run_btn.setAccessibleName("Run backtest")
self._run_btn.setToolTip("Start the backtest with the current configuration")
```

### JSON I/O
All JSON files use `encoding="utf-8"` and `ensure_ascii=False`:
```python
(run_dir / "meta.json").write_text(
    json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
)
```

---

## Testing Patterns

### Test Markers
- `@pytest.mark.bug_condition` — test encodes a bug (expected to fail on unfixed code)
- `@pytest.mark.preservation` — test verifies first-call behavior is unchanged

### Property-Based Testing
Hypothesis is used extensively for property tests in `tests/core/`:
```python
from hypothesis import given, strategies as st
```

### Test File Naming
- `test_*.py` for unit tests
- `test_*_properties.py` for property-based tests
- `test_*_bugfix*.py` for regression/bug tests
- `test_*_preservation*.py` for preservation tests

### No UI in Core Tests
Core tests (`tests/core/`) never import PySide6 — they run in CI without a display.
