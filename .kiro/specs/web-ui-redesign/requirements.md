# Requirements Document

## Introduction

The Freqtrade Strategy Workstation web UI (`app/re_web/`) is a React single-page application that lets traders configure, run, and analyse Freqtrade backtests and hyperparameter-optimisation sessions. The current UI is functional but lacks visual polish, clear information hierarchy, and step-by-step workflow guidance on the Backtest and Optimizer pages.

This feature delivers a full visual and UX redesign across all seven pages — Dashboard, Backtest, Optimizer, Run Detail, Comparison, Download, and Settings — while staying entirely within the existing pure-CSS custom-property system and introducing no new npm packages. All existing functionality must be preserved.

The redesign targets three interlocking goals:

1. **Visual polish** — refined typography scale, consistent spacing rhythm, stronger colour hierarchy, elevated card/panel treatment, and polished button/input states.
2. **Layout & structure** — cleaner page layouts, improved information hierarchy, a more purposeful sidebar/header, and better use of whitespace.
3. **Workflow clarity** — explicit step-by-step flows on Backtest and Optimizer pages, richer status feedback, progress indicators, and logical section grouping.

---

## Glossary

- **UI**: The React web application located at `app/re_web/src/`.
- **Design_System**: The set of CSS custom properties defined in `theme.css` and component styles in `app.css`.
- **AppShell**: The `AppShell.tsx` component that renders the sidebar navigation and wraps all page content.
- **Sidebar**: The left-hand navigation panel rendered by `AppShell`.
- **Page**: A top-level route component (Dashboard, Backtest, Optimizer, Run Detail, Comparison, Download, Settings).
- **Panel**: A surface container styled with the `.panel` CSS class.
- **MetricCard**: The `MetricCard.tsx` component used to display a single KPI value.
- **Workflow_Step**: A numbered, visually distinct section within the Backtest or Optimizer page that guides the user through a sequential task.
- **Status_Indicator**: Any visual element (badge, progress bar, spinner, colour change) that communicates the current state of a background operation.
- **Tone**: A semantic colour role (`good`, `bad`, `warn`, `neutral`) applied to values and indicators.
- **Autosave**: The debounced background persistence of form state via `useAutosave`.
- **SSE**: Server-Sent Events stream used for live log output on Backtest and Optimizer pages.
- **Terminal**: The `<pre class="terminal">` element used to display live process output.
- **Equity_Chart**: The SVG equity-curve component rendered on the Run Detail page.
- **Run**: A saved backtest result stored in the backend index.
- **Session**: An optimizer hyperparameter-search session.
- **Trial**: A single parameter evaluation within an optimizer Session.

---

## Requirements

### Requirement 1: Design System Tokens

**User Story:** As a developer maintaining the UI, I want a well-structured set of CSS custom properties that cover typography, spacing, and elevation, so that every component can be styled consistently without ad-hoc overrides.

#### Acceptance Criteria

1. THE Design_System SHALL define a typographic scale with at least four named font-size tokens (`--text-xs`, `--text-sm`, `--text-base`, `--text-lg`, `--text-xl`, `--text-2xl`) in `theme.css`.
2. THE Design_System SHALL define a spacing scale with at least six named tokens (`--space-1` through `--space-6`) in `theme.css`.
3. THE Design_System SHALL define at least two elevation tokens (`--shadow-sm`, `--shadow-md`) in `theme.css` for use on panels and cards.
4. WHEN the `data-theme` attribute is set to `light`, THE Design_System SHALL provide equivalent light-mode values for all new tokens.
5. THE Design_System SHALL preserve all existing custom properties (`--bg`, `--surface`, `--surface-2`, `--surface-3`, `--text`, `--muted`, `--border`, `--accent`, `--accent-strong`, `--amber`, `--red`, `--green`, `--blue`, `--shadow`, `--radius`, `--font`) without renaming or removing them.

---

### Requirement 2: AppShell and Sidebar Redesign

**User Story:** As a user navigating the workstation, I want a sidebar that clearly communicates the active page and provides a polished brand area, so that I always know where I am and can navigate confidently.

#### Acceptance Criteria

