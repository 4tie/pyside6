# Implementation Plan: App Theme Redesign

## Overview

Centralise the Freqtrade GUI visual theme into `app/ui/theme.py`, remove all scattered inline `setStyleSheet` calls from pages and widgets, add a `theme_mode` field to `AppSettings`, wire dark/light mode switching through `MainWindow`, and apply consistent spacing/layout to the three Params/Output pages.

## Tasks

- [x] 1. Create `app/ui/theme.py` with palette, spacing, font constants and `build_stylesheet`
  - Create `app/ui/theme.py` with `ThemeMode` enum (`DARK`, `LIGHT`)
  - Define `PALETTE` dict with all 14 required keys: `bg_base`, `bg_surface`, `bg_elevated`, `border`, `border_focus`, `text_primary`, `text_secondary`, `text_disabled`, `accent`, `accent_hover`, `accent_pressed`, `success`, `danger`, `warning`
  - Define `_LIGHT_PALETTE` dict with inverted/adjusted values for light mode
  - Define `SPACING` dict with keys `xs` (4), `sm` (8), `md` (12), `lg` (16), `xl` (24)
  - Define `FONT` dict with keys `family`, `size_sm` (11), `size_base` (13), `size_lg` (15), `mono_family`
  - Implement `build_stylesheet(mode: ThemeMode = ThemeMode.DARK) -> str` that assembles the complete QSS from constants, covering all widget types currently in `_STYLESHEET` plus new semantic object-name rules
  - QSS must include rules for: `QWidget`, `QDialog`, `QTabWidget`, `QTabBar`, `QToolBar`, `QPushButton` (default, `#secondary`, `#danger`, `#success`, disabled), `QLineEdit`, `QSpinBox`, `QDoubleSpinBox`, `QComboBox`, `QPlainTextEdit`, `QTextEdit`, `QLabel`, `QCheckBox`, `QGroupBox`, `QListWidget`, `QScrollBar` (vertical + horizontal), `QDockWidget`, `QMenuBar`, `QMenu`, `QScrollArea`, `QSplitter`, `QToolTip`, `QMessageBox`
  - QSS must include semantic object-name rules: `QLabel#warning_banner`, `QLabel#success_banner`, `QLabel#path_label`, `QLabel#hint_label`, `QLabel#status_ok`, `QLabel#status_error`
  - `build_stylesheet` falls back to `ThemeMode.DARK` and logs a warning for unexpected mode values — never raises
  - Add module-level `_log = get_logger("ui.theme")`
  - _Requirements: 1.1, 1.2, 1.3, 4.1, 4.2, 4.3, 4.4, 5.2, 5.3, 5.4, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 7.1, 7.2, 7.3, 8.1, 8.2, 8.3, 8.4, 9.1, 9.2, 9.3, 9.4, 9.5, 10.1, 10.2_

  - [x] 1.1 Write unit tests for `theme.py` constants and `build_stylesheet`
    - `test_build_stylesheet_dark_returns_string` — non-empty string
    - `test_build_stylesheet_light_returns_string` — non-empty string
    - `test_build_stylesheet_dark_light_differ` — dark ≠ light
    - `test_palette_keys_present` — all 14 keys in `PALETTE`
    - `test_spacing_keys_present` — all 5 keys in `SPACING`
    - `test_font_keys_present` — all 5 keys in `FONT`
    - _Requirements: 1.1, 1.2, 4.1_

  - [x] 1.2 Write property test: PALETTE completeness (Property 1)
    - **Property 1: PALETTE completeness**
    - **Validates: Requirements 1.1, 1.3**
    - Use `@given(mode=st.sampled_from(ThemeMode))` with `@settings(max_examples=100)`
    - Assert every value in `PALETTE` appears in the generated QSS string

  - [x] 1.3 Write property test: SPACING completeness (Property 2)
    - **Property 2: SPACING completeness**
    - **Validates: Requirements 1.2, 1.3**
    - Use `@given(mode=st.sampled_from(ThemeMode))` with `@settings(max_examples=100)`
    - Assert every value in `SPACING` appears as a string in the generated QSS

  - [x] 1.4 Write property test: stylesheet round-trip stability (Property 4)
    - **Property 4: Stylesheet round-trip stability**
    - **Validates: Requirements 1.3, 10.2**
    - Use `@given(mode=st.sampled_from(ThemeMode))` with `@settings(max_examples=100)`
    - Assert `build_stylesheet(mode) == build_stylesheet(mode)`

- [x] 2. Add `theme_mode` field to `AppSettings` and write serialisation tests
  - In `app/core/models/settings_models.py`, add `theme_mode: str = Field("dark", description="UI colour mode: dark or light")` to `AppSettings`
  - Write unit tests: `test_appsettings_theme_mode_default` and `test_appsettings_theme_mode_light`
  - _Requirements: 10.3_

  - [x] 2.1 Write property test: theme mode serialisation round-trip (Property 5)
    - **Property 5: Theme mode serialisation round-trip**
    - **Validates: Requirement 10.3**
    - Use `@given(mode=st.sampled_from(["dark", "light"]))` with `@settings(max_examples=100)`
    - Assert `AppSettings.model_validate_json(AppSettings(theme_mode=mode).model_dump_json()).theme_mode == mode`

