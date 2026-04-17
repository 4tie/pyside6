# Requirements Document

## Introduction

This feature redesigns the visual theme and layout of the Freqtrade GUI desktop application (PySide6) to produce a cleaner, more polished, and more consistent user interface. The current app already uses a dark VS Code-inspired stylesheet defined in `main_window.py`, but individual pages and widgets have inconsistent spacing, ad-hoc inline styles, and layout patterns that make the UI feel unfinished. The redesign centralises the theme into a dedicated module, enforces consistent spacing and typography across all pages and widgets, and improves the visual hierarchy so users can navigate and operate the app more efficiently.

## Glossary

- **Theme_Module**: The new `app/ui/theme.py` module that owns the global QSS stylesheet, colour palette constants, and spacing constants.
- **Main_Window**: The `MainWindow` class in `app/ui/main_window.py`.
- **Page**: Any top-level `QWidget` added as a tab — Backtest, Optimize, Download Data, Strategy Config, Terminal.
- **Widget**: A reusable sub-component — `TerminalWidget`, `BacktestResultsWidget`, `BacktestStatsWidget`, `BacktestSummaryWidget`, `BacktestTradesWidget`, `DataStatusWidget`.
- **Toolbar**: The `QToolBar` at the top of `Main_Window`.
- **Tab_Bar**: The `QTabBar` that switches between Pages.
- **Params_Panel**: The left-hand form panel present on Backtest, Optimize, and Download Data pages.
- **Output_Panel**: The right-hand terminal/results panel present on Backtest, Optimize, and Download Data pages.
- **Inline_Style**: A `setStyleSheet(...)` call made directly on an individual widget rather than through `Theme_Module`.
- **Colour_Palette**: The set of named colour constants defined in `Theme_Module`.
- **Spacing_Scale**: The set of named integer margin/padding/spacing constants defined in `Theme_Module`.

---

## Requirements

### Requirement 1: Centralised Theme Module

**User Story:** As a developer, I want all colours, spacing values, and the global QSS stylesheet to live in one place, so that I can update the visual design without hunting through multiple files.

#### Acceptance Criteria

1. THE `Theme_Module` SHALL define a `PALETTE` dict containing at minimum the colour keys: `bg_base`, `bg_surface`, `bg_elevated`, `border`, `border_focus`, `text_primary`, `text_secondary`, `text_disabled`, `accent`, `accent_hover`, `accent_pressed`, `success`, `danger`, `warning`.
2. THE `Theme_Module` SHALL define a `SPACING` dict containing at minimum the keys: `xs` (4 px), `sm` (8 px), `md` (12 px), `lg` (16 px), `xl` (24 px).
3. THE `Theme_Module` SHALL expose a `build_stylesheet() -> str` function that returns the complete application QSS string built from `PALETTE` and `SPACING` constants.
4. WHEN `Main_Window.__init__` is called, THE `Main_Window` SHALL call `Theme_Module.build_stylesheet()` and pass the result to `QApplication.instance().setStyleSheet()`.
5. THE `Theme_Module` SHALL be the single source of truth for colours — no hex colour literals SHALL appear in any other UI file after the redesign.

### Requirement 2: Elimination of Inline Styles

**User Story:** As a developer, I want inline `setStyleSheet` calls removed from page and widget files, so that the theme is applied uniformly and overrides are easy to reason about.

#### Acceptance Criteria

1. THE `Theme_Module` SHALL cover all widget types currently styled inline, including `QLabel` path/status labels, validation warning banners, export path labels, and pairs display labels.
2. WHEN a widget requires a semantic variant (e.g. danger, success, secondary, warning), THE `Theme_Module` SHALL define a QSS rule scoped to a Qt object name (e.g. `QLabel#warning_banner`) so that pages can apply the variant by calling `widget.setObjectName("warning_banner")` without any inline stylesheet.
3. THE `BacktestPage`, `DownloadDataPage`, `StrategyConfigPage`, `OptimizePage`, and `TerminalWidget` SHALL contain zero `setStyleSheet(...)` calls after the redesign, with the exception of the single `apply_preferences` call in `TerminalWidget` that applies user-configurable terminal colours.