1. THE AppShell SHALL render the Sidebar with a fixed width of 220–260 px on viewports wider than 1050 px.
2. THE Sidebar SHALL display the brand name and subtitle in a visually distinct brand block at the top, separated from the navigation list by adequate whitespace.
3. WHEN a navigation link is active, THE Sidebar SHALL render it with a filled background using `var(--surface-2)` and the full-brightness `var(--text)` colour, distinguishable from inactive links which use `var(--muted)`.
4. THE Sidebar SHALL render each navigation link with an icon and label aligned on a single row with consistent padding and a minimum touch target of 38 px height.
5. THE Sidebar SHALL render the theme-toggle button in the footer area, visually separated from the navigation list.
6. WHEN the viewport width is 680 px or less, THE AppShell SHALL hide the Sidebar and display the MobileNav bottom bar instead, preserving all existing mobile navigation behaviour.

---

### Requirement 3: Page Header Consistency

**User Story:** As a user on any page, I want a consistent page header with a clear title, subtitle, and action area, so that I can orient myself and access primary actions without hunting.

#### Acceptance Criteria

1. THE UI SHALL render every Page with a `.page-header` element containing a title (`<h1>`), a descriptive subtitle (`<p>`), and an optional action area aligned to the right.
2. THE UI SHALL apply a consistent bottom margin or gap between the `.page-header` and the first content section on every Page.
3. WHEN the viewport width is 680 px or less, THE UI SHALL stack the `.page-header` title block and action area vertically with full-width action buttons.
4. THE UI SHALL render `<h1>` elements using the `--text-2xl` token and `<h2>` elements using the `--text-base` token once those tokens are defined.

---

### Requirement 4: MetricCard Visual Polish

**User Story:** As a user reviewing backtest results, I want metric cards that are visually clear and easy to scan, so that I can quickly assess key performance indicators.

#### Acceptance Criteria

1. THE MetricCard SHALL render a coloured accent bar at the top of the card (not the left side) using the Tone colour, with a height of 3–4 px and full card width.
2. THE MetricCard SHALL display the label in uppercase, muted, small text above the value.
3. THE MetricCard SHALL display the value in a large, bold font using the Tone colour when the tone is `good`, `bad`, or `warn`.
4. THE MetricCard SHALL display the optional detail text below the value in muted, small text.
5. WHEN the user hovers over a MetricCard on a pointer device, THE MetricCard SHALL apply a subtle elevation change (increased `box-shadow`) without changing its background colour.
6. THE metric-grid SHALL use a responsive grid that shows 6 columns on wide viewports, 3 columns on medium viewports (≤ 1050 px), and 2 columns on narrow viewports (≤ 680 px).

---

### Requirement 5: Panel and Card Elevation

**User Story:** As a user reading the UI, I want panels and cards to have clear visual separation from the page background, so that content groupings are immediately obvious.

#### Acceptance Criteria

1. THE UI SHALL render every `.panel` with a background of `var(--surface)`, a `1px` border using `var(--border)`, a border-radius of `var(--radius)`, and a box-shadow using `var(--shadow-sm)`.
2. THE UI SHALL render `.panel-header` with a bottom border or bottom margin that visually separates the header from the panel body.
3. THE UI SHALL apply consistent internal padding of `var(--space-4)` (or equivalent) to all `.panel` elements.
4. WHEN a `.panel` contains a `.table-wrap`, THE UI SHALL render the table flush to the panel edges with no additional horizontal padding on the table itself.

---

### Requirement 6: Button and Input Visual States

**User Story:** As a user interacting with forms and controls, I want buttons and inputs that have clear visual states for default, hover, focus, disabled, and active, so that I always know what is interactive and what is happening.

#### Acceptance Criteria

1. THE UI SHALL render `.button` elements with a minimum height of 36 px, consistent horizontal padding, and a border-radius of `var(--radius)`.
2. WHEN a `.button.primary` is rendered, THE UI SHALL use `var(--accent)` as the background and a contrasting dark text colour.
3. WHEN a `.button` is in the `disabled` state, THE UI SHALL reduce its opacity to 0.45 and change the cursor to `not-allowed`.
4. WHEN an `input`, `select`, or `textarea` receives focus, THE UI SHALL apply a `2px` outline or border using `var(--accent)` with no default browser outline.
5. THE UI SHALL render `input` and `select` elements with a minimum height of 38 px and consistent padding.
6. WHEN the user hovers over a `.button` on a pointer device, THE UI SHALL apply a background shift to `var(--surface-3)`.

---

### Requirement 7: Backtest Page — Workflow Steps

**User Story:** As a trader running a backtest, I want the Backtest page to guide me through a clear sequence of steps — configure, select pairs, run, monitor — so that I never lose track of what to do next.

#### Acceptance Criteria

