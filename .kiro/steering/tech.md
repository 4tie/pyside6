# Tech Stack

## Language & Runtime
- Python 3.9+ — type hints, `pathlib`, `dataclasses` used throughout
- Pure Python desktop app — no JavaScript/TypeScript

## Core Dependencies
| Package | Version | Role |
|---------|---------|------|
| PySide6 | >=6.6.0 | Qt6 bindings — UI, signals, QProcess |
| pydantic | >=2.0.0 | Data models, validation, JSON serialization |
| freqtrade | latest | Crypto trading bot (invoked as subprocess) |

## Key Qt Components
- `QObject` + `Signal` — reactive state (`SettingsState`)
- `QProcess` — non-blocking subprocess with live stdout/stderr streaming
- `QMainWindow` + `QTabWidget` — tab-based main window
- `QDialog` — pairs selector dialog

## Linting
- `ruff` — linter and formatter

## Common Commands
```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
python main.py

# Run tests
pytest --tb=short

# Lint
ruff check .
ruff format .
```

## Logging
- Entry point: `get_logger("name")` from `app.core.utils.app_logger`
- Log files written to `data/log/` (rotating, 5MB max)
- Section routing: `ui.*` → `ui.log`, `services.*` → `services.log`, `process.*` → `process.log`

## Settings Storage
- Persisted at `~/.freqtrade_gui/settings.json`
- Loaded into `AppSettings` (Pydantic model with path normalization)

## Freqtrade Execution
- Preferred: `python -m freqtrade <subcommand>` via venv Python
- Fallback: direct `freqtrade` executable from venv `Scripts/` (Windows) or `bin/` (Unix)
- Controlled by `AppSettings.use_module_execution` (default: `True`)
- Never rely on shell activation — inject `VIRTUAL_ENV` and prepend venv bin to `PATH` via `QProcessEnvironment`

## Platform Notes
- Windows path: `{venv}/Scripts/python.exe`, `{venv}/Scripts/freqtrade.exe`
- Unix path: `{venv}/bin/python`, `{venv}/bin/freqtrade`
- Branch with `if os.name == "nt":` for platform differences
