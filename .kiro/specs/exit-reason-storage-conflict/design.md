# Exit Reason Storage Conflict Bugfix Design

## Overview

`_write_trades()` in `results_store.py` serializes `BacktestTrade.exit_reason` under the key
`"reason"`, while freqtrade's canonical key is `"exit_reason"`. The internal round-trip
(`_write_trades` → `load_run`) works by accident because both sides use `"reason"`, but any
`trades.json` produced by freqtrade natively — or by any code expecting the standard key —
yields an empty `exit_reason` when loaded through `load_run()`. A secondary symptom is a
fake `raw_data` reconstruction in `load_run()` that exists solely to paper over the mismatch.

The fix is three targeted changes to `results_store.py` only:
1. Write `"exit_reason"` in `_write_trades()`.
2. Read with backward-compat fallback in `load_run()` trade construction.
3. Replace the fake `raw_data` reconstruction with a simple normalization pass.

## Glossary

- **isWriteDefect (C1)**: A `trades.json` record that contains `"reason"` but NOT `"exit_reason"` — the signature of a file written by the buggy `_write_trades()`. Proves the write-side diverges from the freqtrade standard.
- **isReadDefect (C2)**: A `trades.json` record that contains `"exit_reason"` but NOT `"reason"` — a freqtrade-native file that the old `load_run()` silently misreads. Proves the read-side fails on any standard freqtrade output.
- **Property (P)**: After the fix, `load_run()` SHALL populate `BacktestTrade.exit_reason` correctly for every trade record regardless of which key was used to store it.
- **Preservation**: All other fields of `BacktestTrade` and `BacktestResults` (pair, profit, duration, raw_data structure, etc.) must be identical before and after the fix for any run that matches neither defect condition.
- **`_write_trades()`**: Private function in `app/core/backtests/results_store.py` that serializes `BacktestResults.trades` to `trades.json`.
- **`load_run()`**: Static method on `RunStore` in `app/core/backtests/results_store.py` that reconstructs `BacktestResults` from a saved run folder.
- **legacy run**: A run folder whose `trades.json` was written by the buggy code and therefore uses `"reason"` as the key (matches `isWriteDefect`).
- **native freqtrade trades.json**: A file produced directly by freqtrade that uses `"exit_reason"` as the key (matches `isReadDefect`).

## Bug Details

### Bug Condition

Two distinct defect conditions exist, each exposing a different failure mode:

**C1 — isWriteDefect**: The record was written by the buggy `_write_trades()` and uses `"reason"` instead of `"exit_reason"`. The internal round-trip silently works but diverges from the freqtrade standard.

**C2 — isReadDefect**: The record is a freqtrade-native file using the canonical `"exit_reason"` key, but the old `load_run()` looks up `"reason"` and silently returns `""`.

**Formal Specification:**
```
FUNCTION isWriteDefect(trade_record)
  INPUT: trade_record — a dict entry from trades.json
  OUTPUT: boolean
  RETURN "reason" IN trade_record.keys() AND "exit_reason" NOT IN trade_record.keys()
END FUNCTION

FUNCTION isReadDefect(trade_record)
  INPUT: trade_record — a dict entry from trades.json
  OUTPUT: boolean
  RETURN "exit_reason" IN trade_record.keys() AND "reason" NOT IN trade_record.keys()
END FUNCTION
```

### Examples

- **Legacy run (written by buggy code)**: `{"pair": "BTC/USDT", "reason": "roi", ...}` — `load_run()` returns `exit_reason="roi"` by accident (reads `"reason"`), but `raw_data` reconstruction is a fake workaround.
- **Native freqtrade trades.json**: `{"pair": "BTC/USDT", "exit_reason": "roi", ...}` — `load_run()` returns `exit_reason=""` because it looks up `t.get("reason", "")` and finds nothing.
- **New run after fix**: `{"pair": "BTC/USDT", "exit_reason": "roi", ...}` — `load_run()` returns `exit_reason="roi"` correctly via `t.get("exit_reason", t.get("reason", ""))`.
- **Trade with no exit reason**: `{"pair": "BTC/USDT", "exit_reason": "", ...}` — `load_run()` returns `exit_reason=""` (default preserved).

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- All other `BacktestTrade` fields (pair, stake_amount, open_date, close_date, open_rate, close_rate, profit, profit_abs, duration, is_open) must be identical after the fix.
- `RunStore.save()` followed by `load_run()` must continue to produce a `BacktestResults` with all fields intact.
- `results_parser.py` behavior is completely unaffected — it already uses `"exit_reason"` and is not touched.
- `BacktestTradesWidget` display of `exit_reason` must continue to work for runs loaded from both the parser and the store.
- Trades with no exit reason must continue to default `exit_reason` to `""`.