1. THE Backtest Page SHALL organise its content into visually distinct numbered Workflow_Steps: (1) Configure, (2) Pairs, (3) Run.
2. WHEN a Workflow_Step is the current active step, THE UI SHALL render it with a highlighted step number or border to indicate focus.
3. THE Backtest Page SHALL render the configuration form (strategy, timeframe, timerange, wallet, max trades) in Step 1.
4. THE Backtest Page SHALL render the pairs chip-grid and available-pairs selector in Step 2.
5. THE Backtest Page SHALL render the action buttons (Start, Stop, Download) and the live Terminal output in Step 3.
6. THE Backtest Page SHALL display the current Status_Indicator (idle / running / complete / error) prominently within Step 3, adjacent to the action buttons.
7. WHEN the backtest status is `running`, THE Backtest Page SHALL render a progress indicator (animated loading bar or spinner) visible without scrolling.
8. WHEN the backtest status transitions to `complete` or `error`, THE Backtest Page SHALL render a clearly styled success or error alert with the result message.

---

### Requirement 8: Optimizer Page — Workflow Steps

**User Story:** As a trader running hyperparameter optimisation, I want the Optimizer page to guide me through configure → inspect parameters → run → monitor trials, so that the multi-step process is easy to follow.

#### Acceptance Criteria

1. THE Optimizer Page SHALL organise its content into visually distinct numbered Workflow_Steps: (1) Configure, (2) Parameter Space, (3) Run & Monitor.
2. THE Optimizer Page SHALL render the strategy, timeframe, pairs, timerange, trials, and scoring fields in Step 1.
3. THE Optimizer Page SHALL render the parameter-space panel (param list) in Step 2, with a "Load Params" action clearly associated with that step.
4. THE Optimizer Page SHALL render the session controls (Start, Stop), session table, trial grid, and live Terminal in Step 3.
5. WHEN the optimizer is streaming (SSE active), THE Optimizer Page SHALL render a visible progress indicator within Step 3.
6. WHEN a Trial is marked `is_best`, THE Optimizer Page SHALL render its trial tile with a distinct accent border and a star or "Best" label.
7. THE Optimizer Page SHALL display the active Session's status using a Status_Indicator badge adjacent to the Step 3 heading.
8. WHEN no trials have been recorded yet, THE Optimizer Page SHALL render an empty-state message within the trial grid area of Step 3.

---

### Requirement 9: Status Feedback and Progress Indicators

**User Story:** As a user who has started a long-running operation, I want clear, consistent status feedback throughout the UI, so that I always know whether a process is running, succeeded, or failed.

#### Acceptance Criteria

1. THE UI SHALL render a `.loading-bar` element at the top of the page content area whenever an async data-fetch is in progress.
2. THE StatusBadge component SHALL render with distinct visual styles for each status value: `idle` (muted), `running` (amber, animated pulse), `complete` (green), `error` (red).
3. WHEN the `saveState` is `saving`, THE UI SHALL render the save-state chip with amber colour and the label "saving".
4. WHEN the `saveState` is `saved`, THE UI SHALL render the save-state chip with green colour and the label "saved".
5. WHEN the `saveState` is `error`, THE UI SHALL render the save-state chip with red colour and the label "error".
6. THE UI SHALL render `.alert` elements with a left border accent (4 px) in the appropriate Tone colour in addition to the existing border treatment.
7. WHEN an `.alert.error` is rendered, THE UI SHALL use `var(--red)` for the left border and a subtle red-tinted background.

---

### Requirement 10: Run Detail Page — Information Hierarchy

**User Story:** As a trader reviewing a completed backtest run, I want the Run Detail page to present the most important metrics prominently and organise supplementary data in clearly labelled tabs, so that I can quickly assess performance and drill into details.

#### Acceptance Criteria

1. THE Run Detail Page SHALL render the metric strip (Profit, Win rate, Drawdown, Trades, Final balance, Saved) as the first content section below the page header.
2. THE Run Detail Page SHALL render the Equity_Chart, Trades table, Diagnosis, Params, and Diff in a tabbed interface below the metric strip.
3. WHEN the Diagnosis tab contains one or more issues or suggestions, THE UI SHALL render the tab label with a numeric badge showing the count.
4. THE Equity_Chart SHALL render with a minimum height of 280 px and fill the available panel width.
5. THE Run Detail Page SHALL render the run selector as a styled dropdown in the page header action area, not as a separate section.
6. WHEN no run is selected, THE Run Detail Page SHALL render a centred empty-state message prompting the user to select a run.

---

### Requirement 11: Comparison Page — Layout and Controls

