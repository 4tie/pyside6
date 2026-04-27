"""
Centralized theme — dark palette, accent colors, typography, spacing.
"""
from __future__ import annotations

# ── Palette ──────────────────────────────────────────────────────────────────
BG_BASE      = "#0d0f14"   # deepest background
BG_SURFACE   = "#13161e"   # cards / panels
BG_ELEVATED  = "#1a1e2a"   # hover / selected
BG_BORDER    = "#252a38"   # subtle borders
BG_INPUT     = "#1e2230"   # input fields

ACCENT       = "#4f8ef7"   # primary blue
ACCENT_HOVER = "#6ba3ff"
ACCENT_DIM   = "#2a4a8a"

GREEN        = "#3ecf8e"   # profit / positive
GREEN_DIM    = "#1a5c3e"
RED          = "#f75f5f"   # loss / negative
RED_DIM      = "#5c1a1a"
YELLOW       = "#f7c948"   # warning
PURPLE       = "#a78bfa"   # hyperopt / special

TEXT_PRIMARY   = "#e8eaf0"
TEXT_SECONDARY = "#8892a4"
TEXT_MUTED     = "#4a5568"
TEXT_ACCENT    = ACCENT

# ── Typography ────────────────────────────────────────────────────────────────
FONT_FAMILY  = "Inter, Segoe UI, SF Pro Display, Arial, sans-serif"
FONT_MONO    = "JetBrains Mono, Fira Code, Consolas, monospace"

# ── Spacing ───────────────────────────────────────────────────────────────────
RADIUS       = "8px"
RADIUS_LG    = "12px"
RADIUS_SM    = "4px"

# ── Chart colors ─────────────────────────────────────────────────────────────
CHART_BG     = "#0d0f14"
CHART_GRID   = "#1e2230"
CHART_LINE   = ACCENT
CHART_FILL   = "#1a2a4a"
CHART_GREEN  = GREEN
CHART_RED    = RED


