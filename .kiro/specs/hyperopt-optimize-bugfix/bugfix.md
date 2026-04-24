# Bugfix Requirements Document

## Introduction

Three bugs prevent the Hyperopt/Optimize and Download Data features from functioning correctly.

**Bug 1** — `create_optimize_command` in `app/core/freqtrade/commands.py` (the public wrapper) does not accept `epochs`, `spaces`, or `hyperopt_loss` parameters, but `OptimizeService.build_command()` passes all three. This causes a `TypeError` before Freqtrade is ever invoked, making the Run Hyperopt button completely non-functional.

**Bug 2** — `create_optimize_command` in `app/core/freqtrade/runners/optimize_runner.py` constructs `OptimizeRunCommand` without the required `export_dir` field, causing an instantiation error at runtime.

**Bug 3** — `create_download_data_command` in `app/core/freqtrade/runners/download_data_runner.py` populates `DownloadDataRunCommand.strategy_file` with `str(paths.strategy_file)`. Because download-data does not require a strategy, `paths.strategy_file` is `None`, so the field is set to the string `"None"` instead of being absent or empty.

---

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN `OptimizeService.build_command()` is called with `epochs`, `spaces`, or `hyperopt_loss` THEN the system raises a `TypeError` because the `create_optimize_command` wrapper in `commands.py` does not declare those parameters

1.2 WHEN `create_optimize_command` in `optimize_runner.py` successfully builds the freqtrade args THEN the system raises a `TypeError` when constructing `OptimizeRunCommand` because the required `export_dir` field is not provided

1.3 WHEN `create_download_data_command` is called without a strategy THEN the system stores the string `"None"` in `DownloadDataRunCommand.strategy_file` because `paths.strategy_file` is `None` and is cast directly to `str`

### Expected Behavior (Correct)

2.1 WHEN `OptimizeService.build_command()` is called with `epochs`, `spaces`, or `hyperopt_loss` THEN the system SHALL forward those parameters through the `create_optimize_command` wrapper to the underlying runner without raising an error

2.2 WHEN `create_optimize_command` in `optimize_runner.py` builds the freqtrade args THEN the system SHALL construct `OptimizeRunCommand` with a valid `export_dir` pointing to `{user_data_dir}/hyperopt_results/`, creating the directory if it does not exist

2.3 WHEN `create_download_data_command` is called without a strategy THEN the system SHALL construct `DownloadDataRunCommand` without a `strategy_file` field (or with an empty/null value), not the string `"None"`

### Unchanged Behavior (Regression Prevention)

3.1 WHEN `OptimizeService.build_command()` is called with valid `strategy_name`, `timeframe`, and `epochs` THEN the system SHALL CONTINUE TO build and return a valid `OptimizeRunCommand` ready for `ProcessService`

3.2 WHEN `create_optimize_command` is called with optional `timerange`, `pairs`, `spaces`, `hyperopt_loss`, or `extra_flags` THEN the system SHALL CONTINUE TO include those arguments in the freqtrade command args list

3.3 WHEN `create_download_data_command` is called with valid `timeframe` and optional `pairs`, `timerange`, `prepend`, or `erase` THEN the system SHALL CONTINUE TO build and return a valid `DownloadDataRunCommand` with the correct freqtrade args

3.4 WHEN `create_backtest_command` is called THEN the system SHALL CONTINUE TO build and return a valid `BacktestRunCommand` unaffected by any changes to the optimize or download-data paths

---

## Bug Condition Pseudocode

### Bug 1 — Wrapper Signature Mismatch

```pascal
FUNCTION isBugCondition_1(call)
  INPUT: call — invocation of create_optimize_command wrapper
  OUTPUT: boolean

  RETURN call.has_kwarg("epochs")
      OR call.has_kwarg("spaces")
      OR call.has_kwarg("hyperopt_loss")
END FUNCTION

// Property: Fix Checking
FOR ALL call WHERE isBugCondition_1(call) DO
  result ← create_optimize_command'(call)
  ASSERT no_TypeError(result)
  ASSERT result IS OptimizeRunCommand
END FOR

// Property: Preservation Checking
FOR ALL call WHERE NOT isBugCondition_1(call) DO
  ASSERT create_optimize_command(call) = create_optimize_command'(call)
END FOR
```

### Bug 2 — Missing export_dir

```pascal
FUNCTION isBugCondition_2(runner_call)
  INPUT: runner_call — invocation of optimize_runner.create_optimize_command
  OUTPUT: boolean

  RETURN OptimizeRunCommand constructed WITHOUT export_dir field
END FUNCTION

// Property: Fix Checking
FOR ALL runner_call WHERE isBugCondition_2(runner_call) DO
  result ← create_optimize_command'(runner_call)
  ASSERT result.export_dir IS NOT NULL
  ASSERT result.export_dir ends_with "hyperopt_results"
END FOR

// Property: Preservation Checking
FOR ALL runner_call WHERE NOT isBugCondition_2(runner_call) DO
  ASSERT create_optimize_command(runner_call) = create_optimize_command'(runner_call)
END FOR
```

### Bug 3 — "None" strategy_file in Download Data

```pascal
FUNCTION isBugCondition_3(paths)
  INPUT: paths — ResolvedRunPaths from find_run_paths
  OUTPUT: boolean

  RETURN paths.strategy_file IS None
END FUNCTION

// Property: Fix Checking
FOR ALL paths WHERE isBugCondition_3(paths) DO
  result ← create_download_data_command'(paths)
  ASSERT result.strategy_file ≠ "None"
END FOR

// Property: Preservation Checking
FOR ALL paths WHERE NOT isBugCondition_3(paths) DO
  ASSERT create_download_data_command(paths) = create_download_data_command'(paths)
END FOR
```
