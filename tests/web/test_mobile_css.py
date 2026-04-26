"""Static file smoke tests for mobile CSS and frontend configuration.

All tests read static files from the workspace root using pathlib.Path;
no browser or build step required.

Requirements validated: 4.1, 4.3, 4.4, 5.1, 5.6, 6.1, 7.2, 8.1, 8.6, 9.1, 9.2, 9.3
"""

import json
from pathlib import Path

# Workspace root is the directory containing run_web.py
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent

INDEX_HTML = WORKSPACE_ROOT / "app" / "re_web" / "index.html"
APP_CSS = WORKSPACE_ROOT / "app" / "re_web" / "src" / "styles" / "app.css"
PACKAGE_JSON = WORKSPACE_ROOT / "app" / "re_web" / "package.json"
VITE_CONFIG = WORKSPACE_ROOT / "app" / "re_web" / "vite.config.ts"

MEDIA_QUERY = "@media (max-width: 680px)"


def _media_680_block(css: str) -> str:
    """Return the substring of css starting from the 680px media query to end of file.

    This is a simple approach: find the media query marker and return everything
    from that point onward, which includes the block content.
    """
    idx = css.find(MEDIA_QUERY)
    if idx == -1:
        return ""
    return css[idx:]


# ── Requirement 4.1 ───────────────────────────────────────────────────────────

def test_viewport_fit_cover():
    """index.html must include viewport-fit=cover for iPhone notch support."""
    content = INDEX_HTML.read_text(encoding="utf-8")
    assert "viewport-fit=cover" in content


# ── Requirements 4.3, 4.4 ─────────────────────────────────────────────────────

def test_safe_area_inset_bottom():
    """app.css must use env(safe-area-inset-bottom) for iPhone home-bar clearance."""
    content = APP_CSS.read_text(encoding="utf-8")
    assert "env(safe-area-inset-bottom)" in content


def test_safe_area_inset_top():
    """app.css must use env(safe-area-inset-top) for iPhone status-bar clearance."""
    content = APP_CSS.read_text(encoding="utf-8")
    assert "env(safe-area-inset-top)" in content


# ── Requirements 6.1, 7.2 — inside @media (max-width: 680px) ─────────────────

def test_touch_target_min_height():
    """min-height: 44px must appear inside the 680px media block (touch target rule)."""
    block = _media_680_block(APP_CSS.read_text(encoding="utf-8"))
    assert block, f"Could not find '{MEDIA_QUERY}' in app.css"
    assert "min-height: 44px" in block


def test_input_font_size_16px():
    """font-size: 16px must appear inside the 680px media block (prevents iOS zoom)."""
    block = _media_680_block(APP_CSS.read_text(encoding="utf-8"))
    assert block, f"Could not find '{MEDIA_QUERY}' in app.css"
    assert "font-size: 16px" in block


# ── Requirement 5.1, 5.6 ─────────────────────────────────────────────────────

def test_mobile_nav_display_flex():
    """.mobile-nav { display: flex } must appear inside the 680px media block."""
    block = _media_680_block(APP_CSS.read_text(encoding="utf-8"))
    assert block, f"Could not find '{MEDIA_QUERY}' in app.css"
    # Both the selector and the property must be present in the block
    assert ".mobile-nav" in block
    assert "display: flex" in block


def test_sidebar_hidden_mobile():
    """.sidebar { display: none } must appear inside the 680px media block."""
    block = _media_680_block(APP_CSS.read_text(encoding="utf-8"))
    assert block, f"Could not find '{MEDIA_QUERY}' in app.css"
    assert ".sidebar" in block
    assert "display: none" in block


# ── Requirement 8.1 ───────────────────────────────────────────────────────────

def test_metric_grid_two_column():
    """repeat(2, 1fr) must appear inside the 680px media block for metric grid."""
    block = _media_680_block(APP_CSS.read_text(encoding="utf-8"))
    assert block, f"Could not find '{MEDIA_QUERY}' in app.css"
    assert "repeat(2, 1fr)" in block


# ── Requirement 8.6 ───────────────────────────────────────────────────────────

def test_tab_list_scrollbar_hidden():
    """scrollbar-width: none must appear inside the 680px media block."""
    block = _media_680_block(APP_CSS.read_text(encoding="utf-8"))
    assert block, f"Could not find '{MEDIA_QUERY}' in app.css"
    assert "scrollbar-width: none" in block


