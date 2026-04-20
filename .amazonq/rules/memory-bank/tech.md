# tech.md — Technology Stack

## Programming Language
- **Python 3.x** (desktop application)

## Core Dependencies
- **PySide6 >= 6.6.0** — Qt6 bindings for Python (UI framework)
- **Pydantic >= 2.0.0** — Data validation and settings management
- **Freqtrade** — Trading bot framework (subprocess/module integration)
- **filelock** — File locking for concurrent access
- **optuna** — Hyperparameter optimization

## Development & Testing
- **pytest >= 7.4.0** — Test framework
- **pytest-cov >= 4.1.0** — Coverage reporting
- **pytest-qt >= 4.2.0** — Qt testing support
- **hypothesis >= 6.100.0** — Property-based testing

## Build System
- Standard Python package with `requirements.txt`
- No complex build tooling required

## Development Commands
```bash
# Install dependencies
pip install -r requirements.txt

# Run application
python main.py

# Run tests
pytest

# Run tests with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/core/services/test_backtest_service.py

# Run CI checks
python data/tools/run_checks.py
```

## CI Checks (automated)
- `check_docs.py` — Validate documentation consistency
- `check_hardcoded_paths.py` — Detect hardcoded paths
- `check_layer_violations.py` — Enforce architecture layer separation
- `check_strategy_json.py` — Validate strategy JSON files

## Freqtrade Integration
- Runs as subprocess or module execution (configurable)
- Commands built via `app/core/freqtrade/command_runner.py`
- Strategy/config resolution via `app/core/freqtrade/resolvers/`
- Results parsed from JSON output

## AI Integration (Optional)
- Provider abstraction in `app/core/ai/providers/`
- Supports Ollama, OpenRouter, and future providers
- Not a hard dependency — core app works without AI
- AI features: deep analysis, code suggestions, chat assistance

## Logging
- Rotating file logs in `data/log/`
- Separate logs: app.log, services.log, process.log, ui.log
- Configured via `app/core/utils/app_logger.py`

## Configuration
- User settings in `data/settings.json`
- Freqtrade config in `user_data/config.json`
- Strategy parameters in `user_data/strategies/*.json`

## Platform Support
- Windows (primary development platform)
- Linux/macOS (should work, not primary target)
