# Requirements Document

## Introduction

This feature extends the Freqtrade strategy workstation's web interface in two complementary directions:

1. **Tailscale / remote-access support** — make the server explicitly discoverable and configurable for access from devices on a Tailscale network (e.g. an iPhone at `100.x.x.x:8000`). The server already binds to `0.0.0.0`, so the network path works today; the gap is discoverability, startup guidance, and a `--tailscale` convenience flag that auto-detects and prints the Tailscale IP.

2. **Mobile / iPhone UI** — make the React SPA (`app/re_web/`) fully usable on a 390 px-wide iPhone screen. The existing CSS has two breakpoints (`≤1050 px`, `≤680 px`) but is missing touch-target sizing, safe-area insets, a proper mobile navigation pattern, viewport meta, and font-scaling guards.

No new runtime dependencies are introduced on the backend. No CSS framework is added; all styling stays in the existing pure-CSS custom-property system.

---

## Glossary

- **Server**: The FastAPI + uvicorn process launched by `run_web.py`.
- **React_App**: The React 18 + TypeScript SPA located in `app/re_web/`.
- **AppShell**: The top-level layout component (`AppShell.tsx`) that renders the sidebar and main content area.
- **Sidebar**: The vertical navigation panel (248 px wide on desktop) rendered by `AppShell`.
- **Mobile_Nav**: The navigation control rendered on viewports ≤ 680 px — either a hamburger-triggered drawer or a bottom navigation bar.
- **Tailscale_IP**: The `100.x.x.x` address assigned to the host machine by the Tailscale daemon.
- **Touch_Target**: An interactive element whose tappable area is at least 44 × 44 CSS pixels, per WCAG 2.5.5.
- **Safe_Area_Inset**: The CSS environment variable (`env(safe-area-inset-*`) that accounts for iPhone notch, Dynamic Island, and home-indicator padding.
- **Viewport_Meta**: The `<meta name="viewport">` tag in `index.html` that controls initial scale and prevents unwanted zoom on mobile browsers.
- **Banner**: The startup text printed to stdout by `run_web.py` that lists accessible URLs.

---

## Requirements

### Requirement 1: Tailscale convenience flag

**User Story:** As a developer running the workstation on a Mac, I want to start the server with a single flag and immediately see the Tailscale URL printed in the terminal, so that I can open it on my iPhone without manually looking up the Tailscale IP.

#### Acceptance Criteria

1. WHEN `--tailscale` is passed to `run_web.py`, THE Server SHALL detect the host machine's Tailscale IP address by querying the local Tailscale daemon or network interfaces.
2. WHEN `--tailscale` is passed and a Tailscale IP is found, THE Server SHALL bind to `0.0.0.0` and print the Tailscale URL (`http://<tailscale-ip>:<port>/app`) in the startup Banner alongside the existing local URL.
3. IF `--tailscale` is passed but no Tailscale IP can be detected, THEN THE Server SHALL print a warning message to stdout and continue starting normally bound to `0.0.0.0`.
4. WHEN `--tailscale` is not passed, THE Server SHALL behave identically to its current behaviour, with no change to startup output or binding.
5. THE Server SHALL accept `--tailscale` as an optional boolean flag with no required argument (i.e. `python run_web.py --tailscale`).

---

### Requirement 2: Configurable host via environment variable

**User Story:** As a developer, I want to set the server host in a `.env` file so that I don't have to remember CLI flags when starting the server repeatedly.

#### Acceptance Criteria

1. WHEN the environment variable `WEB_HOST` is set, THE Server SHALL use its value as the default bind address, overridable by the `--host` CLI flag.
2. WHEN the environment variable `WEB_PORT` is set to a valid integer, THE Server SHALL use its value as the default port, overridable by the `--port` CLI flag.
3. IF `WEB_PORT` is set to a value that is not a valid integer in the range 1–65535, THEN THE Server SHALL print an error message and exit with a non-zero status code before attempting to bind.
4. THE Server SHALL load `WEB_HOST` and `WEB_PORT` from the `.env` file that is already loaded by `run_web.py` via `python-dotenv`, requiring no additional file-loading logic.

