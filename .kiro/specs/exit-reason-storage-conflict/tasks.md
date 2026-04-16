# Exit Reason Storage Conflict — Tasks

## Tasks

- [x] 1. Fix `_write_trades()` to use `"exit_reason"` key
  - [x] 1.1 In `app/core/backtests/results_store.py`, change `"reason": t.exit_reason` to `"exit_reason": t.exit_reason` in the `_write_trades()` dict literal

- [x] 2. Fix `load_run()` trade construction to use canonical key with backward-compat fallback
  - [x] 2.1 In `load_run()`, change `exit_reason=t.get("reason", "")` to `exit_reason=t.get("exit_reason", t.get("reason", ""))`

- [x] 3. Fix `load_run()` `raw_data` to use normalization pass instead of fake reconstruction
  - [x] 3.1 Replace the fake `raw_data = {"result": {"trades": [{"exit_reason": t.get("reason", "")} for t in t_data]}}` with a normalization loop that copies `"reason"` → `"exit_reason"` on each record if needed, then sets `raw_data = {"result": {"trades": t_data}}`

- [x] 4. Write tests in `tests/core/backtests/test_results_store.py`
  - [x] 4.1 Write unit test: `_write_trades()` output contains `"exit_reason"` key and NOT `"reason"` — validates the C1 write fix (isWriteDefect: record has `"reason"` but NOT `"exit_reason"`)
  - [x] 4.2 Write unit test: `load_run()` on a native freqtrade `trades.json` with `"exit_reason"` key (C2 — isReadDefect) correctly populates `BacktestTrade.exit_reason`; before the fix this silently returned `""`
  - [x] 4.3 Write unit test: `load_run()` on a legacy `trades.json` with `"reason"` key (C1 — isWriteDefect) correctly populates `BacktestTrade.exit_reason` via the backward-compat fallback `t.get("exit_reason", t.get("reason", ""))`
  - [x] 4.4 Write property-based test (Hypothesis): round-trip `RunStore.save()` → `load_run()` preserves `exit_reason` for arbitrary trade lists — **Property 4: Preservation** (inputs match neither C1 nor C2 after fix; all trade fields including `exit_reason` must be identical)
  - [x] 4.5 Write property-based test (Hypothesis): `load_run()` on records with `"exit_reason"` key (C2 — isReadDefect) populates `BacktestTrade.exit_reason` correctly for arbitrary string values — **Property 2: Fix Checking Read Defect**
  - [x] 4.6 Write property-based test (Hypothesis): `load_run()` on legacy records with `"reason"` key (C1 — isWriteDefect) migrates the value to `exit_reason` correctly for arbitrary string values — **Property 3: Fix Checking Write Defect**
