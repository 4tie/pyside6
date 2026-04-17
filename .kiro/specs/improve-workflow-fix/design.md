# Improve Workflow Fix — Bugfix Design

## Overview

The Improve tab's candidate backtest pipeline fails because three methods in `ImproveService`
(`prepare_sandbox`, `accept_candidate`, `rollback`) write the flat `params.json` format directly
as the strategy JSON file. Freqtrade expects a nested format with a `strategy_name` key, a
`params` sub-object with renamed keys, and metadata fields (`ft_stratparam_v`, `export_time`).

The fix introduces a single private helper `_build_freqtrade_params_file` that reads the live
strategy JSON as a base (preserving fields like `trailing` that are not tracked in `params.json`),
merges the flat candidate config into the nested structure using a defined key mapping, and
updates `export_time`. All three write methods are updated to call this helper instead of
serialising the flat dict directly.

Five secondary gaps are also addressed: error message specificity on backtest failure, sandbox
cleanup after accept, `load_baseline_params` fallback to the live strategy JSON, and two missing
diagnosis/suggestion rules for `profit_factor_low` and `expectancy_negative`.

## Glossary

- **Bug_Condition (C)**: A strategy parameter file written by `ImproveService` is in the flat
  `params.json` format rather than the freqtrade nested format, causing freqtrade to reject it
  with `ERROR - Invalid parameter file provided.`
- **Property (P)**: The desired behavior — every file written by `ImproveService` to
  `{strategy_name}.json` is in the freqtrade nested format and is accepted by freqtrade without
  error.
- **Preservation**: All existing behaviors that must remain unchanged — sandbox creation,
  atomic write pattern, `params.json` loading when the file exists, existing diagnosis rules,
  existing suggestion handlers, existing `IssueBadge` colors, and the success path of the
  candidate backtest.
- **`_build_freqtrade_params_file`**: New private helper in `ImproveService`
  (`app/core/services/improve_service.py`) that converts a flat params dict to the freqtrade
  nested strategy JSON format.
- **flat params**: The dict stored in `params.json` with keys `buy_params`, `sell_params`,
  `minimal_roi`, `stoploss` (scalar), `max_open_trades` (scalar).
- **nested format**: The freqtrade strategy JSON format with top-level keys `strategy_name`,
  `params`, `ft_stratparam_v`, `export_time`, where `params` contains `buy`, `sell`, `roi`,
  `stoploss` (dict), `max_open_trades` (dict), `trailing`.
- **`profit_factor`**: Ratio of gross profit to gross loss over the backtest period; values
  below 1.0 indicate losses exceed gains.
- **`expectancy`**: Average profit/loss per trade; negative values indicate the average trade
  loses money.

## Bug Details

### Bug Condition

The bug manifests when any of `prepare_sandbox`, `accept_candidate`, or `rollback` writes a
strategy parameter file. Each method calls `json.dumps(candidate_config, indent=2)` directly on
the flat dict, producing a file that freqtrade rejects.

**Formal Specification:**
```
FUNCTION isBugCondition(written_file_content)
  INPUT: written_file_content — dict parsed from the written JSON file
  OUTPUT: boolean

  RETURN "strategy_name" NOT IN written_file_content
         OR "params" NOT IN written_file_content
         OR "ft_stratparam_v" NOT IN written_file_content
         -- i.e. the file is in flat format, not freqtrade nested format
END FUNCTION
```

### Examples

- **`prepare_sandbox` writes flat format**: `{"stoploss": -0.245, "minimal_roi": {"0": 0.109},
  "buy_params": {"buy_ma_count": 16}, "sell_params": {"sell_ma_count": 2}}` → freqtrade rejects
  with `ERROR - Invalid parameter file provided.`
- **`accept_candidate` writes flat format**: Same flat dict written to
  `{strategies_dir}/MultiMeee.json` → corrupts the live strategy parameter file; future
  freqtrade runs also fail.
- **`rollback` writes flat format**: Baseline params written in flat format → same corruption.
- **Edge case — `load_baseline_params` with missing `params.json`**: Returns `{}` instead of
  falling back to the live strategy JSON, so the candidate config starts empty.

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- `prepare_sandbox` must continue to create a timestamped sandbox directory under
  `{user_data_path}/strategies/_improve_sandbox/`, copy the strategy `.py` file into it, and
  return the sandbox path.
- `accept_candidate` and `rollback` must continue to use the atomic `.tmp` → `os.replace()`
  write pattern.
- `load_baseline_params` must continue to return the parsed dict from `params.json` when the
  file exists and is valid, without consulting the live strategy JSON.
