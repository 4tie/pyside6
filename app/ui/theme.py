"""Centralised theme module for the Freqtrade GUI application.

Defines colour palette, spacing, font constants, and the ``build_stylesheet``
function that assembles the complete QSS string from those constants.

This module has NO imports from the rest of the application — it is a pure
data/string module (only stdlib + get_logger from app.core.utils.app_logger).

Dark palette:
  bg_base      #1e1e1e  — VS Code-style deepest background
  bg_surface   #252526  — sidebar / panel surface (1 step lighter)
  bg_elevated  #2d2d30  — inputs, raised cards (2 steps lighter)
  bg_card      #333337  — metric cards, table rows
  border       #3e3e42  — subtle separator
  border_focus #4ec9a0  — mint-green focus ring (no blue)
  accent       #4ec9a0  — mint-green accent: tab underline, scrollbar, checkbox
  accent_hover #6ad4b0
  accent_pressed #3aaa84
  text_primary   #d4d4d4  — VS Code default text
  text_secondary #9d9d9d  — dimmed labels
  text_disabled  #555558
  success  #4ec9a0  — same mint (profit positive, wins)
  danger   #f44747  — VS Code red
  warning  #ce9178  — VS Code orange-brown
"""
from enum import Enum
from typing import Final

from app.core.utils.app_logger import get_logger

_log = get_logger("ui.theme")


# ---------------------------------------------------------------------------
# Theme mode
# ---------------------------------------------------------------------------

class ThemeMode(Enum):
    DARK = "dark"
    LIGHT = "light"


# ---------------------------------------------------------------------------
# Dark palette
# ---------------------------------------------------------------------------

PALETTE: Final[dict] = {
    # Backgrounds — neutral grays, no blue tint
    "bg_base":      "#1a1a1a",   # slightly deeper for better contrast
    "bg_surface":   "#242424",   # sidebar / left panels
    "bg_elevated":  "#2c2c2c",   # inputs, raised cards
    "bg_card":      "#323232",   # metric cards, table rows
    # Borders
    "border":       "#3a3a3a",
    "border_focus": "#4ec9a0",
    # Text
    "text_primary":   "#e0e0e0",   # slightly brighter for readability
    "text_secondary": "#9a9a9a",
    "text_disabled":  "#555558",
    # Accent — mint green, never blue
    "accent":         "#4ec9a0",
    "accent_hover":   "#6ad4b0",
    "accent_pressed": "#3aaa84",
    # Semantic
    "success": "#4ec9a0",
    "danger":  "#f44747",
    "warning": "#ce9178",
}

# ---------------------------------------------------------------------------
# Light palette
# ---------------------------------------------------------------------------

_LIGHT_PALETTE: Final[dict] = {
    # Backgrounds
    "bg_base":      "#ffffff",
    "bg_surface":   "#f3f3f3",
    "bg_elevated":  "#e8e8e8",
    "bg_card":      "#dcdcdc",
    # Borders
    "border":       "#c8c8c8",
    "border_focus": "#3aaa84",
    # Text
    "text_primary":   "#1e1e1e",
    "text_secondary": "#6e6e6e",
    "text_disabled":  "#aaaaaa",
    # Accent — same mint
    "accent":         "#3aaa84",
    "accent_hover":   "#4ec9a0",
    "accent_pressed": "#2e8a6a",
    # Semantic
    "success": "#3aaa84",
    "danger":  "#d32f2f",
    "warning": "#b5651d",
}

# ---------------------------------------------------------------------------
# Spacing scale
# ---------------------------------------------------------------------------

SPACING: Final[dict] = {
    "xs":  4,
    "sm":  8,
    "md": 12,
    "lg": 16,
    "xl": 24,
}

# ---------------------------------------------------------------------------
# Font constants
# ---------------------------------------------------------------------------

FONT: Final[dict] = {
    "family":      "Segoe UI, SF Pro Display, Ubuntu, Helvetica Neue, Arial, sans-serif",
    "size_sm":     11,
    "size_base":   13,
    "size_lg":     15,
    "mono_family": "Consolas, Menlo, DejaVu Sans Mono, Courier New, monospace",
}


