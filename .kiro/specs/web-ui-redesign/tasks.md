# Implementation Plan: Web UI Redesign

## Overview

Deliver the visual and UX redesign of the Freqtrade Strategy Workstation SPA by working through four groups in dependency order: design tokens first, then component CSS, then TSX restructuring, then tests. All changes land in seven files; no new npm packages are introduced except `fast-check` as a dev dependency for property-based tests.

## Tasks

- [x] 1. Add design tokens to `theme.css`
  - [x] 1.1 Add typography scale tokens to `:root`
    - Append `--text-xs: 11px`, `--text-sm: 12px`, `--text-base: 14px`, `--text-lg: 16px`, `--text-xl: 20px`, `--text-2xl: 24px` to the existing `:root` block in `app/re_web/src/styles/theme.css`
    - Do not rename or remove any existing token
    - _Requirements: 1.1, 1.5_

  - [x] 1.2 Add spacing scale tokens to `:root`
    - Append `--space-1: 4px` through `--space-6: 24px` (4 px base unit) to the `:root` block
    - _Requirements: 1.2, 1.5_

  - [x] 1.3 Add elevation tokens to `:root`
    - Append `--shadow-sm: 0 1px 4px rgba(0,0,0,0.18), 0 2px 8px rgba(0,0,0,0.10)` and `--shadow-md: 0 4px 16px rgba(0,0,0,0.22), 0 8px 24px rgba(0,0,0,0.12)` to the `:root` block
    - _Requirements: 1.3, 1.5_

  - [x] 1.4 Mirror all new tokens in `:root[data-theme='light']`
    - Add all six typography tokens, six spacing tokens, and two elevation tokens to the `:root[data-theme='light']` block with light-appropriate opacity values for shadows
    - _Requirements: 1.4_

  - [x] 1.5 Write property test P1 — token parity across themes
    - Install `fast-check` as a dev dependency (`npm install --save-dev fast-check`) in `app/re_web/`
    - Create `app/re_web/src/tests/theme.test.ts`
    - **Property 1: Design Token Parity Across Themes** — for any token name in the new token set, `theme.css` must define it in both `:root` and `:root[data-theme='light']`
    - Use `fc.constantFrom(...newTokenNames)` as the arbitrary
    - Minimum 100 iterations
    - Tag: `// Feature: web-ui-redesign, Property 1: Design Token Parity Across Themes`
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4**

  - [x] 1.6 Write property test P2 — existing token preservation
    - In `app/re_web/src/tests/theme.test.ts`
    - **Property 2: Existing Token Preservation** — for any token name in the existing token set (`--bg`, `--surface`, `--surface-2`, `--surface-3`, `--text`, `--muted`, `--border`, `--accent`, `--accent-strong`, `--amber`, `--red`, `--green`, `--blue`, `--shadow`, `--radius`, `--font`), the updated `theme.css` must still define it in `:root`
    - Use `fc.constantFrom(...existingTokenNames)` as the arbitrary
    - Tag: `// Feature: web-ui-redesign, Property 2: Existing Token Preservation`
    - **Validates: Requirements 1.5**

- [x] 2. Update sidebar and AppShell styles in `app.css`
  - [x] 2.1 Set sidebar width and active-link accent bar
    - In `app/re_web/src/styles/app.css`, update `.app-shell` to `grid-template-columns: 240px minmax(0,1fr)`
    - Add `.nav-link.active::before` pseudo-element rule: `content: ''`, `position: absolute`, `left: 0`, `top: 4px`, `bottom: 4px`, `width: 4px`, `border-radius: 2px`, `background: var(--accent)`; set `.nav-link` to `position: relative`
    - Update `.nav-link.active` to use `color: var(--text)` and `background: var(--surface-2)`; inactive links keep `color: var(--muted)`
    - _Requirements: 2.1, 2.3_

  - [x] 2.2 Update brand block and sidebar footer spacing
    - Set `.brand strong` to `font-size: var(--text-base, 14px)` and `.brand span` to `font-size: var(--text-xs, 11px)` and `color: var(--muted)`
    - Ensure `.sidebar` footer area (theme-button) is visually separated from the nav list via the existing `grid-template-rows: auto 1fr auto` layout
    - _Requirements: 2.2, 2.5_

