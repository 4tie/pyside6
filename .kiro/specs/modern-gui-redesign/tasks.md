# Implementation Plan: Modern GUI Redesign

## Overview

Implement the redesigned UI within `app/ui/`, adding new subdirectories (`shell/`, `panels/`, `widgets/` subfolders) and updating existing files in-place. Each task builds incrementally — shared widgets first, then shell components, then pages, then wiring. All files in `app/core/` and `app/app_state/` are never touched.

All code is Python 3.9+ with PySide6. Follow project conventions: `_log = get_logger("ui.<module>")`, `snake_case` methods, `PascalCase` classes, empty `__init__.py` files.

---

## Tasks

- [x] 1. Scaffold `app/ui/` directory structure and update theme module
  - Create all `__init__.py` files (empty) for every new package under `app/ui/` (`shell/`, `panels/`, `widgets/` subfolders)
  - Update `app/ui/theme.py` in-place to add `build_v2_additions(palette, spacing, font) -> str` returning QSS for new object names (`nav_item`, `nav_item_active`, `metric_card`, `section_header`, `command_palette`, `toast_info`, `toast_success`, `toast_error`, `toast_warning`, `page_title`)
  - _Requirements: 1.1, 1.4, 1.7, 9.1, 9.2, 9.3, 18.1_

  - [x] 1.1 Write unit test for theme module and `build_v2_additions`
    - Verify `build_stylesheet` is importable from `app/ui/theme` and returns a non-empty string
    - Verify `build_v2_additions` returns a non-empty string containing each new object name
    - **Property P6: Theme Consistency — `build_stylesheet` and `build_v2_additions` must produce consistent output**
    - **Validates: Requirements 1.1, 1.4, 18.1**

- [-] 2. Implement shared widgets
  - [x] 2.1 Implement `MetricCard` in `app/ui/widgets/metric_card.py`
    - `QFrame` subclass with `title: str`, `value: str = "—"`, `trend: Optional[float] = None`
    - `objectName = "metric_card"`; trend arrow shown as `▲`/`▼` colored green/red
    - Public `set_value(value: str, trend: Optional[float])` method for live updates
    - _Requirements: 3.2, 5.1_

  - [x] 2.2 Implement `SectionHeader` in `app/ui/widgets/section_header.py`
    - `QWidget` wrapping any `QWidget` body; `QToolButton` arrow toggle; `toggled = Signal(bool)`
    - `collapsed: bool = False` constructor param; animates body show/hide
    - `objectName = "section_header"` on the title bar widget
    - _Requirements: 3.3, 3.6_

  - [x] 2.3 Implement `RunConfigForm` in `app/ui/widgets/run_config_form.py`
    - `QWidget` with `config_changed = Signal(dict)`; constructor flags `show_strategy`, `show_timeframe`, `show_timerange`, `show_pairs` (all default `True`)
    - `get_config() -> dict` and `set_config(config: dict) -> None` public API
    - Reuses `PairsSelectorDialog` from `app/ui/dialogs/pairs_selector_dialog.py` for pairs selection
    - Inline validation: non-empty strategy required when `show_strategy=True`; timeframe non-empty; timerange format validated
    - _Requirements: 4.1, 4.2, 4.3, 7.3, 7.4_

  - [x] 2.4 Write unit tests for `RunConfigForm`
    - Test `get_config` returns correct dict after setting each field
    - Test `set_config` populates all visible fields
    - Test `config_changed` signal fires on field change
    - Test inline validation rejects empty required fields
    - _Requirements: 4.3_

  - [x] 2.5 Implement `NotificationToast` in `app/ui/widgets/notification_toast.py`
    - `QWidget` overlay; `show_message(message: str, level: str = "info", duration_ms: int = 3000)`
    - Levels: `info`, `success`, `error`, `warning` — each sets matching `objectName`
    - Positioned bottom-right via `QWidget.move()`; auto-hides via `QTimer`
    - _Requirements: 7.3, 16.2_

  - [x] 2.6 Implement `CommandPalette` in `app/ui/widgets/command_palette.py`
    - Frameless `QDialog`; `command_selected = Signal(str)`
    - Constructor: `commands: list[dict]` where each dict has `id`, `label`, `shortcut`, `action`
    - `QLineEdit` at top with live fuzzy filtering into `QListWidget` below
    - Enter/click executes selected command and closes dialog
    - `objectName = "command_palette"` on the dialog
    - _Requirements: 11.1, 11.4_

  - [x] 2.7 Implement `OnboardingWizard` in `app/ui/widgets/onboarding_wizard.py`
    - `QWizard` subclass with pages: Welcome → Venv Path → User Data → Validation → Done
    - Venv Path page validates path exists and contains Python executable
    - User Data page validates directory exists or offers to create it
    - Validation page runs `SettingsService.validate_settings` and shows pass/fail per item
    - _Requirements: 20.1, 20.2, 20.3, 20.4_

