# Feature: pair-favorites, Property 5: toggle_favorite_pair mutates and persists
"""
Property-based tests for SettingsState.toggle_favorite_pair.
"""
import sys
import pytest
from unittest.mock import MagicMock
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.models.settings_models import AppSettings


# ---------------------------------------------------------------------------
# Session-scoped QApplication fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def qt_app():
    """Create (or reuse) a QApplication for the test session.

    SettingsState inherits from QObject, so a QApplication must exist before
    any QObject is instantiated.
    """
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    return app


# ---------------------------------------------------------------------------
# Property 5: toggle_favorite_pair mutates and persists
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    initial_pairs=st.lists(st.text(min_size=1, max_size=8), max_size=5, unique=True),
    pair=st.text(min_size=1, max_size=8),
)
def test_toggle_favorite_pair_mutates_and_persists(
    qt_app,
    initial_pairs: list[str],
    pair: str,
) -> None:
    """Property 5: toggle_favorite_pair mutates and persists.

    For any AppSettings with a random favorite_pairs list and any pair string:
    - Calling toggle_favorite_pair flips membership of the pair.
    - save_settings is called exactly once per toggle.
    - Calling toggle_favorite_pair again flips membership back.
    - save_settings has been called exactly twice in total.

    Validates: Requirements 3.2, 3.3
    """
    from app.app_state.settings_state import SettingsState

    # Build settings with the generated initial favorites
    app_settings = AppSettings(favorite_pairs=list(initial_pairs))
    was_present = pair in app_settings.favorite_pairs

    # Instantiate state and wire up settings
    state = SettingsState()
    state.current_settings = app_settings

    # Mock save_settings to avoid disk I/O
    state.settings_service.save_settings = MagicMock(return_value=True)

    # --- First toggle ---
    state.toggle_favorite_pair(pair)

    if was_present:
        assert pair not in state.current_settings.favorite_pairs, (
            f"Expected {pair!r} to be removed, but it is still present"
        )
    else:
        assert pair in state.current_settings.favorite_pairs, (
            f"Expected {pair!r} to be added, but it is absent"
        )

    state.settings_service.save_settings.assert_called_once()

    # --- Second toggle (reverse direction) ---
    state.toggle_favorite_pair(pair)

    # Membership should be back to original
    if was_present:
        assert pair in state.current_settings.favorite_pairs, (
            f"Expected {pair!r} to be re-added, but it is absent"
        )
    else:
        assert pair not in state.current_settings.favorite_pairs, (
            f"Expected {pair!r} to be re-removed, but it is still present"
        )

    assert state.settings_service.save_settings.call_count == 2, (
        f"Expected save_settings to be called exactly twice, "
        f"got {state.settings_service.save_settings.call_count}"
    )
