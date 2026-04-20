# structure.md — Project Organization

## Top-Level Layout
```
pyside6/
├── main.py                  # Entry point
├── requirements.txt
├── app/                     # Application source
├── data/                    # Docs, rules, logs, tools
├── tests/                   # Test suite
└── user_data/               # Runtime freqtrade assets (strategies, results, config)
```

## App Directory
```
app/
├── app_state/               # Shared state and signals (settings_state.py, ai_state.py)
├── core/
│   ├── ai/                  # AI layer (context, journal, models, prompts, providers, runtime, tools)
│   ├── backtests/           # Results domain (parsing, models, indexing, storage)
│   ├── freqtrade/           # Freqtrade integration (resolvers, runners, command_runner.py)
│   ├── models/              # Shared domain models (diagnosis, improve, loop, settings)
│   ├── services/            # Business logic and orchestration (all major services)
│   ├── utils/               # Utilities (app_logger.py, date_utils.py)
│   └── versioning/          # Version tracking (index, models, store, service)
└── ui/
    ├── dialogs/             # Modal dialogs (pairs_selector, settings)
    ├── pages/               # Top-level workflow tabs (backtest, loop, improve, optimize, etc.)
    ├── widgets/             # Reusable visual components (results, stats, trades, terminal, AI chat)
    ├── main_window.py       # Main application window
    └── theme.py             # App theming
```

## Canonical Layers (strict separation)
| Layer | Location | Responsibility |
|---|---|---|
| UI | `app/ui/` | Display, forms, buttons, user actions |
| App State | `app/app_state/` | Shared state, signals, active selections |
| Service | `app/core/services/` | Business rules, orchestration, file I/O |
| Results Domain | `app/core/backtests/` | Result models, parsing, indexing, storage |
| Freqtrade Integration | `app/core/freqtrade/` | Command construction, strategy/config resolution |
| AI (future) | `app/core/ai/` | Deep analysis, suggestions, provider abstraction |

## Data Directory
```
data/
├── docs/                    # Canonical product/architecture/workflow docs
├── rules/                   # Short operational rules for contributors
├── tools/                   # CI checks, MCP helpers, automation scripts
├── log/                     # Application logs
└── memory/                  # Project facts JSON
```

## Tests Directory
```
tests/
├── core/                    # Unit/property tests for core layers
│   ├── ai/                  # AI service tests
│   ├── backtests/           # Results store tests
│   ├── services/            # Service layer tests
│   └── versioning/          # Versioning tests
├── ui/                      # UI tests (pages, widgets)
└── conftest.py              # Shared fixtures
```

## Architecture Rules
- UI must NOT build freqtrade commands directly
- Services must NOT import UI code
- No UI imports inside `app/core/**`
- No subprocess logic inside UI
- AI layer must NOT be a hard dependency for core app functionality
- No hardcoded absolute paths
- No command building duplicated across multiple files