### Requirement 3: Consistent Page Layout — Params/Output Split

**User Story:** As a user, I want the Backtest, Optimize, and Download Data pages to have a consistent two-panel layout with uniform spacing, so that the app feels coherent and I always know where to look.

#### Acceptance Criteria

1. THE `BacktestPage`, `OptimizePage`, and `DownloadDataPage` SHALL each use a horizontal split with the `Params_Panel` on the left and the `Output_Panel` on the right, with a fixed stretch ratio of 1:2.
2. THE `Params_Panel` on each Page SHALL use `SPACING["lg"]` (16 px) as the outer content margin and `SPACING["sm"]` (8 px) as the spacing between form rows.
3. THE `Output_Panel` on each Page SHALL use `SPACING["sm"]` (8 px) as the outer content margin.
4. WHEN a Page is displayed, THE `Params_Panel` SHALL have a minimum width of 260 px and a maximum width of 360 px so that it does not grow excessively on wide screens.
5. THE `Params_Panel` on each Page SHALL use a `QScrollArea` so that its contents remain accessible when the window is resized below the minimum height.

### Requirement 4: Typography Consistency

**User Story:** As a user, I want all text in the app to use a consistent font family and size scale, so that the interface looks professional and is easy to read.

#### Acceptance Criteria

1. THE `Theme_Module` SHALL define a `FONT` dict containing at minimum the keys: `family` (system sans-serif fallback chain), `size_sm` (11 px), `size_base` (13 px), `size_lg` (15 px), `mono_family` (monospace fallback chain).
2. THE `build_stylesheet()` function SHALL apply `FONT["family"]` and `FONT["size_base"]` as the default font for `QWidget`.
3. THE `build_stylesheet()` function SHALL apply `FONT["mono_family"]` and `FONT["size_sm"]` to `QPlainTextEdit` and `QTextEdit` so that terminal output uses a monospace font by default.
4. THE `build_stylesheet()` function SHALL apply `FONT["size_sm"]` to `QLabel` instances with object name `hint_label` to distinguish secondary/hint text from primary labels.

### Requirement 5: Toolbar and Tab Bar Visual Refinement

**User Story:** As a user, I want the toolbar and tab bar to look polished and clearly indicate the active tab, so that navigation feels intentional and modern.

#### Acceptance Criteria

1. THE `Toolbar` SHALL display the application title on the left and the Settings action on the right, separated by an expanding spacer — this existing behaviour SHALL be preserved.
2. THE `build_stylesheet()` function SHALL style `QTabBar::tab` with a bottom-border indicator of 2 px using `PALETTE["accent"]` for the selected tab and `transparent` for unselected tabs.
3. THE `build_stylesheet()` function SHALL style `QTabBar::tab` with `PALETTE["bg_surface"]` background for unselected tabs and `PALETTE["bg_base"]` for the selected tab, creating a subtle lift effect.
4. THE `build_stylesheet()` function SHALL remove the default `QTabWidget::pane` border and replace it with a 1 px top border using `PALETTE["border"]` to visually connect the tab bar to the page content.
5. THE `Toolbar` height SHALL be constrained to 40 px via `setFixedHeight` so that it does not expand on high-DPI displays.

### Requirement 6: Form Controls Visual Consistency

**User Story:** As a user, I want all input fields, combo boxes, spin boxes, and buttons to have a consistent look and feel, so that the interface feels unified.

#### Acceptance Criteria

1. THE `build_stylesheet()` function SHALL apply a uniform border-radius of 4 px to `QLineEdit`, `QSpinBox`, `QDoubleSpinBox`, `QComboBox`, `QPushButton`, and `QGroupBox`.
2. THE `build_stylesheet()` function SHALL apply `PALETTE["border_focus"]` as the border colour for `QLineEdit`, `QSpinBox`, `QDoubleSpinBox`, and `QComboBox` when they receive keyboard focus.
3. THE `build_stylesheet()` function SHALL style `QPushButton` with `PALETTE["accent"]` background and `PALETTE["text_primary"]` foreground as the default primary action style.
4. THE `build_stylesheet()` function SHALL style `QPushButton#secondary` with a transparent background, `PALETTE["border"]` border, and `PALETTE["text_secondary"]` foreground.
5. THE `build_stylesheet()` function SHALL style `QPushButton#danger` with `PALETTE["danger"]` background.
6. THE `build_stylesheet()` function SHALL style `QPushButton#success` with `PALETTE["success"]` background.
7. WHEN a `QPushButton` is disabled, THE `build_stylesheet()` function SHALL apply `PALETTE["bg_elevated"]` background and `PALETTE["text_disabled"]` foreground.