- [x] 3. Update MetricCard styles in `app.css`
  - [x] 3.1 Style metric-card-bar, label, value, and detail
    - Update `.metric-card-bar` to `height: 3px`, `width: 100%`, `display: block`
    - Update `.metric-label` to `text-transform: uppercase`, `font-size: var(--text-xs, 11px)`, `color: var(--muted)`, `letter-spacing: 0.05em`
    - Update `.metric-value` to `font-size: var(--text-xl, 20px)`, `font-weight: 700`
    - Update `.metric-detail` to `font-size: var(--text-xs, 11px)`, `color: var(--muted)`
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [x] 3.2 Add hover elevation and resting shadow to MetricCard
    - Set `.metric-card` to `box-shadow: var(--shadow-sm)` at rest
    - Set `.metric-card:hover` to `box-shadow: var(--shadow-md)` (no background change)
    - _Requirements: 4.5_

  - [x] 3.3 Update metric-grid responsive breakpoints
    - Set `.metric-grid` to `grid-template-columns: repeat(6, minmax(120px, 1fr))` at wide viewport
    - At `max-width: 1050px`: `repeat(3, minmax(150px, 1fr))`
    - At `max-width: 680px`: `repeat(2, 1fr)`
    - _Requirements: 4.6_

- [x] 4. Update Panel styles in `app.css`
  - [x] 4.1 Apply shadow-sm, space-4 padding, and panel-header border
    - Update `.panel` to `padding: var(--space-4, 16px)` and `box-shadow: var(--shadow-sm)`
    - Update `.panel-header` to add `border-bottom: 1px solid var(--border)`, `padding-bottom: var(--space-3, 12px)`, `margin-bottom: var(--space-3, 12px)`
    - _Requirements: 5.1, 5.2, 5.3_

  - [x] 4.2 Flush table-wrap inside panel
    - Add `.panel > .table-wrap` rule: `margin-left: calc(-1 * var(--space-4, 16px))`, `margin-right: calc(-1 * var(--space-4, 16px))`, `width: calc(100% + 2 * var(--space-4, 16px))`
    - _Requirements: 5.4_

- [x] 5. Update Button and Input styles in `app.css`
  - [x] 5.1 Add disabled state and focus ring
    - Add `.button:disabled, .icon-button:disabled` rule: `opacity: 0.45`, `cursor: not-allowed`
    - Update `input:focus, select:focus, textarea:focus` to `outline: 2px solid var(--accent)`, `outline-offset: -1px`, `border-color: var(--accent)` (replace existing `border-color`-only rule)
    - _Requirements: 6.3, 6.4_

  - [x] 5.2 Add hover surface-3 and primary button hover
    - Confirm `.button:hover, .icon-button:hover` uses `background: var(--surface-3)` (update if currently `--surface-2`)
    - Add `.button.primary:hover` rule: `background: var(--accent-strong)`
    - _Requirements: 6.6_

- [x] 6. Add StatusBadge pulse animation and Alert left-border styles in `app.css`
  - [x] 6.1 Add pulse keyframe and apply to running state
    - Add `@keyframes pulse-badge` with `0%, 100% { opacity: 1 }` and `50% { opacity: 0.55 }`
    - Add `.status-badge.tone-warn { animation: pulse-badge 1.4s ease-in-out infinite }`
    - _Requirements: 9.2_

  - [x] 6.2 Add left-border accent and tinted backgrounds to Alert
    - Update `.alert` to add `border-left: 4px solid var(--border)` and `background: var(--surface)`
    - Add `.alert.error` rule: `border-left-color: var(--red)`, `background: color-mix(in srgb, var(--red), var(--surface) 92%)`
    - Add `.alert.warn` rule: `border-left-color: var(--amber)`, `background: color-mix(in srgb, var(--amber), var(--surface) 92%)`
    - Add `.alert.success` rule: `border-left-color: var(--green)`, `background: color-mix(in srgb, var(--green), var(--surface) 92%)`
    - _Requirements: 9.6, 9.7_

