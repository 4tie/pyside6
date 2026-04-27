# App Event Analysis Report
Generated: 2026-04-27

---

## 1. Log Files Analyzed

| File | Lines | Coverage |
|------|-------|----------|
| `data/log/app.log` | 936 | Current session (2026-04-27) |
| `data/log/services.log` | 15,736 | Sessions from 2026-04-26 |
| `data/log/process.log` | 6,153 | Sessions from 2026-04-16 (Windows) |
| `data/log/ui.log` | 6,704 | Sessions from 2026-04-16 to 2026-04-27 |
| `data/log/web.log` | — | Present, not analyzed (empty/minimal) |

---

## 2. Normal App Lifecycle Events

### Startup
- App initialises `MainWindow` and `AIChatDock` on every launch — consistent and clean.
- Settings are loaded from `data/settings.json` on startup and saved repeatedly during UI interactions (settings_state is persisted on every change).
- Strategy discovery (`freqtrade.discovery`) runs on page navigation and on settings changes — fires multiple times per session, which is expected.

### Backtest Runs
- Backtests are launched via `process_run_manager` as subprocess calls to `freqtrade backtesting`.
- Each run gets a UUID (e.g. `ba19f093`, `adbb5ba1`, `c80f7f3c`).
- Runs complete with `exit_code=0` and `status=finished` in all observed cases.
- Results are parsed, saved to `user_data/backtest_results/{strategy}/`, and indexed.
- Example successful run (2026-04-27): strategy `yesv3`, 104 trades, profit +21.78%, saved as `run_2026-04-27_11-15-25_e646bb`.

### Post-Backtest Analysis
- `pair_analysis` fires after every backtest — analyses distinct pairs, flags best/worst.
- `diagnosis` service fires after every backtest — `0 rules fired` in all observed runs (no diagnosis rules triggered).
- Backtest results are stored and indexed correctly every time.

### Hyperopt Runs (process.log — Windows session 2026-04-16)
- Multiple hyperopt runs launched for strategy `MultiMeee` with various loss functions (`SharpeHyperOptLoss`, `MultiMetricHyperOptLoss`).
- Runs appear to complete normally based on stdout/stderr chunk flow.

### Improve / Loop Page
- Strategy improvement suggestions applied: `minimal_roi` and `stoploss` values updated multiple times.
- Candidates accepted and rolled back correctly (`Candidate accepted`, `Rolled back to previous baseline`).
- Stale sandbox directories cleaned up on startup (13 sandboxes cleaned on 2026-04-19).

---

## 3. Warnings Found

### W1 — Ollama not running (ui.log, 2026-04-16 19:09:53)
```
WARNING | freqtrade_gui.ui.ai_chat_dock | Failed to list models:
HTTPConnectionPool(host='localhost', port=11434): Max retries exceeded
```
- **Cause:** Ollama local AI server was not running when the app started.
- **Impact:** AI chat dock showed 0 models. Resolved automatically in the next session when Ollama was running.
- **Status:** One-off, not recurring. No action needed.

### W2 — AIChatDock constructor signature mismatch (ui.log, 2026-04-24)
```
WARNING | freqtrade_gui.ui.ai_panel | Failed to instantiate AIChatDock:
AIChatDock.__init__() missing 1 required positional argument: 'settings_state'
```
- **Cause:** `AIChatDock` was called without the required `settings_state` argument from `ai_panel`. This happened across 4 consecutive app launches on 2026-04-24 (09:10, 09:23, 09:34, 09:37).
- **Impact:** AI panel failed to load in those sessions. The issue resolved itself in later sessions, suggesting a code change fixed it.
- **Status:** Appears fixed in sessions after 2026-04-24. Worth verifying `ai_panel` always passes `settings_state`.

### W3 — Unknown page_id (ui.log, 2026-04-24 09:37:54)
```
WARNING | freqtrade_gui.ui.main_window | Unknown page_id: 'strategy_lab'
```
- **Cause:** Navigation attempted to a page `strategy_lab` that is not registered in the main window's page map.
- **Impact:** Navigation silently failed — user would see no page change.
- **Status:** Likely a stale reference to a renamed or removed page. Should be cleaned up.

### W4 — Freqtrade `force_exit` config warning (services.log / app.log — recurring)
```
WARNING - freqtrade.configuration.configuration - `force_exit` ...
```
- **Cause:** Freqtrade subprocess emits this on every run — it's a deprecation notice from freqtrade itself about a config key.
- **Impact:** None on the GUI app. Purely informational from the subprocess.
- **Status:** Cosmetic. Can be resolved by updating the freqtrade config to use the new key name.