# ---------------------------------------------------------------------------
# Stylesheet builder
# ---------------------------------------------------------------------------

def build_stylesheet(mode: ThemeMode = ThemeMode.DARK) -> str:
    """Assemble and return the complete application QSS string.

    Args:
        mode: ``ThemeMode.DARK`` or ``ThemeMode.LIGHT``.  Any unexpected value
              falls back to ``ThemeMode.DARK`` with a logged warning.

    Returns:
        A complete QSS string ready to pass to ``QApplication.setStyleSheet``.
    """
    if not isinstance(mode, ThemeMode):
        _log.warning(
            "build_stylesheet received unexpected mode %r — falling back to DARK", mode
        )
        mode = ThemeMode.DARK

    p = PALETTE if mode == ThemeMode.DARK else _LIGHT_PALETTE
    sp = SPACING
    f = FONT

    qss = f"""
/* ── Base ──────────────────────────────────────────────────────────── */
QWidget {{
    background-color: {p["bg_base"]};
    color: {p["text_primary"]};
    font-family: {f["family"]};
    font-size: {f["size_base"]}px;
}}

QDialog {{
    background-color: {p["bg_surface"]};
    color: {p["text_primary"]};
}}

/* ── Tabs ───────────────────────────────────────────────────────────── */
QTabWidget::pane {{
    border: none;
    border-top: 1px solid {p["border"]};
    background-color: {p["bg_base"]};
}}

QTabBar::tab {{
    background-color: {p["bg_surface"]};
    color: {p["text_secondary"]};
    padding: {sp["sm"]}px 18px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: {f["size_base"]}px;
    min-width: 80px;
}}

QTabBar::tab:selected {{
    background-color: {p["bg_base"]};
    color: {p["text_primary"]};
    border-bottom: 2px solid {p["accent"]};
}}

QTabBar::tab:hover:!selected {{
    background-color: {p["bg_elevated"]};
    color: {p["text_primary"]};
}}

/* ── Toolbar ────────────────────────────────────────────────────────── */
QToolBar {{
    background-color: {p["bg_surface"]};
    border-bottom: 1px solid {p["border"]};
    spacing: {sp["xs"]}px;
    padding: 3px {sp["xs"]}px;
}}

QToolBar QToolButton {{
    background-color: transparent;
    color: {p["text_secondary"]};
    border: none;
    padding: {sp["xs"]}px 10px;
    border-radius: 3px;
    font-size: {f["size_base"]}px;
}}

QToolBar QToolButton:hover {{
    background-color: {p["bg_elevated"]};
    color: {p["text_primary"]};
}}

/* ── Buttons ────────────────────────────────────────────────────────── */
QPushButton {{
    background-color: {p["bg_elevated"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border"]};
    padding: {sp["xs"]}px {sp["lg"]}px;
    border-radius: 4px;
    font-size: {f["size_base"]}px;
    font-weight: 500;
}}

QPushButton:hover {{
    background-color: {p["bg_card"]};
    border-color: {p["accent_hover"]};
    color: {p["text_primary"]};
}}

QPushButton:pressed {{
    background-color: {p["accent_pressed"]};
    border-color: {p["accent_pressed"]};
    color: {p["bg_base"]};
}}

QPushButton:disabled {{
    background-color: {p["bg_surface"]};
    color: {p["text_disabled"]};
    border-color: {p["border"]};
}}

QPushButton#secondary {{
    background-color: transparent;
    color: {p["text_secondary"]};
    border: 1px solid {p["border"]};
}}

QPushButton#secondary:hover {{
    background-color: {p["bg_elevated"]};
    border-color: {p["border_focus"]};
    color: {p["text_primary"]};
}}

QPushButton#danger {{
    background-color: transparent;
    color: {p["danger"]};
    border: 1px solid {p["danger"]};
}}

QPushButton#danger:hover {{
    background-color: {p["danger"]};
    color: {p["bg_base"]};
}}

QPushButton#success {{
    background-color: transparent;
    color: {p["success"]};
    border: 1px solid {p["success"]};
}}

QPushButton#success:hover {{
    background-color: {p["success"]};
    color: {p["bg_base"]};
}}

/* ── Inputs ─────────────────────────────────────────────────────────── */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {p["bg_elevated"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border"]};
    border-radius: 4px;
    padding: 5px {sp["sm"]}px;
    font-size: {f["size_base"]}px;
    selection-background-color: {p["accent"]};
    selection-color: {p["bg_base"]};
}}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {p["border_focus"]};
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox QAbstractItemView {{
    background-color: {p["bg_elevated"]};
    color: {p["text_primary"]};
    selection-background-color: {p["accent"]};
    selection-color: {p["bg_base"]};
    border: 1px solid {p["border"]};
    outline: none;
}}

QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background-color: {p["bg_elevated"]};
    border: none;
    width: 16px;
}}

/* ── Text Editors ───────────────────────────────────────────────────── */
QPlainTextEdit, QTextEdit {{
    background-color: {p["bg_elevated"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border"]};
    border-radius: 4px;
    padding: 5px {sp["sm"]}px;
    font-family: {f["mono_family"]};
    font-size: {f["size_sm"]}px;
    selection-background-color: {p["accent"]};
    selection-color: {p["bg_base"]};
}}

QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {p["border_focus"]};
}}

/* ── Labels ─────────────────────────────────────────────────────────── */
QLabel {{
    color: {p["text_primary"]};
    background-color: transparent;
    border: none;
}}

QLabel#hint_label {{
    color: {p["text_secondary"]};
    font-size: {f["size_sm"]}px;
}}

QLabel#path_label {{
    color: {p["text_secondary"]};
    font-size: {f["size_sm"]}px;
}}

QLabel#warning_banner {{
    background-color: {p["bg_elevated"]};
    color: {p["warning"]};
    border: 1px solid {p["border"]};
    border-left: 3px solid {p["warning"]};
    padding: {sp["sm"]}px;
    border-radius: 4px;
}}

QLabel#success_banner {{
    background-color: {p["bg_elevated"]};
    color: {p["success"]};
    border: 1px solid {p["border"]};
    border-left: 3px solid {p["success"]};
    padding: {sp["sm"]}px;
    border-radius: 4px;
}}

QLabel#status_ok {{
    color: {p["success"]};
    font-weight: bold;
}}

QLabel#status_error {{
    color: {p["danger"]};
    font-weight: bold;
}}

/* ── Checkboxes ─────────────────────────────────────────────────────── */
QCheckBox {{
    color: {p["text_primary"]};
    spacing: {sp["xs"]}px;
}}

QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {p["border"]};
    border-radius: 3px;
    background-color: {p["bg_elevated"]};
}}

QCheckBox::indicator:checked {{
    background-color: {p["accent"]};
    border-color: {p["accent"]};
}}

/* ── GroupBox ───────────────────────────────────────────────────────── */
QGroupBox {{
    background-color: {p["bg_surface"]};
    border: 1px solid {p["border"]};
    border-radius: 6px;
    margin-top: {sp["lg"]}px;
    padding-top: {sp["md"]}px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 {sp["xs"]}px;
    color: {p["text_secondary"]};
    font-size: {f["size_sm"]}px;
    text-transform: uppercase;
    letter-spacing: 1px;
}}

/* ── Tables ─────────────────────────────────────────────────────────── */
QTableWidget {{
    background-color: {p["bg_surface"]};
    alternate-background-color: {p["bg_elevated"]};
    gridline-color: {p["border"]};
    border: 1px solid {p["border"]};
    border-radius: 4px;
    color: {p["text_primary"]};
}}

QTableWidget::item {{
    padding: 4px 8px;
}}

QTableWidget::item:selected {{
    background-color: {p["bg_card"]};
    color: {p["text_primary"]};
    border: none;
}}

QHeaderView::section {{
    background-color: {p["bg_elevated"]};
    color: {p["text_secondary"]};
    border: none;
    border-right: 1px solid {p["border"]};
    border-bottom: 1px solid {p["border"]};
    padding: 5px 8px;
    font-size: {f["size_sm"]}px;
    font-weight: bold;
    letter-spacing: 1px;
    text-transform: uppercase;
}}

/* ── Tree ───────────────────────────────────────────────────────────── */
QTreeWidget {{
    background-color: {p["bg_surface"]};
    alternate-background-color: {p["bg_elevated"]};
    border: 1px solid {p["border"]};
    border-radius: 4px;
    color: {p["text_primary"]};
}}

QTreeWidget::item:selected {{
    background-color: {p["bg_card"]};
    color: {p["text_primary"]};
}}

QTreeWidget::item:hover {{
    background-color: {p["bg_elevated"]};
}}

/* ── Lists ──────────────────────────────────────────────────────────── */
QListWidget {{
    background-color: {p["bg_surface"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border"]};
    border-radius: 4px;
}}

QListWidget::item:selected {{
    background-color: {p["bg_card"]};
    color: {p["text_primary"]};
}}

QListWidget::item:hover {{
    background-color: {p["bg_elevated"]};
}}

/* ── Progress bars ──────────────────────────────────────────────────── */
QProgressBar {{
    background-color: {p["bg_elevated"]};
    border-radius: 3px;
    border: 1px solid {p["border"]};
    text-align: center;
    color: {p["text_primary"]};
}}

QProgressBar::chunk {{
    background-color: {p["accent"]};
    border-radius: 2px;
}}

/* ── Scrollbars ─────────────────────────────────────────────────────── */
QScrollBar:vertical {{
    background-color: {p["bg_base"]};
    width: {sp["sm"]}px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background-color: {p["border"]};
    border-radius: 4px;
    min-height: 24px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {p["text_disabled"]};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background-color: {p["bg_base"]};
    height: {sp["sm"]}px;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background-color: {p["border"]};
    border-radius: 4px;
    min-width: 24px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {p["text_disabled"]};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ── Dock ───────────────────────────────────────────────────────────── */
QDockWidget {{
    color: {p["text_primary"]};
}}

QDockWidget::title {{
    background-color: {p["bg_surface"]};
    color: {p["text_secondary"]};
    padding: 5px {sp["sm"]}px;
    border-bottom: 1px solid {p["border"]};
    font-size: {f["size_sm"]}px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
}}

/* ── MenuBar ────────────────────────────────────────────────────────── */
QMenuBar {{
    background-color: {p["bg_surface"]};
    color: {p["text_secondary"]};
    border-bottom: 1px solid {p["border"]};
}}

QMenuBar::item:selected {{
    background-color: {p["bg_elevated"]};
    color: {p["text_primary"]};
}}

QMenu {{
    background-color: {p["bg_surface"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border"]};
}}

QMenu::item:selected {{
    background-color: {p["bg_card"]};
    color: {p["text_primary"]};
}}

/* ── Misc ───────────────────────────────────────────────────────────── */
QScrollArea {{
    border: none;
    background-color: {p["bg_surface"]};
}}

/* Left panel scroll areas keep surface background */
QScrollArea#left_panel_scroll {{
    background-color: {p["bg_surface"]};
    border-right: 1px solid {p["border"]};
}}

QScrollArea#left_panel_scroll QWidget#left_panel_content {{
    background-color: {p["bg_surface"]};
}}

QSplitter::handle {{
    background-color: {p["border"]};
}}

QToolTip {{
    background-color: {p["bg_card"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border"]};
    padding: {sp["xs"]}px {sp["sm"]}px;
    border-radius: 3px;
}}

QMessageBox {{
    background-color: {p["bg_surface"]};
    color: {p["text_primary"]};
}}
"""
    return qss


