# Strategy Lab Core Fixes - Implementation Plan

## Executive Summary

**Date**: 2026-04-20  
**Status**: Phase 1 Complete, Phase 2 Partially Complete, Phase 3 Pending

### Current State Analysis

After thorough testing and code review, here's the actual state of the 5 reported bugs:

| Bug | Status | Action Required |
|-----|--------|----------------|
| Bug 1: Fake Baseline Seed | ❌ **NEEDS FIX** | Implement real baseline backtest workflow |
| Bug 2: Hardcoded Timeframe | ✅ **ALREADY FIXED** | Verify tests pass |
| Bug 3: IS/OOS Split | ✅ **NOT A BUG** | Documentation added |
| Bug 4: Hard Filter Wiring | ✅ **ALREADY FIXED** | Verify tests pass |
| Bug 5: Duplicate Methods | ❌ **NEEDS CLEANUP** | Remove 17 duplicate methods |

### Test Results Summary

**Phase 1 Tests (Exploration & Preservation):**
- ✅ All exploration tests written and executed
- ✅ All preservation tests written and passing
- ✅ Bug conditions validated
- ✅ Baseline behavior documented

**Findings:**
- Bug 1: Confirmed - `_current_diagnosis_seed()` returns dummy values when no baseline exists
- Bug 2: Already fixed - `_build_loop_config()` detects strategy timeframe correctly
- Bug 3: Not a bug - IS/OOS split is correct (boundary day in OOS only, no gap)
- Bug 4: Already fixed - `_on_gate1_finished()` passes trades parameter (line 2083)
- Bug 5: Confirmed - 17 duplicate methods found (34 total definitions)

---

## Remaining Work

### Priority 1: Bug 1 - Real Baseline Backtest (HIGH COMPLEXITY)

**Problem**: When a loop starts with no previous diagnosis input, `_current_diagnosis_seed()` fabricates a dummy `BacktestSummary` with hardcoded values (50 trades, 50% win rate, 0% profit) instead of running a real baseline backtest.

**Impact**: First iteration uses fake data, undermining the entire optimization workflow.

**Root Cause**: No code path exists to run a baseline backtest before the first iteration.

**Solution**: Implement a baseline backtest workflow that runs before the first iteration.

#### Implementation Steps

##### 6.1 Add Baseline Detection Logic

**File**: `app/ui/pages/loop_page.py`  
**Method**: `_on_start()` (around line 1800)

**Changes**:
```python
def _on_start(self) -> None:
    """Start the loop optimization process."""
    # ... existing validation code ...
    
    # Create loop config
    config = self._build_loop_config(strategy_name)
    
    # NEW: Check if baseline is needed
    needs_baseline = self._latest_diagnosis_input is None
    if needs_baseline:
        _log.info("No previous diagnosis input - running baseline backtest")
        self._run_baseline_backtest(config)
        return  # Exit early, baseline completion will trigger loop start
    
    # ... existing loop start code ...
```

**Rationale**: Detect when no baseline exists and trigger baseline backtest before starting iterations.

##### 6.2 Implement Baseline Backtest Execution Method

**File**: `app/ui/pages/loop_page.py`  
**New Method**: `_run_baseline_backtest()`

