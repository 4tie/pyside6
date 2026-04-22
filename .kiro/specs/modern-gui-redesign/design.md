# Design Document: Modern GUI Redesign

## Overview

This document describes the technical design for a complete UI layer redesign of the Freqtrade GUI application. The redesign replaces the current `QTabWidget`-based layout with a modern sidebar-navigation shell while keeping every file outside `app/ui/` completely untouched.

The new UI replaces `app/ui/` in-place. `ModernMainWindow` supersedes the old `MainWindow` and `main.py` imports it directly from `app/ui/main_window`.

---

## Architecture

### Layer Boundaries (unchanged)

```
app/ui/             ← redesigned UI layer lives here (replaces old contents in-place)
    ↓  (imports only)
app/app_state/      ← UNCHANGED: SettingsState, signals
    ↓  (imports only)
app/core/           ← UNCHANGED: services, models, runners, resolvers
```

No file outside `app/ui/` is modified.

### New Directory Layout

```
app/ui/
├── main_window.py              # ModernMainWindow — top-level shell
├── theme.py                    # Theme module (updated in-place; adds build_v2_additions)
├── shell/
│   ├── sidebar.py              # NavSidebar — icon + label nav rail
│   ├── header_bar.py           # HeaderBar — title, status, quick actions
│   └── status_bar.py           # AppStatusBar — process status, notifications
├── pages/
│   ├── dashboard_page.py       # Home dashboard with key metrics
│   ├── backtest_page.py        # Redesigned backtest workflow
│   ├── optimize_page.py        # Redesigned hyperopt workflow
│   ├── download_page.py        # Redesigned data download
│   ├── strategy_page.py        # Unified strategy management
│   └── settings_page.py        # Categorised settings
├── panels/
│   ├── terminal_panel.py       # Dockable terminal (wraps TerminalWidget)
│   ├── ai_panel.py             # Dockable AI chat (wraps AIChatDock)
│   └── results_panel.py        # Slide-in results drawer
├── widgets/
│   ├── metric_card.py          # KPI card: label + value + trend
│   ├── section_header.py       # Titled section divider with collapse
│   ├── run_config_form.py      # Shared strategy/timeframe/pairs form
│   ├── command_palette.py      # Ctrl+P command palette overlay
│   ├── notification_toast.py   # Transient success/error toasts
│   ├── progress_overlay.py     # Full-page progress overlay
│   └── onboarding_wizard.py    # First-run setup wizard
└── dialogs/
    └── pairs_selector_dialog.py  # Multi-select pairs dialog
```

---

## Component Design

### 1. ModernMainWindow

Replaces `MainWindow`. Uses `QMainWindow` with:

- `NavSidebar` as a fixed left dock (not a `QDockWidget` — a plain `QWidget` in a `QHBoxLayout`)
- `QStackedWidget` as the central content area (replaces `QTabWidget`)
- `HeaderBar` at the top (replaces `QToolBar`)
- `AppStatusBar` at the bottom (replaces default `QStatusBar`)
- `QDockWidget` for terminal panel (bottom dock area)
- `QDockWidget` for AI chat panel (right dock area)

```
┌─────────────────────────────────────────────────────┐
│  HeaderBar  (title · breadcrumb · quick actions)    │
├──────────┬──────────────────────────────────────────┤
│          │                                          │
│  Nav     │   QStackedWidget (active page)           │
│  Sidebar │                                          │
│  (icons  │                                          │
│  +labels)│                                          │
│          │                                          │
├──────────┴──────────────────────────────────────────┤
│  Terminal Panel (QDockWidget, bottom, collapsible)  │
└─────────────────────────────────────────────────────┘
                                    ┌──────────────────┐
                                    │  AI Chat Panel   │
                                    │  (QDockWidget,   │
                                    │   right)         │
                                    └──────────────────┘
```

**Signal wiring** (identical to current `MainWindow`):
- `settings_state.settings_saved` → `_on_settings_saved`
- `loop_page.loop_completed` → `strategy_page.refresh`
- `ai_service.connect_backtest_service(backtest_service)`

### 2. NavSidebar

A `QWidget` with a `QVBoxLayout` containing `NavItem` buttons.

