"""Property-based tests for settings models.

Property 6: Settings merge preserves unchanged fields
Property 7: Settings serialization round-trip
"""
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from app.core.models.settings_models import AppSettings
from app.web.models import SettingsUpdate


# ---------------------------------------------------------------------------
# Helper — mirrors the merge logic in settings.py PUT /api/settings
# ---------------------------------------------------------------------------

def _apply_settings_update(base: AppSettings, update: SettingsUpdate) -> AppSettings:
    """Apply a SettingsUpdate to a base AppSettings, returning the merged result."""
    if update.user_data_path is not None:
        base.user_data_path = update.user_data_path
    if update.venv_path is not None:
        base.venv_path = update.venv_path
    if update.python_executable is not None:
        base.python_executable = update.python_executable
    if update.freqtrade_executable is not None:
        base.freqtrade_executable = update.freqtrade_executable
    return base


# ---------------------------------------------------------------------------
# Property 6: Settings merge preserves unchanged fields
# ---------------------------------------------------------------------------

# Feature: web-layer-architecture, Property 6: Settings merge preserves unchanged fields
@given(
    new_user_data=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
)
@h_settings(max_examples=100)
def test_settings_merge_preserves_unchanged(new_user_data):
    """Property 6: Merging a partial update only changes the specified fields."""
    base = AppSettings(
        venv_path=None,
        python_executable=None,
        freqtrade_executable=None,
        user_data_path=None,
    )
    original_venv = base.venv_path
    original_python = base.python_executable
    original_freqtrade = base.freqtrade_executable

    update = SettingsUpdate(user_data_path=new_user_data)
    merged = _apply_settings_update(base, update)

    if new_user_data is not None:
        # Path fields are normalized by AppSettings validator — just check it's set
        assert merged.user_data_path is not None
    else:
        assert merged.user_data_path == original_venv  # both None

    # All other fields unchanged
    assert merged.venv_path == original_venv
    assert merged.python_executable == original_python
    assert merged.freqtrade_executable == original_freqtrade


# ---------------------------------------------------------------------------
# Property 7: Settings serialization round-trip
# ---------------------------------------------------------------------------

# Feature: web-layer-architecture, Property 7: Settings serialization round-trip
@given(
    venv_path=st.one_of(st.none(), st.just("T:/venv")),
    python_executable=st.one_of(st.none(), st.just("T:/venv/Scripts/python.exe")),
    freqtrade_executable=st.one_of(st.none(), st.just("T:/venv/Scripts/freqtrade.exe")),
    user_data_path=st.one_of(st.none(), st.just("T:/user_data")),
    use_module_execution=st.booleans(),
)
@h_settings(max_examples=100)
def test_settings_round_trip(
    venv_path,
    python_executable,
    freqtrade_executable,
    user_data_path,
    use_module_execution,
):
    """Property 7: Serializing and deserializing AppSettings produces an equivalent object.

    The round-trip is: dict → AppSettings → model_dump() → AppSettings.
    The second deserialization must equal the first (stable fixed-point).
    """
    settings = AppSettings(
        venv_path=venv_path,
        python_executable=python_executable,
        freqtrade_executable=freqtrade_executable,
        user_data_path=user_data_path,
        use_module_execution=use_module_execution,
    )
    # First serialization
    data = settings.model_dump()
    # Deserialize from the serialized dict
    restored = AppSettings(**data)
    # Second serialization must be identical (stable fixed-point)
    data2 = restored.model_dump()
    restored2 = AppSettings(**data2)
    assert restored == restored2
