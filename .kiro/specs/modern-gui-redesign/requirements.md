# Requirements Document

## Introduction

This document defines the requirements for a complete GUI redesign of the Freqtrade GUI desktop
application. The redesign replaces the current `app/ui/` layer with a clean, modern,
user-guided interface built on PySide6 (Qt6), Python 3.9+, and Pydantic v2. All existing backend
services (`app/core/`) remain unchanged. The new UI must be intuitive — the user should always
know their next step — and must reduce manual text entry by favouring dropdowns, selectors, and
presets. Every user preference (strategy, pairs, timeframe, theme, etc.) must survive application
restarts.

Key new capabilities introduced by this redesign:
- Multi-select pairs dropdown with favourites pinned to the top
- Timerange presets plus a custom date-range input
- Full Results view with overview metrics, trades table, per-pair breakdown, and diagnostics
- Strategy Lab as a step-based pipeline UI (baseline → analyse → improve → compare → accept/reject)
- Side-by-side comparison view with visual diff highlighting
- Centralised dark and light theme system (dark theme uses neutral gray, never blue-black)
- Compact, responsive, scalable layout with consistent spacing and typography

---

## Glossary

- **Application**: The Freqtrade GUI PySide6 desktop application.
- **Theme_System**: The centralised module (`app/ui/theme.py`) that owns all colour palettes,
  spacing scales, font constants, and QSS generation.
- **Main_Window**: The top-level `QMainWindow` (`ModernMainWindow`) that hosts the sidebar,
  header bar, stacked page area, terminal dock, and AI panel dock.
- **Sidebar**: The collapsible left navigation panel (`NavSidebar`) that lists all top-level pages.
- **Page**: A full-screen `QWidget` displayed in the stacked widget area (e.g. Backtest, Results,
  Strategy Lab, Settings).
- **RunConfigForm**: The reusable configuration form widget used on the Backtest and Optimize pages
  (strategy selector, timeframe selector, timerange input, pairs selector).
- **PairsSelector**: The multi-select dropdown/dialog widget that allows the user to choose trading
  pairs, with favourites pinned to the top.
- **TimerangeControl**: The widget that offers preset timerange buttons (e.g. 1 M, 3 M, 6 M, 1 Y,
  YTD, All) plus a custom date-range input.
- **Results_View**: The tabbed results area shown after a backtest completes or a saved run is
  loaded. Contains Overview, Trades, Pair Results, and Diagnostics sub-views.
- **Overview_Panel**: The sub-view inside Results_View that shows high-level metrics (start
  balance, end balance, total profit, win rate, max drawdown, trade count, Sharpe ratio).
- **Trades_Table**: The sub-view inside Results_View that lists every individual trade with
  sortable columns.
- **Pair_Results_Table**: The sub-view inside Results_View that shows per-pair aggregated
  statistics (profit, win rate, trade count).
- **Diagnostics_Panel**: The sub-view inside Results_View that shows rule-based logic insights
  about strategy behaviour (e.g. bad stoploss, low trade count, weak ROI).
- **Strategy_Lab**: The step-based pipeline page that guides the user through the iterative
  improvement loop: Baseline → Analyse → Improve → Compare → Accept/Reject.
- **Comparison_View**: The widget that displays two backtest runs side-by-side with visual
  highlighting of metric differences.
- **Settings_State**: The `SettingsState` QObject that holds the current `AppSettings` and emits
  `settings_saved` / `settings_changed` signals.
- **AppSettings**: The Pydantic `BaseModel` that persists all user preferences to
  `~/.freqtrade_gui/settings.json`.
- **QSettings**: Qt's built-in key-value store used for UI-only state (window geometry, splitter
  positions, last active page).
- **Terminal_Panel**: The dockable `QDockWidget` that streams live subprocess stdout/stderr output.
- **AI_Panel**: The dockable `QDockWidget` that hosts the AI chat interface (optional feature).
- **Onboarding_Wizard**: The first-run dialog that guides the user through configuring the venv
  path and user_data directory.
