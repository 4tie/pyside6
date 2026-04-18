# Tasks

## Task List

- [x] 1. Add `max_open_trades` parameter to `PairsSelectorDialog` constructor
  - [x] 1.1 Add `max_open_trades: int = 1` parameter to `__init__` signature
  - [x] 1.2 Store it as `self.max_open_trades = max(1, max_open_trades)` in `__init__`
  - [x] 1.3 Initialise `self.locked_pairs: set[str] = set()` in `__init__`
  - [x] 1.4 Initialise `self.lock_buttons: dict[str, QPushButton] = {}` in `__init__`

- [x] 2. Add lock button factory and toggle handler
  - [x] 2.1 Implement `_make_lock_button(self, pair: str) -> QPushButton` — flat button, text `"🔒"` or `"🔓"` based on `locked_pairs`, connected to `_on_lock_clicked`
  - [x] 2.2 Implement `_on_lock_clicked(self, pair: str) -> None` — toggles `locked_pairs`, updates button text, ensures pair is checked when locked, calls `_update_count()`

- [x] 3. Update `_build_rows` to include lock button in each row
  - [x] 3.1 Call `_make_lock_button(pair)` for each pair and store in `self.lock_buttons`
  - [x] 3.2 Insert the lock button as the first widget in each row's `QHBoxLayout` (before the favorite button)

- [x] 4. Update `_on_add_custom` to create lock button for new custom pairs
  - [x] 4.1 Call `_make_lock_button(pair)` for each newly added custom pair
  - [x] 4.2 Store the new lock button in `self.lock_buttons[pair]`
  - [x] 4.3 Insert the lock button as the first widget in the new row's layout

- [x] 5. Implement `_randomize_pairs` method
  - [x] 5.1 Compute `visible_pairs` from `self.all_pairs` filtered by `row_widgets[p].isVisible()`
  - [x] 5.2 Partition into `locked_visible` and `pool`
  - [x] 5.3 Compute `slots_needed = self.max_open_trades - len(locked_visible)`
  - [x] 5.4 Sample from pool: empty list if `slots_needed <= 0`, all pool if `len(pool) <= slots_needed`, else `random.sample(pool, slots_needed)`
  - [x] 5.5 Build `new_selection = set(locked_visible) | set(sampled)`
  - [x] 5.6 Apply to checkboxes with `blockSignals(True/False)` around each update
  - [x] 5.7 Call `self._update_selected()` to sync `self.selected` and count label

- [x] 6. Add Randomize button to the dialog UI
  - [x] 6.1 Create `self.randomize_btn = QPushButton(f"🎲 Randomize ({self.max_open_trades})")` in `init_ui`
  - [x] 6.2 Connect `randomize_btn.clicked` to `self._randomize_pairs`
  - [x] 6.3 Add `randomize_btn` to the action row layout (alongside Select All / Deselect All)

- [x] 7. Update `BacktestPage._on_select_pairs` to pass `max_open_trades`
  - [x] 7.1 Pass `max_open_trades=self.max_open_trades.value()` when constructing `PairsSelectorDialog`

- [x] 8. Update `OptimizePage._on_select_pairs` to pass `max_open_trades`
  - [x] 8.1 Identify the `max_open_trades` value in `OptimizePage` (read from `BacktestPreferences` or a local spinbox)
  - [x] 8.2 Pass `max_open_trades=<value>` when constructing `PairsSelectorDialog`

- [x] 9. Write property-based tests for `_randomize_pairs` logic
  - [x] 9.1 Set up a minimal `PairsSelectorDialog` test fixture (headless, no display required) or extract pure randomize logic into a testable helper
  - [x] 9.2 Write Property 2 test: lock preservation — locked visible pairs always in selection (`hypothesis`)
  - [x] 9.3 Write Property 3 test: selection size equals `max_open_trades` when pool is large enough (`hypothesis`)
  - [x] 9.4 Write Property 4 test: all pool pairs included when pool < slots (`hypothesis`)
  - [x] 9.5 Write Property 5 test: only locked pairs selected when `slots_needed <= 0` (`hypothesis`)
  - [x] 9.6 Write Property 6 test: no duplicates in selection (`hypothesis`)
  - [x] 9.7 Write Property 7 test: selection is a subset of `all_pairs` (`hypothesis`)

- [x] 10. Write property-based tests for lock toggle behaviour
  - [x] 10.1 Write Property 8 test: locking adds pair to `locked_pairs` and checks checkbox (`hypothesis`)
  - [x] 10.2 Write Property 9 test: unlocking removes pair from `locked_pairs` without changing checkbox state (`hypothesis`)
  - [x] 10.3 Write Property 10 test: lock button icon always matches lock state (`hypothesis`)

- [x] 11. Write unit tests for edge cases and examples
  - [x] 11.1 Test default `max_open_trades=1` when constructor argument is omitted (Requirement 1.2)
  - [x] 11.2 Test `max_open_trades=0` is clamped to 1 inside `_randomize_pairs` (Requirement 4.8)
  - [x] 11.3 Test `locked_pairs` is empty on fresh dialog construction (Requirement 6.1)
  - [x] 11.4 Test custom pair gets a lock button in unlocked state after `_on_add_custom` (Requirement 5.2)
  - [x] 11.5 Test Randomize button label equals `f"🎲 Randomize ({max_open_trades})"` (Property 1)

- [x] 12. Run full test suite and fix any regressions
  - [x] 12.1 Run `pytest --tb=short` and confirm all existing tests still pass
  - [x] 12.2 Run `ruff check . && ruff format .` and fix any lint issues
