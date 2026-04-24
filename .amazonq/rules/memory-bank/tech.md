# Technology Stack

## Languages & Runtime
- **Python** (primary language, 3.10+)
- Entry point: `main.py`

## Core Frameworks
| Package | Version | Purpose |
|---------|---------|---------|
| PySide6 | >=6.6.0 | Desktop GUI (Qt6 bindings) |
| Pydantic | >=2.0.0 | Data models and validation |
| FastAPI | >=0.104.0 | Web API layer |
| uvicorn[standard] | >=0.24.0 | ASGI server for web layer |
| freqtrade | latest | Trading bot framework (subprocess execution) |
| python-dotenv | >=1.0.0 | Environment variable loading (.env) |
| filelock | latest | File-based locking |
| optuna | latest | Hyperparameter optimization |
| python-multipart | latest | FastAPI form data |

## AI Providers
- **OpenRouter** — cloud AI (configured via `OPENROUTER_API_KEY` / `OPENROUTER_API_KEYS`)
- **Ollama** — local AI (configured via `OLLAMA_BASE_URL`, default `http://localhost:11434`)

## Testing Stack
| Package | Purpose |
|---------|---------|
| pytest >=7.4.0 | Test runner |
| pytest-cov >=4.1.0 | Coverage |
| pytest-qt >=4.2.0 | Qt widget testing |
| hypothesis >=6.100.0 | Property-based testing |
| playwright >=1.40.0 | Browser/web testing |
| pytest-playwright >=0.4.0 | Playwright pytest integration |

## Linting & Formatting
- **ruff** — linter and formatter (cache in `.ruff_cache/`)
- Config: `pytest.ini` for test configuration

## CI/CD
- GitHub Actions: `.github/workflows/ci.yml`
- CI checks in `data/tools/ci_checks/`:
  - `check_docs.py` — documentation validation
  - `check_hardcoded_paths.py` — no hardcoded absolute paths
  - `check_layer_violations.py` — architecture layer enforcement
  - `check_strategy_json.py` — strategy JSON validation

## Configuration Files
- `.env` — API keys and provider settings (never commit real keys)
- `.env.example` — template for environment setup
- `data/settings.json` — app settings
- `user_data/config.json` — freqtrade runtime config
- `user_data/backtest_config.json` — backtest-specific config

## Development Commands
```bash
# Run desktop app
python main.py

# Run web server
python run_web.py

# Run tests
pytest

# Run tests with coverage
pytest --cov=app

# Run specific test file
pytest tests/core/services/test_improve_service.py

# Lint
ruff check .

# Format
ruff format .
```

## MCP Tools (data/tools/)
- `mcp_freqtrade.py` — Freqtrade MCP helper
- `mcp_project_memory.py` — Project memory MCP helper
- `mcp_pyside6.py` — PySide6 MCP helper
- `post_change_report.py` — Post-change reporting
- `run_checks.py` — Run all CI checks locally
- `update_changelog.py` — Changelog management

## Market Data
- Exchange: Binance
- Pairs: ADA/USDT, BNB/USDT, BTC/USDT, DOGE/USDT, ETH/USDT, SOL/USDT, XRP/USDT
- Timeframes: 1m, 4h, 5m
