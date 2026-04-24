# Implementation Plan

- [x] 1. Write bug condition exploration tests (BEFORE implementing any fix)
  - **Property 1: Bug Condition** - Optimize Wrapper Missing Parameters & Runner Missing export_dir & Download Data "None" strategy_file
  - **CRITICAL**: These tests MUST FAIL on unfixed code — failure confirms the bugs exist
  - **DO NOT attempt to fix the tests or the code when they fail**
  - **NOTE**: These tests encode the expected behavior — they will validate the fixes when they pass after implementation
  - **GOAL**: Surface counterexamples that demonstrate each bug exists
  - **Scoped PBT Approach**: Bugs 1 and 2 are deterministic (any call triggers them); Bug 3 is scoped to `paths.strategy_file is None`
  - Create `tests/test_hyperopt_bugfix_exploration.py`
  - **Bug 1 exploration** — call `commands.create_optimize_command(settings, "MyStrategy", "5m", timerange="20240101-", epochs=100)` and assert `TypeError` is raised (isBugCondition_1: call has kwarg `epochs`)
  - **Bug 1 exploration** — call with `spaces=["roi"]` and assert `TypeError` is raised (isBugCondition_1: call has kwarg `spaces`)
  - **Bug 1 exploration** — call with `hyperopt_loss="SharpeHyperOptLoss"` and assert `TypeError` is raised (isBugCondition_1: call has kwarg `hyperopt_loss`)
  - **Bug 2 exploration** — call `optimize_runner.create_optimize_command(settings, "MyStrategy", "5m", epochs=10)` directly and assert `TypeError` about missing `export_dir` (isBugCondition_2: OptimizeRunCommand constructed without export_dir)
  - **Bug 3 exploration** — call `create_download_data_command(settings, "5m")` with settings where no strategy is configured (paths.strategy_file is None) and assert `result.strategy_file == "None"` (isBugCondition_3: paths.strategy_file is None)
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: All tests FAIL (this is correct — it proves the bugs exist)
  - Document counterexamples found (e.g. "TypeError: create_optimize_command() got an unexpected keyword argument 'epochs'", "TypeError: __init__() missing 1 required positional argument: 'export_dir'", "strategy_file == 'None'")
  - Mark task complete when tests are written, run, and failures are documented
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 2. Write preservation property tests (BEFORE implementing any fix)
  - **Property 2: Preservation** - Backtest Unaffected, Optimize Non-Buggy Calls Unchanged, Download Data With Strategy Unchanged
  - **IMPORTANT**: Follow observation-first methodology — observe behavior on UNFIXED code for non-buggy inputs, then write tests capturing those patterns
  - Create `tests/test_hyperopt_bugfix_preservation.py`
  - **Preservation 1 — Backtest unaffected**: Use `hypothesis` to generate random valid `(strategy_name, timeframe, timerange, pairs, extra_flags)` combinations; assert `create_backtest_command` returns a `BacktestRunCommand` with identical `args`, `program`, `cwd`, `export_dir`, `config_file`, `strategy_file` on unfixed code (isBugCondition_1/2/3 all false for backtest path)
  - **Preservation 2 — Optimize non-buggy calls**: Observe that `commands.create_optimize_command(settings, "S", "5m", timerange="20240101-", pairs=["BTC/USDT"], extra_flags=[])` succeeds on unfixed code (no `epochs`/`spaces`/`hyperopt_loss` kwargs — isBugCondition_1 is false); use `hypothesis` to generate random `(timeframe, timerange, pairs, extra_flags)` combinations and assert the wrapper returns the same result as calling the runner directly
  - **Preservation 3 — Download data with strategy present**: Observe that `create_download_data_command(settings, "5m")` with a non-None `paths.strategy_file` produces `strategy_file == str(paths.strategy_file)` on unfixed code (isBugCondition_3 is false); use `hypothesis` to generate random `(timeframe, timerange, pairs, prepend, erase)` combinations with a non-None strategy path and assert `strategy_file` equals the string form of the path
  - Verify ALL preservation tests PASS on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 3. Fix all three bugs

  - [x] 3.1 Fix Bug 1 — add `epochs`, `spaces`, `hyperopt_loss` to the `create_optimize_command` wrapper in `app/core/freqtrade/commands.py`
    - Add `epochs: int` as a required parameter after `timeframe` in the wrapper signature
    - Add `spaces: list[str] | None = None` as an optional parameter
    - Add `hyperopt_loss: str | None = None` as an optional parameter
    - Forward all three new parameters in the `_create_optimize(...)` call alongside existing `timerange`, `pairs`, `extra_flags`
    - Update the docstring to document the three new parameters
    - _Bug_Condition: isBugCondition_1(call) — call.has_kwarg("epochs") OR call.has_kwarg("spaces") OR call.has_kwarg("hyperopt_loss")_
    - _Expected_Behavior: wrapper forwards all parameters to runner without raising TypeError; returns valid OptimizeRunCommand_
    - _Preservation: calls without epochs/spaces/hyperopt_loss kwargs must produce identical output; backtest path must be completely unaffected_
    - _Requirements: 2.1, 3.1, 3.2_

  - [x] 3.2 Fix Bug 2 — add `export_dir` to `OptimizeRunCommand` construction in `app/core/freqtrade/runners/optimize_runner.py`
    - After resolving `paths`, compute `export_dir = paths.user_data_dir / "hyperopt_results"`
    - Call `export_dir.mkdir(parents=True, exist_ok=True)` to ensure the directory exists before the command is returned
    - Pass `export_dir=str(export_dir)` when constructing `OptimizeRunCommand`
    - No changes to the freqtrade args list are required
    - _Bug_Condition: isBugCondition_2(runner_call) — OptimizeRunCommand constructed WITHOUT export_dir field_
    - _Expected_Behavior: result.export_dir is not None, ends with "hyperopt_results", and the directory exists on the filesystem_
    - _Preservation: freqtrade args list (subcommand, flags, strategy, timeframe, epochs, spaces, hyperopt_loss, etc.) must remain byte-for-byte identical_
    - _Requirements: 2.2, 3.1, 3.2_

  - [x] 3.3 Fix Bug 3 — guard `None` strategy_file in `app/core/freqtrade/runners/download_data_runner.py` and verify `DownloadDataRunCommand` field type
    - In `create_download_data_command`, replace `strategy_file=str(paths.strategy_file)` with `strategy_file=str(paths.strategy_file) if paths.strategy_file is not None else None`
    - Open `app/core/models/command_models.py` and verify `DownloadDataRunCommand.strategy_file` is typed as `Optional[str]`; if it is currently `str` (non-optional), update it to `Optional[str] = None`
    - _Bug_Condition: isBugCondition_3(paths) — paths.strategy_file IS None_
    - _Expected_Behavior: result.strategy_file is None (or empty string), never the literal string "None"_
    - _Preservation: when paths.strategy_file is a valid Path, strategy_file must still equal str(paths.strategy_file); all other DownloadDataRunCommand fields must be unchanged_
    - _Requirements: 2.3, 3.3_

  - [x] 3.4 Verify bug condition exploration tests now pass
    - **Property 1: Expected Behavior** - Optimize Wrapper Forwards All Parameters, Runner Has Valid export_dir, Download Data Has No "None" strategy_file
    - **IMPORTANT**: Re-run the SAME tests from task 1 — do NOT write new tests
    - The tests from task 1 encode the expected behavior; when they pass the fixes are confirmed
    - Run `tests/test_hyperopt_bugfix_exploration.py` against the fixed code
    - **EXPECTED OUTCOME**: All tests PASS (confirms all three bugs are fixed)
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 3.5 Verify preservation tests still pass
    - **Property 2: Preservation** - Backtest Unaffected, Optimize Non-Buggy Calls Unchanged, Download Data With Strategy Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 — do NOT write new tests
    - Run `tests/test_hyperopt_bugfix_preservation.py` against the fixed code
    - **EXPECTED OUTCOME**: All tests PASS (confirms no regressions)
    - Confirm backtest, non-buggy optimize, and download-data-with-strategy paths are all unaffected
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 4. Checkpoint — Ensure all tests pass
  - Run the full test suite: `pytest --tb=short`
  - Ensure `tests/test_hyperopt_bugfix_exploration.py` passes (all three bug conditions fixed)
  - Ensure `tests/test_hyperopt_bugfix_preservation.py` passes (no regressions)
  - Run `ruff check app/core/freqtrade/commands.py app/core/freqtrade/runners/optimize_runner.py app/core/freqtrade/runners/download_data_runner.py app/core/models/command_models.py` and fix any lint issues
  - Ask the user if any questions arise