- All existing `ResultsDiagnosisService` rules (`stoploss_too_wide`, `trades_too_low`,
  `weak_win_rate`, `drawdown_high`, `poor_pair_concentration`, `negative_profit`) must continue
  to fire unchanged.
- All existing `RuleSuggestionService` handlers must continue to return the same suggestions.
- All existing `IssueBadge` severity colors and icons must remain unchanged.
- The success path of `_on_candidate_finished` (exit code 0) must remain unchanged.

**Scope:**
All inputs that do NOT involve writing a strategy parameter file, or that use `params.json`
when it exists, should be completely unaffected by this fix. This includes:
- Reading `params.json` when it is present and valid
- Mouse-driven UI interactions (accept, reject, rollback buttons)
- Existing diagnosis and suggestion logic for all current issue types
- The comparison view and delta cards

## Hypothesized Root Cause

Based on the bug description and code inspection, the causes are:

1. **Direct serialisation of flat dict**: `prepare_sandbox`, `accept_candidate`, and `rollback`
   all call `json.dumps(candidate_config, indent=2)` directly. `candidate_config` is loaded from
   `params.json` (flat format) and passed through unchanged — no conversion step exists.

2. **No format conversion helper**: There is no utility that maps flat keys (`buy_params`,
   `sell_params`, `minimal_roi`, `stoploss`, `max_open_trades`) to the nested freqtrade keys
   (`buy`, `sell`, `roi`, `params["stoploss"]["stoploss"]`, `params["max_open_trades"]["max_open_trades"]`).

3. **`load_baseline_params` has no fallback**: When `params.json` is absent (e.g. first run
   after a fresh install, or a run saved before `params.json` was introduced), the method
   returns `{}` without attempting to read the live strategy JSON, leaving the candidate config
   empty.

4. **Generic error message on failure**: `_on_candidate_finished` uses a static status message
   on non-zero exit; the terminal output (accessible via `self._terminal.get_output()`) is not
   scanned for known freqtrade error phrases.

5. **Sandbox not cleaned up on accept**: `_on_accept` calls `accept_candidate` but never calls
   `reject_candidate` to remove the sandbox directory, accumulating stale directories.

6. **Missing diagnosis rules**: `ResultsDiagnosisService` has no rules for `profit_factor < 1.0`
   or `expectancy < 0.0`, so these conditions are silently ignored.

7. **Missing suggestion handlers**: `RuleSuggestionService` has no entries for
   `profit_factor_low` or `expectancy_negative`, causing a warning log and no suggestion.

## Correctness Properties

Property 1: Bug Condition — Freqtrade Format Round-Trip

_For any_ flat `BaselineParams` dict passed to `_build_freqtrade_params_file(strategy_name,
flat_params)`, the returned dict SHALL satisfy:
- `result["strategy_name"] == strategy_name`
- `result["ft_stratparam_v"] == 1`
- `result["params"]["stoploss"]["stoploss"] == flat_params["stoploss"]` when `stoploss` is
  present and not `None`
- `result["params"]["roi"] == flat_params["minimal_roi"]` when `minimal_roi` is present and
  non-empty
- `result["params"]["max_open_trades"]["max_open_trades"] == flat_params["max_open_trades"]`
  when `max_open_trades` is present and not `None`
- `result["params"]["buy"] == flat_params["buy_params"]` when `buy_params` is present and
  non-empty
- `result["params"]["sell"] == flat_params["sell_params"]` when `sell_params` is present and
  non-empty

**Validates: Requirements 2.1, 2.2, 2.3**

Property 2: Preservation — Live JSON Fields Preserved

_For any_ live strategy JSON containing a `trailing` block, calling
`_build_freqtrade_params_file(strategy_name, flat_params)` SHALL preserve the `trailing` block
in `result["params"]["trailing"]` unchanged (same keys and values as in the live JSON).

**Validates: Requirements 2.1, 2.2, 2.3, 3.1, 3.2, 3.3**

Property 3: Preservation — `load_baseline_params` Fallback Consistency

_For any_ strategy where `params.json` is absent but the live strategy JSON exists, calling
`load_baseline_params(run_dir, strategy_name)` and then
`_build_freqtrade_params_file(strategy_name, result)` SHALL produce a dict structurally
equivalent to the original live strategy JSON — same nested keys and same values for all mapped
fields (`stoploss`, `max_open_trades`, `roi`, `buy`, `sell`).

**Validates: Requirements 2.6, 3.4**

Property 4: Bug Condition — New Diagnosis Rules Are Correct

