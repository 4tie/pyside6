# Implementation Plan

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Resize Event Crashes With Broken super() Call
  - **CRITICAL**: This test MUST FAIL on unfixed code — failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior — it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the `AttributeError` crash
  - **Scoped PBT Approach**: Scope the property to the concrete failing case — a plain `QWidget` container receiving any non-`None` `QResizeEvent`
  - Construct a minimal `_reflow`-style closure that uses the broken `super(type(container), container).resizeEvent(event)` pattern
  - Use `@given(st.integers(min_value=100, max_value=1200))` to generate container widths, fire a synthetic `QResizeEvent` at the closure
  - Assert that `AttributeError: 'super' object has no attribute 'resizeEvent'` is raised for every generated width
  - Run test on UNFIXED code (swap the fixed line back to the broken one in the test fixture, or test the broken pattern directly)
  - **EXPECTED OUTCOME**: Test FAILS (i.e., the property assertion `pytest.raises(AttributeError)` holds — confirming the bug exists)
  - Document counterexample found: `_reflow(QResizeEvent(...))` on a plain `QWidget` raises `AttributeError`
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Non-Resize-Event Paths Produce Identical Badge Layout
  - **IMPORTANT**: Follow observation-first methodology — run the `event=None` path on the current (fixed) code and record observed outputs, then encode those as property assertions
  - Observe: `_reflow(event=None)` on a container of width 400 with pairs `["BTC/USDT", "ETH/USDT"]` positions both badges on row 0 starting at x=0
  - Observe: `_build_pairs_widget([])` returns a `QLabel` with text `"—"` and no container is created
  - Observe: `container.minimumHeight()` is at least 28 after any `_reflow(None)` call
  - Write property-based test using `@given(st.lists(st.text(min_size=3, max_size=12, alphabet=st.characters(whitelist_categories=("Lu","Ll","Nd"), whitelist_characters="/")), min_size=1, max_size=20), st.integers(min_value=100, max_value=1200))` — for each `(pairs, width)`, assert badge geometries from `_reflow(None)` are identical between the original and fixed closures
  - Write unit test: `_build_pairs_widget([])` returns a `QLabel` with `.text() == "—"`
  - Write unit test: for any non-empty pairs list, `container.minimumHeight() >= 28` after `_reflow(None)`
  - Verify all tests PASS on the current (fixed) code before proceeding
  - **EXPECTED OUTCOME**: Tests PASS (confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 3. Fix for resize event crash in `_build_pairs_widget._reflow`

  - [x] 3.1 Implement the fix
    - In `app/ui/pages/results_page.py`, inside the `_reflow` closure in `_build_pairs_widget`, replace:
      ```python
      super(type(container), container).resizeEvent(event)
      ```
      with:
      ```python
      QWidget.resizeEvent(container, event)
      ```
    - No other changes — the reflow geometry logic, `container.resizeEvent = _reflow` assignment, initial `_reflow()` call, and empty-pairs guard are all correct
    - _Bug_Condition: `isBugCondition(container, event)` — `event is not None` AND `type(container) is QWidget` (not a subclass); `super(QWidget, container)` resolves to `QObject` which has no `resizeEvent`_
    - _Expected_Behavior: `QWidget.resizeEvent(container, event)` is called without raising any exception; all badge labels are subsequently repositioned in the flow-wrap layout_
    - _Preservation: `_reflow(event=None)` path unchanged; empty-pairs path unchanged; badge reflow geometry logic unchanged; `container.minimumHeight()` update unchanged_
    - _Requirements: 2.1, 2.2, 3.1, 3.2, 3.3_

  - [x] 3.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Resize Event Forwarded Without Exception
    - **IMPORTANT**: Re-run the SAME test from task 1 — do NOT write a new test
    - The test from task 1 encodes the expected behavior (no `AttributeError` raised)
    - When this test passes, it confirms `QWidget.resizeEvent(container, event)` is called successfully
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - _Requirements: 2.1, 2.2_

  - [x] 3.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Non-Resize-Event Paths Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 — do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions in `event=None` path, empty-pairs path, and badge geometry logic)
    - Confirm all tests still pass after fix (no regressions)

- [x] 4. Checkpoint — Ensure all tests pass
  - Run `pytest --tb=short` and confirm all tests in the results-page resize suite pass
  - Ensure all tests pass; ask the user if questions arise
