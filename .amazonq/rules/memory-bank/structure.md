# structure.md — Project Organization

## Top-Level Layout
```
pyside6/
├── main.py                  # Entry point — QApplication + ModernMainWindow
├── requirements.txt
├── app/                     # Application source code
├── data/                    # Docs, rules, logs, tools, settings
├── tests/                   # pytest test suite
└── user_data/               # Runtime freqtrade assets (strategies, results, data)
```

## App Source Structure
```
app/
├── app_state/               # Shared state and signals (SettingsState, AIState)
├── core/
│   ├── ai/                  # AI layer: providers, tools, runtime, context, prompts, journal
│   ├── backtests/           # Results domain: parsing, models, indexing, storage
│   ├── freqtrade/           # Freqtrade integration: command building, resolvers, runners
│   ├── models/              # Pydantic domain models (analysis, diagnosis, improve, loop, settings)
│   ├── services/            # Business logic and orchestration services
│   ├── utils/               # Logging, date utilities
│   └── versioning/          # Version models, store, index, versioning service
├── ui/                      # Legacy UI (v1) — widgets, pages, dialogs, theme
└── ui_v2/                   # Active UI (v2) — modern redesign
    ├── shell/               # Header bar, sidebar, status bar
    ├── pages/               # Workflow pages: backtest, dashboard, download, optimize, settings, strategy
    ├── panels/              # AI panel, results panel, terminal panel
    ├── widgets/             # Reusable widgets: metric card, notification toast, run config form, etc.
    ├── dialogs/
    ├── main_window.py       # ModernMainWindow — top-level window
    └── theme.py
```

## Architectural Layers
| Layer | Location | Responsibility |
|-------|----------|----------------|
| UI | `app/ui_v2/` | Display, forms, buttons, tables, user actions |
| App State | `app/app_state/` | Shared state, signals, active selections |
| Service | `app/core/services/` | Business rules, orchestration, file I/O |
| Results Domain | `app/core/backtests/` | Result models, parsing, indexing, storage |
| Freqtrade Integration | `app/core/freqtrade/` | Command construction, subprocess contracts |
| AI Layer | `app/core/ai/` | Provider abstraction, tools, prompts, runtime |
| Versioning | `app/core/versioning/` | Candidate/accepted/history version management |

## Key Relationships
- `main.py` → `SettingsState` → `ModernMainWindow`
- UI pages → Services (never reverse)
- Services → Freqtrade layer for command execution
- Services → Backtests domain for result parsing
- AI layer is optional — core services work without it
- `user_data/` is runtime-owned, never hardcoded paths

## Data Directory
```
data/
├── docs/          # Canonical product/architecture/workflow docs
├── rules/         # Short operational rules for contributors
├── tools/         # CI checks, MCP helpers, automation scripts
├── log/           # Application logs (rotating)
├── memory/        # Project facts JSON for AI memory
└── settings.json  # App settings persistence
```

## Test Structure
```
tests/
├── core/          # Unit/property tests for services, AI, backtests, versioning
├── ui/            # UI widget and page tests (pytest-qt)
├── ui_v2/         # v2 UI tests
└── conftest.py    # Shared fixtures
```