- [x] 3. Implement shell components
  - [x] 3.1 Implement `NavSidebar` in `app/ui/shell/sidebar.py`
    - `QWidget` with `QVBoxLayout`; `nav_item_clicked = Signal(str)` emitting page id
    - `NavItem(QPushButton)` inner class: icon + label, checkable, `objectName = "nav_item"` / `"nav_item_active"`
    - Six nav items in order: dashboard, backtest, optimize, download, strategy, settings
    - Collapse toggle at bottom: `QPropertyAnimation` on `maximumWidth` between 48 px (icon-only) and 180 px
    - `set_active(page_id: str)` updates `objectName` on all items
    - _Requirements: 2.1, 2.3, 2.6, 2.7_

  - [x] 3.2 Implement `HeaderBar` in `app/ui/shell/header_bar.py`
    - `QWidget` fixed height 48 px; app icon + app name + breadcrumb separator + page title label
    - `set_page_title(title: str)` updates breadcrumb
    - Command palette button (🔍) and settings shortcut button (⚙) on right side
    - Theme toggle button cycles Dark → Light; calls `build_stylesheet` + `build_v2_additions` and applies via `QApplication.setStyleSheet`
    - _Requirements: 2.3, 9.1, 18.1, 18.5_

  - [x] 3.3 Implement `AppStatusBar` in `app/ui/shell/status_bar.py`
    - `QWidget` replacing default `QStatusBar`
    - `set_status(message: str, level: str = "info")` for process status messages
    - Displays last message with timestamp; clears after 10 seconds via `QTimer`
    - _Requirements: 3.2, 16.2_

- [x] 4. Implement dockable panels
  - [x] 4.1 Implement `TerminalPanel` in `app/ui/panels/terminal_panel.py`
    - `QDockWidget` subclass; wraps `TerminalWidget` from `app/ui/widgets/terminal_widget.py`
    - `setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)`
    - `setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable)`
    - Exposes `.terminal` attribute for external access
    - _Requirements: 10.1, 10.2_

  - [x] 4.2 Implement `AiPanel` in `app/ui/panels/ai_panel.py`
    - `QDockWidget` subclass; wraps `AIChatDock` from `app/ui/widgets/ai_chat_dock.py` unchanged
    - `setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)`
    - `setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable)`
    - _Requirements: 15.1, 15.5_

  - [x] 4.3 Implement `ResultsPanel` in `app/ui/panels/results_panel.py`
    - `QDockWidget` wrapping `BacktestResultsWidget` from `app/ui/widgets/backtest_results_widget.py`
    - `setAllowedAreas(Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)`
    - _Requirements: 4.4, 5.1_

- [x] 5. Checkpoint — Ensure all tests pass
  - Run `pytest --tb=short` and confirm zero new failures before proceeding to pages.
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement `DashboardPage`
  - Create `app/ui/pages/dashboard_page.py`
  - `QWidget` with `__init__(self, settings_state: SettingsState, parent=None)`
  - `MetricCard` grid (2×2): last backtest profit, win rate, total trades, best strategy — data from `RunStore` / `IndexStore`
  - Recent runs `QListWidget` populated from `IndexStore.get_strategy_runs`
  - Quick-action buttons: "Run Last Backtest" (emits signal), "Download Data" (navigates), "Open Strategy" (navigates)
  - Empty-state label shown when no runs exist
  - _Requirements: 3.2, 3.7, 7.5, 16.1_