### W5 — IPairList pair warning (app.log, 2026-04-27 11:19:23)
```
WARNING - freqtrade.plugins.pairlist.IPairList - Pair ...
```
- **Cause:** Freqtrade subprocess warning about a pair in the pairlist configuration.
- **Impact:** None on the GUI. Freqtrade still ran successfully.
- **Status:** Cosmetic subprocess warning.

---

## 4. Errors Found

### E1 — Baseline sandbox: strategy file not found (ui.log, 2026-04-21 06:15–06:16)
```
ERROR | freqtrade_gui.ui.loop_page | Failed to prepare sandbox for baseline:
Strategy file not found: T:\ae\pyside6\user_data\strategies\venv_path=...
```
- **Cause:** The strategy file path was being constructed incorrectly — the `Settings` object's string representation was being concatenated into the path instead of the actual strategy filename. This happened 3 times in quick succession.
- **Impact:** Loop/improve page could not start baseline backtests. User had to retry.
- **Status:** Appears to be a bug where a `Settings` object was passed as a string to the path builder. Resolved in later sessions — no recurrence after 2026-04-21.

### E2 — Baseline backtest exit code 62097 (ui.log, 2026-04-21 14:39:16)
```
ERROR | freqtrade_gui.ui.loop_page | Baseline backtest failed with exit code: 62097
```
- **Cause:** Exit code 62097 is unusual — likely a Windows process termination signal or the process was killed externally. The command used `--strategy-path` twice in the same command, which may have caused freqtrade to reject it.
- **Impact:** Baseline backtest failed. Loop page could not proceed.
- **Status:** One-off. The duplicate `--strategy-path` flag in the command is suspicious and may be a bug in the command builder.

### E3 — Baseline backtest exit code 2 (ui.log, 2026-04-22 06:21:25 and 06:21:50)
```
ERROR | freqtrade_gui.ui.loop_page | Baseline backtest failed with exit code: 2
```
- **Cause:** Exit code 2 from freqtrade typically means a configuration or argument error. Strategy `MultiMa_v3` was being tested. The sandbox path may not have existed yet.
- **Impact:** Baseline backtest failed twice in a row for `MultiMa_v3`.
- **Status:** Resolved in subsequent sessions. Likely a transient path/config issue.

---

## 5. Unusual Patterns

### P1 — Settings saved excessively (app.log, 2026-04-27 11:15:28–11:16:27)
- `Settings saved` fires 10+ times within a 2-second window during UI interactions.
- Each save is triggered by individual UI widget changes rather than batching.
- **Impact:** No data loss, but unnecessary I/O. Could cause minor slowdowns on slower disks.
- **Recommendation:** Debounce settings saves (e.g. 300ms delay after last change).

### P2 — Strategy discovery called redundantly (app.log, 2026-04-27)
- `Listing strategies from: .../user_data` fires 3–4 times per navigation event.
- **Impact:** Minor — each call is fast, but it's redundant work.
- **Recommendation:** Cache strategy list and invalidate only on file system changes.

### P3 — Pair analysis runs on every UI refresh (app.log, 2026-04-27)
- `pair_analysis` and `diagnosis` fire on every settings load cycle, not just after new backtests.
- **Impact:** Redundant computation. `diagnosis: 0 rules fired` every time.
- **Recommendation:** Only re-run analysis when backtest results actually change.

### P4 — Cross-platform path artifacts (process.log)
- `process.log` contains Windows paths (`T:\ae\pyside6\...`) from earlier sessions, while current logs use Linux paths (`/home/mohs/Desktop/ae/pyside6/...`).
- **Impact:** None — historical only. The app migrated from Windows to Linux.
- **Status:** Informational.

---

## 6. Summary

| Category | Count | Severity |
|----------|-------|----------|
| Errors (app-level) | 3 distinct error types | Medium |
| Warnings (app-level) | 3 distinct warning types | Low–Medium |
| Subprocess warnings | 2 types (freqtrade config) | Low |
| Unusual patterns | 4 | Low |

**No CRITICAL errors or crashes were found.** All backtest runs in the current session (2026-04-27) completed successfully with `exit_code=0`.

The most actionable issues are:
1. **W2** — `AIChatDock` missing `settings_state` arg (verify fix is stable)
2. **W3** — Unknown page `strategy_lab` (remove stale reference)
3. **E1/E2** — Loop page sandbox/command builder bugs (verify fixed)
4. **P1** — Debounce settings saves to reduce I/O churn
