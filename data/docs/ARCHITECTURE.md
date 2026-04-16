# ARCHITECTURE.md — Freqtrade GUI

## طبقات النظام

```
UI Layer
  app/ui/pages/          ← backtest_page, dd_page, settings_page
  app/ui/widgets/        ← terminal_widget, backtest_results_widget, data_status_widget
  app/ui/dialogs/        ← pairs_selector_dialog
  app/ui/main_window.py  ← QMainWindow + QTabWidget
        ↓
State Layer
  app/app_state/settings_state.py  ← QObject + Signals (settings_saved, settings_loaded, ...)
        ↓
Service Layer
  app/core/services/     ← business logic, لا تستورد UI أبداً
        ↓
Model Layer
  app/core/models/       ← Pydantic models
        ↓
Infrastructure
  app/core/freqtrade/    ← command building
  app/core/utils/        ← logger, date helpers
```

---

## Backend (Services)

| Service | مسؤوليته |
|---------|---------|
| `SettingsService` | تحميل/حفظ/تحقق من `~/.freqtrade_gui/settings.json` |
| `BacktestService` | بناء backtest command، قائمة الاستراتيجيات |
| `BacktestResultsService` | parse zip → `BacktestResults` dataclass |
| `DownloadDataService` | بناء download-data command |
| `ProcessService` | QProcess wrapper، streaming stdout/stderr |
| `RunStore` | حفظ run كـ folder منظم (meta/results/trades/params) |
| `IndexStore` | index.json عام لكل الـ runs |
| `StrategyIndexStore` | index.json خاص بكل strategy |

---

## Backtest Flow

```
BacktestPage._run_backtest()
  → BacktestService.build_command()
      → CommandRunner.build_backtest_command()
      → BacktestCommand(program, args, cwd, export_dir)
  → ProcessService.execute_command([cmd.program] + cmd.args)
      → QProcess streams stdout → TerminalWidget
  → on exit 0: _try_load_results()
      → scan backtest_results/*.zip newer than run start
      → BacktestResultsService.parse_backtest_zip()
      → RunStore.save() → backtest_results/{strategy}/run_*/
      → BacktestResultsWidget.display_results()
      → _refresh_run_picker()
```

**ملاحظة مهمة:** freqtrade يتجاهل `--export-filename` ويكتب الـ zip دائماً في `backtest_results/*.zip`. الكود يتعامل مع هذا بـ timestamp filter.

---

## Download Flow

```
DDPage._run_download()
  → DownloadDataService.build_command()
      → CommandRunner.build_download_command()
  → ProcessService.execute_command([cmd.program] + cmd.args)
      → QProcess streams stdout → TerminalWidget
  → on exit 0: DataStatusWidget.refresh()
```

---

## State Management

- `SettingsState` (QObject) يحمل `current_settings: AppSettings`
- يُمرَّر للـ pages عبر constructor — لا تُنشئ الـ pages state بنفسها
- Signals: `settings_saved`, `settings_loaded`, `settings_changed`, `settings_validated`
- `MainWindow` يربط الـ signals بالـ slots في `__init__`

---

## AI Flow (Placeholder)

`app/core/ai/` — فارغ حالياً، مخصص لمستقبل AI-assisted strategy analysis.

---

## Process Execution Rule

**دائماً:** `[cmd.program] + cmd.args` مباشرة إلى `ProcessService.execute_command()`
**ممنوع:** تحويل الـ command لـ string ثم `split()` — يكسر المسارات التي تحتوي spaces