- [x] 7. Implement `BacktestPage`
  - Create `app/ui/pages/backtest_page.py`
  - `QWidget` with `__init__(self, settings_state: SettingsState, parent=None)`
  - `QSplitter` (horizontal) with `RunConfigForm` on left, tabbed output on right
  - Right panel: "Results" tab → `BacktestResultsWidget` (reused), "Terminal" tab → `TerminalWidget` (new instance)
  - Run picker toolbar above tabs (reused logic from existing `BacktestPage`)
  - "Run" / "Stop" buttons wired to `BacktestService`; live command preview label (collapsible `SectionHeader`)
  - Splitter state persisted via `QSettings("FreqtradeGUI", "ModernUI")` key `splitter/backtest`
  - `loop_completed = Signal()` emitted when backtest finishes
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 8.6_

  - [x] 7.1 Write unit test for `BacktestPage` config round-trip
    - Construct page, call `run_config_form.set_config(cfg)`, assert `run_config_form.get_config() == cfg`
    - _Requirements: 4.1, 4.3_

- [x] 8. Implement `OptimizePage`
  - Create `app/ui/pages/optimize_page.py`
  - `QWidget` with `__init__(self, settings_state: SettingsState, parent=None)`
  - `QSplitter` (horizontal): left panel has `RunConfigForm` + hyperopt options group (epochs `QSpinBox`, spaces `QComboBox`, loss function `QComboBox`) + collapsible advisor `SectionHeader`
  - Right panel: `TerminalWidget`; revert button in toolbar above terminal
  - Inline warnings below relevant fields (not at bottom)
  - Splitter state persisted under key `splitter/optimize`
  - _Requirements: 14.1, 14.5, 8.6_

- [x] 9. Implement `DownloadPage`
  - Create `app/ui/pages/download_page.py`
  - `QWidget` with `__init__(self, settings_state: SettingsState, parent=None)`
  - `QSplitter` (horizontal): left panel has `RunConfigForm` (timeframe + timerange + pairs only, `show_strategy=False`) + inline validation warnings
  - Right panel: "Data Status" tab → `DataStatusWidget` (reused), "Terminal" tab → `TerminalWidget`
  - _Requirements: 13.1, 13.3, 13.4, 8.6_

- [x] 10. Implement `StrategyPage`
  - Create `app/ui/pages/strategy_page.py`
  - `QWidget` with `__init__(self, settings_state: SettingsState, parent=None)`
  - Master-detail `QSplitter`: left `QListWidget` of strategies with search `QLineEdit` at top; each item shows name + last modified + last backtest profit from index
  - Right detail panel: tabbed — "Parameters" tab reuses `StrategyConfigPage` form, "History" tab shows run history `QTableWidget` from `IndexStore`
  - Quick Actions toolbar: "Backtest Now", "Optimize Now" buttons
  - Right-click context menu on list: Backtest, Optimize, Edit
  - `refresh()` slot reloads strategy list from `strategies/` directory
  - Splitter state persisted under key `splitter/strategy`
  - _Requirements: 6.1, 6.2, 6.3, 6.5, 6.6, 8.6_

- [x] 11. Implement `SettingsPage`
  - Create `app/ui/pages/settings_page.py`
  - `QWidget` with `__init__(self, settings_state: SettingsState, parent=None)`
  - Category sidebar (`QListWidget`) + `QStackedWidget` for category panels: Paths, Execution, Terminal, AI, Appearance, About
  - Reuses all existing `SettingsService` / `SettingsState` logic — no new persistence code
  - Search `QLineEdit` at top filters visible fields via `QLineEdit.textChanged`
  - Real-time validation with inline error labels per field
  - _Requirements: 12.1, 12.2, 12.3, 1.2_

  - [x] 11.1 Write property test for settings round-trip
    - Save settings via `SettingsPage` form fields, load via `SettingsService.load_settings()`, assert loaded model equals saved model
    - **Property P3: Settings Round-Trip — settings saved via new UI must produce identical `AppSettings` JSON**
    - **Validates: Requirements 12.3, 1.2**