---

### Requirement 3: Startup Banner shows all reachable URLs

**User Story:** As a developer, I want the startup banner to list every URL where the app is reachable, so that I can copy the right one for each device without guessing.

#### Acceptance Criteria

1. WHEN the Server starts bound to `0.0.0.0`, THE Banner SHALL display the local loopback URL (`http://127.0.0.1:<port>/app`).
2. WHEN `--tailscale` is passed and a Tailscale IP is detected, THE Banner SHALL display the Tailscale URL on a dedicated line labelled `Tailscale`.
3. WHEN the Server starts bound to a specific non-loopback IP (e.g. via `--host 192.168.1.10`), THE Banner SHALL display that bound address as the `Network` URL.
4. THE Banner SHALL always display the API docs URL (`http://127.0.0.1:<port>/docs`).

---

### Requirement 4: Viewport and document-level mobile foundations

**User Story:** As an iPhone user, I want the app to render at the correct scale and not require pinching or horizontal scrolling, so that it is immediately usable when I open it.

#### Acceptance Criteria

1. THE React_App's `index.html` SHALL include a `<meta name="viewport">` tag with `width=device-width, initial-scale=1, viewport-fit=cover`.
2. THE React_App SHALL set `min-width` on `body` to a value no greater than 320 px so that the layout does not force horizontal scroll on any iPhone model.
3. WHEN the viewport width is ≤ 680 px, THE React_App SHALL apply `padding-bottom: env(safe-area-inset-bottom)` (or equivalent) to the bottom-most fixed or sticky element so that content is not obscured by the iPhone home indicator.
4. WHEN the viewport width is ≤ 680 px, THE React_App SHALL apply `padding-top: env(safe-area-inset-top)` to the top-most fixed or sticky element so that content is not obscured by the notch or Dynamic Island.

---

### Requirement 5: Mobile navigation pattern

**User Story:** As an iPhone user, I want a navigation control that is easy to reach with my thumb and does not consume most of the screen, so that I can switch between pages without frustration.

#### Acceptance Criteria

1. WHILE the viewport width is ≤ 680 px, THE AppShell SHALL render a bottom navigation bar fixed to the bottom of the viewport in place of the horizontal top bar used at ≤ 1050 px.
2. THE Mobile_Nav SHALL display icon + label pairs for each route defined in `AppShell.tsx`, with each item occupying an equal share of the bar width.
3. THE Mobile_Nav SHALL visually distinguish the active route using the existing `--accent` CSS custom property.
4. THE Mobile_Nav SHALL be implemented entirely in CSS and the existing `AppShell.tsx` component without introducing new component files, unless the component exceeds 150 lines after modification, in which case a single `MobileNav.tsx` sub-component is permitted.
5. WHEN a Mobile_Nav item is tapped, THE AppShell SHALL call `onNavigate` with the corresponding route path, matching the existing desktop navigation behaviour.
6. WHILE the viewport width is ≤ 680 px, THE AppShell SHALL hide the desktop sidebar entirely (not merely collapse it) so that it does not consume vertical space.

---

### Requirement 6: Touch target sizing

**User Story:** As an iPhone user, I want all buttons, links, and interactive controls to be large enough to tap accurately, so that I don't accidentally trigger the wrong action.

#### Acceptance Criteria

1. THE React_App SHALL ensure every interactive element (buttons, nav links, tab controls, icon buttons) has a minimum tappable area of 44 × 44 CSS pixels on viewports ≤ 680 px.
2. WHEN an interactive element's visible size is smaller than 44 × 44 px, THE React_App SHALL expand the tappable area using `min-height`, padding, or a pseudo-element rather than changing the visible size, so that the visual design is preserved.
3. THE React_App SHALL apply touch-target rules via the existing CSS files (`app.css`) using `@media (max-width: 680px)` rules, without inline styles or JavaScript-based sizing.

---

### Requirement 7: Readable typography and no horizontal overflow on mobile