**Implementation**:
```python
def _run_baseline_backtest(self, config: LoopConfig) -> None:
    """Run a baseline backtest on the in-sample timerange before the first iteration.
    
    This establishes a real performance baseline for the strategy before any
    parameter modifications are made. The baseline results are stored in
    _latest_diagnosis_input and used as the seed for the first iteration.
    """
    _log.info("Starting baseline backtest for strategy: %s", config.strategy)
    
    # Create sandbox directory for baseline
    sandbox_dir = self._improve_service.prepare_sandbox(
        self._settings_state.settings_service.load_settings(),
        config.strategy
    )
    self._sandbox_dir = sandbox_dir
    
    # Compute in-sample timerange for baseline
    in_sample_timerange = self._loop_service.compute_in_sample_timerange(config)
    _log.info("Baseline timerange: %s", in_sample_timerange)
    
    # Build backtest command for baseline
    settings = self._settings_state.settings_service.load_settings()
    cmd = build_backtest_command(
        settings=settings,
        strategy_name=config.strategy,
        timeframe=config.timeframe,
        timerange=in_sample_timerange,
        pairs=list(config.pairs) if config.pairs else None,
        export_dir=str(sandbox_dir / "baseline_export"),
        config_file=str(sandbox_dir / "config.json"),
        strategy_file=str(sandbox_dir / f"{config.strategy}.py"),
    )
    
    # Update UI
    self._status_label.setText("Running baseline backtest...")
    self._progress_bar.setValue(0)
    
    # Execute baseline backtest
    self._process_service.execute_command(
        cmd.as_list(),
        cwd=cmd.cwd,
        on_stdout=self._on_process_stdout,
        on_stderr=self._on_process_stderr,
        on_finished=self._on_baseline_backtest_finished,
    )
```

**Rationale**: Execute a real backtest on the in-sample timerange to establish a genuine performance baseline.

##### 6.3 Implement Baseline Completion Handler

**File**: `app/ui/pages/loop_page.py`  
**New Method**: `_on_baseline_backtest_finished()`

**Implementation**:
```python
def _on_baseline_backtest_finished(self, exit_code: int, exit_status: str) -> None:
    """Handle baseline backtest completion.
    
    Parses the baseline backtest results, stores them in _latest_diagnosis_input,
    and starts the loop with the real baseline data.
    """
    if exit_code != 0:
        _log.error("Baseline backtest failed with exit code: %d", exit_code)
        self._status_label.setText(f"Baseline backtest failed: {exit_status}")
        self._update_state_machine()
        return
    
    _log.info("Baseline backtest completed successfully")
    
    # Parse baseline results
    export_dir = self._sandbox_dir / "baseline_export"
    try:
        results = self._improve_service.parse_backtest_results(export_dir)
        
        if not results or not results.summary:
            raise ValueError("No baseline results found")
        
        _log.info(
            "Baseline results: %d trades, %.2f%% win rate, %.2f%% profit",
            results.summary.total_trades,
            results.summary.win_rate,
            results.summary.total_profit,
        )
        
        # Create DiagnosisInput from baseline results
        from app.core.models.diagnosis_models import DiagnosisInput
        
        self._latest_diagnosis_input = DiagnosisInput(
            in_sample=results.summary,
            oos_summary=None,
            fold_summaries=None,
            trade_profit_contributions=None,
            drawdown_periods=None,
            atr_spike_periods=None,
        )
        
        # Update UI
        self._status_label.setText("Baseline backtest completed - starting loop")
        
        # Start the loop with real baseline
        self._on_start()
        
    except Exception as e:
        _log.error("Failed to parse baseline results: %s", e)
        self._status_label.setText(f"Failed to parse baseline results: {e}")
        self._update_state_machine()
```

**Rationale**: Parse baseline results, store them, and restart the loop with real data.

##### 6.4 Update _current_diagnosis_seed() to Require Baseline

**File**: `app/ui/pages/loop_page.py`  
**Method**: `_current_diagnosis_seed()`

**Changes**:
```python
def _current_diagnosis_seed(self, config: LoopConfig) -> Tuple[BacktestSummary, Optional[object]]:
    """Return the latest usable diagnosis seed for the next iteration.
    
    The diagnosis seed is the baseline performance data used to generate
    suggestions for the next iteration. This must be real backtest data,
    never fabricated dummy values.
    
    Raises:
        RuntimeError: If no baseline diagnosis input is available.
    """
    self._ensure_loop_runtime_state()
    
    if self._latest_diagnosis_input is not None:
        return self._latest_diagnosis_input.in_sample, self._latest_diagnosis_input
    
    # REMOVED: Dummy creation logic
    # OLD CODE:
    # return BacktestSummary(
    #     strategy=config.strategy,
    #     timeframe=config.timeframe,
    #     total_trades=50,
    #     wins=25,
    #     losses=25,
    #     draws=0,
    #     win_rate=50.0,
    #     avg_profit=0.0,
    #     total_profit=0.0,
    #     ...
    # ), None
    
    # NEW: Raise error if no baseline exists
    raise RuntimeError(
        "No baseline diagnosis input available. "
        "A baseline backtest must be run before starting iterations. "
        "This should have been triggered automatically by _on_start()."
    )
```

