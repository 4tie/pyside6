# Bugfix Requirements Document

## Introduction

`results_store.py` uses the key `"reason"` when writing trade records to `trades.json`, but freqtrade's native output and `results_parser.py` both use `"exit_reason"`. The write/read cycle within our own storage is internally consistent (`"reason"` → `"reason"`), but it diverges from the canonical freqtrade key. This means any `trades.json` produced by freqtrade directly (or any code expecting the standard key) will yield an empty `exit_reason` when loaded through `load_run()`. Additionally, `load_run()` contains an unnecessary `raw_data` reconstruction workaround that exists solely to paper over this inconsistency.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN `_write_trades()` serializes a `BacktestTrade` to `trades.json` THEN the system writes the field under the key `"reason"` instead of `"exit_reason"`

1.2 WHEN `load_run()` reads a `trades.json` that uses the freqtrade-native key `"exit_reason"` THEN the system returns an empty string for `exit_reason` on every trade because it looks up `t.get("reason", "")`

1.3 WHEN `load_run()` reconstructs `raw_data` THEN the system builds a fake `{"result": {"trades": [{"exit_reason": t.get("reason", "")} ...]}}` structure as a workaround for the key mismatch

### Expected Behavior (Correct)

2.1 WHEN `_write_trades()` serializes a `BacktestTrade` to `trades.json` THEN the system SHALL write the field under the key `"exit_reason"`

2.2 WHEN `load_run()` reads a `trades.json` that uses the key `"exit_reason"` THEN the system SHALL correctly populate `BacktestTrade.exit_reason` with the stored value

2.3 WHEN `load_run()` builds `raw_data` THEN the system SHALL normalize each trade record so that `"exit_reason"` is always present — if a record has `"reason"` but not `"exit_reason"`, copy the value across — and SHALL NOT build a separate fake trade-list reconstruction just for this field

2.4 WHEN `load_run()` reads a legacy `trades.json` entry that contains the key `"reason"` but NOT `"exit_reason"` THEN the system SHALL populate `BacktestTrade.exit_reason` from the `"reason"` value, so that runs saved before this fix remain readable without data loss. The implementation SHALL use: `t.get("exit_reason", t.get("reason", ""))`

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a backtest run is saved via `RunStore.save()` and then loaded via `load_run()` THEN the system SHALL CONTINUE TO return a `BacktestResults` with all trade fields (pair, profit, duration, etc.) intact and matching the original

3.2 WHEN `results_parser.py` parses a freqtrade zip or result JSON THEN the system SHALL CONTINUE TO populate `BacktestTrade.exit_reason` correctly using the `"exit_reason"` key from freqtrade's output

3.3 WHEN `BacktestTradesWidget` displays trades THEN the system SHALL CONTINUE TO render the `exit_reason` column correctly for runs loaded from both the parser and the store

3.4 WHEN a trade has no exit reason THEN the system SHALL CONTINUE TO default `exit_reason` to an empty string `""`

---

## Bug Condition (Pseudocode)

```pascal
FUNCTION isBugCondition(trade_record)
  INPUT: trade_record — a dict entry from trades.json
  OUTPUT: boolean

  // Bug is triggered when the record was written by _write_trades()
  // and therefore uses "reason" instead of "exit_reason"
  RETURN "reason" IN trade_record.keys() AND "exit_reason" NOT IN trade_record.keys()
END FUNCTION
```

```pascal
// Property: Fix Checking
FOR ALL trade_record WHERE isBugCondition(trade_record) DO
  result ← load_run'(run_dir_containing(trade_record))
  // Backward compat: "reason" value is migrated to exit_reason
  ASSERT result.trades[i].exit_reason = trade_record["reason"]
  // New writes use canonical key
  ASSERT "exit_reason" IN written_trade_record.keys()
  ASSERT "reason" NOT IN written_trade_record.keys()
END FOR

// Property: Preservation Checking
FOR ALL trade_record WHERE NOT isBugCondition(trade_record) DO
  ASSERT load_run(run_dir) = load_run'(run_dir)   // all other fields unchanged
END FOR
```
