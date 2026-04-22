# tech.md — Technology Stack

## Languages & Runtime
- Python 3.12 (target, per CI)
- PySide6 >= 6.6.0 — Qt6 desktop GUI framework
- Freqtrade — crypto trading bot (runs as subprocess or module)

## Core Dependencies
| Package | Purpose |
|---------|---------|
| PySide6 >= 6.6.0 | GUI framework |
| pydantic >= 2.0.0 | Data models and validation |
| freqtrade | Trading bot integration |
| filelock | File-based locking for concurrent access |
| optuna | Hyperparameter optimization |

## Dev / Test Dependencies
| Package | Purpose |
|---------|---------|
| pytest >= 7.4.0 | Test runner |
| pytest-cov >= 4.1.0 | Coverage reporting |
| pytest-qt >= 4.2.0 | Qt widget testing |
| hypothesis >= 6.100.0 | Property-based testing |
| ruff | Linting and formatting |

## Development Commands
```bash
# Run all tests
pytest

# Run only core tests (no UI, works without PySide6)
pytest tests/core/ --tb=short -q

# Run UI tests
pytest tests/ui/ tests/ui_v2/

# Lint
ruff check app/ data/tools/

# Format check
ruff format --check app/ data/tools/

# Run the app
python main.py
```

## pytest Configuration (pytest.ini)
- testpaths: `tests/`
- addopts: `--tb=short -q`
- Custom markers:
  - `bug_condition` — encodes a bug condition (expected to fail on unfixed code)
  - `preservation` — verifies first-call behavior is unchanged by a fix

## CI Pipeline (GitHub Actions)
Three jobs on push/PR to `main`:
1. **Lint & Format** — `ruff check` + `ruff format --check` on `app/` and `data/tools/`
2. **Tests** — `pytest tests/core/` (UI tests skipped in CI, PySide6 too heavy)
3. **Structure Rules** — validates docs exist, no UI imports in services, no hardcoded paths, strategy JSON format

## Architecture Constraints
- No UI imports inside `app/core/**`
- No subprocess logic in UI layer
- No hardcoded absolute paths
- AI provider is optional — app must work without a live AI connection
- Freqtrade runs as subprocess via `app/core/freqtrade/` layer

## Logging
- Rotating log files in `data/log/`
- Separate loggers: `app.log`, `process.log`, `services.log`, `ui.log`
- Setup via `app/core/utils/app_logger.py`

## Settings Persistence
- `data/settings.json` — app settings (paths, venv, exchange config)
- `SettingsState` in `app/app_state/settings_state.py` manages load/save
