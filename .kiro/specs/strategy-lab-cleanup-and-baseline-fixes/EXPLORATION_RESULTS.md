# Exploratory Bug Condition Testing Results

## Phase 1: Confirmation of Bugs in Unfixed Code

All exploratory tests **FAILED as expected**, confirming that the bugs exist in the unfixed code.

### Bug 1: Duplicate _update_state_machine() in loop_page.py

**Counterexample Found:**
- File: `app/ui/pages/loop_page.py`
- Method: `_update_state_machine`
- Definitions found: **2**
- Line numbers: **695, 1343**
- Status: ✅ Bug confirmed - duplicate method definitions exist

### Bug 2: Duplicate Gate Runner Methods in loop_service.py

**Counterexamples Found:**

1. **_run_oos_gate()**
   - File: `app/core/services/loop_service.py`
   - Definitions found: **2**
   - Line numbers: **791, 1874**
   - Status: ✅ Bug confirmed

2. **_run_walk_forward_gate()**
   - File: `app/core/services/loop_service.py`
   - Definitions found: **2**
   - Line numbers: **875, 1912**
   - Status: ✅ Bug confirmed

3. **_run_stress_gate()**
   - File: `app/core/services/loop_service.py`
   - Definitions found: **2**
   - Line numbers: **964, 1948**
   - Status: ✅ Bug confirmed

4. **_run_consistency_gate()**
   - File: `app/core/services/loop_service.py`
   - Definitions found: **2**
   - Line numbers: **1020, 1972**
   - Status: ✅ Bug confirmed

### Bug 3: build_backtest_command() Parameter Mismatch

**Counterexample Found:**
- Function: `build_backtest_command()`
- Invalid kwargs attempted: `export_dir`, `config_file`, `strategy_file`
- Error: `TypeError: build_backtest_command() got an unexpected keyword argument 'export_dir'`
- Status: ✅ Bug confirmed - function signature mismatch

### Bug 4: ProcessService.execute_command() Parameter Mismatch

**Counterexample Found:**
- Method: `ProcessService.execute_command()`
- Invalid kwargs attempted: `cwd`, `on_stdout`, `on_stderr`
- Error: `TypeError: ProcessService.execute_command() got an unexpected keyword argument 'cwd'`
- Status: ✅ Bug confirmed - parameter name mismatch

### Bug 5: Callback Signature Mismatch

**Counterexample Found:**
- Method: `_on_baseline_backtest_finished()`
- File: `app/ui/pages/loop_page.py`
- Current signature: `(self, exit_code: int, exit_status: str)` - **2 parameters**
- Expected signature: `(self, exit_code: int)` - **1 parameter**
- Status: ✅ Bug confirmed - callback signature mismatch with ProcessService convention

## Summary

All 5 bugs have been confirmed through exploratory testing:
- ✅ Bug 1: Duplicate _update_state_machine() (2 definitions at lines 695, 1343)
- ✅ Bug 2: Duplicate gate methods (4 methods with 2 definitions each)
- ✅ Bug 3: build_backtest_command() parameter mismatch (TypeError on export_dir)
- ✅ Bug 4: execute_command() parameter mismatch (TypeError on cwd)
- ✅ Bug 5: Callback signature mismatch (2 params instead of 1)

**Next Step:** Proceed to Phase 2 (Preservation Property Tests) and Phase 3 (Implementation).
