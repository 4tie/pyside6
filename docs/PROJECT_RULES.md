# PROJECT_RULES.md

## Code Style

- Logger: `_log = get_logger("module_name")` in every non-trivial module
- Docstrings: Google-style on all public classes/methods; one-line on private helpers
- Type hints: full signatures using `from typing import Optional, List, Dict, ...`
- `__init__.py`: always empty — import directly from module files

## Structure Rules

- Stateless logic → `@staticmethod` (e.g. `CommandRunner`, `BacktestResultsService`)
- Stateful services → instance state + `__init__` deps (e.g. `BacktestService(settings_service)`)
- Services never import UI code
- `@dataclass` for internal DTOs; `pydantic.BaseModel` for user-facing settings
- Pydantic fields always have `Field(default, description="...")`
- Path fields use `@field_validator(..., mode="before")` with `Path.expanduser().resolve()`

## Qt Rules

- State objects extend `QObject`, declare `Signal(ModelType)` as class attributes
- UI pages receive `SettingsState` via constructor — never instantiate state themselves
- `QProcess` managed only by `ProcessService`
- `MainWindow` wires all signals→slots in `__init__`

## Naming

- Classes: `PascalCase`
- Methods/functions: `snake_case`; private: `_snake_case`
- Module logger: always `_log`
- Qt signals: `noun_past_tense` (e.g. `settings_saved`, `settings_loaded`)

## Error Handling

- `ValueError` for config/logic errors
- `FileNotFoundError` for missing files
- Catch broad `Exception` only in IO/persistence; log + re-raise as `ValueError`
- Never silently swallow exceptions in service layer

## Paths

- Always `pathlib.Path` — no string concatenation
- Resolve: `Path(x).expanduser().resolve()`
- Windows: `os.name == "nt"` for `Scripts/` vs `bin/`
- `mkdir(parents=True, exist_ok=True)` before writing