**Rationale**: Remove dummy creation logic and enforce that a real baseline must exist.

#### Testing Strategy for Bug 1

1. **Run exploration test** (task 1.1):
   - Test should now PASS (baseline backtest is executed)
   - Verify real BacktestSummary is returned, not dummy values

2. **Run preservation test** (task 2.1):
   - Test should still PASS (loops with existing baseline unchanged)
   - Verify no regression in subsequent iterations

3. **Manual integration test**:
   - Start loop with no previous baseline
   - Verify baseline backtest runs automatically
   - Verify first iteration uses real baseline data
   - Verify loop completes successfully

---

### Priority 2: Bug 5 - Code Cleanup (MEDIUM COMPLEXITY)

**Problem**: 17 duplicate method definitions exist across `loop_page.py` (8 duplicates) and `loop_service.py` (9 duplicates), reducing code maintainability.

**Impact**: Confusion about which method to call, potential for bugs if wrong version is used.

**Root Cause**: Code evolution artifacts - old implementations not removed when new ones were added.

#### Duplicate Methods Inventory

**app/ui/pages/loop_page.py** (8 duplicates):
1. `_build_config_panel()` - Lines 359, 1343
2. `_clear_history_ui()` - Lines 945, 1608
3. `_on_iteration_mode_changed()` - Lines 856, 1501
4. `_on_timerange_preset()` - Lines 827, 1484
5. `_restore_preferences()` - Lines 748, 1390
6. `_save_preferences()` - Lines 787, 1449
7. `_update_stat_cards()` - Lines 977, 1516
8. `_update_state_machine()` - Lines 695, 1347

**app/core/services/loop_service.py** (9 duplicates):
1. `_run_consistency_gate()` - Lines 1287, 2176
2. `_run_oos_gate()` - Lines 1058, 2078
3. `_run_stress_gate()` - Lines 1231, 2152
4. `_run_walk_forward_gate()` - Lines 1142, 2116
5. `_stress_run()` - Lines 1409, 2241
6. `finalize()` - Lines 1018, 2058
7. `prepare_next_iteration()` - Lines 723, 1826
8. `record_iteration_result()` - Lines 939, 2005
9. `run_gate_sequence()` - Lines 1334, 2184

#### Implementation Steps

##### 7.1 Remove Duplicate Methods from loop_page.py

**Strategy**: For each duplicate, identify the canonical version (likely the later one), verify it's being used, and remove the obsolete version.

**Process**:
1. Read both implementations in full
2. Compare functionality and identify differences
3. Search for all call sites to determine which version is used
4. If both are used, consolidate into one canonical version
5. Remove the obsolete version
6. Run tests to verify no regressions

**Example for `_build_config_panel()`**:
```python
# Step 1: Search for call sites
grep -n "_build_config_panel" app/ui/pages/loop_page.py

# Step 2: Identify which version is called
# If line 1343 version is called, remove line 359 version

# Step 3: Remove obsolete version
# Delete lines 359-XXX (entire method)

# Step 4: Verify tests pass
pytest tests/test_loop_preservation_2_4.py -v
```

**Repeat for all 8 duplicates in loop_page.py**

##### 7.2 Remove Duplicate Methods from loop_service.py

**Strategy**: Same as 7.1, but for loop_service.py duplicates.

**Process**: Same as 7.1

