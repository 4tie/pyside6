# Requirements Document

## Introduction

This feature redesigns the tab layouts across the Freqtrade GUI desktop application to fix content overflow and clipping issues. Currently, pages like Optimize and Strategy Config suffer from controls being cut off or requiring unexpected scrolling. The redesign ensures all controls are visible and accessible within each tab, and splits dense content into logical sub-sections where needed. The terminal output remains always visible as before.

## Glossary

- **Tab_Page**: A top-level page widget hosted inside the main `QTabWidget` (Backtest, Optimize, Download Data, Strategy Config, Settings).
- **Params_Panel**: The left-side scrollable panel on a Tab_Page that contains configuration controls (strategy, timeframe, pairs, etc.).
- **Output_Panel**: The right-side panel on a Tab_Page that contains the terminal and/or results widgets.
- **Terminal_Widget**: The `TerminalWidget` component that streams live subprocess stdout/stderr output.
- **Terminal_Toggle**: A collapsible section header button that shows or hides the Terminal_Widget.
- **Sub_Section**: A `QGroupBox` or equivalent container used to group related controls within a Params_Panel.
- **Overflow**: A condition where widget content extends beyond the visible bounds of its parent container, causing clipping or requiring unintended scrolling.
- **Settings_Page**: The settings configuration Tab_Page (`settings_page.py`).
- **Backtest_Page**: The backtest Tab_Page (`backtest_page.py`).
- **Optimize_Page**: The hyperopt Tab_Page (`optimize_page.py`).
- **Download_Page**: The data download Tab_Page (`download_data_page.py`).
- **Strategy_Config_Page**: The strategy parameter editor Tab_Page (`strategy_config_page.py`).

---

## Requirements

### Requirement 1: Params Panel Fits Without Overflow

**User Story:** As a user, I want all configuration controls on every Tab_Page to be fully visible without horizontal clipping, so that I can access every input without resizing the window.

#### Acceptance Criteria

1. THE Params_Panel SHALL use a `QScrollArea` with `setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)` so that no horizontal scrollbar appears and no content is clipped horizontally.
2. WHEN the application window is at its minimum supported width (800 px), THE Params_Panel SHALL display all controls without horizontal Overflow.
3. THE Params_Panel SHALL set a `minimumWidth` of no less than 320 px and a `maximumWidth` of no more than 520 px so that it does not crowd the Output_Panel.
4. WHILE the Params_Panel contains more controls than fit vertically in the visible area, THE Params_Panel SHALL provide a vertical scrollbar so the user can reach all controls.

---

### Requirement 2: Terminal Widget Hidden by Default with Toggle

**User Story:** As a user, I want the live terminal output to be hidden by default and revealed only when I need it, so that the Output_Panel is not dominated by an empty text area before a run starts.

#### Acceptance Criteria

1. THE Terminal_Toggle SHALL be rendered as a clickable button or section header labelled "Terminal Output ▶" when the Terminal_Widget is hidden.
2. WHEN the user clicks the Terminal_Toggle, THE Terminal_Widget SHALL become visible and the Terminal_Toggle label SHALL change to "Terminal Output ▼".
3. WHEN the user clicks the Terminal_Toggle again while the Terminal_Widget is visible, THE Terminal_Widget SHALL become hidden and the Terminal_Toggle label SHALL revert to "Terminal Output ▶".
4. WHEN a subprocess run starts on any Tab_Page, THE Terminal_Widget SHALL automatically become visible and the Terminal_Toggle label SHALL update to "Terminal Output ▼".
5. THE Terminal_Toggle collapse state SHALL persist per Tab_Page for the lifetime of the application session (i.e. collapsing the terminal on Optimize_Page SHALL NOT affect the state on Backtest_Page).
6. WHILE the Terminal_Widget is hidden, THE Output_Panel SHALL expand its remaining content (results tabs, advisor panel, etc.) to fill the freed vertical space.

---

### Requirement 3: Optimize Page Layout Restructured into Sub-Sections

**User Story:** As a user, I want the Optimize page controls to be organised into clearly labelled sub-sections, so that I can quickly find the setting I need without scrolling through an undifferentiated list.

