# Requirements Document

## Introduction

The Improve Tab UX feature enhances the existing "Improve" tab in the Freqtrade GUI desktop application. The tab already implements a full improvement workflow (select strategy → select run → analyze → apply suggestions → run candidate backtest → compare → accept/reject/rollback), but users who are unfamiliar with the workflow have no guidance on what to do next at each stage. This feature adds step-by-step guidance, contextual instructions, a visual workflow progress indicator, and improved user-facing text so that any user can navigate the workflow confidently without prior knowledge of how it works.

No changes are made to the underlying service layer, diagnosis logic, or suggestion logic. All changes are purely in `app/ui/pages/improve_page.py` and any new helper widgets it introduces.

---

## Glossary

- **ImprovePage**: The existing PySide6 `QWidget` page at `app/ui/pages/improve_page.py` that hosts the full improvement workflow UI.
- **WorkflowStep**: One of the five named stages of the improvement workflow: `SELECT`, `ANALYZE`, `APPLY`, `BACKTEST`, `DECIDE`. Each step has a label, description, and active/complete/pending state.
- **StepIndicator**: A horizontal widget at the top of `ImprovePage` that renders the five `WorkflowStep` nodes connected by lines, showing which step is currently active and which are complete.
- **ContextBanner**: A dismissible, styled banner widget displayed below the `StepIndicator` that shows the instruction text relevant to the current `WorkflowStep`.
- **EmptyStatePanel**: A placeholder widget shown inside a group box when that group has no data yet, containing an icon, a short explanation, and a next-action hint.
- **TooltipHint**: A `QLabel` with a `?` icon that, when hovered, shows a `QToolTip` with explanatory text. Used on buttons and combo boxes that may be unclear to new users.
- **BaselineRun**: The `BacktestResults` loaded from the `RunStore` that serves as the reference point for comparison (unchanged from existing implementation).
- **CandidateRun**: The `BacktestResults` produced by running a backtest with the `CandidateConfig` applied (unchanged from existing implementation).
- **CandidateConfig**: The in-memory parameter snapshot representing proposed changes (unchanged from existing implementation).

---

## Requirements

### Requirement 1: Workflow Step Indicator

**User Story:** As a user opening the Improve tab for the first time, I want to see a clear visual representation of the workflow stages, so that I understand the overall process and know where I am at any point.

#### Acceptance Criteria

1. THE `ImprovePage` SHALL display a `StepIndicator` widget as the first element in its layout, above all other controls.
2. THE `StepIndicator` SHALL render exactly five steps in left-to-right order: "1 · Select", "2 · Analyze", "3 · Apply", "4 · Backtest", "5 · Decide".
3. THE `StepIndicator` SHALL visually distinguish three states for each step node: **active** (highlighted with the theme accent color `#4ec9a0`, bold label), **complete** (dimmed with a checkmark prefix), and **pending** (dimmed, no checkmark).
4. WHEN the page first loads, THE `StepIndicator` SHALL show step 1 ("Select") as active and steps 2–5 as pending.
5. WHEN the user clicks "Analyze" and a `BaselineRun` is successfully loaded, THE `StepIndicator` SHALL advance to show step 2 ("Analyze") as complete and step 3 ("Apply") as active.
6. WHEN the user applies at least one non-advisory suggestion, THE `StepIndicator` SHALL advance to show step 3 ("Apply") as complete and step 4 ("Backtest") as active.
7. WHEN the candidate backtest completes successfully and a `CandidateRun` is available, THE `StepIndicator` SHALL advance to show step 4 ("Backtest") as complete and step 5 ("Decide") as active.
8. WHEN the user clicks "Accept" or "Reject", THE `StepIndicator` SHALL reset to show step 1 ("Select") as active and steps 2–5 as pending, ready for the next iteration.
9. THE `StepIndicator` SHALL connect adjacent step nodes with a horizontal line that is rendered in the accent color for completed segments and in the border color `#3e3e42` for pending segments.

---

### Requirement 2: Contextual Instruction Banner

**User Story:** As a user at any stage of the workflow, I want to see a short, plain-language instruction telling me exactly what to do next, so that I never feel lost or unsure how to proceed.

#### Acceptance Criteria

1. THE `ImprovePage` SHALL display a `ContextBanner` widget directly below the `StepIndicator` and above the strategy/run selector controls.
2. THE `ContextBanner` SHALL display a different instruction message for each of the five workflow steps, as follows:
   - Step 1 (Select): "Choose a strategy and a saved backtest run, then click **Analyze** to detect performance issues."
   - Step 2 (Analyze): "Review the detected issues and suggested parameter changes below."
   - Step 3 (Apply): "Click **Apply** on one or more suggestions to build your candidate configuration, then click **Run Backtest on Candidate**."
   - Step 4 (Backtest): "The candidate backtest is running. Wait for it to finish, then review the comparison."
   - Step 5 (Decide): "Compare the results. Click **Accept** to save the improvements, or **Reject** to discard them."