def stylesheet() -> str:
    """Return the full application QSS stylesheet."""
    return f"""
/* ── Global ─────────────────────────────────────────────────────────────── */
* {{
    font-family: {FONT_FAMILY};
    color: {TEXT_PRIMARY};
    outline: none;
}}

QMainWindow, QDialog {{
    background: {BG_BASE};
}}

QWidget {{
    background: transparent;
}}

QWidget#surface {{
    background: {BG_SURFACE};
    border-radius: {RADIUS};
}}

/* ── ScrollBar ───────────────────────────────────────────────────────────── */
QScrollBar:vertical {{
    background: {BG_BASE};
    width: 6px;
    margin: 0;
    border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {BG_BORDER};
    border-radius: 3px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {TEXT_MUTED};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {BG_BASE};
    height: 6px;
    border-radius: 3px;
}}
QScrollBar::handle:horizontal {{
    background: {BG_BORDER};
    border-radius: 3px;
    min-width: 30px;
}}

/* ── Buttons ─────────────────────────────────────────────────────────────── */
QPushButton {{
    background: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BG_BORDER};
    border-radius: {RADIUS_SM};
    padding: 7px 16px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton:hover {{
    background: {BG_BORDER};
    border-color: {ACCENT_DIM};
}}
QPushButton:pressed {{
    background: {ACCENT_DIM};
}}
QPushButton#primary {{
    background: {ACCENT};
    color: white;
    border: none;
    font-weight: 600;
}}
QPushButton#primary:hover {{
    background: {ACCENT_HOVER};
}}
QPushButton#primary:pressed {{
    background: {ACCENT_DIM};
}}
QPushButton#danger {{
    background: {RED_DIM};
    color: {RED};
    border: 1px solid {RED_DIM};
}}
QPushButton#danger:hover {{
    background: {RED};
    color: white;
}}
QPushButton#success {{
    background: {GREEN_DIM};
    color: {GREEN};
    border: 1px solid {GREEN_DIM};
}}
QPushButton#success:hover {{
    background: {GREEN};
    color: white;
}}
QPushButton:disabled {{
    background: {BG_SURFACE};
    color: {TEXT_MUTED};
    border-color: {BG_BORDER};
}}

/* ── Inputs ──────────────────────────────────────────────────────────────── */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BG_BORDER};
    border-radius: {RADIUS_SM};
    padding: 6px 10px;
    font-size: 13px;
    selection-background-color: {ACCENT_DIM};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {ACCENT};
}}

QComboBox {{
    background: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BG_BORDER};
    border-radius: {RADIUS_SM};
    padding: 6px 10px;
    font-size: 13px;
    min-width: 120px;
}}
QComboBox:hover {{
    border-color: {ACCENT_DIM};
}}
QComboBox:focus {{
    border-color: {ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TEXT_SECONDARY};
    margin-right: 6px;
}}
QComboBox QAbstractItemView {{
    background: {BG_ELEVATED};
    border: 1px solid {BG_BORDER};
    border-radius: {RADIUS_SM};
    selection-background-color: {ACCENT_DIM};
    color: {TEXT_PRIMARY};
    padding: 4px;
}}

QSpinBox, QDoubleSpinBox {{
    background: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BG_BORDER};
    border-radius: {RADIUS_SM};
    padding: 6px 10px;
    font-size: 13px;
}}
QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {ACCENT};
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background: {BG_BORDER};
    border: none;
    width: 18px;
}}

/* ── Labels ──────────────────────────────────────────────────────────────── */
QLabel {{
    background: transparent;
    color: {TEXT_PRIMARY};
}}
QLabel#muted {{
    color: {TEXT_SECONDARY};
    font-size: 12px;
}}
QLabel#title {{
    font-size: 20px;
    font-weight: 700;
    color: {TEXT_PRIMARY};
}}
QLabel#subtitle {{
    font-size: 14px;
    color: {TEXT_SECONDARY};
}}
QLabel#metric_value {{
    font-size: 26px;
    font-weight: 700;
}}
QLabel#metric_label {{
    font-size: 11px;
    color: {TEXT_SECONDARY};
    text-transform: uppercase;
    letter-spacing: 1px;
}}
QLabel#positive {{
    color: {GREEN};
    font-weight: 600;
}}
QLabel#negative {{
    color: {RED};
    font-weight: 600;
}}
QLabel#badge {{
    background: {ACCENT_DIM};
    color: {ACCENT};
    border-radius: 10px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}}

/* ── Tables ──────────────────────────────────────────────────────────────── */
QTableWidget, QTableView {{
    background: {BG_SURFACE};
    alternate-background-color: {BG_ELEVATED};
    gridline-color: {BG_BORDER};
    border: 1px solid {BG_BORDER};
    border-radius: {RADIUS};
    font-size: 12px;
    selection-background-color: {ACCENT_DIM};
    selection-color: {TEXT_PRIMARY};
}}
QTableWidget::item, QTableView::item {{
    padding: 6px 10px;
    border: none;
}}
QTableWidget::item:selected, QTableView::item:selected {{
    background: {ACCENT_DIM};
}}
QHeaderView::section {{
    background: {BG_ELEVATED};
    color: {TEXT_SECONDARY};
    border: none;
    border-bottom: 1px solid {BG_BORDER};
    padding: 8px 10px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
QHeaderView::section:hover {{
    background: {BG_BORDER};
    color: {TEXT_PRIMARY};
}}

/* ── Tabs ────────────────────────────────────────────────────────────────── */
QTabWidget::pane {{
    background: {BG_SURFACE};
    border: 1px solid {BG_BORDER};
    border-radius: {RADIUS};
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {TEXT_SECONDARY};
    padding: 8px 18px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 13px;
    font-weight: 500;
}}
QTabBar::tab:selected {{
    color: {ACCENT};
    border-bottom: 2px solid {ACCENT};
}}
QTabBar::tab:hover {{
    color: {TEXT_PRIMARY};
}}

/* ── Splitter ────────────────────────────────────────────────────────────── */
QSplitter::handle {{
    background: {BG_BORDER};
}}
QSplitter::handle:horizontal {{
    width: 1px;
}}
QSplitter::handle:vertical {{
    height: 1px;
}}

/* ── CheckBox ────────────────────────────────────────────────────────────── */
QCheckBox {{
    spacing: 8px;
    font-size: 13px;
    color: {TEXT_PRIMARY};
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {BG_BORDER};
    border-radius: 3px;
    background: {BG_INPUT};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}

/* ── Slider ──────────────────────────────────────────────────────────────── */
QSlider::groove:horizontal {{
    background: {BG_BORDER};
    height: 4px;
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {ACCENT};
    width: 14px;
    height: 14px;
    border-radius: 7px;
    margin: -5px 0;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 2px;
}}

/* ── ProgressBar ─────────────────────────────────────────────────────────── */
QProgressBar {{
    background: {BG_BORDER};
    border: none;
    border-radius: 3px;
    height: 6px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 3px;
}}

/* ── GroupBox ────────────────────────────────────────────────────────────── */
QGroupBox {{
    background: {BG_SURFACE};
    border: 1px solid {BG_BORDER};
    border-radius: {RADIUS};
    margin-top: 12px;
    padding: 12px;
    font-size: 12px;
    font-weight: 600;
    color: {TEXT_SECONDARY};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: {TEXT_SECONDARY};
    background: {BG_SURFACE};
}}

/* ── ToolTip ─────────────────────────────────────────────────────────────── */
QToolTip {{
    background: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BG_BORDER};
    border-radius: {RADIUS_SM};
    padding: 6px 10px;
    font-size: 12px;
}}

/* ── Menu ────────────────────────────────────────────────────────────────── */
QMenu {{
    background: {BG_ELEVATED};
    border: 1px solid {BG_BORDER};
    border-radius: {RADIUS_SM};
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 20px;
    border-radius: {RADIUS_SM};
    font-size: 13px;
}}
QMenu::item:selected {{
    background: {ACCENT_DIM};
    color: {ACCENT};
}}
QMenu::separator {{
    height: 1px;
    background: {BG_BORDER};
    margin: 4px 8px;
}}
"""