- [x] 7. Add workflow-step CSS classes in `app.css`
  - Add `.workflow-step`, `.workflow-step-header`, `.step-badge`, `.workflow-step.active .step-badge`, and `.workflow-step h2` rules as specified in the design document
  - `.workflow-step`: `display: grid`, `gap: var(--space-3, 12px)`
  - `.workflow-step-header`: `display: flex`, `align-items: center`, `gap: var(--space-3, 12px)`, `padding-bottom: var(--space-2, 8px)`
  - `.step-badge`: 26×26 px circle, `font-size: var(--text-xs)`, `font-weight: 700`, `background: var(--surface-2)`, `color: var(--muted)`, `border: 1.5px solid var(--border)`
  - `.workflow-step.active .step-badge`: `background: var(--accent)`, `color: #06110f`, `border-color: var(--accent-strong)`
  - `.workflow-step h2`: `font-size: var(--text-base)`, `font-weight: 650`, `color: var(--text)`
  - _Requirements: 7.1, 7.2, 8.1_

- [x] 8. Update `AppShell.tsx` — add `aria-current="page"`
  - In `app/re_web/src/components/AppShell.tsx`, add `aria-current={active ? 'page' : undefined}` to the `<a>` element inside the `routes.map` callback
  - The `active` boolean is already computed; only the attribute assignment is new
  - _Requirements: 15.3_

- [x] 9. Update `StatusBadge.tsx` — explicit tone mapping
  - In `app/re_web/src/components/StatusBadge.tsx`, replace the substring-matching tone logic with an explicit `TONE_MAP` record:
    ```ts
    const TONE_MAP: Record<string, string> = {
      idle:     'neutral',
      running:  'warn',
      started:  'warn',
      complete: 'good',
      success:  'good',
      error:    'bad',
      failed:   'bad',
    };
    ```
  - Retain the existing substring-matching fallback for status strings not in the map
  - _Requirements: 9.2_

  - [x] 9.1 Write property test P6 — StatusBadge tone mapping
    - Create `app/re_web/src/tests/StatusBadge.test.tsx`
    - **Property 6: StatusBadge Tone Mapping** — for any status in `{idle, running, complete, error}`, `StatusBadge` renders `tone-{expected}` where expected is `neutral`, `warn`, `good`, `bad` respectively; the mapping must be injective
    - Use `fc.constantFrom('idle', 'running', 'complete', 'error')` as the arbitrary
    - Tag: `// Feature: web-ui-redesign, Property 6: StatusBadge Tone Mapping`
    - **Validates: Requirements 9.2**