3. THE `ContextBanner` SHALL update its message immediately whenever the active workflow step changes.
4. THE `ContextBanner` SHALL display a dismiss button ("✕") that, when clicked, hides the banner for the remainder of the session without affecting workflow state.
5. IF the `ContextBanner` has been dismissed, THE `ImprovePage` SHALL NOT show it again until the application is restarted.
6. THE `ContextBanner` SHALL be styled with a left-border accent in the theme accent color `#4ec9a0`, a slightly elevated background `#2d2d30`, and body text in `#d4d4d4` at 12px.

---

### Requirement 3: Empty State Panels

**User Story:** As a user who has not yet completed a step, I want the empty sections of the page to explain what they are for and what I need to do to populate them, so that I don't see blank boxes with no context.

#### Acceptance Criteria

1. WHEN no `BaselineRun` has been loaded, THE `ImprovePage` SHALL display an `EmptyStatePanel` inside the "Baseline Summary" group box containing the icon "📊", the text "No run loaded yet", and the hint "Select a strategy and run above, then click Analyze."
2. WHEN no `BaselineRun` has been loaded, THE `ImprovePage` SHALL display an `EmptyStatePanel` inside the "Detected Issues" group box containing the icon "🔍", the text "Issues will appear here after analysis", and the hint "Click Analyze to scan your backtest results."
3. WHEN no `BaselineRun` has been loaded, THE `ImprovePage` SHALL display an `EmptyStatePanel` inside the "Suggested Actions" group box containing the icon "💡", the text "Suggestions will appear here after analysis", and the hint "Each suggestion targets a specific performance issue."
4. WHEN a `BaselineRun` is loaded but no suggestions have been applied, THE `ImprovePage` SHALL display an `EmptyStatePanel` inside the "Candidate Preview" group box containing the icon "⚙️", the text "No changes applied yet", and the hint "Click Apply on a suggestion above to start building your candidate."
5. WHEN no `CandidateRun` is available, THE `ImprovePage` SHALL display an `EmptyStatePanel` inside the "Comparison" group box containing the icon "⚖️", the text "Comparison will appear after the candidate backtest", and the hint "Apply suggestions and run the candidate backtest to see results here."
6. THE `EmptyStatePanel` SHALL render the icon at 28px, the main text in `#9d9d9d` at 13px, and the hint text in `#9d9d9d` at 11px italic, all center-aligned.
7. WHEN a group box transitions from empty to populated, THE `ImprovePage` SHALL replace the `EmptyStatePanel` with the actual content using the existing fade-in animation (`_fade_in_widget`).

---

### Requirement 4: Improved Button and Label Text

**User Story:** As a user, I want all buttons, labels, and group box titles to use clear, action-oriented language that matches what each control actually does, so that I don't have to guess what will happen when I click something.

#### Acceptance Criteria

1. THE "Analyze" button SHALL be labeled "⚡ Analyze Run" (replacing the current "⚡ Analyze") to make it clear the action analyzes the selected run.
2. THE "Load Latest" button SHALL be labeled "↓ Load Latest Run" to make it clear the action selects the most recent run.
3. THE "Run Backtest on Candidate" button SHALL be labeled "▶ Run Candidate Backtest" for conciseness and consistency with Freqtrade terminology.
4. THE "Reset Candidate" button SHALL be labeled "↺ Reset to Baseline" to make it clear the action reverts to the original parameters.
5. THE "Accept" button SHALL be labeled "✅ Accept & Save" to make it clear the action permanently saves the candidate parameters.
6. THE "Reject" button SHALL be labeled "✕ Reject & Discard" to make it clear the action discards the candidate without saving.
7. THE "Rollback" button SHALL be labeled "↩ Rollback to Previous" to make it clear the action restores the prior accepted state.
8. THE "Detected Issues" group box title SHALL remain "Detected Issues" but SHALL include a count suffix when issues are present, e.g. "Detected Issues (3)".
9. THE "Suggested Actions" group box title SHALL remain "Suggested Actions" but SHALL include a count suffix when suggestions are present, e.g. "Suggested Actions (2)".
10. THE "Candidate Preview" group box title SHALL be renamed to "Candidate Changes" to better describe its content (a diff of parameter changes).
11. THE "Comparison" group box title SHALL be renamed to "Results Comparison" for clarity.

---

### Requirement 5: Tooltip Hints on Key Controls

**User Story:** As a user who is unsure what a control does, I want to hover over it and see a brief explanation, so that I can learn the workflow without leaving the app.

#### Acceptance Criteria