### Requirement 7: GroupBox and Section Header Styling

**User Story:** As a user, I want group boxes and section headers to visually separate content areas without adding visual clutter, so that the layout is easy to scan.

#### Acceptance Criteria

1. THE `build_stylesheet()` function SHALL style `QGroupBox` with a 1 px border using `PALETTE["border"]`, a border-radius of 6 px, and a top margin of `SPACING["lg"]` px to accommodate the title.
2. THE `build_stylesheet()` function SHALL style `QGroupBox::title` with `PALETTE["text_secondary"]` colour, `FONT["size_sm"]` font size, and uppercase letter-spacing to distinguish it from body text.
3. THE `build_stylesheet()` function SHALL NOT apply a background colour to `QGroupBox` so that it inherits the page background transparently.

### Requirement 8: Scrollbar Styling

**User Story:** As a user, I want scrollbars to be slim and unobtrusive, so that they do not distract from the content.

#### Acceptance Criteria

1. THE `build_stylesheet()` function SHALL style vertical `QScrollBar` with a width of 8 px and no arrow buttons.
2. THE `build_stylesheet()` function SHALL style horizontal `QScrollBar` with a height of 8 px and no arrow buttons.
3. THE `build_stylesheet()` function SHALL style `QScrollBar::handle` with `PALETTE["border"]` colour, a border-radius of 4 px, and a minimum length of 24 px.
4. WHEN the user hovers over a `QScrollBar::handle`, THE `build_stylesheet()` function SHALL apply `PALETTE["text_disabled"]` colour to the handle to provide hover feedback.

### Requirement 9: Status and Feedback Labels

**User Story:** As a user, I want validation warnings, status messages, and path labels to be visually distinct and consistently styled, so that I can quickly identify important feedback.

#### Acceptance Criteria

1. THE `build_stylesheet()` function SHALL define a style for `QLabel#warning_banner` using `PALETTE["warning"]` as a background tint, a 1 px border, and `SPACING["sm"]` padding.
2. THE `build_stylesheet()` function SHALL define a style for `QLabel#success_banner` using `PALETTE["success"]` as a background tint, a 1 px border, and `SPACING["sm"]` padding.
3. THE `build_stylesheet()` function SHALL define a style for `QLabel#path_label` using `PALETTE["text_secondary"]` colour and `FONT["size_sm"]` font size.
4. THE `build_stylesheet()` function SHALL define a style for `QLabel#status_ok` using `PALETTE["success"]` colour and bold font weight.
5. THE `build_stylesheet()` function SHALL define a style for `QLabel#status_error` using `PALETTE["danger"]` colour and bold font weight.

### Requirement 10: Theme Persistence and Settings Integration

**User Story:** As a user, I want the app to remember my preferred colour mode (dark/light) between sessions, so that I do not have to reconfigure it every time I launch the app.

#### Acceptance Criteria

1. THE `Theme_Module` SHALL expose a `ThemeMode` enum with values `DARK` and `LIGHT`.
2. THE `Theme_Module` SHALL expose a `build_stylesheet(mode: ThemeMode) -> str` function that returns the appropriate QSS for the given mode.
3. THE `AppSettings` model SHALL include a `theme_mode` field of type `str` with default value `"dark"` and a description of `"UI colour mode: dark or light"`.
4. WHEN `Main_Window.__init__` is called, THE `Main_Window` SHALL read `settings.theme_mode` and pass the corresponding `ThemeMode` to `Theme_Module.build_stylesheet()`.
5. WHEN the user changes `theme_mode` in the Settings dialog and saves, THE `Main_Window` SHALL re-apply the stylesheet by calling `QApplication.instance().setStyleSheet(Theme_Module.build_stylesheet(new_mode))` without requiring an app restart.