- [x] 12. Implement `ModernMainWindow`
  - Create `app/ui/main_window.py` (replaces old `MainWindow`)
  - `QMainWindow` subclass; constructor: `__init__(self, settings_state: SettingsState, parent=None)`
  - Layout: `HeaderBar` at top (set as central widget header via `QVBoxLayout` wrapper), `NavSidebar` + `QStackedWidget` in `QHBoxLayout` as central widget body, `AppStatusBar` replacing default status bar
  - Add `TerminalPanel` to `Qt.BottomDockWidgetArea`, `AiPanel` to `Qt.RightDockWidgetArea`
  - Instantiate all six pages and add to `QStackedWidget`
  - Wire `NavSidebar.nav_item_clicked` → `QStackedWidget.setCurrentWidget` + `HeaderBar.set_page_title` + `NavSidebar.set_active`
  - Wire all signals identical to current `MainWindow`: `settings_state.settings_saved` → `_on_settings_saved`; `backtest_page.loop_completed` → `strategy_page.refresh`; `ai_service.connect_backtest_service(backtest_service)`
  - Register `QShortcut` for `Ctrl+1`–`Ctrl+6`, `Ctrl+P`, `Ctrl+\``, `Ctrl+Shift+A`, `F5`
  - Register commands list for `CommandPalette` covering all shortcuts
  - Apply `build_stylesheet` + `build_v2_additions` on init and on theme toggle
  - Persist/restore geometry, windowState, sidebar/collapsed, lastPage via `QSettings("FreqtradeGUI", "ModernUI")` in `closeEvent` / `__init__`
  - Trigger `OnboardingWizard` when `settings_state.settings.venv_path` is empty
  - `main.py` imports `ModernMainWindow` from `app/ui/main_window` (replacing the old `MainWindow`)
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.8, 2.4, 8.1, 8.2, 11.2, 18.4, 18.5, 20.1_

  - [x] 12.1 Write property test for signal continuity
    - Enumerate all `Signal` connections made in `MainWindow.__init__` (existing); assert each is also connected in `ModernMainWindow.__init__`
    - **Property P2: Signal Continuity — every signal connected in `MainWindow` must also be connected in `ModernMainWindow`**
    - **Validates: Requirements 1.8, 2.4**

  - [x] 12.2 Write property test for service immutability
    - After running the full test suite, assert no file in `app/core/` or `app/app_state/` was modified (check via `git diff --name-only`)
    - **Property P1: Service Immutability — no file outside `app/ui/` and `main.py` is modified**
    - **Validates: Requirements 18.2**

- [ ] 13. Checkpoint — Ensure all tests pass
  - Run `pytest --tb=short` and confirm zero new failures.
  - Run `ruff check app/ui/` and fix any lint errors.
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 14. Accessibility and keyboard navigation pass
  - Add `setAccessibleName` / `setToolTip` to all interactive elements in `NavSidebar`, `HeaderBar`, `RunConfigForm`, and all page action buttons
  - Ensure `TabFocusReason` traversal order is logical in each page (use `setTabOrder`)
  - Add `setWhatsThis` help text to complex form fields in `RunConfigForm`, `SettingsPage`, `BacktestPage`
  - Verify all icon-only buttons have accessible text alternatives
  - _Requirements: 17.1, 17.3, 17.4, 17.5, 7.1, 7.2_

- [ ] 15. Final checkpoint — Ensure all tests pass
  - Run `pytest --tb=short` and confirm zero new failures.
  - Run `ruff check . && ruff format --check .` and fix any issues.
  - Ensure all tests pass, ask the user if questions arise.

---

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- All pages follow the constructor signature `__init__(self, settings_state: SettingsState, parent=None)`
- All new code lives within `app/ui/` — `app/core/` and `app/app_state/` are never modified
- Property tests (P1–P6) validate the correctness properties defined in the design document
- `QSplitter` handle width should be set to 4 px in all pages for visual consistency
- `QDockWidget` panels use `setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable)` — no floating by default