1. THE strategy combo box SHALL have a `QToolTip` with the text "Select the strategy whose backtest results you want to improve."
2. THE run combo box SHALL have a `QToolTip` with the text "Select a saved backtest run to use as the baseline for comparison."
3. THE "Analyze Run" button SHALL have a `QToolTip` with the text "Load the selected run, detect performance issues, and generate parameter suggestions."
4. THE "Load Latest Run" button SHALL have a `QToolTip` with the text "Automatically select the most recently saved run for this strategy."
5. THE "Run Candidate Backtest" button SHALL have a `QToolTip` with the text "Run a backtest using the candidate parameters. Results will be compared to the baseline."
6. THE "Accept & Save" button SHALL have a `QToolTip` with the text "Write the candidate parameters to the strategy file. This replaces the current parameters permanently."
7. THE "Reject & Discard" button SHALL have a `QToolTip` with the text "Discard the candidate parameters. The strategy file is not modified."
8. THE "Rollback to Previous" button SHALL have a `QToolTip` with the text "Restore the strategy parameters to the state before the last Accept."
9. THE "Reset to Baseline" button SHALL have a `QToolTip` with the text "Clear all applied suggestions and reset the candidate to match the current baseline parameters."

---

### Requirement 6: Inline Section Descriptions

**User Story:** As a user reading the results of an analysis, I want each section to have a one-line description of what it contains, so that I understand the purpose of each panel without needing external documentation.

#### Acceptance Criteria

1. THE "Detected Issues" group box SHALL display a subtitle label immediately below its title reading: "Issues found in the baseline run that may be limiting strategy performance."
2. THE "Suggested Actions" group box SHALL display a subtitle label immediately below its title reading: "Rule-based parameter changes that address the detected issues. Apply one or more, then run the candidate backtest."
3. THE "Candidate Changes" group box SHALL display a subtitle label immediately below its title reading: "Parameters that will be changed from the baseline when the candidate backtest runs."
4. THE "Results Comparison" group box SHALL display a subtitle label immediately below its title reading: "Side-by-side metrics for the baseline and candidate runs. Green = improvement, red = regression."
5. THE subtitle labels SHALL be styled in `#9d9d9d` at 11px, displayed on a single line (no word wrap), and positioned with 10px left padding to align with the group box content.

---

### Requirement 7: Status Message Improvements

**User Story:** As a user watching the workflow progress, I want status messages to be specific, actionable, and consistently placed, so that I always know what just happened and what to do next.

#### Acceptance Criteria

1. WHEN the "Analyze Run" button is clicked and loading begins, THE `ImprovePage` SHALL display the status message "⏳ Loading run — please wait…" in the accent color `#4ec9a0`.
2. WHEN analysis completes successfully and issues are found, THE `ImprovePage` SHALL display the status message "✅ Analysis complete — {N} issue(s) found. Review suggestions below and click Apply." where N is the count of detected issues.
3. WHEN analysis completes successfully and no issues are found, THE `ImprovePage` SHALL display the status message "✅ Analysis complete — no issues detected. Your strategy looks healthy!"
4. WHEN the candidate backtest starts, THE `ImprovePage` SHALL display the status message "⏳ Running candidate backtest — see terminal output below…" in the accent color `#4ec9a0`.
5. WHEN the candidate backtest completes successfully, THE `ImprovePage` SHALL display the status message "✅ Candidate backtest complete — review the comparison below and click Accept or Reject."
6. WHEN the candidate backtest fails (non-zero exit code), THE `ImprovePage` SHALL display the status message "❌ Candidate backtest failed — check the terminal output above for errors."
7. WHEN the user clicks "Accept & Save", THE `ImprovePage` SHALL display the status message "✅ Accepted — strategy parameters saved. You can run another iteration or switch to a different run."
8. WHEN the user clicks "Reject & Discard", THE `ImprovePage` SHALL display the status message "↩ Rejected — candidate discarded. Apply different suggestions or select a new run."
9. WHEN the user clicks "Rollback to Previous", THE `ImprovePage` SHALL display the status message "↩ Rolled back — parameters restored to the previous accepted state."
10. THE status label SHALL always be visible (not hidden between state transitions) and SHALL retain the last message until a new action produces a new message.

---

### Requirement 8: No-Configuration Guard

**User Story:** As a user who has not yet configured the app settings, I want to see a clear explanation of why the Improve tab is not functional, so that I know exactly what to set up before I can use it.

#### Acceptance Criteria

1. IF `SettingsState` reports that `user_data_path` is not configured (empty or default), THEN THE `ImprovePage` SHALL display a full-width warning banner at the top of the page reading: "⚠️ User data path is not configured. Go to Settings and set your Freqtrade user_data directory to use this tab."
2. THE warning banner SHALL be styled with a yellow-orange left border (`#ce9178`), elevated background `#2d2d30`, and text in `#d4d4d4` at 12px.
3. WHILE the `user_data_path` is not configured, THE `ImprovePage` SHALL disable the strategy combo box, run combo box, "Load Latest Run" button, and "Analyze Run" button.
4. WHEN `SettingsState` emits `settings_changed` and `user_data_path` becomes valid, THE `ImprovePage` SHALL hide the warning banner and re-enable the disabled controls.
5. WHEN `SettingsState` emits `settings_changed` and `user_data_path` becomes empty or invalid, THE `ImprovePage` SHALL show the warning banner and disable the controls.