**Scope:**
All inputs that do NOT involve the `"reason"` / `"exit_reason"` key are completely unaffected.
This includes:
- All other fields in `trades.json` records.
- `results.json`, `meta.json`, `params.json`, `config.snapshot.json` — none of these change.
- `results_models.py`, `results_parser.py`, `results_index.py`, all UI widgets.

## Hypothesized Root Cause

1. **Wrong key in `_write_trades()`**: The dict literal uses `"reason": t.exit_reason` instead of `"exit_reason": t.exit_reason`. This is the primary defect — it causes every saved `trades.json` to diverge from the freqtrade standard.

2. **Matching wrong key in `load_run()` trade construction**: `t.get("reason", "")` was written to match the buggy writer. It silently works for legacy runs but fails for any file using the canonical key.

3. **Fake `raw_data` reconstruction**: `raw_data = {"result": {"trades": [{"exit_reason": t.get("reason", "")} for t in t_data]}}` is a workaround that re-maps `"reason"` → `"exit_reason"` in memory. It should be replaced by a normalization pass over the actual `t_data` list so `raw_data` reflects the real on-disk structure (normalized).

## Correctness Properties

Property 1: Bug Condition - Write Uses Canonical Key

_For any_ `BacktestTrade` serialized by the fixed `_write_trades()`, the output dict SHALL
contain the key `"exit_reason"` with the trade's exit reason value, and SHALL NOT contain
the key `"reason"`.

**Validates: Requirements 2.1**

Property 2: Bug Condition - Load Reads Canonical Key

_For any_ `trades.json` record where `isBugCondition` returns false (i.e., the record uses
`"exit_reason"`), the fixed `load_run()` SHALL populate `BacktestTrade.exit_reason` with
the stored value rather than returning an empty string.

**Validates: Requirements 2.2**

Property 3: Bug Condition - Backward Compat for Legacy Runs

_For any_ `trades.json` record where `isBugCondition` returns true (i.e., the record uses
`"reason"` but not `"exit_reason"`), the fixed `load_run()` SHALL populate
`BacktestTrade.exit_reason` from the `"reason"` value, preserving data from runs saved
before this fix.

**Validates: Requirements 2.4**

Property 4: Preservation - Round-Trip Integrity

_For any_ `BacktestResults` saved via `RunStore.save()` and reloaded via `load_run()`, the
fixed code SHALL produce a `BacktestResults` where every `BacktestTrade` field is identical
to the original, including `exit_reason`.

**Validates: Requirements 3.1**

## Fix Implementation

### Changes Required

**File**: `app/core/backtests/results_store.py`

**Change 1 — `_write_trades()`: use canonical key**

```python
# Before
"reason": t.exit_reason,

# After
"exit_reason": t.exit_reason,
```

**Change 2 — `load_run()` trade construction: backward-compat fallback**

```python
# Before
exit_reason=t.get("reason", ""),

# After
exit_reason=t.get("exit_reason", t.get("reason", "")),
```

**Change 3 — `load_run()` raw_data: normalization pass instead of fake reconstruction**

```python
# Before
raw_data = {"result": {"trades": [{"exit_reason": t.get("reason", "")} for t in t_data]}}

# After
for record in t_data:
    if "exit_reason" not in record and "reason" in record:
        record["exit_reason"] = record["reason"]
raw_data = {"result": {"trades": t_data}}
```

No other files require changes.

## Testing Strategy

### Validation Approach

Two-phase approach: first surface counterexamples on unfixed code to confirm the root cause,
then verify the fix works and preserves all existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Demonstrate the bug on unfixed code before implementing the fix. Confirm or refute
the root cause analysis.