**User Story:** As an iPhone user, I want text to be readable without zooming and the layout to fit within the screen width, so that I can read backtest results comfortably.

#### Acceptance Criteria

1. WHEN the viewport width is ≤ 680 px, THE React_App SHALL render body text at a minimum font size of 15 px to prevent iOS Safari from auto-zooming form inputs.
2. WHEN the viewport width is ≤ 680 px, THE React_App SHALL render `input`, `select`, and `textarea` elements at a font size of at least 16 px to prevent iOS Safari from zooming the viewport on focus.
3. THE React_App SHALL set `overflow-x: hidden` on the `body` element to prevent any component from causing horizontal scroll at viewport widths ≤ 680 px.
4. WHEN the viewport width is ≤ 680 px, THE React_App SHALL render `.metric-value` at a font size of at least 18 px and no more than 22 px.
5. WHEN the viewport width is ≤ 680 px, tables inside `.table-wrap` SHALL remain horizontally scrollable within their container without causing the page body to scroll horizontally.

---

### Requirement 8: Page-level layout adaptations for mobile

**User Story:** As an iPhone user, I want each page to use the available screen width efficiently, so that I can see meaningful content without excessive scrolling or truncation.

#### Acceptance Criteria

1. WHEN the viewport width is ≤ 680 px, THE React_App SHALL render `.metric-grid` as a two-column grid (not one column) so that metric cards use horizontal space efficiently.
2. WHEN the viewport width is ≤ 680 px, THE React_App SHALL render `.split-layout` and `.optimizer-layout` as a single-column stack.
3. WHEN the viewport width is ≤ 680 px, THE React_App SHALL render `.form-grid` as a single-column layout.
4. WHEN the viewport width is ≤ 680 px, THE React_App SHALL render `.page-header` with the title and action buttons stacked vertically, with action buttons full-width.
5. WHEN the viewport width is ≤ 680 px, THE React_App SHALL render `.toolbar` and `.button-row` with buttons that wrap to new lines rather than overflowing.
6. WHEN the viewport width is ≤ 680 px, THE React_App SHALL render `.tab-list` as a horizontally scrollable row with no visible scrollbar, so that tabs remain accessible without wrapping.

---

### Requirement 9: Vite dev server mobile access

**User Story:** As a developer, I want to run the Vite dev server in a way that is reachable from my phone on the same network, so that I can test mobile UI changes without a full production build.

#### Acceptance Criteria

1. THE `package.json` `dev` script SHALL be updated to bind to `0.0.0.0` instead of `127.0.0.1` so that the Vite dev server is reachable from other devices on the local network.
2. WHEN the Vite dev server starts, THE Vite_Config SHALL continue to proxy `/api` requests to `http://127.0.0.1:8000` so that API calls work correctly during development.
3. THE `package.json` `preview` script SHALL also bind to `0.0.0.0` for consistency with the `dev` script.

---

### Requirement 10: Mobile navigation overflow strategy

**User Story:** As an iPhone user, I want the bottom navigation bar to remain usable even though it contains seven routes, so that I can reach every page without the bar becoming too cramped to tap.

#### Acceptance Criteria

1. WHEN the viewport width is ≤ 680 px and the Mobile_Nav contains more than five items, THE Mobile_Nav SHALL display the first four routes as fixed items and collapse the remaining routes into a single "More" overflow button occupying the fifth slot.
2. WHEN the "More" button is tapped, THE React_App SHALL reveal the hidden routes in a compact sheet or popover anchored above the nav bar, with each item meeting the 44 × 44 px touch-target requirement.
3. THE active route indicator SHALL be visible on the "More" button itself when the currently active route is one of the hidden routes, so the user always knows which section is open.
4. WHEN a hidden route item is tapped, THE sheet SHALL dismiss and THE AppShell SHALL call `onNavigate` with the corresponding route path.
5. THE overflow sheet SHALL be dismissed by tapping outside it or by tapping the "More" button a second time.
6. THE overflow mechanism SHALL be implemented in `AppShell.tsx` (or `MobileNav.tsx` if already extracted) using React state and CSS, with no new npm packages.

