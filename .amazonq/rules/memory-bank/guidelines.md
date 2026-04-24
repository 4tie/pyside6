# Development Guidelines

## Architecture Rules (Non-Negotiable)
- UI (`app/ui/`) must not build freqtrade commands directly — delegate to services
- `app/core/**` must never import from `app/ui/**`
- AI layer (`app/core/ai/`) must not be a hard dependency for core app functionality
- No subprocess logic in UI layer
- No hardcoded absolute paths — always use `Path(...).expanduser().resolve()`
- No duplicate command building across multiple files
- Accepted strategy version vs candidate version must always be clearly separated
- AI optimization never writes to the accepted strategy directly — always creates a candidate first

## Code Quality Standards

### Module Structure
- All packages use empty `__init__.py` files for namespace packages (no re-exports unless intentional)
- Public API re-exports are done in package-level `__init__.py` (e.g. `app/core/freqtrade/__init__.py` re-exports command builders)
- Module-level logger: `_log = get_logger("module.name")` — always private, always at top of file

### Naming Conventions
- Classes: `PascalCase` (e.g. `BacktestService`, `SettingsState`, `AIService`)
- Functions/methods: `snake_case`
- Private module-level variables: leading underscore (`_log`, `_create_backtest`)
- Constants: `UPPER_SNAKE_CASE`
- Pydantic model fields: `snake_case` with `Field(default, description="...")` always including description

### Type Annotations
- All function signatures use full type annotations
- `Optional[T]` for nullable fields (from `typing`)
- `List[T]` for typed lists in function signatures
- `list[str]` (lowercase) acceptable in Pydantic model fields (Python 3.10+ style)
- `from __future__ import annotations` used in complex modules for forward references

## Pydantic Patterns

### Model Definition
```python
class MyModel(BaseModel):
    field_name: str = Field("default", description="Clear description")
    optional_field: Optional[str] = Field(None, description="...")
    list_field: list[str] = Field(default_factory=list, description="...")
```

### Validators
- Use `@field_validator("field_name")` with `@classmethod` for field-level validation
- Use `@model_validator(mode="before")` with `@classmethod` for cross-field migration/normalization
- Migration validators handle legacy field names (e.g. `selected_model` → `chat_model`)
- Env var loading done in `@model_validator(mode="before")` — check env only when field not already set

### Path Normalization
```python
@field_validator("venv_path", "user_data_path", mode="before")
@classmethod
def normalize_paths(cls, v):
    if v is None:
        return None
    return str(Path(v).expanduser().resolve())
```

## Qt / PySide6 Patterns

### State Classes (QObject)
```python
class MyState(QObject):
    # Declare all signals at class level
    something_changed = Signal(MyModel)
    
    def __init__(self):
        super().__init__()
        self.current_value: Optional[MyModel] = None
```

- State classes inherit `QObject`, declare signals at class level
- Signals emitted after successful operations, not before
- State classes delegate to service classes — no business logic in state

### Service Classes (Plain Python)
- Services are plain Python classes (no QObject inheritance)
- Injected via constructor: `def __init__(self, settings_service: SettingsService)`
- Services do not emit Qt signals — state classes do
- Services return typed results, raise exceptions on failure

## Logging Pattern
```python
from app.core.utils.app_logger import get_logger
_log = get_logger("layer.module_name")

# Usage
_log.info("Action completed: key=%s value=%s", key, value)
_log.debug("Building command: %s", strategy_name)
_log.warning("File not found: %s", path)
_log.error("Failed to parse: %s", e)
```
- Logger name follows `"layer.module"` convention (e.g. `"services.backtest"`, `"freqtrade.commands"`)
- Always use `%s` format strings, never f-strings in log calls
- Log at entry/exit of significant operations with relevant context

## Error Handling
- Services catch exceptions, log with `_log.error(...)`, and return `None` or `False` on failure
- Command builders: catch, log error, re-raise (let caller decide)
- UI layer: handle `None` returns gracefully, show user-facing messages
- Never silently swallow exceptions in core services

## Service Layer Patterns
```python
class MyService:
    def __init__(self, settings_service: SettingsService):
        self.settings_service = settings_service
    
    def do_thing(self, param: str) -> Optional[Result]:
        settings = self.settings_service.load_settings()
        if not settings.user_data_path:
            return None
        try:
            # ... work ...
            _log.info("Done: %s", param)
            return result
        except Exception as e:
            _log.error("Failed: %s", e)
            return None
```

## AI Subsystem Patterns
- `AIService` is the single integration point — wires journal, tools, context providers, runtime
- `ToolRegistry` + `register_*_tools()` pattern for registering tool groups
- Context providers implement `AppContextProvider` interface
- `AsyncConversationRuntime` created fresh on each `get_runtime()` call (picks up settings changes)
- Tool callbacks return `dict` with `"output"` or `"error"` key

## Product-First Guideline
When choosing between:
- Building core backtest/results/versioning behavior, OR
- Building AI/provider complexity

Always choose core product behavior first.

## Testing Conventions
- Tests mirror source structure: `tests/core/services/` mirrors `app/core/services/`
- Property-based tests use `hypothesis` library
- Qt widget tests use `pytest-qt`
- Test files named `test_<module_name>.py`
- Conftest at `tests/conftest.py` for shared fixtures
- Do not remove existing test cases

## CI Checks (run before committing)
- `check_layer_violations.py` — enforces no UI imports in core
- `check_hardcoded_paths.py` — no absolute paths in source
- `check_docs.py` — documentation completeness
- `check_strategy_json.py` — strategy JSON validity
- Run all: `python data/tools/run_checks.py`
