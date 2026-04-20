"""Unit tests for app/ui_v2/theme.py.

Validates:
- Re-export: ``build_stylesheet`` imported from ``app.ui_v2.theme`` produces
  output identical to the same function from ``app.ui.theme``.
- ``build_v2_additions`` returns a non-empty string containing every new
  v2 object name.

**Property P6: Theme Consistency — ``build_stylesheet`` output must be
identical from both modules.**

Validates: Requirements 9.1, 18.1
"""
import pytest
from hypothesis import given, settings as hyp_settings
from hypothesis import strategies as st

# Import from both modules under test
import app.ui.theme as _orig_theme
import app.ui_v2.theme as _v2_theme


# ---------------------------------------------------------------------------
# Helpers
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


# ---------------------------------------------------------------------------
# Unit tests — re-export correctness
# ---------------------------------------------------------------------------


class TestThemeReExport:
    """Verify that app.ui_v2.theme re-exports the same symbols as app.ui.theme."""

    def test_build_stylesheet_dark_identical(self):
        """build_stylesheet(DARK) output is identical from both modules."""
        orig = _orig_theme.build_stylesheet(_orig_theme.ThemeMode.DARK)
        v2 = _v2_theme.build_stylesheet(_v2_theme.ThemeMode.DARK)
        assert orig == v2

    def test_build_stylesheet_light_identical(self):
        """build_stylesheet(LIGHT) output is identical from both modules."""
        orig = _orig_theme.build_stylesheet(_orig_theme.ThemeMode.LIGHT)
        v2 = _v2_theme.build_stylesheet(_v2_theme.ThemeMode.LIGHT)
        assert orig == v2

    def test_theme_mode_enum_identical(self):
        """ThemeMode enum values are the same object (or equal) from both modules."""
        assert _orig_theme.ThemeMode.DARK.value == _v2_theme.ThemeMode.DARK.value
        assert _orig_theme.ThemeMode.LIGHT.value == _v2_theme.ThemeMode.LIGHT.value

    def test_palette_identical(self):
        """PALETTE dict is identical from both modules."""
        assert _orig_theme.PALETTE == _v2_theme.PALETTE

    def test_spacing_identical(self):
        """SPACING dict is identical from both modules."""
        assert _orig_theme.SPACING == _v2_theme.SPACING

    def test_font_identical(self):
        """FONT dict is identical from both modules."""
        assert _orig_theme.FONT == _v2_theme.FONT


# ---------------------------------------------------------------------------
# Unit tests — build_v2_additions
# ---------------------------------------------------------------------------


class TestBuildV2Additions:
    """Verify build_v2_additions returns correct QSS."""

    def test_returns_non_empty_string(self):
        """build_v2_additions returns a non-empty string."""
        result = _v2_theme.build_v2_additions(
            _v2_theme.PALETTE, _v2_theme.SPACING, _v2_theme.FONT
        )
        assert isinstance(result, str)
        assert len(result.strip()) > 0

    @pytest.mark.parametrize("obj_name", _V2_OBJECT_NAMES)
    def test_contains_each_object_name(self, obj_name: str):
        """build_v2_additions QSS contains each required object name."""
        result = _v2_theme.build_v2_additions(
            _v2_theme.PALETTE, _v2_theme.SPACING, _v2_theme.FONT
        )
        assert obj_name in result, (
            f"Expected object name '{obj_name}' not found in build_v2_additions output"
        )

    def test_works_with_light_palette(self):
        """build_v2_additions works with the light palette without errors."""
        result = _v2_theme.build_v2_additions(
            _v2_theme._LIGHT_PALETTE, _v2_theme.SPACING, _v2_theme.FONT
        )
        assert isinstance(result, str)
        assert len(result.strip()) > 0

    def test_all_object_names_present_in_one_call(self):
        """All v2 object names are present in a single build_v2_additions call."""
        result = _v2_theme.build_v2_additions(
            _v2_theme.PALETTE, _v2_theme.SPACING, _v2_theme.FONT
        )
        missing = [name for name in _V2_OBJECT_NAMES if name not in result]
        assert missing == [], f"Missing object names in QSS: {missing}"


# ---------------------------------------------------------------------------
# Property P6 — Theme Consistency (Hypothesis)
# ---------------------------------------------------------------------------


@hyp_settings(max_examples=10)
@given(
    mode=st.sampled_from([_orig_theme.ThemeMode.DARK, _orig_theme.ThemeMode.LIGHT])
)
def test_p6_build_stylesheet_identical_across_modules(mode):
    """Property P6: build_stylesheet output must be identical from both modules.

    **Validates: Requirements 9.1, 18.1**
    """
    orig_output = _orig_theme.build_stylesheet(mode)
    v2_output = _v2_theme.build_stylesheet(mode)
    assert orig_output == v2_output, (
        f"build_stylesheet({mode!r}) differs between app.ui.theme and app.ui_v2.theme"
    )
