# Hyperopt/Optimize & Download Data Bugfix Design

## Overview

Three bugs prevent the Hyperopt/Optimize and Download Data features from functioning. The fixes
are surgical: each targets a single function signature or field assignment with no architectural
changes required.

- **Bug 1** — The public `create_optimize_command` wrapper in `app/core/freqtrade/commands.py`
  is missing `epochs`, `spaces`, and `hyperopt_loss` parameters. `OptimizeService.build_command()`
  passes all three, causing an immediate `TypeError` before Freqtrade is ever invoked.

- **Bug 2** — `create_optimize_command` in `app/core/freqtrade/runners/optimize_runner.py`
  constructs `OptimizeRunCommand` without the required `export_dir` field, causing a dataclass
  instantiation `TypeError` at runtime.

- **Bug 3** — `create_download_data_command` in
  `app/core/freqtrade/runners/download_data_runner.py` sets `strategy_file=str(paths.strategy_file)`
  when `paths.strategy_file` is `None`, producing the literal string `"None"` in the model.

All three fixes are additive or corrective changes to existing functions. No new modules,
services, or abstractions are introduced.

---

## Glossary

- **Bug_Condition (C)**: The condition that identifies an input or call that triggers the bug.
- **Property (P)**: The desired correct behavior when the bug condition holds.
- **Preservation**: Existing behavior that must remain unchanged after the fix.
- **`create_optimize_command` (wrapper)**: The public function in `app/core/freqtrade/commands.py`
  that delegates to the runner. This is the entry point called by `OptimizeService`.
- **`create_optimize_command` (runner)**: The internal function in
  `app/core/freqtrade/runners/optimize_runner.py` that builds the freqtrade args and constructs
  `OptimizeRunCommand`.
- **`OptimizeRunCommand`**: Frozen dataclass in `app/core/models/command_models.py` with required
  fields `program`, `args`, `cwd`, `export_dir`, `config_file`, `strategy_file`.
- **`DownloadDataRunCommand`**: Dataclass in `app/core/models/command_models.py` with fields
  `program`, `args`, `cwd`, `config_file`, `strategy_file`.
- **`ResolvedRunPaths`**: Dataclass returned by `find_run_paths()`; `strategy_file` is
  `Optional[Path]` and is `None` when no strategy is required (e.g. download-data).
- **`export_dir`**: Directory where hyperopt results are written; must be
  `{user_data_dir}/hyperopt_results/` and must exist before the process starts.

---

## Bug Details

### Bug 1 — Wrapper Signature Mismatch

The bug manifests when `OptimizeService.build_command()` calls the public wrapper with `epochs`,
`spaces`, or `hyperopt_loss`. The wrapper's signature does not declare those parameters, so Python
raises `TypeError: create_optimize_command() got an unexpected keyword argument 'epochs'` before
any freqtrade subprocess is started.

**Formal Specification:**
```
FUNCTION isBugCondition_1(call)
  INPUT: call — invocation of create_optimize_command in commands.py
  OUTPUT: boolean

  RETURN call.has_kwarg("epochs")
      OR call.has_kwarg("spaces")
      OR call.has_kwarg("hyperopt_loss")
END FUNCTION
```

**Examples:**
- `create_optimize_command(settings, "MyStrategy", "5m", epochs=100)` → `TypeError` (bug)
- `create_optimize_command(settings, "MyStrategy", "5m", epochs=100, spaces=["roi"])` → `TypeError` (bug)
- `create_optimize_command(settings, "MyStrategy", "5m", timerange="20240101-")` → succeeds (no bug condition)

### Bug 2 — Missing `export_dir` in `OptimizeRunCommand`

The bug manifests when `optimize_runner.create_optimize_command` reaches the `OptimizeRunCommand`
constructor. The `export_dir` field is required (no default) but is not passed, causing
`TypeError: __init__() missing 1 required positional argument: 'export_dir'`.

**Formal Specification:**
```
FUNCTION isBugCondition_2(runner_call)
  INPUT: runner_call — execution of optimize_runner.create_optimize_command
  OUTPUT: boolean

  RETURN OptimizeRunCommand instantiated WITHOUT export_dir argument
END FUNCTION
```

**Examples:**
- Any call to `optimize_runner.create_optimize_command(...)` → `TypeError` on construction (bug)
- After fix: `result.export_dir` ends with `"hyperopt_results"` and the directory exists on disk

