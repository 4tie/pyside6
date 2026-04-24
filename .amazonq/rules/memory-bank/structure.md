# Project Structure

## Top-Level Layout
```
pyside6/
├── main.py                  # Entry point — loads .env, creates QApplication, launches ModernMainWindow
├── requirements.txt
├── app/                     # Application source
├── data/                    # Docs, rules, logs, tools, settings
├── tests/                   # pytest test suite
└── user_data/               # Runtime freqtrade assets (strategies, results, config, market data)
```

## App Directory
```
app/
├── app_state/               # Shared state and signals (settings, AI state)
├── core/
│   ├── ai/                  # AI subsystem (providers, prompts, runtime, tools, context, journal)
│   ├── backtests/           # Results domain (parsing, models, indexing, storage)
│   ├── freqtrade/           # Freqtrade integration (commands, resolvers, runners, discovery, parsing)
│   ├── mappers/             # Data transformation (loop_mapper)
│   ├── models/              # Pydantic domain models (ai, backtest, strategy, loop, versioning, etc.)
│   ├── parsing/             # Parsers (backtest, JSON, strategy)
│   ├── services/            # Business logic and orchestration (30+ service files)
│   ├── storage/             # Storage abstractions
│   ├── utils/               # Logging, date utils, path utils
│   └── versioning/          # Version index and store
├── ui/
│   ├── ai/                  # Qt conversation adapter
│   ├── dialogs/             # Modal dialogs (pairs selector)
│   ├── pages/               # Top-level workflow tabs (backtest, dashboard, improve, loop, optimize, etc.)
│   ├── panels/              # Dockable panels (AI, results, terminal)
│   ├── shell/               # App chrome (header bar, sidebar, status bar)
│   ├── widgets/             # Reusable visual components
│   ├── main_window.py       # ModernMainWindow — root widget
│   └── theme.py             # Theming
└── web/
    ├── api/routes/          # FastAPI route handlers
    ├── static/              # Web UI assets
    ├── main.py              # FastAPI app
    ├── dependencies.py
    └── models.py
```

## Canonical Layers (A→F)
| Layer | Location | Responsibility |
|-------|----------|----------------|
| A — UI | `app/ui/` | Tabs, forms, widgets, display — no heavy business logic |
| B — App State | `app/app_state/` | Settings, shared signals, active selections |
| C — Service | `app/core/services/` | Business rules, orchestration, file I/O, candidate versioning |
| D — Results Domain | `app/core/backtests/`, `app/core/models/` | Result models, parsing, indexing, storage |
| E — Freqtrade Integration | `app/core/freqtrade/` | Command construction, strategy/config resolution, execution contracts |
| F — AI | `app/core/ai/` | Provider abstraction, prompts, context, tool execution |

## Key Architecture Rules
- UI must not build freqtrade commands directly
- `app/core/**` must not import UI code
- AI layer must not be a hard dependency for core app functionality
- No subprocess logic in UI layer
- No hardcoded absolute paths
- No duplicate command building across files
- Accepted version vs candidate version must always be clearly separated

## Data Directory
```
data/
├── docs/          # Canonical product/architecture/workflow docs + freqtrade reference docs
├── log/           # Rotating log files (app, process, services, ui)
├── memory/        # project_facts.json — persistent project memory
├── rules/         # Short operational rules (guidelines, product, structure, tech)
└── tools/         # CI checks, MCP helpers, changelog tools
```

## User Data (Runtime)
```
user_data/
├── strategies/    # .py strategy files + .json parameter files
├── backtest_results/  # Organized by strategy, with _improve/ and _loop/ subdirs
├── data/binance/  # Downloaded OHLCV market data
├── hyperopt_results/
├── config.json
└── backtest_config.json
```