- [x] 10. Restructure `BacktestPage.tsx` into three workflow steps
  - In `app/re_web/src/pages/BacktestPage.tsx`, replace the existing `<section className="split-layout">` flat layout with three `<section className="workflow-step">` elements:
    - **Step 1 — Configure**: `<section className="workflow-step active">` containing `.workflow-step-header` (badge "1", h2 "Configure") and a `.panel.form-grid` with strategy, timeframe, preset, timerange, wallet, and max-trades fields
    - **Step 2 — Pairs**: `<section className="workflow-step">` containing `.workflow-step-header` (badge "2", h2 "Pairs") and a `.panel` with the chip-grid of available pairs
    - **Step 3 — Run & Monitor**: `<section className="workflow-step">` containing `.workflow-step-header` (badge "3", h2 "Run & Monitor", `StatusBadge`), `.button-row` (Start, Stop, Download), conditional `.loading-bar` when `status.status === 'running'`, and `.panel` with terminal output
  - Compute the `active` class: Step 1 active when no strategy selected; Step 2 active when strategy selected but no pairs; Step 3 active when pairs selected or run in progress
  - Move the `StatusBadge` and save-state chip from the page header toolbar into the Step 3 header
  - Render a success/error `.alert` below the page header when `status.status === 'complete'` or `'error'`
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8_

  - [x] 10.1 Write property test P4 — BacktestPage workflow step structure
    - Create `app/re_web/src/tests/BacktestPage.test.tsx`
    - **Property 4 (BacktestPage): Workflow Step Structure Invariant** — rendered output contains exactly three `.workflow-step` elements; each has a `.step-badge` child with the correct number and an `<h2>` with the correct heading (`Configure`, `Pairs`, `Run & Monitor`)
    - Tag: `// Feature: web-ui-redesign, Property 4: Workflow Step Structure Invariant`
    - **Validates: Requirements 7.1**

  - [x] 10.2 Write property test P5 — BacktestPage progress indicator
    - In `app/re_web/src/tests/BacktestPage.test.tsx`
    - **Property 5 (BacktestPage): Progress Indicator on Active Operation** — for any state where `status.status === 'running'`, rendered output contains a `.loading-bar` element
    - Use `fc.record({ status: fc.constant('running') })` as the arbitrary
    - Tag: `// Feature: web-ui-redesign, Property 5: Progress Indicator on Active Operation`
    - **Validates: Requirements 7.7, 9.1**

  - [x] 10.3 Write property test P8 (BacktestPage) — empty pairs state
    - In `app/re_web/src/tests/BacktestPage.test.tsx`
    - **Property 8 (BacktestPage): Empty State Invariant** — for any state where `availablePairs` is empty, the pairs chip-grid in Step 2 renders without crashing and contains no `.chip` elements
    - Tag: `// Feature: web-ui-redesign, Property 8: Empty State Invariant`
    - **Validates: Requirements 8.8**

- [x] 11. Restructure `OptimizerPage.tsx` into three workflow steps
  - In `app/re_web/src/pages/OptimizerPage.tsx`, replace the existing `<section className="split-layout optimizer-layout">` and subsequent flat panels with three `<section className="workflow-step">` elements:
    - **Step 1 — Configure**: `<section className="workflow-step active">` containing `.workflow-step-header` (badge "1", h2 "Configure") and a `.panel.form-grid` with strategy, timeframe, pairs, timerange, trials, min-trades, target-profit, and drawdown-cap fields
    - **Step 2 — Parameter Space**: `<section className="workflow-step">` containing `.workflow-step-header` (badge "2", h2 "Parameter Space", "Load Params" button) and a `.panel` with the param-list
    - **Step 3 — Run & Monitor**: `<section className="workflow-step">` containing `.workflow-step-header` (badge "3", h2 "Run & Monitor", `StatusBadge` for active session, Start/Stop buttons), conditional `.loading-bar` when `streaming === true`, `.panel` with sessions table, `.panel` with trial grid (best tile retains `borderLeft: '3px solid var(--accent)'` and `★`), and conditional `.panel` with live-log terminal
  - Compute the `active` class: Step 1 active when no strategy; Step 2 active when strategy selected but no params loaded; Step 3 active when params loaded or session running
  - Render an empty-state element with class `empty-state` inside the trial grid when `trials.length === 0`
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8_

  - [x] 11.1 Write property test P4 — OptimizerPage workflow step structure
    - Create `app/re_web/src/tests/OptimizerPage.test.tsx`
    - **Property 4 (OptimizerPage): Workflow Step Structure Invariant** — rendered output contains exactly three `.workflow-step` elements with headings `Configure`, `Parameter Space`, `Run & Monitor`
    - Tag: `// Feature: web-ui-redesign, Property 4: Workflow Step Structure Invariant`
    - **Validates: Requirements 8.1**

  - [x] 11.2 Write property test P5 — OptimizerPage progress indicator
    - In `app/re_web/src/tests/OptimizerPage.test.tsx`
    - **Property 5 (OptimizerPage): Progress Indicator on Active Operation** — for any state where `streaming === true`, rendered output contains a `.loading-bar` element within Step 3
    - Tag: `// Feature: web-ui-redesign, Property 5: Progress Indicator on Active Operation`
    - **Validates: Requirements 8.5, 9.1**

  - [x] 11.3 Write property test P7 — best trial tile invariant
    - In `app/re_web/src/tests/OptimizerPage.test.tsx`
    - **Property 7: Best Trial Tile Invariant** — for any trial record where `is_best === true`, the rendered trial tile has `border-left` referencing `var(--accent)` and contains a star character (`★`)
    - Use `fc.record({ is_best: fc.constant(true), trial_number: fc.nat() })` as the arbitrary
    - Tag: `// Feature: web-ui-redesign, Property 7: Best Trial Tile Invariant`
    - **Validates: Requirements 8.6**

  - [x] 11.4 Write property test P8 (OptimizerPage) — empty trials state
    - In `app/re_web/src/tests/OptimizerPage.test.tsx`
    - **Property 8 (OptimizerPage): Empty State Invariant** — for any state where `trials` is an empty array, the trial grid area in Step 3 contains an element with class `empty-state`
    - Tag: `// Feature: web-ui-redesign, Property 8: Empty State Invariant`
    - **Validates: Requirements 8.8**