### Bug 3 — `"None"` String in `DownloadDataRunCommand.strategy_file`

The bug manifests when `find_run_paths()` returns `paths.strategy_file = None` (the normal case
for download-data, which requires no strategy). `str(None)` evaluates to `"None"`, so the model
field is set to the string `"None"` rather than being absent or empty.

**Formal Specification:**
```
FUNCTION isBugCondition_3(paths)
  INPUT: paths — ResolvedRunPaths from find_run_paths()
  OUTPUT: boolean

  RETURN paths.strategy_file IS None
END FUNCTION
```

**Examples:**
- `paths.strategy_file = None` → `strategy_file="None"` in the command model (bug)
- `paths.strategy_file = Path("/some/strategy.py")` → `strategy_file="/some/strategy.py"` (no bug condition)

---

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- `create_backtest_command` in `commands.py` and `backtest_runner.py` must be completely unaffected.
- All optional parameters (`timerange`, `pairs`, `extra_flags`, `prepend`, `erase`) must continue
  to be forwarded correctly to the underlying runners.
- `OptimizeService.build_command()` call signature must remain unchanged — callers pass the same
  arguments as before.
- `DownloadDataService.build_command()` call signature must remain unchanged.
- When `paths.strategy_file` is a valid `Path`, `DownloadDataRunCommand.strategy_file` must
  continue to be set to its string representation.
- The freqtrade args list built by `optimize_runner` (subcommand, flags, strategy, timeframe,
  epochs, etc.) must remain identical after the fix.

**Scope:**
All inputs that do NOT satisfy any of the three bug conditions should be completely unaffected.
This includes:
- Backtest command building (separate runner, no shared code paths changed)
- Download-data calls where a strategy file is present
- Any optimize call that somehow bypassed the wrapper (not a real path, but preserved for safety)

---

## Hypothesized Root Cause

### Bug 1
The wrapper in `commands.py` was written to mirror the backtest wrapper's simpler signature and
was never updated when `OptimizeService` was extended to pass `epochs`, `spaces`, and
`hyperopt_loss`. The runner already accepts all three parameters correctly — only the wrapper is
missing them.

### Bug 2
`OptimizeRunCommand` was modelled after `BacktestRunCommand`, which also requires `export_dir`.
When the optimize runner was written, `export_dir` was omitted from the constructor call. Because
`OptimizeRunCommand` is a plain `@dataclass` (not frozen, no defaults), Python raises `TypeError`
at instantiation rather than at definition time, so the error only surfaces at runtime.

### Bug 3
`DownloadDataRunCommand` was modelled after `BacktestRunCommand` and `OptimizeRunCommand`, both of
which always have a strategy file. The `strategy_file` field was copied across without accounting
for the fact that download-data does not require a strategy. `find_run_paths()` correctly returns
`None` for `strategy_file` in this case, but the runner unconditionally calls `str()` on it.

---

## Correctness Properties

Property 1: Bug Condition — Optimize Wrapper Forwards All Parameters

_For any_ call to `create_optimize_command` (wrapper) where `epochs`, `spaces`, or
`hyperopt_loss` is passed as a keyword argument (isBugCondition_1 returns true), the fixed
function SHALL forward those parameters to the runner without raising a `TypeError`, and SHALL
return a valid `OptimizeRunCommand` instance.

**Validates: Requirements 2.1**

Property 2: Bug Condition — OptimizeRunCommand Has Valid export_dir

_For any_ invocation of `optimize_runner.create_optimize_command` (isBugCondition_2 returns
true), the fixed function SHALL construct `OptimizeRunCommand` with a non-null `export_dir`
whose path ends with `"hyperopt_results"`, and the directory SHALL exist on the filesystem
before the command is returned.

**Validates: Requirements 2.2**

Property 3: Bug Condition — DownloadDataRunCommand Has No "None" strategy_file

_For any_ call to `create_download_data_command` where `paths.strategy_file` is `None`
(isBugCondition_3 returns true), the fixed function SHALL construct `DownloadDataRunCommand`
with `strategy_file` set to `None` or an empty string — never the literal string `"None"`.

**Validates: Requirements 2.3**

Property 4: Preservation — Non-Buggy Optimize Calls Unchanged

