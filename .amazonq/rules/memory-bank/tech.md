# Technology Stack

## Languages & Runtime
- Python 3.9+ (type hints, dataclasses, pathlib used throughout)
- No JavaScript/TypeScript — pure Python desktop app

## Core Dependencies
| Package | Version | Role |
|---------|---------|------|
| PySide6 | >=6.6.0 | Qt6 bindings: QApplication, QMainWindow, QProcess, QObject, Signal |
| pydantic | >=2.0.0 | Data models, validation, JSON serialization (`model_dump()`, `field_validator`) |
| freqtrade | latest | Crypto trading bot (invoked as subprocess via `python -m freqtrade`) |

## Key Qt Components Used
- `QObject` + `Signal` — reactive state management in `SettingsState`
- `QProcess` — non-blocking subprocess execution with live stdout/stderr streaming
- `QMainWindow` + `QTabWidget` — tab-based main window
- `QDialog` — pairs selector dialog
- `QWidget` — base for all pages and widgets

## Build & Run
```bash
# Install dependencies
pip install -r requirements.txt

# Run application
python main.py
```

## Linting
- `ruff` (cache present at `.ruff_cache/`) — fast Python linter/formatter

## Settings Storage
- `~/.freqtrade_gui/settings.json` — user settings persisted as JSON

## Logging
- File logger at `{user_data_path}/logs/app.log`
- Console handler for development
- Logger per module via `get_logger("module_name")` from `app.core.utils.app_logger`

## Freqtrade Execution Strategy
- Preferred: `python -m freqtrade <subcommand>` (uses venv Python)
- Fallback: direct `freqtrade` executable from venv Scripts/bin
- Controlled by `AppSettings.use_module_execution` (default: `True`)

## Platform Notes
- Windows path handling: `os.name == "nt"` checks for `Scripts/python.exe` vs `bin/python`
- Path normalization via `Path.expanduser().resolve()` on all path fields
