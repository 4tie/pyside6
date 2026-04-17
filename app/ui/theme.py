"""Centralised theme module for the Freqtrade GUI application.

Defines colour palette, spacing, font constants, and the ``build_stylesheet``
function that assembles the complete QSS string from those constants.

This module has NO imports from the rest of the application — it is a pure
data/string module (only stdlib + get_logger from app.core.utils.app_logger).
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
# Dark palette (default)
# ---------------------------------------------------------------------------

PALETTE: Final[dict] = {
    # Backgrounds
    "bg_base":      "#1e1e1e",
    "bg_surface":   "#2d2d2d",
    "bg_elevated":  "#3c3c3c",
    # Borders
    "border":       "#3c3c3c",
    "border_focus": "#007acc",
    # Text
    "text_primary":   "#d4d4d4",
    "text_secondary": "#aaaaaa",
    "text_disabled":  "#666666",
    # Accent (VS Code blue)
    "accent":         "#0e639c",
    "accent_hover":   "#1177bb",
    "accent_pressed": "#0a4f7e",
    # Semantic
    "success": "#1a7a3c",
    "danger":  "#c72e2e",
    "warning": "#856404",
}

# ---------------------------------------------------------------------------
# Light palette
# ---------------------------------------------------------------------------

_LIGHT_PALETTE: Final[dict] = {
    # Backgrounds (inverted — light backgrounds)
    "bg_base":      "#ffffff",
    "bg_surface":   "#f3f3f3",
    "bg_elevated":  "#e8e8e8",
    # Borders
    "border":       "#d0d0d0",
    "border_focus": "#007acc",
    # Text (dark text on light background)
    "text_primary":   "#1e1e1e",
    "text_secondary": "#555555",
    "text_disabled":  "#aaaaaa",
    # Accent — same blue
    "accent":         "#0e639c",
    "accent_hover":   "#1177bb",
    "accent_pressed": "#0a4f7e",
    # Semantic
    "success": "#1a7a3c",
    "danger":  "#c72e2e",
    "warning": "#856404",
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
    background-color: {p["accent"]};
    color: {p["text_primary"]};
    border: none;
    padding: {sp["xs"]}px {sp["lg"]}px;
    border-radius: 4px;
    font-size: {f["size_base"]}px;
    font-weight: 500;
}}

QPushButton:hover {{
    background-color: {p["accent_hover"]};
}}

QPushButton:pressed {{
    background-color: {p["accent_pressed"]};
}}

QPushButton:disabled {{
    background-color: {p["bg_elevated"]};
    color: {p["text_disabled"]};
}}

QPushButton#secondary {{
    background-color: transparent;
    color: {p["text_secondary"]};
    border: 1px solid {p["border"]};
}}

QPushButton#secondary:hover {{
    background-color: {p["bg_surface"]};
    border-color: {p["border_focus"]};
}}

QPushButton#danger {{
    background-color: {p["danger"]};
    color: {p["text_primary"]};
}}

QPushButton#danger:hover {{
    background-color: {p["danger"]};
    opacity: 0.85;
}}

QPushButton#success {{
    background-color: {p["success"]};
    color: {p["text_primary"]};
}}

QPushButton#success:hover {{
    background-color: {p["success"]};
    opacity: 0.85;
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
    border: 1px solid {p["border"]};
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
}}

QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {p["border_focus"]};
}}

/* ── Labels ─────────────────────────────────────────────────────────── */
QLabel {{
    color: {p["text_primary"]};
    background-color: transparent;
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
    background-color: {p["warning"]};
    color: {p["text_primary"]};
    border: 1px solid {p["warning"]};
    padding: {sp["sm"]}px;
    border-radius: 4px;
}}

QLabel#success_banner {{
    background-color: {p["success"]};
    color: {p["text_primary"]};
    border: 1px solid {p["success"]};
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
    background-color: {p["border_focus"]};
    border-color: {p["border_focus"]};
}}

/* ── GroupBox ───────────────────────────────────────────────────────── */
QGroupBox {{
    border: 1px solid {p["border"]};
    border-radius: 6px;
    margin-top: {sp["lg"]}px;
    padding-top: {sp["md"]}px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 {sp["xs"]}px;
    color: {p["text_secondary"]};
    font-size: {f["size_sm"]}px;
    text-transform: uppercase;
}}

/* ── Lists ──────────────────────────────────────────────────────────── */
QListWidget {{
    background-color: {p["bg_surface"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border"]};
    border-radius: 4px;
}}

QListWidget::item:selected {{
    background-color: {p["accent"]};
    color: {p["text_primary"]};
}}

QListWidget::item:hover {{
    background-color: {p["bg_elevated"]};
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
}}

/* ── MenuBar ────────────────────────────────────────────────────────── */
QMenuBar {{
    background-color: {p["bg_surface"]};
    color: {p["text_secondary"]};
    border-bottom: 1px solid {p["border"]};
}}

QMenuBar::item:selected {{
    background-color: {p["bg_elevated"]};
}}

QMenu {{
    background-color: {p["bg_surface"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border"]};
}}

QMenu::item:selected {{
    background-color: {p["accent"]};
}}

/* ── Misc ───────────────────────────────────────────────────────────── */
QScrollArea {{
    border: none;
    background-color: transparent;
}}

QSplitter::handle {{
    background-color: {p["border"]};
}}

QToolTip {{
    background-color: {p["bg_elevated"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border"]};
    padding: {sp["xs"]}px;
    border-radius: 3px;
}}

QMessageBox {{
    background-color: {p["bg_surface"]};
    color: {p["text_primary"]};
}}
"""
    return qss