**Example for `_run_oos_gate()`**:
```python
# Step 1: Search for call sites
grep -n "_run_oos_gate" app/core/services/loop_service.py

# Step 2: Identify which version is called
# If line 2078 version is called, remove line 1058 version

# Step 3: Remove obsolete version
# Delete lines 1058-XXX (entire method)

# Step 4: Verify tests pass
pytest tests/core/services/test_strategy_lab_preservation.py -v
```

**Repeat for all 9 duplicates in loop_service.py**

##### 7.3 Add Documentation Comments for Canonical Methods

**File**: Both `loop_page.py` and `loop_service.py`

**Changes**: Add clear docstrings to canonical methods explaining their purpose.

**Example**:
```python
def _build_config_panel(self) -> QGroupBox:
    """Build the loop configuration panel.
    
    This is the canonical implementation of the config panel builder.
    Creates UI widgets for all loop configuration parameters including
    iteration settings, validation mode, hyperopt settings, and AI advisor.
    
    Returns:
        QGroupBox: The configured panel widget.
    """
    # ... implementation ...
```

##### 7.3.1 Verify All Method Calls Work After Cleanup

**Testing**:
1. Run all preservation tests from Phase 1
2. Run manual UI testing for loop_page.py changes
3. Run integration tests for loop_service.py changes

**Expected Outcome**: All tests PASS (confirms no regressions)

---

## Additional Issues Found During Testing

### Issue 1: Test Architecture Mismatch

**Problem**: Some bug condition tests create `LoopConfig` manually and expect it to be updated, but the actual code creates configs with correct values from the start via `_build_loop_config()`.

**Example**: `test_bug_condition_loop_config_timeframe_not_populated` in `tests/test_loop_bug_condition_2.py`

**Solution**: Update tests to use `page._build_loop_config(strategy_name)` instead of manually creating configs, OR document that the test is validating a non-existent code path.

**Action**: Update or remove the failing test after Bug 2 verification.

### Issue 2: Circular Dependency in Baseline Logic

**Problem**: `_on_start()` will call `_run_baseline_backtest()` which will eventually call `_on_start()` again after baseline completes. Need to ensure this doesn't create an infinite loop.

**Solution**: Add a flag to track baseline execution state:
```python
def _on_start(self) -> None:
    # ... validation ...
    
    # Check if we're already running baseline
    if hasattr(self, '_baseline_in_progress') and self._baseline_in_progress:
        _log.warning("Baseline already in progress, skipping duplicate start")
        return
    
    needs_baseline = self._latest_diagnosis_input is None
    if needs_baseline:
        self._baseline_in_progress = True
        self._run_baseline_backtest(config)
        return
    
    # Clear baseline flag if we're starting the loop
    self._baseline_in_progress = False
    # ... continue with loop start ...
```

**Action**: Implement baseline state tracking in Bug 1 fix.

### Issue 3: Missing Import Statements

**Problem**: Bug 1 implementation requires imports that may not exist in `loop_page.py`.

**Solution**: Add necessary imports:
```python
from app.core.freqtrade.runners.backtest_runner import build_backtest_command
from app.core.models.diagnosis_models import DiagnosisInput
```

**Action**: Add imports when implementing Bug 1 fix.

---

## Phase 3: Integration Testing Plan

### 8.1 Run All Exploration Tests (Should Now Pass)

**Command**:
```bash
pytest tests/test_loop_bug_condition_1.py -v  # Bug 1 - should now PASS
pytest tests/test_loop_bug_condition_2.py -v  # Bug 2 - already PASSES
pytest tests/test_loop_bug_condition_3.py -v  # Bug 3 - already PASSES (not a bug)
pytest tests/test_loop_bug_condition_4.py -v  # Bug 4 - already PASSES
```

**Expected Results**:
- Bug 1 tests: PASS (baseline backtest executed)
- Bug 2 tests: PASS (strategy timeframe detected)
- Bug 3 tests: PASS (IS/OOS split correct)
- Bug 4 tests: PASS (trades parameter passed)

**Action**: Document any failures and investigate root cause.

