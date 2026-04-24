# Project Structure

## Top-Level Layout

```
main.py                  # Desktop app entry point (PySide6)
run_web.py               # Web server entry point (FastAPI/uvicorn)
requirements.txt         # All runtime + dev dependencies
pytest.ini               # Test configuration
.env / .env.example      # Environment variable config
data/                    # Runtime data (settings, logs, patterns, memory)
user_data/               # Freqtrade user data (strategies, backtest results, config)
app/                     # All application source code
tests/                   # All tests
docs/                    # API reference documentation
```

## Application Source (`app/`)

```
app/
├── core/                # Business logic — NO PySide6, NO app.ui, NO app.app_state imports
│   ├── ai/              # AI subsystem
│   │   ├── context/     # Context providers (app state, backtest, strategy)
│   │   ├── journal/     # Event journal + signal adapters
│   │   ├── providers/   # Ollama and OpenRouter provider implementations
│   │   ├── runtime/     # AsyncConversationRuntime, agent policy
│   │   └── tools/       # Tool registry and tool definitions
│   ├── backtests/       # Backtest result parsing, indexing, storage
│   ├── freqtrade/       # Freqtrade subprocess commands, discovery, runners
│   ├── mappers/         # Data transformation between layers
│   ├── models/          # Pydantic models (domain objects, no UI concerns)
│   ├── parsing/         # JSON, backtest, strategy file parsers
│   ├── services/        # All business logic services
│   ├── storage/         # Low-level persistence utilities
│   ├── utils/           # app_logger, date_utils, path_utils
│   └── versioning/      # Strategy version index and store
│
├── ui/                  # PySide6 desktop UI — may import app.core, NOT app.web
│   ├── pages/           # One file per page (backtest, results, compare, etc.)
│   ├── widgets/         # Reusable Qt widgets (charts, stat_card, terminal)
│   ├── dialogs/         # Modal dialogs (rollback, etc.)
│   ├── adapters/        # Bridges between UI events and core services
│   ├── shell/           # Sidebar navigation
│   ├── main_window.py   # ModernMainWindow — top-level shell
│   └── theme.py         # Stylesheet and color constants
│
├── web/                 # FastAPI web layer — NO app.ui imports
│   ├── api/routes/      # One router file per domain area
│   ├── static/          # Vanilla JS + HTML pages served at /static
│   ├── main.py          # FastAPI app factory, router registration
│   ├── models.py        # Web-layer Pydantic request/response models
│   ├── dependencies.py  # FastAPI dependency injection
│   └── process_output_bus.py  # SSE event bus for streaming process output
│
├── api/                 # Legacy/internal API routers (runs_router)
│
└── app_state/           # Qt-aware state objects (QObject + Signal)
    ├── settings_state.py  # SettingsState — wraps SettingsService with Qt signals
    └── ai_state.py        # AI panel state
```

## Tests (`tests/`)

```
tests/
├── conftest.py          # Shared fixtures (tmp_path-based, no hardcoded paths)
├── test_architecture.py # Layer boundary enforcement (run as part of CI)
├── core/                # Unit tests for core services and models
├── ui/                  # pytest-qt widget tests
├── web/                 # FastAPI route tests (playwright + httpx)
├── api/                 # API router tests
├── property/            # Hypothesis property-based tests
└── test_*.py            # Top-level integration / bugfix tests
```

## Architecture Rules (enforced by `test_architecture.py`)

1. `app/core/` — **no PySide6 imports** (framework-agnostic business logic)
2. `app/core/services/` — **no `app.ui` or `app.app_state` imports**
3. `app/web/` — **no `app.ui` imports**

Violations cause `test_architecture.py` to fail. Always run it after structural changes.

## Key Conventions

- **Models**: All domain objects are Pydantic v2 `BaseModel` subclasses in `app/core/models/`
- **Services**: Stateless or lightly stateful classes in `app/core/services/`; injected via constructor
- **State objects**: `app/app_state/` holds `QObject` subclasses that wrap services and emit Qt signals
- **Pages**: Each UI page receives `SettingsState` (and optionally `ProcessRunManager`) via constructor; pages do not instantiate services directly
- **Logging**: `_log = get_logger("section.module")` at module level in every file
- **Paths**: Use `pathlib.Path` throughout; normalize with `Path.expanduser().absolute()` (not `.resolve()` — avoids breaking venv symlinks)
- **Tests**: Use `tmp_path` or `tempfile.TemporaryDirectory` — never hardcode machine paths; Hypothesis tests create their own temp dirs inline
- **Bugfix tests**: `bug_condition` marker = expected to fail on unfixed code; `preservation` marker = must pass on unfixed code

## Runtime Data Locations

| Path | Contents |
|---|---|
| `data/settings.json` | Persisted app settings (gitignored) |
| `data/log/` | Rotating log files (gitignored) |
| `data/patterns.json` | Failure pattern database |
| `data/memory/` | AI conversation memory |
| `user_data/strategies/` | Freqtrade strategy `.py` + `.json` params files |
| `user_data/backtest_results/` | Freqtrade backtest ZIP/JSON output |
| `user_data/config.json` | Active freqtrade config |