- [x] 12. Write static CSS unit tests
  - Create `app/re_web/src/tests/css.test.ts`
  - Read `theme.css` as a string and assert all new token names (`--text-xs` through `--text-2xl`, `--space-1` through `--space-6`, `--shadow-sm`, `--shadow-md`) appear in both the `:root` block and the `:root[data-theme='light']` block
  - Read `app.css` as a string and assert:
    - `.panel` rule contains `box-shadow: var(--shadow-sm)`
    - `.button:disabled` or `.icon-button:disabled` rule contains `opacity: 0.45`
    - `.alert.error` rule contains `border-left-color: var(--red)`
    - `.nav-link.active::before` rule contains `background: var(--accent)`
    - `.workflow-step` rule is present
    - `.step-badge` rule is present
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 5.1, 6.3, 9.6, 9.7_

- [x] 13. Write component unit tests
  - Create `app/re_web/src/tests/AppShell.test.tsx`
    - Render `AppShell` with a known active path; assert the active `<a>` has `aria-current="page"` and all other `<a>` elements do not
    - _Requirements: 15.3_

  - Create or extend `app/re_web/src/tests/MetricCard.test.tsx`
    - Render `MetricCard` with each tone (`good`, `bad`, `warn`, `neutral`); assert `.metric-card-bar` has the correct inline `background` style and `.metric-value` is present
    - _Requirements: 4.1, 4.3_

  - Extend `app/re_web/src/tests/StatusBadge.test.tsx`
    - Render `StatusBadge` with each canonical status (`idle`, `running`, `complete`, `error`); assert the rendered `<span>` has the correct `tone-*` class
    - _Requirements: 9.2_

  - [x] 13.1 Write property test P3 — MetricCard tone rendering invariant
    - In `app/re_web/src/tests/MetricCard.test.tsx`
    - **Property 3: MetricCard Tone Rendering Invariant** — for any tone in `{good, bad, warn, neutral}`, `MetricCard` renders a `.metric-card-bar` with a non-empty `background` style and a `.metric-value` element
    - Use `fc.constantFrom('good', 'bad', 'warn', 'neutral')` as the arbitrary
    - Tag: `// Feature: web-ui-redesign, Property 3: MetricCard Tone Rendering Invariant`
    - **Validates: Requirements 4.1, 4.3**

- [x] 14. Final checkpoint — run all tests
  - Ensure all tests pass, ask the user if questions arise.
  - Run `npm run test -- --run` (or `npx vitest run`) from `app/re_web/` to execute the full test suite
  - Verify no TypeScript errors with `npx tsc --noEmit` from `app/re_web/`
  - Confirm the seven target files are the only modified source files

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Property tests use `fast-check` with a minimum of 100 iterations per property
- All eight correctness properties from the design document are covered: P1 and P2 in task 1, P3 in task 13, P4–P5 in tasks 10–11, P6 in task 9, P7 in task 11, P8 in tasks 10 and 11
- CSS fallback values (`var(--token, fallback)`) should be used at all call sites as described in the design's error-handling section
- The `active` workflow-step class computation must default to Step 1 when state is indeterminate — the UI must never show no active step