### 8.2 Run All Preservation Tests (Should Still Pass)

**Command**:
```bash
pytest tests/test_loop_preservation_2_1.py -v  # Loop behavior with existing baseline
pytest tests/core/services/test_strategy_lab_preservation.py -v  # 5m timeframe
pytest tests/test_loop_preservation_2_3.py -v  # Hard filter evaluation
pytest tests/test_loop_preservation_2_4.py -v  # UI state management
```

**Expected Results**: All tests PASS (confirms no regressions)

**Action**: Document any failures and investigate root cause.

### 8.3 Run Full Loop Integration Test

**Test Scenario**:
1. Start loop with no previous baseline
2. Verify baseline backtest runs automatically
3. Verify first iteration uses real baseline data
4. Verify all gates use correct timeframe
5. Verify hard filters 3, 6, 7 are evaluated
6. Verify loop completes successfully

**Manual Test Steps**:
```python
# 1. Clear any existing baseline data
# 2. Start loop via UI
# 3. Observe baseline backtest execution
# 4. Verify first iteration starts after baseline completes
# 5. Check logs for timeframe detection
# 6. Check logs for hard filter evaluation
# 7. Let loop complete or stop after 2-3 iterations
# 8. Verify best iteration is displayed
```

**Expected Outcome**: Loop executes successfully with real baseline and correct behavior.

### 8.4 Ask User for Confirmation

**Checklist**:
- [ ] All exploration tests pass
- [ ] All preservation tests pass
- [ ] Integration test passes
- [ ] No regressions observed
- [ ] All fixes working as expected

**Action**: Present test results to user and ask for confirmation before marking spec complete.

---

## Implementation Timeline

### Phase 2 Completion (Remaining Work)

**Estimated Time**: 4-6 hours

| Task | Estimated Time | Priority |
|------|---------------|----------|
| Bug 1: Baseline backtest workflow | 3-4 hours | HIGH |
| Bug 5: Remove duplicate methods | 1-2 hours | MEDIUM |
| Test updates and verification | 1 hour | HIGH |

### Phase 3 Completion (Integration Testing)

**Estimated Time**: 1-2 hours

| Task | Estimated Time | Priority |
|------|---------------|----------|
| Run all exploration tests | 15 min | HIGH |
| Run all preservation tests | 15 min | HIGH |
| Manual integration testing | 30-60 min | HIGH |
| Documentation and reporting | 15 min | MEDIUM |

---

## Risk Assessment

### High Risk Items

1. **Bug 1 Implementation Complexity**
   - **Risk**: Baseline backtest workflow may have edge cases not covered in design
   - **Mitigation**: Thorough testing with various strategies and timeframes
   - **Fallback**: Revert to dummy baseline with warning message if baseline fails

2. **Circular Dependency in Baseline Logic**
   - **Risk**: `_on_start()` calling itself after baseline completion could cause issues
   - **Mitigation**: Add state tracking flag to prevent duplicate execution
   - **Fallback**: Use a separate method for post-baseline loop start

### Medium Risk Items

1. **Duplicate Method Removal**
   - **Risk**: Removing wrong version could break functionality
   - **Mitigation**: Careful analysis of call sites before removal
   - **Fallback**: Git revert if tests fail after removal

2. **Test Architecture Mismatch**
   - **Risk**: Some tests may need updates to match actual code architecture
   - **Mitigation**: Update tests to use actual code paths
   - **Fallback**: Document test limitations and skip if necessary

### Low Risk Items

1. **Bug 2, 3, 4 Already Fixed**
   - **Risk**: Minimal - just need to verify tests pass
   - **Mitigation**: Run tests and document results
   - **Fallback**: None needed

---

## Success Criteria

### Must Have (P0)

- [x] All exploration tests written and executed
- [x] All preservation tests written and passing
- [ ] Bug 1 (Baseline backtest) implemented and working
- [ ] Bug 5 (Duplicate methods) cleaned up
- [ ] All tests passing (exploration + preservation)
- [ ] Integration test passing