```python
class NavItem(QPushButton):
    """Single navigation entry: icon + label, checkable."""
    # objectName: "nav_item"
    # objectName when active: "nav_item_active"
```

Nav items (in order):

| Icon | Label | Page |
|------|-------|------|
| 🏠 | Dashboard | DashboardPage |
| 📊 | Backtest | BacktestPage |
| 🔬 | Optimize | OptimizePage |
| ⬇ | Download | DownloadPage |
| 📋 | Strategy | StrategyPage |
| ⚙ | Settings | SettingsPage |

Collapse toggle at the bottom shrinks sidebar to icon-only mode (48 px wide) by hiding the label `QLabel` inside each `NavItem`. Width animates via `QPropertyAnimation` on `maximumWidth`.

Keyboard shortcuts: `Ctrl+1` through `Ctrl+6` switch pages.

### 3. HeaderBar

A `QWidget` (not `QToolBar`) with a fixed height of 48 px:

```
[App Icon]  Freqtrade GUI  >  [Page Title]     [🔍 Cmd Palette]  [⚙ Settings]  [Theme Toggle]
```

- Breadcrumb updates when active page changes
- Command palette button opens `CommandPalette` overlay (`Ctrl+P`)
- Settings button opens `SettingsDialog` (reused from `app/ui/dialogs/`)
- Theme toggle cycles Dark → Light → Dark, calls `build_stylesheet` and `QApplication.setStyleSheet`

### 4. Pages

All pages receive `SettingsState` via constructor — identical to current pattern.

#### DashboardPage

A read-only overview assembled from existing services:

- `MetricCard` grid: last backtest profit, win rate, total trades, best strategy
- Recent runs list (from `IndexStore.get_strategy_runs`)
- Quick-action buttons: "Run Last Backtest", "Download Data", "Open Strategy"
- Data sourced entirely from `RunStore` / `IndexStore` — no new services

#### BacktestPage (redesigned)

Two-panel layout using `QSplitter` (replaces fixed left/right split):

**Left panel — RunConfigForm:**
- `QComboBox` strategy selector
- Timeframe input + preset chips (reused logic)
- Timerange input + preset chips
- Pairs selector button (reuses `PairsSelectorDialog`)
- Collapsible "Advanced" `SectionHeader` → wallet, max trades
- "Run" / "Stop" buttons
- Live command preview (collapsible, monospace label)

**Right panel — tabbed output:**
- "Results" tab → `BacktestResultsWidget` (reused unchanged)
- "Terminal" tab → `TerminalWidget` (reused unchanged)
- Run picker toolbar above tabs (reused logic)

Key improvement: `QSplitter` lets users resize panels. Splitter state persisted via `QSettings`.

#### OptimizePage (redesigned)

Same two-panel `QSplitter` pattern:

**Left panel:**
- `RunConfigForm` (shared widget)
- Hyperopt options group: epochs, spaces, loss function
- Advisor panel (collapsible `SectionHeader`)
- Warnings inline below relevant fields (not at bottom)

**Right panel:**
- `TerminalWidget`
- Revert button moved to toolbar above terminal

#### DownloadPage (redesigned)

**Left panel:**
- `RunConfigForm` (timeframe + timerange + pairs only)
- Validation warnings inline

**Right panel — tabbed:**
- "Data Status" tab → `DataStatusWidget` (reused)
- "Terminal" tab → `TerminalWidget` (reused)

#### StrategyPage (redesigned)

Replaces `StrategyConfigPage` with a master-detail layout:

**Left — strategy list:**
- `QListWidget` of all strategies (`.py` files from `strategies/`)
- Each item shows: name, last modified, last backtest profit (from index)
- Search/filter `QLineEdit` at top
- Right-click context menu: Backtest, Optimize, Edit

**Right — detail panel (tabbed):**
- "Parameters" tab → existing `StrategyConfigPage` form (reused)
- "History" tab → run history table from `IndexStore`
- "Quick Actions" toolbar: Backtest Now, Optimize Now

#### SettingsPage (redesigned)

Replaces `SettingsDialog` as a full page with category sidebar:

Categories: Paths, Execution, Terminal, AI, Appearance, About

