"""Unit and property-based tests for AppSettings.theme_mode field.

Validates: Requirement 10.3
"""
from hypothesis import given
from hypothesis import settings as hyp_settings
from hypothesis import strategies as st

from app.core.models.settings_models import AppSettings


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def test_appsettings_theme_mode_default():
    """AppSettings().theme_mode defaults to 'dark'."""
    assert AppSettings().theme_mode == "dark"


def test_appsettings_theme_mode_light():
    """AppSettings(theme_mode='light').theme_mode == 'light'."""
    assert AppSettings(theme_mode="light").theme_mode == "light"


# ---------------------------------------------------------------------------
# Property 5: Theme mode serialisation round-trip
# Feature: app-theme-redesign
# Validates: Requirement 10.3
# ---------------------------------------------------------------------------

@given(mode=st.sampled_from(["dark", "light"]))
@hyp_settings(max_examples=100)
def test_theme_mode_roundtrip(mode):
    """Serialising AppSettings to JSON and back preserves theme_mode.

    **Validates: Requirement 10.3**
    """
    settings_obj = AppSettings(theme_mode=mode)
    json_str = settings_obj.model_dump_json()
    restored = AppSettings.model_validate_json(json_str)
    assert restored.theme_mode == mode