_For any_ `BacktestSummary`, `diagnose()` SHALL include a `profit_factor_low` issue if and only
if `0 < summary.profit_factor < 1.0`, and SHALL include an `expectancy_negative` issue if and
only if `summary.expectancy < 0.0`.

**Validates: Requirements 2.7, 2.8, 3.5**

Property 5: Preservation — New Suggestions Are Advisory-Only

_For any_ `profit_factor_low` or `expectancy_negative` issue, `suggest()` SHALL return a
`ParameterSuggestion` with `is_advisory=True` and `proposed_value=None`.

**Validates: Requirements 2.9, 2.10**

## Fix Implementation

### Changes Required

#### File: `app/core/services/improve_service.py`

**Add import**: `from datetime import datetime, timezone`

**New private helper — `_build_freqtrade_params_file`**:

```
FUNCTION _build_freqtrade_params_file(self, strategy_name, flat_params)
  INPUT: strategy_name: str, flat_params: dict
  OUTPUT: dict in freqtrade nested format

  live_json_path = {user_data_path}/strategies/{strategy_name}.json

  IF live_json_path.exists():
    TRY: base = parse JSON from live_json_path
    EXCEPT JSONDecodeError: base = {"strategy_name": strategy_name, "params": {}, "ft_stratparam_v": 1}
  ELSE:
    base = {"strategy_name": strategy_name, "params": {}, "ft_stratparam_v": 1}

  ft_params = copy of base.get("params", {})

  IF "stoploss" in flat_params AND flat_params["stoploss"] is not None:
    ft_params["stoploss"] = {"stoploss": flat_params["stoploss"]}
  IF "max_open_trades" in flat_params AND flat_params["max_open_trades"] is not None:
    ft_params["max_open_trades"] = {"max_open_trades": flat_params["max_open_trades"]}
  IF "minimal_roi" in flat_params AND flat_params["minimal_roi"]:
    ft_params["roi"] = flat_params["minimal_roi"]
  IF "buy_params" in flat_params AND flat_params["buy_params"]:
    ft_params["buy"] = flat_params["buy_params"]
  IF "sell_params" in flat_params AND flat_params["sell_params"]:
    ft_params["sell"] = flat_params["sell_params"]

  base["params"] = ft_params
  base["strategy_name"] = strategy_name
  base["ft_stratparam_v"] = 1
  base["export_time"] = datetime.now(timezone.utc).isoformat()

  RETURN base
END FUNCTION
```

**Update `prepare_sandbox`**: Replace `json.dumps(candidate_config, indent=2)` with
`json.dumps(self._build_freqtrade_params_file(strategy_name, candidate_config), indent=2)`.

**Update `accept_candidate`**: Replace `json.dumps(candidate_config, indent=2)` with
`json.dumps(self._build_freqtrade_params_file(strategy_name, candidate_config), indent=2)`.

**Update `rollback`**: Replace `json.dumps(baseline_params, indent=2)` with
`json.dumps(self._build_freqtrade_params_file(strategy_name, baseline_params), indent=2)`.

**Update `load_baseline_params`**: Add `strategy_name: str = ""` parameter. After the existing
early-return for missing `params.json`, add a fallback block that reads the live strategy JSON
and converts it to flat format using the reverse key mapping:
- `params["stoploss"]["stoploss"]` → `stoploss`
- `params["max_open_trades"]["max_open_trades"]` → `max_open_trades`
- `params["roi"]` → `minimal_roi`
- `params["buy"]` → `buy_params`
- `params["sell"]` → `sell_params`

#### File: `app/ui/pages/improve_page.py`

**Update `_on_candidate_finished`**: In the `else` branch (non-zero exit code), call
`self._terminal.get_output()` to retrieve terminal text, scan it for known freqtrade error
phrases (`"Invalid parameter file"`, `"Strategy not found"`, `"No data found"`,
`"Configuration error"`, `"No pairs defined"`), and append the first matched phrase in
parentheses to the status message. Fall back to the existing generic message if no phrase
matches.

**Update `_on_accept`**: After the successful `accept_candidate` call, add sandbox cleanup:
```
IF self._sandbox_dir is not None:
  self._improve_service.reject_candidate(self._sandbox_dir)
  self._sandbox_dir = None
```

**Update call site for `load_baseline_params`**: Pass `strategy_name` as the second argument
wherever `load_baseline_params` is called in `improve_page.py`.

#### File: `app/core/services/results_diagnosis_service.py`

**Add threshold constants**:
```python
PROFIT_FACTOR_LOW: float = 1.0
EXPECTANCY_NEGATIVE: float = 0.0
```

