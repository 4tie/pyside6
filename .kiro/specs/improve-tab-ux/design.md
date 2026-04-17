# Design Document — Improve Tab UX

## Overview

This feature adds step-by-step guidance, contextual instructions, empty-state panels, improved text, tooltips, and a no-configuration guard to the existing `ImprovePage` in `app/ui/pages/improve_page.py`. The underlying service layer, diagnosis logic, and suggestion logic are untouched. All changes are confined to the UI layer.

The goal is to make the five-stage improvement workflow (Select → Analyze → Apply → Backtest → Decide) self-explanatory for first-time users without changing any behavior.

### Key Design Decisions

- **All new widgets live in `improve_page.py`** — no new files. The file already contains `AnimatedMetricCard`, `IssueBadge`, and `SuggestionRow` as module-level helper classes; the new widgets follow the same pattern.
- **Workflow state is tracked by a single integer `_workflow_step` (1–5)** on `ImprovePage`. All new widgets read from this value; advancing the step calls a single `_set_workflow_step(n)` method that updates both the `StepIndicator` and the `ContextBanner` atomically.
- **No new signals or state objects** — the existing `settings_changed` signal from `SettingsState` is sufficient for the no-configuration guard.
- **PySide6 only** — no third-party widget libraries. All styling uses inline `setStyleSheet` calls consistent with the existing palette constants.

---

## Architecture

The change is entirely within the UI layer. No service, model, or state layer files are modified.

```
app/ui/pages/improve_page.py
├── StepIndicator          (new module-level QWidget)
├── ContextBanner          (new module-level QWidget)
├── EmptyStatePanel        (new module-level QWidget)
├── AnimatedMetricCard     (existing — unchanged)
├── IssueBadge             (existing — unchanged)
├── SuggestionRow          (existing — unchanged)
└── ImprovePage            (existing — modified)
    ├── _workflow_step: int          (new instance var, 1–5)
    ├── _banner_dismissed: bool      (new instance var)
    ├── _step_indicator: StepIndicator
    ├── _context_banner: ContextBanner
    └── _set_workflow_step(n)        (new method)
```

### Workflow Step Transitions

```
Page load          → step 1 (Select)
Analyze success    → step 3 (Apply)   [step 2 complete]
Apply suggestion   → step 4 (Backtest) [step 3 complete]
Backtest complete  → step 5 (Decide)  [step 4 complete]
Accept / Reject    → step 1 (Select)  [reset]
```

---

## Components and Interfaces

### `StepIndicator(QWidget)`

Renders five labeled step nodes connected by horizontal lines.

```python
class StepIndicator(QWidget):
    STEPS = [
        (1, "Select"),
        (2, "Analyze"),
        (3, "Apply"),
        (4, "Backtest"),
        (5, "Decide"),
    ]

    def __init__(self, parent=None): ...

    def set_active_step(self, step: int) -> None:
        """Set the currently active step (1–5). Steps < active are complete."""
```

**Rendering rules:**
- Each step node is a `QLabel` with a circular indicator.
- State `complete` (step < active): dimmed text (`_C_TEXT_DIM`), "✓ " prefix.
- State `active` (step == active): accent color (`_C_GREEN`), bold font.
- State `pending` (step > active): dimmed text (`_C_TEXT_DIM`), no prefix.
- Connector lines between nodes: accent color for completed segments, border color (`_C_BORDER`) for pending segments.
- Fixed height of ~48px; stretches horizontally.

### `ContextBanner(QWidget)`

Dismissible instruction banner with per-step messages.

```python
BANNER_MESSAGES: Dict[int, str] = {
    1: "Choose a strategy and a saved backtest run, then click <b>Analyze Run</b> to detect performance issues.",
    2: "Review the detected issues and suggested parameter changes below.",
    3: "Click <b>Apply</b> on one or more suggestions to build your candidate configuration, then click <b>Run Candidate Backtest</b>.",
    4: "The candidate backtest is running. Wait for it to finish, then review the comparison.",
    5: "Compare the results. Click <b>Accept &amp; Save</b> to save the improvements, or <b>Reject &amp; Discard</b> to discard them.",
}

class ContextBanner(QWidget):
    def __init__(self, parent=None): ...

    def set_step(self, step: int) -> None:
        """Update the displayed message for the given step. No-op if dismissed."""

    def is_dismissed(self) -> bool:
        """Return True if the user has dismissed the banner this session."""
```

