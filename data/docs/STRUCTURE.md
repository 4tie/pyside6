# STRUCTURE.md — Freqtrade GUI

## خريطة المجلدات

```
pyside6/
├── main.py                          ← entry point فقط، لا logic هنا
├── requirements.txt
├── app/
│   ├── app_state/
│   │   └── settings_state.py        ← QObject + Signals، لا تعدّل بدون سبب
│   ├── core/
│   │   ├── ai/                      ← placeholder، لا تلمس
│   │   ├── freqtrade/
│   │   │   └── command_runner.py    ← BacktestCommand dataclass + CommandRunner
│   │   ├── models/
│   │   │   └── settings_models.py   ← Pydantic: AppSettings + nested prefs
│   │   ├── services/
│   │   │   ├── backtest_service.py
│   │   │   ├── backtest_results_service.py
│   │   │   ├── dd_service.py
│   │   │   ├── process_service.py   ← لا تعدّل execute_command signature
│   │   │   ├── run_store.py         ← RunStore + IndexStore + StrategyIndexStore
│   │   │   └── settings_service.py
│   │   └── utils/
│   │       ├── app_logger.py        ← get_logger() + setup_logging()
│   │       └── date_utils.py
│   └── ui/
│       ├── main_window.py           ← tabs + signal wiring فقط
│       ├── dialogs/
│       │   └── pairs_selector_dialog.py
│       ├── pages/
│       │   ├── settings_page.py
│       │   ├── backtest_page.py     ← أكبر ملف UI، تعديل بحذر
│       │   └── dd_page.py
│       └── widgets/
│           ├── terminal_widget.py
│           ├── backtest_results_widget.py
│           └── data_status_widget.py
├── data/
│   ├── docs/                        ← هذه الملفات
│   ├── rules/                       ← guidelines, product, structure, tech
│   ├── memory/
│   │   └── project_facts.json       ← persistent agent memory
│   ├── tools/                       ← MCP servers
│   └── log/                         ← app.log, ui.log, services.log, process.log
├── tests/
│   ├── core/                        ← unit tests للـ services
│   └── ui/                          ← ui tests (فارغ حالياً)
└── user_data/
    ├── strategies/                  ← .py + .json parameter files
    ├── backtest_results/
    │   ├── *.zip                    ← freqtrade يكتب هنا مباشرة
    │   ├── index.json               ← IndexStore
    │   └── {strategy}/
    │       ├── index.json           ← StrategyIndexStore
    │       └── run_*/               ← meta/results/trades/params
    ├── data/binance/                ← OHLCV data
    └── config.json
```

---

## الملفات التي لا يُعبث بها عشوائياً

| الملف | السبب |
|-------|-------|
| `app/app_state/settings_state.py` | تغيير الـ signals يكسر كل الـ pages |
| `app/core/models/settings_models.py` | تغيير الـ fields يكسر الـ JSON المحفوظ |
| `app/core/services/process_service.py` | `execute_command` signature ثابت |
| `app/core/services/run_store.py` | تغيير structure الـ JSON يكسر الـ index القديم |
| `user_data/strategies/*.json` | format محدد من freqtrade source |

---

## أين يُضاف الجديد

| ما تريد إضافته | أين |
|---------------|-----|
| command جديد لـ freqtrade | `command_runner.py` method جديدة |
| service جديد | `app/core/services/` ملف جديد |
| صفحة UI جديدة | `app/ui/pages/` + تسجيل في `main_window.py` |
| widget جديد | `app/ui/widgets/` |
| setting جديد | `settings_models.py` field + `settings_page.py` UI |
| MCP tool جديد | `data/tools/mcp_*.py` |
| doc جديد | `data/docs/` |