**Add two rules in `diagnose()`** (after existing rules):
```
IF 0.0 < summary.profit_factor < PROFIT_FACTOR_LOW:
  append DiagnosedIssue(
    issue_id="profit_factor_low",
    description=f"Profit factor {summary.profit_factor:.2f} is below 1.0 — losses exceed gains over the backtest period."
  )

IF summary.expectancy < EXPECTANCY_NEGATIVE:
  append DiagnosedIssue(
    issue_id="expectancy_negative",
    description=f"Expectancy {summary.expectancy:.4f} is negative — the average trade loses money."
  )
```

#### File: `app/core/services/rule_suggestion_service.py`

**Add two entries to the `handlers` dict** in `_handle_issue`:
```python
"profit_factor_low": RuleSuggestionService._suggest_profit_factor_low,
"expectancy_negative": RuleSuggestionService._suggest_expectancy_negative,
```

**Add two static handler methods**:
```python
@staticmethod
def _suggest_profit_factor_low(_params: dict) -> ParameterSuggestion:
    return ParameterSuggestion(
        parameter="entry_conditions",
        proposed_value=None,
        reason="Profit factor below 1.0 — losses exceed gains",
        expected_effect="Review entry/exit conditions to improve trade quality",
        is_advisory=True,
    )

@staticmethod
def _suggest_expectancy_negative(_params: dict) -> ParameterSuggestion:
    return ParameterSuggestion(
        parameter="entry_filters",
        proposed_value=None,
        reason="Negative expectancy — average trade loses money",
        expected_effect="Consider tightening entry filters to improve trade selectivity",
        is_advisory=True,
    )
```

#### File: `app/ui/pages/improve_page.py` — `IssueBadge.SEVERITY_COLORS`

**Add two entries**:
```python
"profit_factor_low": (_C_ORANGE, "🟠"),
"expectancy_negative": (_C_ORANGE, "🟠"),
```

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that
demonstrate the bug on unfixed code, then verify the fix works correctly and preserves existing
behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm
or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write unit tests that call `prepare_sandbox`, `accept_candidate`, and `rollback`
with a flat params dict and assert that the written JSON file is in the freqtrade nested format.
Run these tests on the UNFIXED code to observe failures and confirm the root cause.

**Test Cases**:
1. **`prepare_sandbox` writes flat format** (will fail on unfixed code): Call
   `prepare_sandbox("MultiMeee", flat_params)`, read the written JSON, assert
   `"strategy_name" in result` — fails because the file contains the flat dict.
2. **`accept_candidate` writes flat format** (will fail on unfixed code): Call
   `accept_candidate("MultiMeee", flat_params)`, read the written JSON, assert
   `result["params"]["stoploss"]["stoploss"] == flat_params["stoploss"]` — fails.
3. **`rollback` writes flat format** (will fail on unfixed code): Call
   `rollback("MultiMeee", flat_params)`, read the written JSON, assert
   `"ft_stratparam_v" in result` — fails.
4. **`load_baseline_params` returns empty on missing `params.json`** (will fail on unfixed
   code): Call `load_baseline_params(run_dir_without_params, "MultiMeee")`, assert result is
   non-empty — fails because the fallback does not exist.

**Expected Counterexamples**:
- Written JSON files contain flat keys (`buy_params`, `stoploss` as scalar) instead of nested
  keys (`params.buy`, `params.stoploss.stoploss`).
- Possible causes: no format conversion step, direct `json.dumps` of flat dict.

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed function produces
the expected behavior.

**Pseudocode:**
```
FOR ALL flat_params WHERE isBugCondition(json.dumps(flat_params)) DO
  result := _build_freqtrade_params_file(strategy_name, flat_params)
  ASSERT result["strategy_name"] == strategy_name
  ASSERT result["ft_stratparam_v"] == 1
  ASSERT result["params"]["stoploss"]["stoploss"] == flat_params["stoploss"]
  ASSERT result["params"]["roi"] == flat_params["minimal_roi"]
  ASSERT result["params"]["max_open_trades"]["max_open_trades"] == flat_params["max_open_trades"]
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold (i.e. inputs that do
not involve writing a strategy parameter file, or `params.json` reads when the file exists), the
fixed code produces the same result as the original code.

**Pseudocode:**
```
FOR ALL flat_params WHERE NOT isBugCondition(flat_params) DO
  -- params.json exists and is valid
  ASSERT load_baseline_params_original(run_dir) == load_baseline_params_fixed(run_dir)