_For any_ call to `create_optimize_command` where none of the three bug conditions hold (e.g.
a call with only `strategy_name`, `timeframe`, `timerange`, `pairs`, `extra_flags`), the fixed
wrapper SHALL produce the same `OptimizeRunCommand` as the original wrapper, preserving all
freqtrade args and field values.

**Validates: Requirements 3.1, 3.2**

Property 5: Preservation — Download Data Calls With Strategy Unchanged

_For any_ call to `create_download_data_command` where `paths.strategy_file` is NOT `None`
(isBugCondition_3 returns false), the fixed function SHALL produce the same
`DownloadDataRunCommand` as the original function, preserving `strategy_file` and all other
fields.

**Validates: Requirements 3.3**

Property 6: Preservation — Backtest Command Building Unaffected

_For any_ call to `create_backtest_command`, the fixed codebase SHALL produce the same
`BacktestRunCommand` as the original codebase, with no change to behavior, args, or fields.

**Validates: Requirements 3.4**

---

## Fix Implementation

### Bug 1 — `app/core/freqtrade/commands.py`

**Function:** `create_optimize_command`

**Specific Changes:**
1. Add `epochs: int` as a required parameter after `timeframe`.
2. Add `spaces: list[str] | None = None` as an optional parameter.
3. Add `hyperopt_loss: str | None = None` as an optional parameter.
4. Forward all three new parameters in the `_create_optimize(...)` call.
5. Update the docstring to document the new parameters.

The `timerange` and `pairs` parameters already exist in the wrapper but were not being forwarded
with `epochs`/`spaces`/`hyperopt_loss` — confirm they are forwarded correctly too.

### Bug 2 — `app/core/freqtrade/runners/optimize_runner.py`

**Function:** `create_optimize_command`

**Specific Changes:**
1. Resolve `export_dir` as `paths.user_data_dir / "hyperopt_results"`.
2. Call `export_dir.mkdir(parents=True, exist_ok=True)` to ensure the directory exists.
3. Pass `export_dir=str(export_dir)` when constructing `OptimizeRunCommand`.

No changes to the freqtrade args list are required.

### Bug 3 — `app/core/freqtrade/runners/download_data_runner.py`

**Function:** `create_download_data_command`

**Specific Changes:**
1. Replace `strategy_file=str(paths.strategy_file)` with a conditional:
   `strategy_file=str(paths.strategy_file) if paths.strategy_file is not None else None`.
2. This requires `DownloadDataRunCommand.strategy_file` to accept `Optional[str]` — verify the
   field type in `command_models.py` and update if it is currently `str` (non-optional).

---

## Testing Strategy

### Validation Approach

Testing follows a two-phase approach: first run exploratory tests against the **unfixed** code to
confirm the bug manifests as described, then run fix-checking and preservation tests against the
**fixed** code to verify correctness and no regressions.

---

### Exploratory Bug Condition Checking

**Goal:** Surface counterexamples that demonstrate each bug on unfixed code. Confirm or refute
the root cause analysis.

**Test Plan:** Call each buggy function with inputs that satisfy the bug condition and assert the
expected failure. Run on unfixed code — these tests are expected to fail (raise `TypeError`).

**Test Cases:**

1. **Bug 1 — Wrapper rejects `epochs`**: Call `create_optimize_command(settings, "S", "5m", epochs=10)` and assert `TypeError` is raised. (Confirms bug condition.)
2. **Bug 1 — Wrapper rejects `spaces`**: Call with `spaces=["roi"]` and assert `TypeError`.
3. **Bug 1 — Wrapper rejects `hyperopt_loss`**: Call with `hyperopt_loss="SharpeHyperOptLoss"` and assert `TypeError`.
4. **Bug 2 — Runner raises on construction**: Call `optimize_runner.create_optimize_command(settings, "S", "5m", epochs=10)` directly and assert `TypeError` about `export_dir`.
5. **Bug 3 — strategy_file is "None" string**: Call `create_download_data_command(settings, "5m")` with a settings object where no strategy is configured, and assert `result.strategy_file == "None"`.

**Expected Counterexamples:**
- Bugs 1 and 2 raise `TypeError` with messages about unexpected/missing keyword arguments.
- Bug 3 produces a `DownloadDataRunCommand` with `strategy_file == "None"` (string).