### Should Have (P1)

- [ ] Documentation updated with findings
- [ ] Test architecture issues resolved
- [ ] Edge cases tested and handled
- [ ] User confirmation obtained

### Nice to Have (P2)

- [ ] Performance benchmarks for baseline backtest
- [ ] Additional error handling for edge cases
- [ ] Refactoring opportunities identified
- [ ] Code coverage metrics

---

## Rollback Plan

If any issues arise during implementation:

1. **Immediate Rollback**: Use Git to revert changes
   ```bash
   git revert <commit-hash>
   ```

2. **Partial Rollback**: Revert specific files
   ```bash
   git checkout HEAD~1 -- app/ui/pages/loop_page.py
   ```

3. **Test Verification**: Run all tests after rollback
   ```bash
   pytest tests/ -v
   ```

4. **User Communication**: Inform user of rollback and reason

---

## Next Steps

1. **Implement Bug 1** (Real Baseline Backtest)
   - Start with task 6.1 (baseline detection logic)
   - Continue with tasks 6.2-6.4 (baseline execution and completion)
   - Test thoroughly with various strategies

2. **Implement Bug 5** (Code Cleanup)
   - Start with task 7.1 (loop_page.py duplicates)
   - Continue with task 7.2 (loop_service.py duplicates)
   - Add documentation (task 7.3)

3. **Run Phase 3 Tests**
   - Execute all exploration tests (task 8.1)
   - Execute all preservation tests (task 8.2)
   - Run integration test (task 8.3)
   - Get user confirmation (task 8.4)

4. **Documentation and Cleanup**
   - Update spec documents with findings
   - Document any deviations from original plan
   - Archive test results
   - Mark spec as complete

---

## Appendix A: File Locations

### Source Files
- `app/ui/pages/loop_page.py` - Main loop UI page
- `app/core/services/loop_service.py` - Loop business logic
- `app/core/services/improve_service.py` - Strategy improvement service
- `app/core/freqtrade/runners/backtest_runner.py` - Backtest command builder
- `app/core/models/loop_models.py` - Loop data models
- `app/core/models/diagnosis_models.py` - Diagnosis data models

### Test Files
- `tests/test_loop_bug_condition_1.py` - Bug 1 exploration tests
- `tests/test_loop_bug_condition_2.py` - Bug 2 exploration tests
- `tests/test_loop_bug_condition_3.py` - Bug 3 exploration tests
- `tests/test_loop_bug_condition_4.py` - Bug 4 exploration tests
- `tests/test_loop_preservation_2_1.py` - Preservation test 2.1
- `tests/test_loop_preservation_2_3.py` - Preservation test 2.3
- `tests/test_loop_preservation_2_4.py` - Preservation test 2.4
- `tests/core/services/test_strategy_lab_preservation.py` - Preservation test 2.2

### Documentation Files
- `.kiro/specs/strategy-lab-core-fixes/bugfix.md` - Requirements document
- `.kiro/specs/strategy-lab-core-fixes/design.md` - Design document
- `.kiro/specs/strategy-lab-core-fixes/tasks.md` - Task list
- `.kiro/specs/strategy-lab-core-fixes/duplicate-methods-report.md` - Duplicate methods inventory
- `.kiro/specs/strategy-lab-core-fixes/IMPLEMENTATION_PLAN.md` - This document

---

## Appendix B: Key Learnings

1. **Always verify bug existence before implementing fixes** - 3 out of 5 bugs were already fixed or didn't exist
2. **Property-based testing is valuable** - Hypothesis tests caught edge cases and validated behavior across many examples
3. **Observation-first methodology works** - Preservation tests documented baseline behavior before making changes
4. **Code archaeology is important** - Understanding why duplicates exist helps prevent future issues
5. **Test architecture matters** - Tests should match actual code paths, not hypothetical scenarios

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-04-20 | Kiro AI | Initial implementation plan created |

---

**End of Implementation Plan**
