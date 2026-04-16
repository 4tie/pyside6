# STRUCTURE.md — Project Structure Map

## 1) Current top-level structure
```text
pyside6/
├── main.py
├── requirements.txt
├── app/
├── data/
├── tests/
└── user_data/
```

---

## 2) Current real app structure
```text
app/
├── app_state/
│   └── settings_state.py
├── core/
│   ├── ai/
│   │   ├── models/
│   │   └── prompts/
│   ├── backtests/
│   ├── freqtrade/
│   │   ├── resolvers/
│   │   └── runners/
│   ├── models/
│   ├── services/
│   └── utils/
└── ui/
    ├── dialogs/
    ├── pages/
    └── widgets/
```

---

## 3) Meaning of major areas

### `app/app_state/`
Shared state and signals.
Do not overload it with business logic.

### `app/core/freqtrade/`
Freqtrade integration contracts:
- command building
- resolvers
- runners

### `app/core/backtests/`
Results domain:
- parsing
- models
- indexing
- storage helpers

### `app/core/services/`
Product services and orchestration.
This is where most business rules should live.

### `app/core/ai/`
AI placeholder area.
Keep this future-ready, but do not make it a hard dependency for the core app yet.

### `app/ui/pages/`
Top-level workflow tabs.
Must reflect the product flow, not random tools.

### `app/ui/widgets/`
Reusable visual building blocks.
Use these for results, stats, trades, terminal, data status, and future diff/compare widgets.

### `data/docs/`
Canonical product and workflow documents.

### `data/rules/`
Short operational rules for assistants and contributors.

### `data/tools/`
Project-local automation and MCP helper scripts.

### `user_data/`
Runtime/user-owned freqtrade assets:
- strategies
- parameter JSON files
- backtest results
- config
- market data

---

## 4) Files that are product-critical
- `main.py`
- `app/app_state/settings_state.py`
- `app/core/services/backtest_service.py`
- `app/core/services/backtest_results_service.py`
- `app/core/services/process_service.py`
- `app/core/services/run_store.py`
- `app/core/services/strategy_config_service.py`
- `app/ui/pages/backtest_page.py`
- `app/ui/pages/optimize_page.py`
- `app/ui/pages/strategy_config_page.py`
- `app/ui/main_window.py`

These files affect the core user journey and should not be changed casually.

---

## 5) Recommended future additions
عندما تحتاج التوسعة، أضفها بهذا الاتجاه:

### Services
- `logic_analysis_service.py`
- `candidate_version_service.py`
- `compare_service.py`
- `version_history_service.py`
- `acceptance_service.py`
- `rollback_service.py`
- `ai_analysis_service.py` (later)

### UI pages/widgets
- compare widget/page
- versions/history widget/page
- diff viewer widget
- AI chat panel shell

### Docs
- `PRODUCT_FLOW.md`
- `IMPLEMENTATION_PRIORITY.md`

---

## 6) Structure rules
- UI should not build freqtrade commands directly.
- Services should not import UI code.
- AI placeholders should not dictate product architecture yet.
- Runtime files remain in `user_data/`.
- Product rules remain in `data/docs/` and `data/rules/`.
