# Technology Stack

## Languages & Runtime
- Python 3.9+ (type hints, dataclasses, pathlib used throughout)
- No JavaScript/TypeScript — pure Python desktop app

## Core Dependencies
| Package | Version | Role |
|---------|---------|------|
| PySide6 | >=6.6.0 | Qt6 bindings: QApplication, QMainWindow, QProcess, QObject, Signal |
| pydantic | >=2.0.0 | Data models, validation, JSON serialization |
| fastmcp | latest | MCP server framework for AI tool integration |
| freqtrade | latest | Crypto trading bot (invoked as subprocess) |

## Key Qt Components
- `QObject` + `Signal` — reactive state in `SettingsState`
- `QProcess` — non-blocking subprocess with live stdout/stderr streaming
- `QMainWindow` + `QTabWidget` — tab-based main window
- `QDialog` — pairs selector dialog

## Build & Run
```bash
pip install -r requirements.txt
python main.py
```

## Linting
- `ruff` — fast Python linter/formatter

## Settings Storage
- `~/.freqtrade_gui/settings.json` — user settings as JSON

## Logging
- File: `data/log/app.log`
- Console handler for development
- Per-module via `get_logger("module_name")` from `app.core.utils.app_logger`

## Freqtrade Execution
- Preferred: `python -m freqtrade <subcommand>` (venv Python)
- Fallback: direct `freqtrade` executable from venv Scripts/bin
- Controlled by `AppSettings.use_module_execution` (default: `True`)

## Platform Notes
- Windows: `os.name == "nt"` → `Scripts/python.exe` vs `bin/python`
- Path normalization via `Path.expanduser().resolve()` on all path fields
