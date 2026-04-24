# Tech Stack

## Runtime Environment

- **Python 3.12**
- **Virtual environment**: `.venv/` at project root

## Core Dependencies

| Library | Purpose |
|---|---|
| PySide6 ≥ 6.6 | Desktop UI framework (Qt6 bindings) |
| FastAPI ≥ 0.104 | Web API server |
| uvicorn | ASGI server for FastAPI |
| Pydantic v2 | Data models and validation throughout |
| freqtrade | Trading bot engine (subprocess execution) |
| pyqtgraph | Charts and plotting widgets |
| python-dotenv | `.env` loading at startup |
| optuna | Hyperparameter optimization support |
| filelock | File-level locking for concurrent writes |
| numpy | Numerical utilities |
| requests | HTTP client for AI provider calls |
| sse-starlette | Server-sent events for streaming AI responses |

## AI Providers

- **Ollama** (local, default): `http://localhost:11434`
- **OpenRouter** (cloud): API keys via `OPENROUTER_API_KEY` / `OPENROUTER_API_KEYS` env vars

## Testing

- **pytest** with `hypothesis` for property-based tests
- **pytest-qt** for PySide6 widget tests
- **playwright / pytest-playwright** for web UI tests
- Custom markers: `bug_condition` (expected to fail on unfixed code), `preservation` (must pass on unfixed code)

## Common Commands

```bash
# Run the desktop app
python main.py

# Run the web server (standalone)
python run_web.py
# Web UI: http://127.0.0.1:8000  |  API docs: http://127.0.0.1:8000/docs

# Run all tests
pytest

# Run tests with coverage
pytest --cov=app

# Run a specific test file
pytest tests/test_architecture.py

# Run only property-based tests
pytest tests/property/

# Run architecture boundary linter standalone
python tests/test_architecture.py
```

## Environment Variables

Configured via `.env` (see `.env.example`):

| Variable | Purpose |
|---|---|
| `OPENROUTER_API_KEY` | Single OpenRouter key |
| `OPENROUTER_API_KEYS` | Comma-separated key list for rotation |
| `OLLAMA_BASE_URL` | Override Ollama server URL |
| `AI_PROVIDER` | Default AI provider (`ollama` or `openrouter`) |
| `AI_CHAT_MODEL` | Default chat model |
| `AI_TASK_MODEL` | Default tool-calling model |
| `AI_STREAM_ENABLED` | Enable streaming responses (`true`/`false`) |
| `AI_TOOLS_ENABLED` | Enable tool calling (`true`/`false`) |
| `FREQTRADE_GUI_LOG_DIR` | Override log output directory |

## Logging

- Entry point: `app/core/utils/app_logger.py`
- Logger hierarchy: `freqtrade_gui.<section>.<module>` (e.g. `freqtrade_gui.services.loop`)
- Always use `get_logger("section.module")` — never `logging.getLogger()` directly
- Log files written to `data/log/` (rotated, 5 MB max, 3 backups)
- Section routing: `ui.*` → `ui.log`, `services.*` → `services.log`, `process.*` → `process.log`
- Custom `CMD` level (25) for subprocess/freqtrade command output