- [x] 3. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Update `MainWindow` to use `theme.py` and support live theme switching
  - Remove the `_STYLESHEET` module-level constant from `main_window.py`
  - In `MainWindow.__init__`: read `settings.theme_mode`, convert to `ThemeMode` (default `ThemeMode.DARK` for unknown values), call `build_stylesheet(mode)`, pass result to `QApplication.instance().setStyleSheet(...)`
  - In `_on_settings_saved`: compare old vs new `theme_mode`; if changed, re-apply stylesheet via `QApplication.instance().setStyleSheet(build_stylesheet(new_mode))`
  - In `_build_toolbar`: add `toolbar.setFixedHeight(40)`
  - _Requirements: 1.4, 5.1, 5.5, 10.4, 10.5_

- [x] 5. Remove inline styles from `BacktestPage` and `DownloadDataPage`
  - In `backtest_page.py`: replace `export_label.setStyleSheet(...)` with `export_label.setObjectName("path_label")`; replace `pairs_display_label.setStyleSheet(...)` with `pairs_display_label.setObjectName("hint_label")`
  - In `download_data_page.py`: replace `validation_label.setStyleSheet(...)` with `validation_label.setObjectName("warning_banner")`; replace `pairs_display_label.setStyleSheet(...)` with `pairs_display_label.setObjectName("hint_label")`
  - _Requirements: 2.1, 2.2, 2.3_

- [x] 6. Remove inline styles from `OptimizePage` and `StrategyConfigPage`
  - In `optimize_page.py`: replace `data_warning_label.setStyleSheet(...)` with `setObjectName("warning_banner")`; replace `result_warning_label.setStyleSheet(...)` with `setObjectName("warning_banner")`; replace `_advisor_tips.setStyleSheet(...)` with `setObjectName("success_banner")`; replace `_advisor_warnings.setStyleSheet(...)` with `setObjectName("warning_banner")`; replace `_advisor_status.setStyleSheet(...)` with `setObjectName("hint_label")`; replace `revert_button.setStyleSheet(...)` with `revert_button.setObjectName("secondary")`
  - In `strategy_config_page.py`: replace `_path_label.setStyleSheet(...)` with `_path_label.setObjectName("path_label")`; in `_set_status`, replace inline `setStyleSheet(f"color: {color}; ...")` with `status_label.setObjectName("status_ok")` or `status_label.setObjectName("status_error")` based on the `error` flag
  - _Requirements: 2.1, 2.2, 2.3_

- [x] 7. Remove inline styles from `SettingsPage`, `BacktestResultsWidget`, `AIChatDock`, and `DataStatusWidget`
  - In `settings_page.py`: replace `python_path_display.setStyleSheet("color: gray;")` and `freqtrade_path_display.setStyleSheet("color: gray;")` with `setObjectName("hint_label")`; replace `validation_result.setStyleSheet(...)` calls with `setObjectName("warning_banner")` / `setObjectName("success_banner")` / `setObjectName("status_error")` as appropriate; remove inline stylesheet from `_on_settings_changed`
  - In `backtest_results_widget.py`: replace `_export_path_label.setStyleSheet(...)` with `setObjectName("path_label")`
  - In `ai_chat_dock.py`: replace all inline `setStyleSheet` calls with appropriate `setObjectName` calls matching the semantic rules in `theme.py`
  - In `data_status_widget.py`: replace legend colour labels and `_summary_label` inline styles with `setObjectName` calls
  - _Requirements: 2.1, 2.2, 2.3_

- [x] 8. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8.1 Write static analysis test: no hex literals outside `theme.py` (Property 3)
  - **Property 3: No hex literals outside theme module**
  - **Validates: Requirements 1.5, 2.3**
  - Write a `pytest` test that walks all `.py` files under `app/ui/` (excluding `theme.py`) and asserts zero occurrences of bare hex colour literals matching `#[0-9a-fA-F]{3,6}` outside of comments and `setObjectName` arguments

- [x] 9. Apply consistent Params/Output layout to `BacktestPage`, `OptimizePage`, and `DownloadDataPage`
  - Wrap each page's `params_layout` in a `QScrollArea` (`setWidgetResizable(True)`, horizontal scroll off)
  - Set `params_panel.setMinimumWidth(260)` and `params_panel.setMaximumWidth(360)` on the scroll area
  - Set outer content margin to `SPACING["lg"]` (16 px) and row spacing to `SPACING["sm"]` (8 px) on the params layout
  - Set outer content margin to `SPACING["sm"]` (8 px) on the output layout
  - Preserve the existing 1:2 horizontal stretch ratio between params and output panels
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 10. Add Appearance group with theme mode selector to `SettingsPage`
  - Add an "Appearance" `QGroupBox` to `settings_page.py` containing a `QComboBox` (or two `QRadioButton`s) for Dark / Light mode selection
  - In `_load_current_settings`: populate the selector from `self.current_settings.theme_mode`
  - In `_collect_settings`: write the selected mode back to `AppSettings.theme_mode`
  - The existing `_save` → `settings_state.save_settings` → `MainWindow._on_settings_saved` chain already handles re-applying the stylesheet — no additional wiring needed
  - _Requirements: 10.3, 10.4, 10.5_

- [x] 11. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- `TerminalWidget.apply_preferences` is explicitly excluded from inline style removal — it applies user-configurable colours and must remain
- `theme.py` has no imports from the rest of the application — keep it a pure data/string module
- Property tests use `hypothesis` (already present in the project via `.hypothesis/`)
- The `_advisor_tips` panel in `OptimizePage` uses a blue info tint — map it to `success_banner` or add a dedicated `info_banner` object name rule in `theme.py` if the colour semantics differ
- When removing inline styles from `ai_chat_dock.py`, audit all `setStyleSheet` calls carefully; some may need new object-name rules added to `theme.py` first