# ---------------------------------------------------------------------------
# v2 UI additions stylesheet builder
# ---------------------------------------------------------------------------

def build_v2_additions(palette: dict, spacing: dict, font: dict) -> str:
    """Return QSS for all custom object names introduced by the redesigned UI layer.

    Args:
        palette: Colour palette dict (e.g. ``PALETTE`` or ``_LIGHT_PALETTE``).
        spacing: Spacing scale dict (e.g. ``SPACING``).
        font:    Font constants dict (e.g. ``FONT``).

    Returns:
        A QSS string covering every custom ``objectName`` used by the v2 UI.
    """
    p = palette
    sp = spacing
    f = font

    qss = f"""
/* ── nav_item — inactive sidebar button ────────────────────────────── */
QPushButton#nav_item {{
    background-color: transparent;
    color: {p["text_secondary"]};
    border: none;
    border-radius: 4px;
    padding: {sp["xs"]}px {sp["sm"]}px;
    font-size: {f["size_base"]}px;
    text-align: left;
}}

QPushButton#nav_item:hover {{
    background-color: {p["bg_elevated"]};
    color: {p["text_primary"]};
}}

/* ── nav_item_active — active sidebar button ────────────────────────── */
QPushButton#nav_item_active {{
    background-color: {p["bg_elevated"]};
    color: {p["accent"]};
    border: none;
    border-left: 3px solid {p["accent"]};
    border-radius: 4px;
    padding: {sp["xs"]}px {sp["sm"]}px;
    font-size: {f["size_base"]}px;
    font-weight: 600;
    text-align: left;
}}

QPushButton#nav_item_active:hover {{
    background-color: {p["bg_card"]};
}}

/* ── metric_card — dashboard KPI card ──────────────────────────────── */
QFrame#metric_card {{
    background-color: {p["bg_card"]};
    border: 1px solid {p["border"]};
    border-radius: 6px;
    padding: {sp["md"]}px;
}}

QFrame#metric_card QLabel {{
    background-color: transparent;
}}

/* ── section_header — collapsible section title bar ────────────────── */
QWidget#section_header {{
    background-color: {p["bg_surface"]};
    border: 1px solid {p["border"]};
    border-radius: 4px;
    padding: {sp["xs"]}px {sp["sm"]}px;
}}

QWidget#section_header QToolButton {{
    background-color: transparent;
    color: {p["text_secondary"]};
    border: none;
    font-size: {f["size_sm"]}px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
}}

QWidget#section_header QToolButton:hover {{
    color: {p["text_primary"]};
}}

/* ── command_palette — command palette dialog ───────────────────────── */
QDialog#command_palette {{
    background-color: {p["bg_elevated"]};
    border: 1px solid {p["border_focus"]};
    border-radius: 8px;
}}

QDialog#command_palette QLineEdit {{
    background-color: {p["bg_base"]};
    color: {p["text_primary"]};
    border: none;
    border-bottom: 1px solid {p["border"]};
    border-radius: 0;
    padding: {sp["sm"]}px {sp["md"]}px;
    font-size: {f["size_lg"]}px;
}}

QDialog#command_palette QListWidget {{
    background-color: transparent;
    border: none;
    color: {p["text_primary"]};
}}

QDialog#command_palette QListWidget::item:selected {{
    background-color: {p["bg_card"]};
    color: {p["accent"]};
}}

/* ── toast_info — info notification toast ──────────────────────────── */
QWidget#toast_info {{
    background-color: {p["bg_elevated"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border"]};
    border-left: 4px solid {p["accent"]};
    border-radius: 6px;
    padding: {sp["sm"]}px {sp["md"]}px;
}}

/* ── toast_success — success notification toast ─────────────────────── */
QWidget#toast_success {{
    background-color: {p["bg_elevated"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border"]};
    border-left: 4px solid {p["success"]};
    border-radius: 6px;
    padding: {sp["sm"]}px {sp["md"]}px;
}}

/* ── toast_error — error notification toast ─────────────────────────── */
QWidget#toast_error {{
    background-color: {p["bg_elevated"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border"]};
    border-left: 4px solid {p["danger"]};
    border-radius: 6px;
    padding: {sp["sm"]}px {sp["md"]}px;
}}

/* ── toast_warning — warning notification toast ─────────────────────── */
QWidget#toast_warning {{
    background-color: {p["bg_elevated"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border"]};
    border-left: 4px solid {p["warning"]};
    border-radius: 6px;
    padding: {sp["sm"]}px {sp["md"]}px;
}}

/* ── page_title — large page heading label ──────────────────────────── */
QLabel#page_title {{
    color: {p["text_primary"]};
    font-size: {f["size_lg"]}px;
    font-weight: 700;
    background-color: transparent;
    padding: 0;
}}
"""
    return qss
