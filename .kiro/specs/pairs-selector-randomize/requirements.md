# Requirements Document

## Introduction

This feature adds a **Randomize** button and per-pair **lock** toggle to `PairsSelectorDialog`. When the user clicks Randomize, the dialog automatically selects exactly `max_open_trades` pairs at random from the visible pool. Pairs that the user has locked are always kept in the selection and are excluded from the random pool; the remaining slots are filled by randomly sampling from the unlocked visible pairs. The `max_open_trades` value is passed in by the caller (`BacktestPage` and `OptimizePage`) at dialog construction time — no new service, state class, or model is required.

---

## Glossary

- **Dialog**: `PairsSelectorDialog` — the existing Qt dialog for selecting trading pairs.
- **Caller**: `BacktestPage` or `OptimizePage` — the page that constructs and opens the Dialog.
- **max_open_trades**: An integer ≥ 1 representing the maximum number of simultaneously open trades; determines how many pairs the Randomize action selects.
- **locked_pairs**: The set of pairs the user has explicitly locked inside the Dialog for the current session; these are always included in the selection after randomization.
- **pool**: The set of visible, unlocked pairs available for random sampling.
- **slots_needed**: `max_open_trades − len(locked_pairs ∩ visible_pairs)`; the number of pairs to sample from the pool.
- **Randomize_Button**: The `QPushButton` labelled `"🎲 Randomize (N)"` that triggers the randomization logic.
- **Lock_Button**: A flat `QPushButton` per row that toggles the lock state of a pair.
- **Randomize_Logic**: The pure function `_randomize_pairs()` inside the Dialog that computes the new selection.

---

## Requirements

### Requirement 1: Pass max_open_trades to the Dialog

**User Story:** As a developer, I want `max_open_trades` to be available inside `PairsSelectorDialog`, so that the Randomize feature knows how many pairs to select.

#### Acceptance Criteria

1. THE Dialog SHALL accept a `max_open_trades: int` constructor parameter with a default value of `1`.
2. WHEN `max_open_trades` is not supplied by the Caller, THE Dialog SHALL use `1` as the slot budget.
3. THE Caller (`BacktestPage`) SHALL pass `self.max_open_trades.value()` as `max_open_trades` when constructing the Dialog.
4. THE Caller (`OptimizePage`) SHALL pass `self.max_open_trades.value()` as `max_open_trades` when constructing the Dialog.

---

### Requirement 2: Randomize Button

**User Story:** As a user, I want a Randomize button in the pairs dialog, so that I can quickly get a random selection of pairs matching my max open trades setting.

#### Acceptance Criteria

1. THE Dialog SHALL display a `Randomize_Button` labelled `"🎲 Randomize (N)"` where N equals `max_open_trades`.
2. WHEN `max_open_trades` changes between dialog openings, THE Randomize_Button label SHALL reflect the current value of `max_open_trades`.
3. WHEN the user clicks `Randomize_Button`, THE Dialog SHALL invoke `Randomize_Logic` to compute a new selection.
4. WHEN `Randomize_Logic` completes, THE Dialog SHALL update all checkboxes to reflect the new selection without requiring the user to click OK first.
5. WHEN `Randomize_Logic` completes, THE Dialog SHALL update the selected-count label to reflect the new selection size.

---

### Requirement 3: Lock Toggle per Pair

**User Story:** As a user, I want to lock individual pairs in the dialog, so that those pairs are always kept when I randomize.

#### Acceptance Criteria

1. THE Dialog SHALL display a `Lock_Button` for every pair row, showing `"🔒"` when the pair is locked and `"🔓"` when it is unlocked.
2. WHEN the user clicks a `Lock_Button` for an unlocked pair, THE Dialog SHALL add that pair to `locked_pairs` and display `"🔒"` on its button.
3. WHEN the user clicks a `Lock_Button` for an unlocked pair, THE Dialog SHALL ensure that pair's checkbox is checked.
4. WHEN the user clicks a `Lock_Button` for a locked pair, THE Dialog SHALL remove that pair from `locked_pairs` and display `"🔓"` on its button.
5. WHEN a pair is removed from `locked_pairs`, THE Dialog SHALL leave that pair's checkbox state unchanged.
6. THE Dialog SHALL maintain `locked_pairs` as session-only state — it SHALL NOT persist lock state between dialog openings.

---

### Requirement 4: Randomize Logic — Selection Invariants

**User Story:** As a user, I want the randomization to always respect my max open trades and locked pairs, so that the result is predictable and useful.

#### Acceptance Criteria

1. WHEN `Randomize_Logic` runs, THE Dialog SHALL include all locked visible pairs in the new selection.
2. WHEN `Randomize_Logic` runs, THE Dialog SHALL sample exactly `slots_needed` pairs from the pool when `len(pool) >= slots_needed`.
3. WHEN `Randomize_Logic` runs and `len(pool) < slots_needed`, THE Dialog SHALL include all pool pairs in the new selection.
4. WHEN `Randomize_Logic` runs and `slots_needed <= 0`, THE Dialog SHALL select only the locked visible pairs and deselect all others.
5. WHEN `Randomize_Logic` runs, THE Dialog SHALL deselect all visible pairs that are neither locked nor sampled.
6. WHEN `Randomize_Logic` runs, THE Dialog SHALL NOT select more pairs than `max_open_trades` when `len(pool) >= slots_needed`.
7. WHEN `Randomize_Logic` runs, THE Dialog SHALL sample pairs without replacement from the pool.
8. IF `max_open_trades` is `0` or negative, THEN THE Dialog SHALL treat it as `1` inside `Randomize_Logic`.

---

### Requirement 5: Row Layout Update

**User Story:** As a developer, I want the lock button to be integrated into each pair row, so that the UI is consistent and the lock state is visually clear.

#### Acceptance Criteria

1. THE Dialog SHALL render each pair row in the order: `[Lock_Button] [Favorite_Button] [Checkbox]`.
2. WHEN a new custom pair is added via the custom-pairs input, THE Dialog SHALL create a `Lock_Button` for that row in the unlocked state.
3. WHEN the search filter is active, THE Dialog SHALL display `Lock_Button` only for visible rows.

---

### Requirement 6: No Persistence of Lock State

**User Story:** As a user, I want lock state to be session-only, so that I start fresh each time I open the dialog without unexpected pre-locked pairs.

#### Acceptance Criteria

1. WHEN the Dialog is opened, THE Dialog SHALL initialise `locked_pairs` as an empty set.
2. WHEN the Dialog is closed and reopened, THE Dialog SHALL NOT restore any previously locked pairs.

---

### Requirement 7: No New Dependencies or Models

**User Story:** As a developer, I want the feature implemented without adding new services, state classes, or external libraries, so that the codebase stays minimal.

#### Acceptance Criteria

1. THE Dialog SHALL implement randomization using only the Python standard library `random.sample`.
2. THE Dialog SHALL NOT introduce new Pydantic models, service classes, or state objects for this feature.
3. THE Dialog SHALL NOT persist lock state to `AppSettings` or any settings file.
