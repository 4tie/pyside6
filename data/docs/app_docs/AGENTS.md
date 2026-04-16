# AGENTS.md — AI Agent Guide

## MCP Servers

| Server | File | Purpose |
|--------|------|---------|
| PySide6 | `data/tools/mcp_pyside6.py` | Run app, tests, read logs, inspect UI/Python files |
| Freqtrade | `data/tools/mcp_freqtrade.py` | Run backtest, read results, analyze strategy, read config |
| ProjectMemory | `data/tools/mcp_project_memory.py` | Save/retrieve facts, paths, workflow rules, read docs/rules |

## Agent Startup Workflow

1. `get_workflow_rules()` — load saved rules before doing anything
2. `get_paths()` — load known project paths
3. `read_rule("guidelines.md")` — load coding standards
4. `read_rule("structure.md")` — understand project layout
5. `list_ui_files()` — discover relevant UI files before editing

## After Every Code Change

1. `run_tests()` — verify nothing broke
2. `read_logs()` — check for runtime errors
3. `save_fact("assumptions", ...)` — record any new decisions made

## Tool Reference

### mcp_pyside6
- `run_app` — launches `main.py`
- `run_tests` — pytest with `--tb=short`
- `read_logs` — reads `data/log/app.log`
- `list_ui_files` — all `.py` under `app/ui/`
- `read_python_file(relative_path)` — read any `.py` by relative path

### mcp_freqtrade
- `run_backtest(strategy, timeframe, timerange)` — execute backtest
- `read_backtest_results(strategy)` — parse latest zip/JSON
- `analyze_strategy_path(strategy)` — path + size + first 30 lines
- `read_config` — reads `user_data/config.json`
- `export_results_summary(strategy)` — plain-text metrics summary

### mcp_project_memory
- `save_fact(category, key, value)` — persist to `data/memory/project_facts.json`
- `get_paths()` — retrieve saved paths
- `save_workflow_rule(rule)` — append a workflow rule
- `get_assumptions()` — retrieve saved assumptions
- `get_workflow_rules()` — retrieve all workflow rules
- `read_doc(name)` — read from `data/docs/app_docs/`
- `list_docs()` — list app docs
- `read_rule(name)` — read from `data/rules/`
- `list_rules()` — list all rule files