# ── Requirements 9.1, 9.2 ─────────────────────────────────────────────────────

def test_dev_script_binds_0000():
    """package.json dev script must bind to 0.0.0.0 for Tailscale/LAN access."""
    data = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    assert "--host 0.0.0.0" in data["scripts"]["dev"]


def test_preview_script_binds_0000():
    """package.json preview script must bind to 0.0.0.0 for Tailscale/LAN access."""
    data = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    assert "--host 0.0.0.0" in data["scripts"]["preview"]


# ── Requirement 9.3 ───────────────────────────────────────────────────────────

def test_vite_proxy_intact():
    """vite.config.ts must proxy /api to the local FastAPI server."""
    content = VITE_CONFIG.read_text(encoding="utf-8")
    assert "http://127.0.0.1:8000" in content


# ── Requirements 10.1, 11.1, 13.1, 13.2, 14.1, 14.2, 14.4 ───────────────────
# Enhancement smoke tests added for tasks F–I

def test_mobile_more_sheet_css():
    """.mobile-more-sheet { display: flex } must appear inside the 680px media block."""
    block = _media_680_block(APP_CSS.read_text(encoding="utf-8"))
    assert block, f"Could not find '{MEDIA_QUERY}' in app.css"
    assert ".mobile-more-sheet" in block
    assert "display: flex" in block


def test_run_card_list_css():
    """.run-card-list { display: grid } must appear inside the 680px media block."""
    block = _media_680_block(APP_CSS.read_text(encoding="utf-8"))
    assert block, f"Could not find '{MEDIA_QUERY}' in app.css"
    assert ".run-card-list" in block
    assert "display: grid" in block


def test_run_table_desktop_hidden():
    """.run-table-desktop { display: none } must appear inside the 680px media block."""
    block = _media_680_block(APP_CSS.read_text(encoding="utf-8"))
    assert block, f"Could not find '{MEDIA_QUERY}' in app.css"
    assert ".run-table-desktop" in block
    assert "display: none" in block


def test_hover_none_button_reset():
    """.button:hover reset must appear inside the @media (hover: none) block."""
    css = APP_CSS.read_text(encoding="utf-8")
    hover_query = "@media (hover: none)"
    idx = css.find(hover_query)
    assert idx != -1, f"Could not find '{hover_query}' in app.css"
    block = css[idx:]
    assert ".button:hover" in block


def test_webkit_overflow_scrolling():
    """-webkit-overflow-scrolling: touch must appear and .terminal must be in the same rule block."""
    css = APP_CSS.read_text(encoding="utf-8")
    assert "-webkit-overflow-scrolling: touch" in css
    # Find the rule block containing -webkit-overflow-scrolling: touch.
    # The selector list precedes the opening brace, so we look for the previous
    # closing brace (end of the prior rule) and extract everything from there to
    # the property — that span covers the selector list and the opening brace.
    prop_idx = css.find("-webkit-overflow-scrolling: touch")
    prev_close = css.rfind("}", 0, prop_idx)
    assert prev_close != -1, "Could not find previous closing brace before -webkit-overflow-scrolling"
    rule_context = css[prev_close:prop_idx]
    assert ".terminal" in rule_context, ".terminal selector must be in the same rule block as -webkit-overflow-scrolling: touch"


def test_param_row_mobile_two_col():
    """.param-row { grid-template-columns: 1fr 1fr } must appear inside the 680px media block."""
    block = _media_680_block(APP_CSS.read_text(encoding="utf-8"))
    assert block, f"Could not find '{MEDIA_QUERY}' in app.css"
    assert ".param-row" in block
    assert "grid-template-columns: 1fr 1fr" in block


def test_run_selector_full_width():
    """.run-selector-wrap { width: 100% } must appear inside the 680px media block."""
    block = _media_680_block(APP_CSS.read_text(encoding="utf-8"))
    assert block, f"Could not find '{MEDIA_QUERY}' in app.css"
    assert ".run-selector-wrap" in block
    assert "width: 100%" in block


def test_chip_min_height():
    """.chip { min-height: 36px } must appear inside the 680px media block."""
    block = _media_680_block(APP_CSS.read_text(encoding="utf-8"))
    assert block, f"Could not find '{MEDIA_QUERY}' in app.css"
    assert ".chip" in block
    assert "min-height: 36px" in block