**Styling:** left border 3px solid `_C_GREEN`, background `_C_ELEVATED` (`#2d2d30`), text `_C_TEXT` at 12px. Dismiss button "✕" right-aligned; clicking sets `_dismissed = True` and hides the widget.

### `EmptyStatePanel(QWidget)`

Placeholder shown inside a group box when it has no data.

```python
class EmptyStatePanel(QWidget):
    def __init__(self, icon: str, text: str, hint: str, parent=None): ...
```

**Layout:** vertically centered column — icon `QLabel` at 28px, main text `QLabel` at 13px in `_C_TEXT_DIM`, hint `QLabel` at 11px italic in `_C_TEXT_DIM`. All center-aligned. Minimum height 80px.

### `ImprovePage` modifications

New instance variables:
```python
self._workflow_step: int = 1
self._banner_dismissed: bool = False
self._step_indicator: StepIndicator
self._context_banner: ContextBanner
```

New method:
```python
def _set_workflow_step(self, step: int) -> None:
    """Advance the workflow to the given step and sync all guidance widgets."""
    self._workflow_step = step
    self._step_indicator.set_active_step(step)
    self._context_banner.set_step(step)
```

Modified methods (behavior unchanged, text/labels updated):
- `_init_ui` — inserts `StepIndicator` and `ContextBanner` at top; adds `EmptyStatePanel` instances to each group box; renames buttons and group box titles; adds tooltips; adds subtitle labels.
- `_on_analyze` — calls `_set_workflow_step(3)` on success; updates status message text.
- `_on_apply_suggestion` — calls `_set_workflow_step(4)` on first non-advisory apply.
- `_on_candidate_finished` — calls `_set_workflow_step(5)` on success; updates status message text.
- `_on_accept` — calls `_set_workflow_step(1)` after saving; updates status message text.
- `_on_reject` — calls `_set_workflow_step(1)`; updates status message text.
- `_on_rollback` — updates status message text (step stays at 1 or wherever appropriate).
- `_refresh_strategies` / `_refresh_runs` — check `user_data_path` and show/hide no-config banner.

---

## Data Models

No new data models. The workflow step is a plain `int` (1–5) stored on `ImprovePage`. The dismissed state is a plain `bool` stored on `ContextBanner`.

### Button / Label Text Mapping

| Old text | New text |
|---|---|
| `⚡ Analyze` | `⚡ Analyze Run` |
| `Load Latest` | `↓ Load Latest Run` |
| `▶  Run Backtest on Candidate` | `▶ Run Candidate Backtest` |
| `↺  Reset Candidate` | `↺ Reset to Baseline` |
| `Accept` | `✅ Accept & Save` |
| `Reject` | `✕ Reject & Discard` |
| `Rollback` | `↩ Rollback to Previous` |

### Group Box Title Mapping

| Old title | New title |
|---|---|
| `Detected Issues` | `Detected Issues (N)` when N > 0 |
| `Suggested Actions` | `Suggested Actions (N)` when N > 0 |
| `Candidate Preview` | `Candidate Changes` |
| `Comparison` | `Results Comparison` |

### Status Message Mapping

| Trigger | Message | Color |
|---|---|---|
| Analyze clicked | `⏳ Loading run — please wait…` | `_C_GREEN` |
| Analysis complete, N issues | `✅ Analysis complete — {N} issue(s) found. Review suggestions below and click Apply.` | `_C_GREEN_LIGHT` |
| Analysis complete, 0 issues | `✅ Analysis complete — no issues detected. Your strategy looks healthy!` | `_C_GREEN_LIGHT` |
| Candidate backtest starts | `⏳ Running candidate backtest — see terminal output below…` | `_C_GREEN` |
| Candidate backtest success | `✅ Candidate backtest complete — review the comparison below and click Accept or Reject.` | `_C_GREEN_LIGHT` |
| Candidate backtest failed | `❌ Candidate backtest failed — check the terminal output above for errors.` | `_C_RED_LIGHT` |
| Accept & Save | `✅ Accepted — strategy parameters saved. You can run another iteration or switch to a different run.` | `_C_GREEN_LIGHT` |
| Reject & Discard | `↩ Rejected — candidate discarded. Apply different suggestions or select a new run.` | `_C_YELLOW` |
| Rollback to Previous | `↩ Rolled back — parameters restored to the previous accepted state.` | `_C_YELLOW` |

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

