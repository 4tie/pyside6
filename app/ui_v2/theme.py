"""Theme module for app/ui_v2/.

Re-exports all public symbols from ``app.ui.theme`` so that callers can
import from either location and get identical behaviour.  Adds
``build_v2_additions`` which returns QSS for the new object names
introduced by the v2 UI layer.
"""
from app.core.utils.app_logger import get_logger
from app.ui.theme import (  # noqa: F401
    ThemeMode,
    PALETTE,
    SPACING,
    FONT,
    build_stylesheet,
    _LIGHT_PALETTE,  # noqa: F401 — re-exported for callers that need it
)

_log = get_logger("ui_v2.theme")


def build_v2_additions(palette: dict, spacing: dict, font: dict) -> str:
    """Return QSS for the new object names introduced in the v2 UI layer.

    Args:
        palette: Colour palette dict (e.g. ``PALETTE`` or ``_LIGHT_PALETTE``).
        spacing: Spacing scale dict (e.g. ``SPACING``).
        font:    Font constants dict (e.g. ``FONT``).

    Returns:
        A QSS string containing rules for every new v2 object name:
        ``nav_item``, ``nav_item_active``, ``metric_card``,
        ``section_header``, ``command_palette``, ``toast_info``,
        ``toast_success``, ``toast_error``, ``toast_warning``,
        ``page_title``.
    """
    p = palette
    sp = spacing
    f = font

    qss = f"""
/* ── v2 Nav Items ───────────────────────────────────────────────────── */
QPushButton#nav_item {{
    background-color: transparent;
    color: {p["text_secondary"]};
    border: none;
    border-radius: 4px;
    padding: {sp["sm"]}px {sp["md"]}px;
    text-align: left;
    font-size: {f["size_base"]}px;
}}

QPushButton#nav_item:hover {{
    background-color: {p["bg_elevated"]};
    color: {p["text_primary"]};
}}

QPushButton#nav_item_active {{
    background-color: {p["bg_elevated"]};
    color: {p["accent"]};
    border: none;
    border-left: 3px solid {p["accent"]};
    border-radius: 4px;
    padding: {sp["sm"]}px {sp["md"]}px;
    text-align: left;
    font-size: {f["size_base"]}px;
    font-weight: 600;
}}

/* ── v2 Metric Card ─────────────────────────────────────────────────── */
QFrame#metric_card {{
    background-color: {p["bg_card"]};
    border: 1px solid {p["border"]};
    border-radius: 6px;
    padding: {sp["md"]}px;
}}

QFrame#metric_card:hover {{
    border-color: {p["border_focus"]};
}}

/* ── v2 Section Header ──────────────────────────────────────────────── */
QWidget#section_header {{
    background-color: {p["bg_surface"]};
    border-bottom: 1px solid {p["border"]};
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

/* ── v2 Command Palette ─────────────────────────────────────────────── */
QDialog#command_palette {{
    background-color: {p["bg_elevated"]};
    border: 1px solid {p["border_focus"]};
    border-radius: 8px;
}}

QDialog#command_palette QLineEdit {{
    background-color: {p["bg_base"]};
    border: none;
    border-bottom: 1px solid {p["border"]};
    border-radius: 0;
    font-size: {f["size_lg"]}px;
    padding: {sp["md"]}px;
}}

QDialog#command_palette QListWidget {{
    background-color: transparent;
    border: none;
    font-size: {f["size_base"]}px;
}}

QDialog#command_palette QListWidget::item:selected {{
    background-color: {p["bg_card"]};
    color: {p["text_primary"]};
    border-radius: 4px;
}}

/* ── v2 Toast Notifications ─────────────────────────────────────────── */
QWidget#toast_info {{
    background-color: {p["bg_card"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border"]};
    border-left: 4px solid {p["accent"]};
    border-radius: 6px;
    padding: {sp["sm"]}px {sp["md"]}px;
}}

QWidget#toast_success {{
    background-color: {p["bg_card"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border"]};
    border-left: 4px solid {p["success"]};
    border-radius: 6px;
    padding: {sp["sm"]}px {sp["md"]}px;
}}

QWidget#toast_error {{
    background-color: {p["bg_card"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border"]};
    border-left: 4px solid {p["danger"]};
    border-radius: 6px;
    padding: {sp["sm"]}px {sp["md"]}px;
}}

QWidget#toast_warning {{
    background-color: {p["bg_card"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border"]};
    border-left: 4px solid {p["warning"]};
    border-radius: 6px;
    padding: {sp["sm"]}px {sp["md"]}px;
}}

/* ── v2 Page Title ──────────────────────────────────────────────────── */
QLabel#page_title {{
    color: {p["text_primary"]};
    font-size: {f["size_lg"]}px;
    font-weight: 700;
    background-color: transparent;
    padding: {sp["xs"]}px 0;
}}
"""
    return qss