---

### Requirement 11: RunTable mobile card layout

**User Story:** As an iPhone user viewing the Dashboard or Comparison page, I want the runs list to be readable without horizontal scrolling, so that I can quickly scan strategy results.

#### Acceptance Criteria

1. WHEN the viewport width is ≤ 680 px, THE `RunTable` component SHALL render each run as a stacked card instead of a table row, hiding the table element entirely.
2. EACH card SHALL display: strategy name (bold), run ID (muted, small), profit % (coloured by sign), win rate, drawdown, trade count, and an "Open" button.
3. THE card layout SHALL use CSS grid or flexbox within the existing CSS class system; no new CSS files are introduced.
4. WHEN the viewport width is > 680 px, THE `RunTable` SHALL render the existing table layout unchanged.
5. THE "Open" button on each card SHALL meet the 44 × 44 px touch-target requirement.

---

### Requirement 12: Equity chart touch interaction

**User Story:** As an iPhone user viewing the Run Detail chart, I want to drag my finger across the equity curve to see trade-by-trade balance values, so that I can analyse the chart without a mouse.

#### Acceptance Criteria

1. THE `EquityChart` component SHALL respond to `onTouchMove` events in addition to `onMouseMove`, so that the crosshair and tooltip update as the user drags a finger across the chart.
2. WHEN a touch starts or moves on the chart SVG, THE chart SHALL compute the nearest trade index from the touch X position using the same logic as the mouse handler.
3. WHEN the touch ends (`onTouchEnd`), THE chart SHALL clear the hover state, matching the `onMouseLeave` behaviour.
4. THE touch handlers SHALL call `event.preventDefault()` to suppress iOS Safari's default scroll behaviour while the finger is on the chart.
5. THE chart SVG SHALL set `touch-action: none` via inline style or CSS so that the browser does not intercept the touch for panning.

---

### Requirement 13: iOS Safari scroll momentum and interaction polish

**User Story:** As an iPhone user, I want scrollable areas inside the app to feel native — with momentum scrolling and no stuck hover highlights — so that the app feels as smooth as a native iOS app.

#### Acceptance Criteria

1. THE React_App SHALL apply `-webkit-overflow-scrolling: touch` (or the modern equivalent `overscroll-behavior: contain`) to `.terminal`, `.json-block`, `.param-list`, `.table-wrap`, `.tab-list`, and `.nav-list` so that these areas have momentum scrolling on iOS Safari.
2. WHEN the viewport is a touch device (`@media (hover: none)`), THE React_App SHALL suppress CSS hover styles on `.button`, `.icon-button`, `.nav-link`, `.tab`, `.chip`, and `.table-row-hover` so that tapping does not leave a stuck highlight.
3. THE hover suppression SHALL be applied via a `@media (hover: none)` block in `app.css`, not via JavaScript event listeners.

---

### Requirement 14: Dense-data component mobile layout fixes

**User Story:** As an iPhone user on the Optimizer page, I want the parameter list and trial tiles to be readable without overflowing the screen, so that I can review optimization results.

#### Acceptance Criteria

1. WHEN the viewport width is ≤ 680 px, THE `.param-row` and `.trial-tile` elements SHALL switch from their four-column grid to a two-column grid (name + value), hiding the less important middle columns.
2. WHEN the viewport width is ≤ 680 px, THE `.run-selector-wrap` SHALL expand to `width: 100%` so the run selector fills the available width on the Run Detail page header.
3. WHEN the viewport width is ≤ 680 px, THE `.comparison-controls` selects SHALL each be `width: 100%` so they fill their stacked column layout.
4. WHEN the viewport width is ≤ 680 px, THE `.chip` elements SHALL have a `min-height` of 36 px so they meet a reasonable tap target size within chip grids.
5. ALL changes in this requirement SHALL be applied via `@media (max-width: 680px)` rules in `app.css` with no changes to component TypeScript files.