END FOR

FOR ALL live_json WHERE live_json contains "trailing" block DO
  result := _build_freqtrade_params_file(strategy_name, flat_params)
  ASSERT result["params"]["trailing"] == live_json["params"]["trailing"]
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain
- It catches edge cases that manual unit tests might miss (e.g. `None` values, empty dicts,
  missing keys)
- It provides strong guarantees that the `trailing` block and other untracked fields are
  preserved for all valid live JSON inputs

**Test Plan**: Observe behavior on UNFIXED code first for `load_baseline_params` with a valid
`params.json`, then write property-based tests capturing that behavior.

**Test Cases**:
1. **`load_baseline_params` with valid `params.json`**: Verify the existing path returns the
   same dict before and after the fix.
2. **`trailing` block preservation**: Generate random `trailing` dicts in the live JSON and
   verify they survive a round-trip through `_build_freqtrade_params_file`.
3. **Existing diagnosis rules unchanged**: Verify all six existing rules still fire for their
   respective threshold conditions after adding the two new rules.
4. **Existing suggestion handlers unchanged**: Verify all six existing handlers return the same
   `ParameterSuggestion` values after adding the two new handlers.

### Unit Tests

- Test `_build_freqtrade_params_file` with a full flat params dict and a live JSON base —
  assert all nested keys are correct.
- Test `_build_freqtrade_params_file` with no live JSON present — assert fallback minimal
  structure is used and all provided flat keys are mapped.
- Test `_build_freqtrade_params_file` with partial flat params (e.g. `stoploss` only) — assert
  only the provided keys are overwritten; other nested keys from the live JSON are preserved.
- Test `load_baseline_params` fallback: `params.json` absent, live JSON present — assert
  returned flat dict matches the live JSON's nested values.
- Test `load_baseline_params` primary path: `params.json` present — assert live JSON is not
  consulted.
- Test `diagnose()` with `profit_factor=0.5` — assert `profit_factor_low` issue is present.
- Test `diagnose()` with `profit_factor=0.0` — assert `profit_factor_low` issue is NOT present
  (boundary: must be `> 0`).
- Test `diagnose()` with `profit_factor=1.0` — assert `profit_factor_low` issue is NOT present
  (boundary: must be `< 1.0`).
- Test `diagnose()` with `expectancy=-0.001` — assert `expectancy_negative` issue is present.
- Test `diagnose()` with `expectancy=0.0` — assert `expectancy_negative` issue is NOT present.
- Test `suggest()` with `profit_factor_low` issue — assert `is_advisory=True`,
  `proposed_value=None`, `parameter="entry_conditions"`.
- Test `suggest()` with `expectancy_negative` issue — assert `is_advisory=True`,
  `proposed_value=None`, `parameter="entry_filters"`.

### Property-Based Tests

- **Round-trip property** (Property 1): Generate random flat params dicts (with arbitrary
  `stoploss`, `max_open_trades`, `minimal_roi`, `buy_params`, `sell_params` values) and verify
  that `_build_freqtrade_params_file` maps every present key to the correct nested location.
- **Trailing preservation property** (Property 2): Generate random `trailing` dicts in the live
  JSON and verify they are preserved unchanged in the output of `_build_freqtrade_params_file`.
- **Fallback consistency property** (Property 3): Generate random live strategy JSONs and verify
  that `load_baseline_params` fallback followed by `_build_freqtrade_params_file` produces a
  dict with the same nested values as the original live JSON.
- **Diagnosis boundary property** (Property 4): Generate random `profit_factor` values and
  verify `profit_factor_low` fires if and only if `0 < value < 1.0`; generate random
  `expectancy` values and verify `expectancy_negative` fires if and only if `value < 0.0`.
- **Advisory-only property** (Property 5): For any `profit_factor_low` or
  `expectancy_negative` issue, verify `suggest()` always returns `is_advisory=True` and
  `proposed_value=None`.

### Integration Tests

- Test full `prepare_sandbox` → read written JSON → assert freqtrade nested format is present
  and `strategy_name` matches.
- Test full `accept_candidate` → read live strategy JSON → assert nested format, `trailing`
  block preserved from original live JSON.
- Test full `rollback` → read live strategy JSON → assert nested format, values match baseline
  params.
- Test `_on_candidate_finished` with a mocked terminal containing `"Invalid parameter file"` →
  assert status label includes `"(Invalid parameter file)"`.
- Test `_on_accept` → assert `reject_candidate` is called with `_sandbox_dir` and
  `_sandbox_dir` is set to `None` afterwards.