---

### Fix Checking

**Goal:** Verify that for all inputs where each bug condition holds, the fixed function produces
the expected correct behavior.

**Pseudocode:**
```
// Bug 1
FOR ALL call WHERE isBugCondition_1(call) DO
  result := create_optimize_command_fixed(call)
  ASSERT no TypeError raised
  ASSERT result IS OptimizeRunCommand
END FOR

// Bug 2
FOR ALL runner_call WHERE isBugCondition_2(runner_call) DO
  result := optimize_runner.create_optimize_command_fixed(runner_call)
  ASSERT result.export_dir IS NOT NULL
  ASSERT result.export_dir ends_with "hyperopt_results"
  ASSERT directory at result.export_dir exists on filesystem
END FOR

// Bug 3
FOR ALL paths WHERE isBugCondition_3(paths) DO
  result := create_download_data_command_fixed(paths)
  ASSERT result.strategy_file != "None"
  ASSERT result.strategy_file IS None OR result.strategy_file == ""
END FOR
```

---

### Preservation Checking

**Goal:** Verify that for all inputs where the bug condition does NOT hold, the fixed functions
produce the same result as the original functions.

**Pseudocode:**
```
// Optimize wrapper — non-buggy calls
FOR ALL call WHERE NOT isBugCondition_1(call) DO
  ASSERT create_optimize_command_original(call) = create_optimize_command_fixed(call)
END FOR

// Download data — strategy_file present
FOR ALL paths WHERE NOT isBugCondition_3(paths) DO
  ASSERT create_download_data_command_original(paths) = create_download_data_command_fixed(paths)
END FOR

// Backtest — completely unaffected
FOR ALL call DO
  ASSERT create_backtest_command_original(call) = create_backtest_command_fixed(call)
END FOR
```

**Testing Approach:** Property-based testing is recommended for preservation checking because:
- It generates many combinations of optional parameters automatically.
- It catches edge cases (empty lists, `None` vs omitted, long timerange strings) that manual
  tests miss.
- It provides strong guarantees that the freqtrade args list is byte-for-byte identical for
  all non-buggy inputs.

**Test Cases:**
1. **Optimize args preservation**: Generate random valid `(timeframe, timerange, pairs, extra_flags)` combinations and assert the freqtrade args list is unchanged after the fix.
2. **Download data args preservation**: Generate random `(timeframe, timerange, pairs, prepend, erase)` combinations with a non-None `strategy_file` and assert the full command is unchanged.
3. **Backtest preservation**: Generate random backtest inputs and assert `create_backtest_command` output is identical before and after the fix.

---

### Unit Tests

- Test Bug 1 fix: wrapper accepts `epochs`, `spaces`, `hyperopt_loss` and returns `OptimizeRunCommand`.
- Test Bug 2 fix: runner sets `export_dir` to a path ending in `"hyperopt_results"` and creates the directory.
- Test Bug 3 fix: `strategy_file` is `None` (not `"None"`) when `paths.strategy_file` is `None`.
- Test Bug 3 non-bug path: `strategy_file` is the correct string when `paths.strategy_file` is a real `Path`.
- Test that `OptimizeRunCommand` freqtrade args include `--spaces` and `--hyperopt-loss` when provided.
- Test that `OptimizeRunCommand` freqtrade args omit `--spaces` and `--hyperopt-loss` when not provided.

### Property-Based Tests

- Generate random `epochs` (1–1000), `spaces` subsets, and optional `hyperopt_loss` strings; assert the wrapper always returns a valid `OptimizeRunCommand` without raising.
- Generate random `(timeframe, pairs, timerange)` combinations; assert the freqtrade args list for download-data is identical before and after the Bug 3 fix when `strategy_file` is not `None`.
- Generate random settings with varying `user_data_path` values; assert `export_dir` always resolves to `{user_data_dir}/hyperopt_results` and the directory is created.

### Integration Tests

- End-to-end: call `OptimizeService.build_command(...)` with all parameters and assert a valid `OptimizeRunCommand` is returned with correct `export_dir`, `config_file`, `strategy_file`, and freqtrade args.
- End-to-end: call `DownloadDataService.build_command(...)` and assert `strategy_file` is not the string `"None"`.
- Verify `create_backtest_command` output is unaffected by running it before and after applying the three fixes.
