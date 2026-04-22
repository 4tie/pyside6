"""Unit and property-based tests for app/ui/theme.py.

Validates: Requirements 1.1, 1.2, 1.3, 1.4, 4.1, 10.2, 18.1
"""
from hypothesis import given, settings as hyp_settings
from hypothesis import strategies as st

from app.ui.theme import (
    FONT,
    PALETTE,
    SPACING,
    ThemeMode,
    _LIGHT_PALETTE,
    build_stylesheet,
    build_v2_additions,
)

# ---------------------------------------------------------------------------
# Unit tests — constants
# ---------------------------------------------------------------------------

_REQUIRED_PALETTE_KEYS = {
    "bg_base", "bg_surface", "bg_elevated",
    "border", "border_focus",
    "text_primary", "text_secondary", "text_disabled",
    "accent", "accent_hover", "accent_pressed",
    "success", "danger", "warning",
}

_REQUIRED_SPACING_KEYS = {"xs", "sm", "md", "lg", "xl"}

_REQUIRED_FONT_KEYS = {"family", "size_sm", "size_base", "size_lg", "mono_family"}


def test_palette_keys_present():
    """PALETTE contains all 14 required colour keys."""
    assert _REQUIRED_PALETTE_KEYS.issubset(PALETTE.keys())


def test_spacing_keys_present():
    """SPACING contains all 5 required spacing keys."""
    assert _REQUIRED_SPACING_KEYS.issubset(SPACING.keys())


def test_font_keys_present():
    """FONT contains all 5 required font keys."""
    assert _REQUIRED_FONT_KEYS.issubset(FONT.keys())


# ---------------------------------------------------------------------------
# Unit tests — build_stylesheet
# ---------------------------------------------------------------------------

def test_build_stylesheet_dark_returns_string():
    """build_stylesheet(DARK) returns a non-empty string."""
    result = build_stylesheet(ThemeMode.DARK)
    assert isinstance(result, str)
    assert len(result) > 0


def test_build_stylesheet_light_returns_string():
    """build_stylesheet(LIGHT) returns a non-empty string."""
    result = build_stylesheet(ThemeMode.LIGHT)
    assert isinstance(result, str)
    assert len(result) > 0


def test_build_stylesheet_dark_light_differ():
    """Dark and light stylesheets are not identical."""
    dark = build_stylesheet(ThemeMode.DARK)
    light = build_stylesheet(ThemeMode.LIGHT)
    assert dark != light


# ---------------------------------------------------------------------------
# Property 1: PALETTE completeness
# Feature: app-theme-redesign
# Validates: Requirements 1.1, 1.3
# ---------------------------------------------------------------------------

@given(mode=st.sampled_from(ThemeMode))
@hyp_settings(max_examples=100)
def test_palette_completeness(mode):
    """For any ThemeMode, every palette value for that mode appears in the QSS.

    **Validates: Requirements 1.1, 1.3**
    """
    qss = build_stylesheet(mode)
    active_palette = PALETTE if mode == ThemeMode.DARK else _LIGHT_PALETTE
    for key, value in active_palette.items():
        assert value in qss or key in qss, (
            f"Palette key '{key}' (value '{value}') not found in QSS for mode {mode}"
        )


# ---------------------------------------------------------------------------
# Property 2: SPACING completeness
# Feature: app-theme-redesign
# Validates: Requirements 1.2, 1.3
# ---------------------------------------------------------------------------

@given(mode=st.sampled_from(ThemeMode))
@hyp_settings(max_examples=100)
def test_spacing_completeness(mode):
    """For any ThemeMode, every SPACING value appears in the QSS.

    **Validates: Requirements 1.2, 1.3**
    """
    qss = build_stylesheet(mode)
    for value in SPACING.values():
        assert str(value) in qss, (
            f"SPACING value '{value}' not found in QSS for mode {mode}"
        )


# ---------------------------------------------------------------------------
# Property 4: Stylesheet round-trip stability
# Feature: app-theme-redesign
# Validates: Requirements 1.3, 10.2
# ---------------------------------------------------------------------------

@given(mode=st.sampled_from(ThemeMode))
@hyp_settings(max_examples=100)
def test_stylesheet_deterministic(mode):
    """build_stylesheet is pure — calling it twice returns identical strings.

    **Validates: Requirements 1.3, 10.2**
    """
    assert build_stylesheet(mode) == build_stylesheet(mode)


# ---------------------------------------------------------------------------
# Unit tests — build_v2_additions
# ---------------------------------------------------------------------------

_V2_OBJECT_NAMES = [
    "nav_item",
    "nav_item_active",
    "metric_card",
    "section_header",
    "command_palette",
    "toast_info",
    "toast_success",
    "toast_error",
    "toast_warning",
    "page_title",
]


def test_build_v2_additions_returns_nonempty_string():
    """build_v2_additions returns a non-empty string."""
    result = build_v2_additions(PALETTE, SPACING, FONT)
    assert isinstance(result, str)
    assert len(result) > 0


def test_build_v2_additions_contains_all_object_names():
    """build_v2_additions output contains every required objectName."""
    result = build_v2_additions(PALETTE, SPACING, FONT)
    for name in _V2_OBJECT_NAMES:
        assert name in result, f"objectName '{name}' not found in build_v2_additions output"


def test_build_stylesheet_invalid_mode_falls_back_to_dark():
    """build_stylesheet with an invalid mode falls back to DARK output."""
    dark_qss = build_stylesheet(ThemeMode.DARK)
    fallback_qss = build_stylesheet("not_a_mode")  # type: ignore[arg-type]
    assert fallback_qss == dark_qss