Each category is a `QWidget` shown in a `QStackedWidget`. Reuses all existing `SettingsService` / `SettingsState` logic.

Search bar at top filters visible fields using `QLineEdit.textChanged`.

### 5. Panels

#### TerminalPanel

Wraps `TerminalWidget` in a `QDockWidget`:

```python
class TerminalPanel(QDockWidget):
    def __init__(self, parent):
        super().__init__("Terminal", parent)
        self.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)
        self.terminal = TerminalWidget()
        self.setWidget(self.terminal)
```

All pages that need a terminal reference `ModernMainWindow.terminal_panel.terminal` — they do not own their own `TerminalWidget`. This gives a single unified terminal visible from any page.

Exception: `BacktestPage` and `OptimizePage` embed their own `TerminalWidget` in their right panel for inline output, matching current UX. The global `TerminalPanel` is for the "Check Python / Check Freqtrade" quick actions.

#### AiPanel

Thin wrapper that re-uses `AIChatDock` from `app/ui/widgets/ai_chat_dock.py` unchanged.

### 6. Shared Widgets

#### MetricCard

```python
class MetricCard(QFrame):
    """KPI display: title label + large value + optional trend arrow."""
    def __init__(self, title: str, value: str = "—", trend: Optional[float] = None):
        ...
```

Used on `DashboardPage`. Styled with `objectName="metric_card"`.

#### SectionHeader

```python
class SectionHeader(QWidget):
    """Titled collapsible section. Wraps any QWidget as collapsible body."""
    toggled = Signal(bool)  # expanded state

    def __init__(self, title: str, body: QWidget, collapsed: bool = False):
        ...
```

Replaces `QGroupBox` for collapsible sections. Uses a `QToolButton` with arrow icon as toggle.

#### RunConfigForm

```python
class RunConfigForm(QWidget):
    """Shared strategy/timeframe/pairs configuration form.

    Emits config_changed(dict) whenever any field changes.
    """
    config_changed = Signal(dict)

    def __init__(self, settings_state: SettingsState,
                 show_strategy: bool = True,
                 show_timeframe: bool = True,
                 show_timerange: bool = True,
                 show_pairs: bool = True):
        ...

    def get_config(self) -> dict:
        """Return current form values as a plain dict."""

    def set_config(self, config: dict) -> None:
        """Populate form from a dict (for AI-driven run_with_config)."""
```

Consolidates duplicated form code from `BacktestPage`, `OptimizePage`, `DownloadDataPage`.

#### CommandPalette

```python
class CommandPalette(QDialog):
    """Ctrl+P overlay. Fuzzy-searches registered commands."""
    command_selected = Signal(str)  # command id

    def __init__(self, commands: list[dict], parent=None):
        # commands: [{"id": str, "label": str, "shortcut": str, "action": Callable}]
        ...
```

Shown as a frameless `QDialog` centered on the main window. `QLineEdit` at top, `QListWidget` below with live fuzzy filtering.

#### NotificationToast

```python
class NotificationToast(QWidget):
    """Transient notification shown in bottom-right corner."""
    def show_message(self, message: str, level: str = "info", duration_ms: int = 3000):
        ...
```

Positioned absolutely over the main window using `QWidget.move()`. Auto-hides after `duration_ms`. Levels: `"info"`, `"success"`, `"error"`, `"warning"`.

#### OnboardingWizard

```python
class OnboardingWizard(QWizard):
    """First-run setup wizard using Qt's built-in QWizard."""
    # Pages: Welcome → Venv Path → User Data → Validation → Done
```

Triggered from `ModernMainWindow.__init__` when `settings.venv_path` is empty.

---

## State Management

No changes to `SettingsState`. All pages receive it via constructor:

```python
# ModernMainWindow.__init__
self.settings_state = settings_state  # or SettingsState()
self.backtest_page = BacktestPage(self.settings_state)
self.optimize_page = OptimizePage(self.settings_state)
# etc.
```

Page-level state (selected pairs, last run, etc.) is managed identically to the current implementation — each page owns its own state fields.

---

## Theme System

`app/ui/theme.py` is updated in-place. It retains all existing symbols (`ThemeMode`, `PALETTE`, `_LIGHT_PALETTE`, `SPACING`, `FONT`, `build_stylesheet`) and gains a new function:

```python
def build_v2_additions(palette: dict, spacing: dict, font: dict) -> str:
    """Return QSS for all custom object names introduced by the v2 UI layer."""
    ...
```

`ModernMainWindow` calls both `build_stylesheet` and `build_v2_additions` and applies the combined result via `QApplication.setStyleSheet`. There is no separate re-export module — `app/ui/theme.py` is the single source of truth.

New object names added to QSS:

| objectName | Usage |
|---|---|
| `nav_item` | Inactive sidebar button |
| `nav_item_active` | Active sidebar button |
| `metric_card` | Dashboard KPI card |
| `section_header` | Collapsible section title bar |
| `command_palette` | Command palette dialog |
| `toast_info` / `toast_success` / `toast_error` | Notification toasts |
| `page_title` | Large page heading label |

---

## Navigation Flow

```
ModernMainWindow
    NavSidebar.nav_item_clicked(page_id)
        → QStackedWidget.setCurrentWidget(pages[page_id])
        → HeaderBar.set_page_title(page_title)
        → NavSidebar.set_active(page_id)
```

Page switching is O(1) — `QStackedWidget` keeps all pages in memory (same as current `QTabWidget`).

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+1` | Dashboard |
| `Ctrl+2` | Backtest |
| `Ctrl+3` | Optimize |
| `Ctrl+4` | Download |
| `Ctrl+5` | Strategy |
| `Ctrl+6` | Settings |
| `Ctrl+P` | Command Palette |
| `Ctrl+\`` | Toggle Terminal Panel |
| `Ctrl+Shift+A` | Toggle AI Chat Panel |
| `F5` | Re-run last backtest |

Registered via `QShortcut` in `ModernMainWindow.__init__`.

---

## Persistence

`QSettings("FreqtradeGUI", "ModernUI")` stores:

| Key | Value |
|---|---|
| `geometry` | Main window geometry |
| `windowState` | Dock widget state |
| `sidebar/collapsed` | Bool |
| `splitter/backtest` | `QSplitter` state bytes |
| `splitter/optimize` | `QSplitter` state bytes |
| `splitter/strategy` | `QSplitter` state bytes |
| `lastPage` | Last active page id |

Saved in `closeEvent`, restored in `__init__` after all widgets are created.

---

## Correctness Properties

The following properties must hold throughout the redesign:

### P1 — Service Immutability
No file in `app/core/` or `app/app_state/` is modified. Verified by: `git diff --name-only` showing only `app/ui/**` and `main.py`.

### P2 — Signal Continuity
Every Qt signal that `MainWindow` connects must also be connected in `ModernMainWindow`. Verified by: comparing signal connections between `MainWindow.__init__` and `ModernMainWindow.__init__`.

### P3 — Settings Round-Trip
Settings saved via the new `SettingsPage` must produce an identical `AppSettings` JSON to the current `SettingsDialog`. Verified by: property test that saves via new UI and loads via `SettingsService.load_settings()`.

### P4 — Backtest Parity
A backtest run via `ModernMainWindow.backtest_page` must produce the same `BacktestResults` as the same run via the current `BacktestPage`. Verified by: running a fixed strategy/timeframe/pairs combination through both UIs and comparing `RunStore` output.

### P5 — No Regressions on Existing Tests
`pytest --tb=short` must pass with zero new failures after the redesign. The test suite exercises services and models — not UI — so this is achievable without UI-specific tests.

### P6 — Theme Consistency
`build_stylesheet` and `build_v2_additions` must produce consistent output across all callers. Verified by: unit test asserting the combined stylesheet string contains all expected object names.

---

## Implementation Notes

- All new pages follow the same constructor signature: `__init__(self, settings_state: SettingsState, parent=None)`
- Module-level logger: `_log = get_logger("ui.<module_name>")`
- All imports use `from app.ui.xxx import yyy`
- `__init__.py` files remain empty
- No new third-party dependencies — only PySide6 components already in use
- `QSplitter` handle width set to 4 px for a clean look
- All `QDockWidget` panels use `setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable)` — no floating by default to keep UX predictable
