# AGENTS.md — AI Agent Guide

## MCP Servers

| Server | File | Purpose |
|--------|------|---------|
| PySide6 | `tools/mcp_pyside6.py` | Run app, tests, read logs, list UI files |
| Freqtrade | `tools/mcp_freqtrade.py` | Version check, list strategies/results, read settings |
| ProjectMemory | `tools/mcp_project_memory.py` | Read docs/ and memory-bank rules |

## Available Tools

### mcp_pyside6
- `run_app` — launches `main.py`
- `run_tests` — runs `pytest`, returns stdout+stderr
- `read_logs` — reads `logs/app.log`
- `list_ui` — lists all `.py` and `.ui` files (excludes venv/cache)

### mcp_freqtrade
- `freqtrade_version` — runs `python -m freqtrade --version`
- `list_strategies` — lists `.py` files in `user_data/strategies/`
- `list_backtest_results` — lists `.zip` files in `user_data/backtest_results/`
- `read_settings` — returns current `~/.freqtrade_gui/settings.json`

### mcp_project_memory
- `list_docs` — lists files in `docs/`
- `read_doc(name)` — reads a doc file by name
- `list_rules` — lists memory-bank rule files
- `read_rule(name)` — reads a rule file by name

## Workflow for Agents

1. Call `read_rule("guidelines.md")` and `read_rule("structure.md")` before making code changes
2. Call `list_ui()` to discover relevant files
3. Call `run_tests()` after changes to verify nothing broke
4. Call `read_logs()` if the app crashes or behaves unexpectedly
5. Call `read_settings()` to understand the current environment paths