**User Story:** As a trader comparing two backtest runs, I want the comparison controls and results to be clearly laid out, so that I can select runs and read the verdict without confusion.

#### Acceptance Criteria

1. THE Comparison Page SHALL render the run-selector controls (Baseline, Candidate, Compare button) in a single Panel above the results.
2. WHEN a comparison result is available, THE Comparison Page SHALL render the metric grid (Verdict, Profit diff, Win-rate diff, Drawdown diff, Score diff, Confidence) immediately below the controls panel.
3. THE Comparison Page SHALL render the Recommendations section in a Panel below the metric grid.
4. THE Comparison Page SHALL render the full Runs table in a Panel at the bottom of the page.
5. WHEN the Verdict value is positive (e.g. "better"), THE MetricCard for Verdict SHALL use the `good` tone; WHEN negative, it SHALL use the `bad` tone.

---

### Requirement 12: Download Page — Layout and Feedback

**User Story:** As a trader downloading OHLCV data, I want the Download page to clearly separate configuration from output, so that I can set up a download and monitor its progress without the UI feeling cluttered.

#### Acceptance Criteria

1. THE Download Page SHALL render the configuration form (timeframe, timerange, options, pairs) in the left column of a two-column split layout.
2. THE Download Page SHALL render the Terminal output panel in the right column of the split layout.
3. THE Download Page SHALL render the primary Download action button in the page header action area.
4. WHEN the download status is `running`, THE Download Page SHALL disable the Download button and render a Status_Indicator showing `running`.
5. WHEN the download completes successfully, THE Download Page SHALL render a success Status_Indicator and append a completion message to the Terminal.

---

### Requirement 13: Settings Page — Section Organisation

**User Story:** As a user configuring the workstation, I want the Settings page to group related fields into clearly labelled sections with consistent form layout, so that I can find and update settings without confusion.

#### Acceptance Criteria

1. THE Settings Page SHALL render the Paths & Executables fields in a dedicated Panel at the top of the page.
2. THE Settings Page SHALL render each preference section (Backtest, Optimizer, Download) in its own Panel below the Paths panel.
3. THE Settings Page SHALL render the Save and Validate action buttons in the page header action area.
4. WHEN the Autosave state changes, THE Settings Page SHALL display the save-state chip in the page header toolbar.
5. WHEN the validation result is available, THE Settings Page SHALL render it in an `.alert` element immediately below the page header, using the `error` class for invalid results and no modifier class for valid results.
6. THE Settings Page SHALL render all form labels in muted, small text above their respective inputs, consistent with the `.form-grid label` pattern.

---

### Requirement 14: Responsive Layout Integrity

**User Story:** As a user on a tablet or mobile device, I want the redesigned UI to remain fully usable, so that I can monitor and control backtests from any device.

#### Acceptance Criteria

1. WHEN the viewport width is between 681 px and 1050 px, THE UI SHALL collapse the two-column split layouts (`.split-layout`, `.optimizer-layout`) to a single column.
2. WHEN the viewport width is 680 px or less, THE UI SHALL display the MobileNav bottom bar and hide the Sidebar.
3. WHEN the viewport width is 680 px or less, THE UI SHALL render all `input`, `select`, and `textarea` elements with a minimum font-size of 16 px to prevent iOS auto-zoom.
4. WHEN the viewport width is 680 px or less, THE UI SHALL render all interactive elements (buttons, nav items, chips) with a minimum touch target of 44 px height.
5. THE UI SHALL not introduce horizontal scrolling on the page body at any viewport width from 320 px upward.

---

### Requirement 15: Accessibility Baseline

**User Story:** As a user relying on keyboard navigation or assistive technology, I want the redesigned UI to maintain accessible markup and focus management, so that I can use the workstation without a mouse.

#### Acceptance Criteria

1. THE AppShell SHALL render the Sidebar `<nav>` with an `aria-label="Main navigation"` attribute.
2. THE MobileNav SHALL render its `<nav>` with an `aria-label="Mobile navigation"` attribute.
3. WHEN a navigation link is active, THE UI SHALL set `aria-current="page"` on that link element.
4. THE UI SHALL render all icon-only buttons with an `aria-label` attribute describing the action.
5. WHEN a modal or sheet overlay is open (e.g. mobile more-sheet), THE UI SHALL render a backdrop element that closes the overlay on click, preserving existing behaviour.
6. THE Equity_Chart SVG SHALL include a `role="img"` and `aria-label` attribute describing the chart content.