This feature is primarily UI/UX. Most acceptance criteria are best verified with example-based tests. However, a small number of universal properties exist for the pure logic/state aspects of the new widgets.

### Property 1: Step indicator resets after accept or reject

*For any* workflow state (any active step 1–5 with any history), after the user clicks "Accept & Save" or "Reject & Discard", the `StepIndicator`'s active step SHALL be 1 and all other steps SHALL be pending.

**Validates: Requirements 1.8**

### Property 2: Banner message matches active step

*For any* step value in {1, 2, 3, 4, 5}, calling `ContextBanner.set_step(n)` SHALL result in the banner displaying exactly the message defined for step n in `BANNER_MESSAGES`, provided the banner has not been dismissed.

**Validates: Requirements 2.2, 2.3**

### Property 3: Dismissed banner stays hidden across all step changes

*For any* sequence of `set_step` calls after the banner has been dismissed, the banner widget SHALL remain hidden (not visible) regardless of which step is set.

**Validates: Requirements 2.5**

### Property 4: Status message includes issue count

*For any* list of diagnosed issues of length N ≥ 1, the status message produced after a successful analysis SHALL contain the string representation of N.

**Validates: Requirements 7.2**

### Property 5: Controls disabled when user_data_path is unconfigured

*For any* `SettingsState` where `user_data_path` is empty or unset, the strategy combo box, run combo box, "Load Latest Run" button, and "Analyze Run" button SHALL all be disabled.

**Validates: Requirements 8.3**

---

## Error Handling

All error handling follows existing patterns in `ImprovePage`:

- **No user_data_path**: Show the no-config warning banner (new) and disable controls. No exception raised.
- **Load failure in `_on_analyze`**: Existing `try/except (FileNotFoundError, ValueError)` block; status label shows `❌ Error: {e}`. Step indicator does not advance.
- **Candidate backtest failure**: Existing `exit_code != 0` branch; status label shows the new failure message. Step indicator does not advance to step 5.
- **Accept/rollback OS error**: Existing `QMessageBox.critical` dialog. Step indicator does not reset.
- **Banner dismiss**: Pure in-memory boolean; no persistence, no error path.

---

## Testing Strategy

This feature is a UI/UX enhancement. The testing approach is:

**Unit tests (example-based)** — the majority of tests, covering:
- `StepIndicator.set_active_step(n)` produces correct node states for each n
- `ContextBanner.set_step(n)` shows the correct message for each n
- `ContextBanner` dismiss hides the widget and ignores subsequent `set_step` calls
- `EmptyStatePanel` renders with correct icon, text, and hint strings
- Button text values match the new labels (check `widget.text()`)
- Tooltip text values match the spec (check `widget.toolTip()`)
- Subtitle label text values match the spec
- Status messages match the spec for each trigger
- No-config banner appears when `user_data_path` is empty; controls are disabled
- No-config banner hides and controls re-enable when `user_data_path` becomes valid

**Property-based tests** — for the five correctness properties above, using `hypothesis`:
- Property 1: Generate random step values, simulate accept/reject, assert reset to 1
- Property 2: Generate step values from {1,2,3,4,5}, assert banner text matches `BANNER_MESSAGES[step]`
- Property 3: Generate sequences of step values after dismiss, assert banner stays hidden
- Property 4: Generate lists of `DiagnosedIssue` objects of random length N ≥ 1, assert status message contains str(N)
- Property 5: Generate empty/whitespace/None `user_data_path` values, assert all four controls are disabled

**PBT library**: `hypothesis` (already present in the project via `.hypothesis/` directory).

**Test configuration**: minimum 100 iterations per property test. Each property test tagged with:
`# Feature: improve-tab-ux, Property {N}: {property_text}`

**What is NOT tested**:
- Visual styling (colors, fonts, border widths) — verified by manual review
- Animation behavior (`_fade_in_widget`) — existing, already working
- Service layer behavior — out of scope for this feature