- **Command_Palette**: The Ctrl+P overlay that provides fuzzy-search access to all application
  commands.
- **ProcessService**: The service (`app/core/services/process_service.py`) that owns the
  `QProcess` lifecycle for all subprocess execution.
- **BacktestService**: The service (`app/core/services/backtest_service.py`) that builds backtest
  commands and coordinates result parsing.
- **RunStore**: The static service (`app/core/services/run_store.py`) that saves and loads
  backtest run directories.
- **IndexStore**: The static service (`app/core/backtests/results_index.py`) that maintains the
  global and per-strategy run indexes.

---

## Requirements

### Requirement 1: Centralised Theme System

**User Story:** As a developer, I want all colours, spacing, and typography defined in one place,
so that the entire application can be restyled by editing a single module.

#### Acceptance Criteria

1. THE Theme_System SHALL define exactly two colour palettes: a dark palette and a light palette,
   each as a typed dictionary with the keys `bg_base`, `bg_surface`, `bg_elevated`, `bg_card`,
   `border`, `border_focus`, `text_primary`, `text_secondary`, `text_disabled`, `accent`,
   `accent_hover`, `accent_pressed`, `success`, `danger`, and `warning`.
2. THE Theme_System SHALL define the dark palette using neutral gray backgrounds where `bg_base`
   is `#1e1e1e`, `bg_surface` is `#252526`, `bg_elevated` is `#2d2d30`, and `bg_card` is
   `#333337`, with no blue or blue-black tones in any background key.
3. THE Theme_System SHALL define a single `build_stylesheet(mode: ThemeMode) -> str` function
   that returns a complete QSS string covering all standard Qt widget types used in the
   Application.
4. THE Theme_System SHALL define a single `build_v2_additions(palette, spacing, font) -> str`
   function that returns QSS for all custom object names introduced by the v2 UI layer.
5. WHEN the user switches theme mode, THE Main_Window SHALL call `build_stylesheet` and
   `build_v2_additions` and apply the combined result to `QApplication.setStyleSheet` within
   one event-loop cycle.
6. THE Theme_System SHALL expose `SPACING` and `FONT` constants so that all layout code
   references them rather than hardcoding pixel values or font sizes.
7. IF a caller passes an unrecognised `ThemeMode` value to `build_stylesheet`, THEN THE
   Theme_System SHALL log a warning and fall back to `ThemeMode.DARK`.
8. THE Theme_System SHALL NOT import from any UI page, widget, or panel module — it is a
   pure data/string module.

---

### Requirement 2: Persistent User Preferences

**User Story:** As a user, I want my strategy, pairs, timeframe, theme, and other settings to be
remembered across restarts, so that I never have to re-enter the same configuration.

#### Acceptance Criteria

1. WHEN the Application starts, THE Settings_State SHALL load `AppSettings` from
   `~/.freqtrade_gui/settings.json` before any page is rendered.
2. WHEN the user changes the active strategy, timeframe, pairs, or timerange on the Backtest page,
   THE Application SHALL persist those values to `AppSettings.backtest_preferences` within the
   same user action (i.e. before the next backtest run is triggered).
3. WHEN the Application starts after a previous session, THE RunConfigForm SHALL restore the last
   strategy, timeframe, pairs, and timerange from `AppSettings.backtest_preferences`.
4. WHEN the user changes the theme mode, THE Application SHALL persist the new mode to
   `AppSettings.theme_mode` and apply it immediately without requiring a restart.
5. WHEN the user marks a pair as a favourite in the PairsSelector, THE Application SHALL persist
   the updated favourites list to `AppSettings` so that favourites survive restarts.
6. WHEN the Application starts, THE Main_Window SHALL restore window geometry, dock widget
   positions, sidebar collapsed state, and the last active page from `QSettings`.
7. WHEN the Application closes, THE Main_Window SHALL save window geometry, dock widget
   positions, sidebar collapsed state, and the current active page to `QSettings`.
8. THE AppSettings SHALL use Pydantic v2 `BaseModel` with every field annotated using
   `Field(default, description="...")`.

---