#### Acceptance Criteria

1. THE Optimize_Page SHALL group strategy selection, timeframe, timerange presets, and custom timerange into a Sub_Section labelled "Run Configuration".
2. THE Optimize_Page SHALL group pairs selection into a Sub_Section labelled "Pairs".
3. THE Optimize_Page SHALL retain the existing "Hyperopt Options" Sub_Section containing epochs, spaces, and loss function.
4. THE Optimize_Page SHALL retain the existing "💡 Hyperopt Advisor" collapsible Sub_Section below the Hyperopt Options.
5. WHEN the Optimize_Page Params_Panel is displayed at minimum width, THE Optimize_Page SHALL show all Sub_Sections without horizontal Overflow.

---

### Requirement 4: Strategy Config Page Layout Fits Without Overflow

**User Story:** As a user, I want the Strategy Config page to display all parameter groups and the ROI table without clipping, so that I can edit every field without resizing the window.

#### Acceptance Criteria

1. THE Strategy_Config_Page SHALL wrap the left parameter panel (stoploss, trailing stop, buy/sell params) in a `QScrollArea` with vertical scrolling enabled and horizontal scrolling disabled.
2. THE Strategy_Config_Page SHALL ensure the ROI table panel on the right is also scrollable vertically when the table contains more rows than the visible area.
3. WHEN the Strategy_Config_Page is displayed at minimum window width (800 px), THE Strategy_Config_Page SHALL show both the left parameter panel and the ROI table panel without horizontal Overflow.

---

### Requirement 5: Settings Page Scrollable

**User Story:** As a user, I want the Settings page to be fully scrollable so that all setting groups (venv, paths, terminal, AI, appearance) are reachable without the window needing to be taller than the screen.

#### Acceptance Criteria

1. THE Settings_Page SHALL wrap all setting groups in a `QScrollArea` with vertical scrolling enabled and horizontal scrolling disabled.
2. WHEN the Settings_Page is displayed at a window height of 600 px, THE Settings_Page SHALL allow the user to scroll to the Save and Validate buttons at the bottom.
3. THE Settings_Page SHALL NOT clip any `QGroupBox` or form row horizontally at window widths of 800 px or greater.

---

### Requirement 6: Download Data Page Layout Consistent

**User Story:** As a user, I want the Download Data page to follow the same two-panel layout pattern as the other pages, so that the UI feels consistent and all controls are accessible.

#### Acceptance Criteria

1. THE Download_Page Params_Panel SHALL use a `QScrollArea` with horizontal scrolling disabled and a `minimumWidth` of 320 px.
2. THE Download_Page Output_Panel SHALL contain the Terminal_Toggle and Terminal_Widget following the same collapsible pattern defined in Requirement 2.
3. WHEN the Download_Page is displayed at minimum window width (800 px), THE Download_Page SHALL show all controls in the Params_Panel without horizontal Overflow.

---

### Requirement 7: Backtest Page Terminal Follows Toggle Pattern

**User Story:** As a user, I want the Backtest page terminal to follow the same hide/show toggle pattern as the other pages, so that the Results tab has more space by default.

#### Acceptance Criteria

1. THE Backtest_Page Output_Panel SHALL contain a Terminal_Toggle above the existing `QTabWidget` that controls Terminal_Widget visibility.
2. WHEN a backtest run completes successfully, THE Backtest_Page SHALL automatically switch to the Results tab AND keep the Terminal_Widget in its current toggle state (do not force-expand it).
3. IF the Terminal_Widget is hidden when a backtest run starts, THEN THE Backtest_Page SHALL automatically show the Terminal_Widget so the user can see live output.

---

### Requirement 8: Minimum Window Size Enforced

**User Story:** As a user, I want the application window to enforce a minimum size so that the layout never collapses into an unusable state.

#### Acceptance Criteria

1. THE Main_Window SHALL call `setMinimumSize(800, 600)` so that the window cannot be resized below 800 × 600 px.
2. WHEN the window is at exactly 800 × 600 px, THE Tab_Page currently displayed SHALL show all primary controls without Overflow.