**Test Plan**: Write tests that call `_write_trades()` and inspect the output JSON, and tests
that call `load_run()` with a native freqtrade `trades.json` (using `"exit_reason"`) and assert
the field is populated. Run on UNFIXED code to observe failures.

**Test Cases**:
1. **Write key test**: Call `_write_trades()` with a trade that has `exit_reason="roi"`, read back the JSON, assert `"exit_reason"` key is present (will fail on unfixed code — key is `"reason"`).
2. **Load native freqtrade file**: Construct a `trades.json` with `"exit_reason": "stop_loss"`, call `load_run()`, assert `trade.exit_reason == "stop_loss"` (will fail on unfixed code — returns `""`).
3. **raw_data structure test**: Call `load_run()` on a saved run, assert `raw_data["result"]["trades"]` contains the full trade records, not a stripped single-field list (will fail on unfixed code).

**Expected Counterexamples**:
- `_write_trades()` output contains `"reason"` key instead of `"exit_reason"`.
- `load_run()` returns `exit_reason=""` for native freqtrade files.
- `raw_data` contains only `{"exit_reason": ...}` per trade instead of full records.

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed functions produce
the expected behavior.

**Pseudocode:**
```
// Fix Checking — Write Defect (C1)
FOR ALL trade_record WHERE isWriteDefect(trade_record) DO
  result := load_run_fixed(run_dir_containing(trade_record))
  ASSERT result.trades[i].exit_reason = trade_record["reason"]   // backward compat migration
END FOR

FOR ALL trade IN BacktestResults DO
  written := _write_trades_fixed(trade)
  ASSERT "exit_reason" IN written.keys()
  ASSERT "reason" NOT IN written.keys()
END FOR

// Fix Checking — Read Defect (C2)
FOR ALL trade_record WHERE isReadDefect(trade_record) DO
  result := load_run_fixed(run_dir_containing(trade_record))
  ASSERT result.trades[i].exit_reason = trade_record["exit_reason"]   // no longer silently ""
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed functions
produce the same result as the original.

**Pseudocode:**
```
FOR ALL trade_record WHERE NOT isWriteDefect(trade_record) AND NOT isReadDefect(trade_record) DO
  ASSERT load_run_original(run_dir) fields == load_run_fixed(run_dir) fields
         (excluding exit_reason which is now correctly populated)
END FOR
```

**Testing Approach**: Property-based testing with Hypothesis is recommended for preservation
checking because it generates many trade configurations automatically and catches edge cases
that manual unit tests miss.

**Test Cases**:
1. **Round-trip preservation**: Save a `BacktestResults` via `RunStore.save()`, reload via `load_run()`, assert all trade fields match — including `exit_reason`.
2. **Other fields unaffected**: Verify pair, profit, duration, stake_amount, is_open are identical after the fix.
3. **Empty exit_reason default**: Verify trades with no exit reason still default to `""`.

### Unit Tests

- Test `_write_trades()` output JSON contains `"exit_reason"` key, not `"reason"`.
- Test `load_run()` with a native freqtrade `trades.json` (key `"exit_reason"`) correctly populates `BacktestTrade.exit_reason`.
- Test `load_run()` with a legacy `trades.json` (key `"reason"`) correctly populates `BacktestTrade.exit_reason` via fallback.
- Test `load_run()` `raw_data` contains full trade records with `"exit_reason"` present.
- Test edge case: trade with empty exit reason defaults to `""`.

### Property-Based Tests

- Generate random `BacktestTrade` lists, save via `RunStore.save()`, reload via `load_run()`, assert `exit_reason` round-trips correctly for all trades (Hypothesis `@given`).
- Generate random trade dicts with `"exit_reason"` key, assert `load_run()` populates the field correctly across many values.
- Generate random trade dicts with `"reason"` key (legacy), assert `load_run()` migrates the value to `exit_reason` correctly.

### Integration Tests

- Full save → load cycle via `RunStore.save()` + `load_run()` with multiple trades having varied exit reasons.
- Load a simulated native freqtrade `trades.json` (with `"exit_reason"`) through `load_run()` and verify all trades are populated.
- Verify `raw_data["result"]["trades"]` structure is consistent with what `results_parser.py` would produce.