### Requirement 3: Main Window Shell and Navigation

**User Story:** As a user, I want a clear, consistent navigation structure so that I can move
between all major sections of the application without confusion.

#### Acceptance Criteria

1. THE Main_Window SHALL display a collapsible Sidebar on the left, a header bar at the top, a
   stacked page area in the centre, and a status bar at the bottom.
2. THE Sidebar SHALL list navigation items for: Dashboard, Backtest, Optimize, Download Data,
   Strategy, Strategy Lab, and Settings.
3. WHEN the user clicks a Sidebar navigation item, THE Main_Window SHALL switch the stacked
   widget to the corresponding Page within one event-loop cycle.
4. WHEN the user collapses the Sidebar, THE Sidebar SHALL reduce to icon-only width and THE
   Main_Window SHALL expand the page area to fill the reclaimed space.
5. THE Main_Window SHALL provide keyboard shortcuts Ctrl+1 through Ctrl+7 to navigate directly
   to each Page in Sidebar order.
6. THE Main_Window SHALL provide a Command_Palette accessible via Ctrl+P that supports
   fuzzy-search over all registered commands.
7. THE Main_Window SHALL display a Terminal_Panel as a dockable widget at the bottom dock area,
   toggled via Ctrl+`.
8. WHERE the AI feature is enabled, THE Main_Window SHALL display an AI_Panel as a dockable
   widget at the right dock area, toggled via Ctrl+Shift+A.
9. WHEN the Application starts for the first time (venv path not configured), THE Main_Window
   SHALL display the Onboarding_Wizard before showing any Page.
10. THE Main_Window SHALL display a non-blocking status message in the status bar after every
    navigation event, settings save, and process completion.

---

### Requirement 4: Backtest Page — Configuration

**User Story:** As a user, I want to configure and run a backtest using dropdowns and selectors
rather than typing raw values, so that I make fewer configuration mistakes.

#### Acceptance Criteria

1. THE RunConfigForm SHALL provide a strategy selector that is populated by scanning
   `AppSettings.user_data_path / strategies /` for `.py` files and presenting them as a
   `QComboBox`.
2. THE RunConfigForm SHALL provide a timeframe selector implemented as a `QComboBox` pre-loaded
   with the values `1m`, `3m`, `5m`, `15m`, `30m`, `1h`, `2h`, `4h`, `6h`, `8h`, `12h`, `1d`,
   `3d`, `1w`, and `1M`.
3. THE RunConfigForm SHALL provide a TimerangeControl that offers preset buttons for `1M`, `3M`,
   `6M`, `1Y`, `YTD`, and `All`, plus a custom date-range input accepting `YYYYMMDD-YYYYMMDD`
   format.
4. WHEN the user selects a timerange preset, THE TimerangeControl SHALL compute the corresponding
   `YYYYMMDD-YYYYMMDD` string relative to today's date and populate the timerange field.
5. THE RunConfigForm SHALL provide a PairsSelector that opens a multi-select dialog listing all
   available pairs, with favourite pairs displayed above non-favourite pairs within the same list.
6. WHEN the user opens the PairsSelector, THE PairsSelector SHALL display pairs grouped as
   Favourites (top) and All Pairs (below), with a search/filter input.
7. WHEN the user toggles the favourite star on a pair, THE PairsSelector SHALL move that pair
   to or from the Favourites group immediately without closing the dialog.
8. THE Backtest page SHALL display a collapsible "Advanced Options" section containing dry-run
   wallet size (`QDoubleSpinBox`) and max open trades (`QSpinBox`).
9. THE Backtest page SHALL display a collapsible "Command Preview" section showing the exact
   CLI command that will be executed, updated live as form values change.
10. WHEN the user clicks "Run", THE Backtest page SHALL validate that strategy, timeframe, and
    at least one pair are selected; IF any are missing, THEN THE Backtest page SHALL display a
    `QMessageBox` warning identifying the missing field.

---

### Requirement 5: Backtest Page — Execution and Results Loading

**User Story:** As a user, I want the backtest to run in the background and results to load
automatically when it finishes, so that I do not have to manually find and import result files.

#### Acceptance Criteria

1. WHEN the user clicks "Run", THE Backtest page SHALL disable the Run button, enable the Stop
   button, switch to the Terminal tab, and start the backtest via `ProcessService`.
2. WHILE the backtest process is running, THE Terminal_Panel SHALL stream live stdout and stderr
   output from the subprocess.
3. WHEN the backtest process exits with code 0, THE Backtest page SHALL automatically locate the
   newest `.zip` file written to `backtest_results/` since the run started, parse it, save it via
   `RunStore`, and load the results into the Results_View.
4. WHEN the backtest process exits with a non-zero code, THE Backtest page SHALL display an error
   message in the Terminal_Panel and re-enable the Run button without attempting to load results.
5. WHEN the user clicks "Stop", THE Backtest page SHALL call `ProcessService.stop_process()` and
   re-enable the Run button after the process terminates.
6. THE Backtest page SHALL provide a run-picker `QComboBox` listing all saved runs for the
   currently selected strategy, labelled with run ID, profit percentage, trade count, and
   timestamp.
7. WHEN the user selects a run from the run-picker and clicks "Load", THE Backtest page SHALL
   load that run from `RunStore` and populate the Results_View.
8. WHEN the strategy selection changes, THE Backtest page SHALL refresh the run-picker to show
   only runs for the newly selected strategy.

---

### Requirement 6: Results View

**User Story:** As a user, I want a comprehensive results view that shows me all the information
I need to evaluate a strategy's performance in one place.

#### Acceptance Criteria

1. THE Results_View SHALL be organised as a `QTabWidget` with four tabs: Overview, Trades,
   Pair Results, and Diagnostics.
2. THE Overview_Panel SHALL display the following metrics as labelled cards: starting balance,
   ending balance, total profit (absolute and percentage), win rate, max drawdown, total trade
   count, and Sharpe ratio.
3. WHEN a metric value represents a gain (profit > 0, win rate > 50%), THE Overview_Panel SHALL
   render that metric's value in the `success` colour from the active palette.
4. WHEN a metric value represents a loss (profit < 0, drawdown > 20%), THE Overview_Panel SHALL
   render that metric's value in the `danger` colour from the active palette.
5. THE Trades_Table SHALL display one row per trade with sortable columns: pair, open date, close
   date, duration, profit (%), profit (absolute), and trade direction (long/short).
6. WHEN the user clicks a column header in the Trades_Table, THE Trades_Table SHALL sort all rows
   by that column, toggling between ascending and descending order on successive clicks.
7. THE Pair_Results_Table SHALL display one row per pair with columns: pair, total profit (%),
   win rate (%), and trade count; rows SHALL be sorted by total profit descending by default.
8. THE Diagnostics_Panel SHALL display rule-based insights as a list of labelled findings, each
   with a severity indicator (info, warning, or error) and a plain-language explanation.
9. WHEN no results are loaded, THE Results_View SHALL display a placeholder message in each tab
   instructing the user to run a backtest or load a saved run.
10. THE Results_View SHALL update all four tabs atomically when new results are loaded, with no
    partial state visible to the user.

---

### Requirement 7: Comparison View

**User Story:** As a user, I want to compare two backtest runs side-by-side so that I can
objectively evaluate whether a strategy change improved performance.

#### Acceptance Criteria

1. THE Comparison_View SHALL allow the user to select two runs (Run A and Run B) from separate
   `QComboBox` widgets populated with the same run-picker data as the Backtest page.
2. WHEN the user clicks "Compare", THE Comparison_View SHALL load both runs from `RunStore` and
   display their metrics side-by-side in a table with columns: Metric, Run A, Run B, and Delta.
3. WHEN a Delta value is positive (Run B better than Run A), THE Comparison_View SHALL render
   that Delta cell in the `success` colour.
4. WHEN a Delta value is negative (Run B worse than Run A), THE Comparison_View SHALL render
   that Delta cell in the `danger` colour.
5. THE Comparison_View SHALL display a verdict label summarising the comparison outcome
   (e.g. "Run B is better", "Run A is better", or "No significant difference").
6. IF either selected run cannot be loaded from `RunStore`, THEN THE Comparison_View SHALL
   display a `QMessageBox` error and leave the comparison table unchanged.

---

### Requirement 8: Strategy Lab — Step-Based Pipeline

**User Story:** As a user, I want a guided, step-by-step workflow for iteratively improving a
strategy, so that I always know what to do next and cannot accidentally skip a required step.

#### Acceptance Criteria

1. THE Strategy_Lab SHALL present the improvement pipeline as a sequence of named steps:
   (1) Baseline, (2) Analyse, (3) Improve, (4) Compare, (5) Accept/Reject.
2. THE Strategy_Lab SHALL display a step indicator at the top of the page showing all five steps,
   with the current step highlighted and completed steps marked with a checkmark.
3. WHEN the user has not yet established a baseline, THE Strategy_Lab SHALL display only the
   Baseline step as active and all subsequent steps as disabled.
4. WHEN the user completes the Baseline step by running a backtest, THE Strategy_Lab SHALL
   automatically advance to the Analyse step and enable it.
5. THE Analyse step SHALL display the Diagnostics_Panel populated with findings from the baseline
   run, and a "Proceed to Improve" button that advances to the Improve step.
6. THE Improve step SHALL allow the user to select a candidate strategy file and run a backtest
   against it, producing a candidate result.
7. WHEN the candidate backtest completes, THE Strategy_Lab SHALL automatically advance to the
   Compare step and populate the Comparison_View with baseline vs candidate results.
8. THE Accept/Reject step SHALL display the comparison summary and two buttons: "Accept" (marks
   the candidate as the new accepted version) and "Reject" (discards the candidate and returns
   to the Improve step).
9. WHEN the user clicks "Accept", THE Strategy_Lab SHALL call the versioning service to promote
   the candidate to the accepted version and reset the pipeline to the Baseline step with the
   new accepted version as the new baseline.
10. WHEN the user clicks "Reject", THE Strategy_Lab SHALL discard the candidate result and
    return the pipeline to the Improve step without modifying the accepted version.
11. THE Strategy_Lab SHALL persist the current pipeline state (current step, baseline run ID,
    candidate run ID) to `AppSettings` so that the user can resume after a restart.

---

### Requirement 9: Download Data Page

**User Story:** As a user, I want to download OHLCV market data using the same pair and timeframe
selectors as the Backtest page, so that I do not have to re-enter configuration I have already set.

#### Acceptance Criteria

1. THE Download Data page SHALL provide a PairsSelector, a timeframe selector, and a timerange
   input using the same RunConfigForm widget as the Backtest page.
2. WHEN the user clicks "Download", THE Download Data page SHALL validate that at least one pair
   and one timeframe are selected; IF either is missing, THEN THE Download Data page SHALL
   display a `QMessageBox` warning.
3. WHEN the download process is running, THE Terminal_Panel SHALL stream live output from the
   subprocess.
4. WHEN the download process exits with code 0, THE Download Data page SHALL display a success
   message in the status bar.
5. WHEN the download process exits with a non-zero code, THE Download Data page SHALL display an
   error message in the Terminal_Panel.

---

### Requirement 10: Optimize Page

**User Story:** As a user, I want to run hyperparameter optimisation with the same configuration
controls as backtesting, so that I can quickly iterate between backtesting and optimising.

#### Acceptance Criteria

1. THE Optimize page SHALL provide a strategy selector, timeframe selector, timerange input, and
   pairs selector using the same RunConfigForm widget as the Backtest page.
2. THE Optimize page SHALL provide additional controls for: number of epochs (`QSpinBox`),
   hyperopt loss function (`QComboBox`), and spaces to optimise (checkboxes for buy, sell, roi,
   stoploss, trailing).
3. WHEN the user clicks "Run Optimize", THE Optimize page SHALL validate that strategy, timeframe,
   and at least one pair are selected; IF any are missing, THEN THE Optimize page SHALL display a
   `QMessageBox` warning.
4. WHEN the optimize process is running, THE Terminal_Panel SHALL stream live output from the
   subprocess.
5. WHEN the optimize process exits with code 0, THE Optimize page SHALL display a success message
   in the status bar.

---

### Requirement 11: Strategy Page

**User Story:** As a user, I want to browse and manage my strategies from a dedicated page so
that I can quickly launch a backtest or optimisation run for any strategy.

#### Acceptance Criteria

1. THE Strategy page SHALL display a list of all `.py` strategy files discovered in
   `AppSettings.user_data_path / strategies /`.
2. WHEN the user selects a strategy from the list, THE Strategy page SHALL display metadata for
   that strategy (file name, last modified date, and file size).
3. WHEN the user clicks "Backtest This Strategy", THE Strategy page SHALL emit a signal that
   causes the Main_Window to navigate to the Backtest page and pre-select that strategy in the
   RunConfigForm.
4. WHEN the user clicks "Optimize This Strategy", THE Strategy page SHALL emit a signal that
   causes the Main_Window to navigate to the Optimize page and pre-select that strategy in the
   RunConfigForm.
5. WHEN `AppSettings.user_data_path` changes, THE Strategy page SHALL refresh the strategy list
   automatically.

---

### Requirement 12: Settings Page

**User Story:** As a user, I want a clear settings page where I can configure all application
paths and preferences, with immediate validation feedback.

#### Acceptance Criteria

1. THE Settings page SHALL provide labelled input fields for: venv path, Python executable path,
   Freqtrade executable path, and user_data directory path.
2. WHEN the user clicks the browse button next to a path field, THE Settings page SHALL open a
   `QFileDialog` and populate the corresponding field with the selected path.
3. WHEN the user clicks "Validate", THE Settings page SHALL check that each configured path
   exists and is accessible, and display a per-field status indicator (green checkmark or red
   error label).
4. WHEN the user clicks "Save", THE Settings page SHALL persist the current field values to
   `AppSettings` via `Settings_State.save_settings()` and display a success banner.
5. THE Settings page SHALL provide a theme toggle (dark/light) that applies the new theme
   immediately via the Theme_System.
6. THE Settings page SHALL provide a terminal font size selector (`QSpinBox`) that updates the
   Terminal_Panel font size immediately.

---

### Requirement 13: Dashboard Page

**User Story:** As a user, I want a dashboard that gives me an at-a-glance summary of recent
activity and quick access to common actions, so that I can orient myself immediately on launch.

#### Acceptance Criteria

1. THE Dashboard page SHALL display the most recent backtest result as a summary card showing
   strategy name, profit percentage, trade count, and run timestamp.
2. THE Dashboard page SHALL display quick-action buttons for: "Run Last Backtest", "Go to
   Backtest", "Go to Strategy Lab", and "Go to Settings".
3. WHEN the user clicks a quick-action button, THE Dashboard page SHALL emit a `navigate_to`
   signal with the target page ID, causing the Main_Window to navigate to that page.
4. WHEN no backtest results exist, THE Dashboard page SHALL display a placeholder card with a
   "Run your first backtest" call-to-action button.
5. WHEN `AppSettings` changes, THE Dashboard page SHALL refresh the recent results summary.

---

### Requirement 14: Onboarding Wizard

**User Story:** As a first-time user, I want a guided setup wizard that helps me configure the
application before I can use it, so that I do not encounter cryptic errors from missing paths.

#### Acceptance Criteria

1. WHEN the Application starts and `AppSettings.venv_path` is empty or points to a non-existent
   directory, THE Main_Window SHALL display the Onboarding_Wizard as a modal dialog before
   rendering any Page.
2. THE Onboarding_Wizard SHALL guide the user through at least two steps: (1) select venv path,
   (2) select user_data directory.
3. WHEN the user completes all wizard steps and clicks "Finish", THE Onboarding_Wizard SHALL
   save the configured paths to `AppSettings` via `Settings_State.save_settings()` and close.
4. WHEN the user clicks "Cancel" or closes the Onboarding_Wizard without completing it, THE
   Main_Window SHALL remain functional but display a warning banner indicating that configuration
   is incomplete.

---

### Requirement 15: Terminal Panel

**User Story:** As a user, I want a live terminal output panel that shows me exactly what
commands are running and what output they produce, so that I can diagnose failures without
leaving the application.

#### Acceptance Criteria

1. THE Terminal_Panel SHALL display subprocess stdout in the default text colour and stderr in
   the `warning` colour from the active palette.
2. THE Terminal_Panel SHALL provide a "Clear" button that removes all current output.
3. THE Terminal_Panel SHALL automatically scroll to the bottom when new output is appended,
   unless the user has manually scrolled up, in which case THE Terminal_Panel SHALL not
   auto-scroll until the user scrolls back to the bottom.
4. THE Terminal_Panel SHALL support configurable font size, persisted to `AppSettings`.
5. WHEN the Terminal_Panel is hidden and a process produces output, THE Terminal_Panel SHALL
   display a badge on its toggle button indicating unread output.

---

### Requirement 16: Accessibility

**User Story:** As a user who relies on keyboard navigation or assistive technology, I want all
interactive controls to be accessible, so that I can use the application without a mouse.

#### Acceptance Criteria

1. THE Application SHALL set `setAccessibleName()` on every interactive widget (buttons, inputs,
   combo boxes, checkboxes, table headers).
2. THE Application SHALL set `setToolTip()` on every interactive widget with a description of
   its purpose.
3. THE Application SHALL support full keyboard navigation through all form fields using Tab and
   Shift+Tab.
4. THE Application SHALL ensure that focus indicators are visible in both dark and light themes
   using the `border_focus` colour from the active palette.
5. THE Application SHALL ensure that all text meets a minimum contrast ratio of 4.5:1 against
   its background colour in both dark and light themes.

---

### Requirement 17: Layout Compactness and Responsiveness

**User Story:** As a user running the application on a laptop screen, I want the layout to be
compact and usable at 1024×600 resolution, so that I do not have to scroll horizontally or
resize panels constantly.

#### Acceptance Criteria

1. THE Main_Window SHALL set a minimum size of 1024×600 pixels.
2. THE RunConfigForm SHALL fit within a 300-pixel-wide left panel without horizontal overflow.
3. WHEN the Main_Window is resized, all Pages SHALL reflow their content using Qt layout managers
   (`QVBoxLayout`, `QHBoxLayout`, `QSplitter`) without clipping or overlapping widgets.
4. THE Sidebar SHALL support a collapsed icon-only mode with a minimum width of 48 pixels.
5. ALL splitter positions SHALL be persisted to `QSettings` and restored on next launch.

---

### Requirement 18: Code Quality and Modularity

**User Story:** As a developer, I want the UI code to be clean, modular, and consistent with the
project's existing conventions, so that it is easy to maintain and extend.

#### Acceptance Criteria

1. THE Application SHALL NOT import from any legacy UI module within any `app/ui/` module,
   except for `app/ui/theme.py` which is the single source of truth for all theme symbols.
2. THE Application SHALL NOT import from `app/ui/` within any `app/core/` module.
3. EVERY non-trivial module in `app/ui/` SHALL begin with a triple-quoted module-level
   docstring describing its purpose.
4. EVERY non-trivial module in `app/ui/` SHALL declare a module-level logger using
   `_log = get_logger("ui.<module_path>")`.
5. ALL UI page classes SHALL follow the construction order: store dependencies → `_build_ui()` →
   `_connect_signals()` → `_refresh_*()` → restore persisted state.
6. THE Theme_System SHALL be the single source of truth for all colour values; no page, widget,
   or panel module SHALL hardcode hex colour strings or pixel sizes outside of `theme.py`.
7. ALL interactive widgets SHALL call `setAccessibleName()` and `setToolTip()` during
   construction.
8. THE Application SHALL use `pathlib.Path` for all file system operations and SHALL NOT use
   string concatenation to build paths.
