"""Property-based test for SettingsPage round-trip (P3).

Property P3: Settings Round-Trip — settings saved via new UI must produce
identical ``AppSettings`` JSON to the original settings.

Validates: Requirements 12.3, 1.2
"""
import tempfile
from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings as h_settings, HealthCheck
from hypothesis import strategies as st

from app.core.models.settings_models import AISettings, AppSettings, TerminalPreferences
from app.core.services.settings_service import SettingsService
from app.ui_v2.pages.settings_page import SettingsPage


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Printable text that won't confuse Qt widgets (no null bytes, reasonable length)
_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd", "Pc", "Pd"),
        whitelist_characters=" ._-/:",
    ),
    min_size=0,
    max_size=64,
)

_nonempty_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd", "Pc", "Pd"),
        whitelist_characters=" ._-/:",
    ),
    min_size=1,
    max_size=64,
)

# Optional path-like string (None or a non-empty string)
_opt_path = st.one_of(st.none(), _nonempty_text)

# Valid routing modes accepted by AISettings validator
_routing_mode = st.sampled_from(["single_model", "dual_model"])

# Valid AI providers shown in the combo box
_ai_provider = st.sampled_from(["ollama", "openrouter"])

# Font families present in the terminal panel combo
_font_family = st.sampled_from([
    "Courier", "Courier New", "Consolas", "Lucida Console",
    "Monospace", "DejaVu Sans Mono",
])


@st.composite
def app_settings_strategy(draw) -> AppSettings:
    """Generate varied AppSettings instances for round-trip testing."""
    venv_path = draw(_opt_path)
    user_data_path = draw(_opt_path)
    use_module_execution = draw(st.booleans())

    provider = draw(_ai_provider)
    chat_model = draw(_text)
    task_model = draw(_text)
    routing_mode = draw(_routing_mode)
    timeout_seconds = draw(st.integers(min_value=1, max_value=300))
    stream_enabled = draw(st.booleans())
    tools_enabled = draw(st.booleans())
    max_history_messages = draw(st.integers(min_value=1, max_value=500))
    max_tool_steps = draw(st.integers(min_value=1, max_value=50))
    openrouter_free_only = draw(st.booleans())

    font_family = draw(_font_family)
    font_size = draw(st.integers(min_value=6, max_value=32))

    ai = AISettings(
        provider=provider,
        chat_model=chat_model,
        task_model=task_model,
        routing_mode=routing_mode,
        timeout_seconds=timeout_seconds,
        stream_enabled=stream_enabled,
        tools_enabled=tools_enabled,
        max_history_messages=max_history_messages,
        max_tool_steps=max_tool_steps,
        openrouter_free_only=openrouter_free_only,
    )

    terminal_preferences = TerminalPreferences(
        font_family=font_family,
        font_size=font_size,
    )

    return AppSettings(
        venv_path=venv_path,
        user_data_path=user_data_path,
        use_module_execution=use_module_execution,
        ai=ai,
        terminal_preferences=terminal_preferences,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def settings_state():
    """Return a minimal mock SettingsState that satisfies SettingsPage.__init__."""
    state = MagicMock()
    state.current_settings = AppSettings()
    # settings_changed must support .connect() — MagicMock handles this
    state.settings_changed = MagicMock()
    state.settings_changed.connect = MagicMock()
    return state


# ---------------------------------------------------------------------------
# Property test
# ---------------------------------------------------------------------------


@given(generated=app_settings_strategy())
@h_settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_settings_page_round_trip(qtbot, settings_state, generated: AppSettings):
    """**Property P3: Settings Round-Trip**

    For any generated AppSettings, loading it into SettingsPage via
    ``_populate_panels`` and reading it back via ``_collect_settings``
    must produce identical values for all fields that the form handles.

    **Validates: Requirements 12.3, 1.2**
    """
    # Build a fresh SettingsState mock seeded with the generated settings
    state = MagicMock()
    state.current_settings = generated
    state.settings_changed = MagicMock()
    state.settings_changed.connect = MagicMock()

    page = SettingsPage(settings_state=state)
    qtbot.addWidget(page)

    # Load the generated settings into all panels
    page._current_settings = generated
    page._populate_panels(generated)

    # Collect them back out
    collected = page._collect_settings()

    # ── Paths panel ──────────────────────────────────────────────────
    assert collected.venv_path == generated.venv_path, (
        f"venv_path mismatch: {collected.venv_path!r} != {generated.venv_path!r}"
    )
    assert collected.user_data_path == generated.user_data_path, (
        f"user_data_path mismatch: {collected.user_data_path!r} != {generated.user_data_path!r}"
    )

    # ── Execution panel ──────────────────────────────────────────────
    assert collected.use_module_execution == generated.use_module_execution, (
        f"use_module_execution mismatch: {collected.use_module_execution!r} != "
        f"{generated.use_module_execution!r}"
    )

    # ── AI panel ─────────────────────────────────────────────────────
    assert collected.ai.provider == generated.ai.provider, (
        f"ai.provider mismatch: {collected.ai.provider!r} != {generated.ai.provider!r}"
    )
    assert collected.ai.chat_model == generated.ai.chat_model, (
        f"ai.chat_model mismatch: {collected.ai.chat_model!r} != {generated.ai.chat_model!r}"
    )
    assert collected.ai.task_model == generated.ai.task_model, (
        f"ai.task_model mismatch: {collected.ai.task_model!r} != {generated.ai.task_model!r}"
    )
    assert collected.ai.routing_mode == generated.ai.routing_mode, (
        f"ai.routing_mode mismatch: {collected.ai.routing_mode!r} != {generated.ai.routing_mode!r}"
    )
    assert collected.ai.timeout_seconds == generated.ai.timeout_seconds, (
        f"ai.timeout_seconds mismatch: {collected.ai.timeout_seconds!r} != "
        f"{generated.ai.timeout_seconds!r}"
    )
    assert collected.ai.stream_enabled == generated.ai.stream_enabled, (
        f"ai.stream_enabled mismatch: {collected.ai.stream_enabled!r} != "
        f"{generated.ai.stream_enabled!r}"
    )
    assert collected.ai.tools_enabled == generated.ai.tools_enabled, (
        f"ai.tools_enabled mismatch: {collected.ai.tools_enabled!r} != "
        f"{generated.ai.tools_enabled!r}"
    )
    assert collected.ai.max_history_messages == generated.ai.max_history_messages, (
        f"ai.max_history_messages mismatch: {collected.ai.max_history_messages!r} != "
        f"{generated.ai.max_history_messages!r}"
    )
    assert collected.ai.max_tool_steps == generated.ai.max_tool_steps, (
        f"ai.max_tool_steps mismatch: {collected.ai.max_tool_steps!r} != "
        f"{generated.ai.max_tool_steps!r}"
    )
    assert collected.ai.openrouter_free_only == generated.ai.openrouter_free_only, (
        f"ai.openrouter_free_only mismatch: {collected.ai.openrouter_free_only!r} != "
        f"{generated.ai.openrouter_free_only!r}"
    )

    # ── Terminal panel ────────────────────────────────────────────────
    assert collected.terminal_preferences.font_family == generated.terminal_preferences.font_family, (
        f"terminal_preferences.font_family mismatch: "
        f"{collected.terminal_preferences.font_family!r} != "
        f"{generated.terminal_preferences.font_family!r}"
    )
    assert collected.terminal_preferences.font_size == generated.terminal_preferences.font_size, (
        f"terminal_preferences.font_size mismatch: "
        f"{collected.terminal_preferences.font_size!r} != "
        f"{generated.terminal_preferences.font_size!r}"
    )


# ---------------------------------------------------------------------------
# Persistence round-trip: save → load via SettingsService
# ---------------------------------------------------------------------------


@given(generated=app_settings_strategy())
@h_settings(
    max_examples=30,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_settings_page_save_load_round_trip(
    qtbot, settings_state, generated: AppSettings
):
    """**Property P3 (persistence): Settings saved via SettingsPage and loaded
    via SettingsService.load_settings() must produce identical field values.**

    **Validates: Requirements 12.3, 1.2**
    """
    state = MagicMock()
    state.current_settings = generated
    state.settings_changed = MagicMock()
    state.settings_changed.connect = MagicMock()

    page = SettingsPage(settings_state=state)
    qtbot.addWidget(page)

    # Populate the form with the generated settings
    page._current_settings = generated
    page._populate_panels(generated)

    # Collect what the form would save
    collected = page._collect_settings()

    # Persist via a temporary SettingsService
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp_path = f.name

    svc = SettingsService(settings_file=tmp_path)
    svc.save_settings(collected)
    loaded = svc.load_settings()

    # ── Paths ─────────────────────────────────────────────────────────
    assert loaded.venv_path == collected.venv_path
    assert loaded.user_data_path == collected.user_data_path

    # ── Execution ─────────────────────────────────────────────────────
    assert loaded.use_module_execution == collected.use_module_execution

    # ── AI ────────────────────────────────────────────────────────────
    assert loaded.ai.provider == collected.ai.provider
    assert loaded.ai.chat_model == collected.ai.chat_model
    assert loaded.ai.task_model == collected.ai.task_model
    assert loaded.ai.routing_mode == collected.ai.routing_mode
    assert loaded.ai.timeout_seconds == collected.ai.timeout_seconds
    assert loaded.ai.stream_enabled == collected.ai.stream_enabled
    assert loaded.ai.tools_enabled == collected.ai.tools_enabled
    assert loaded.ai.max_history_messages == collected.ai.max_history_messages
    assert loaded.ai.max_tool_steps == collected.ai.max_tool_steps
    assert loaded.ai.openrouter_free_only == collected.ai.openrouter_free_only

    # ── Terminal ──────────────────────────────────────────────────────
    assert loaded.terminal_preferences.font_family == collected.terminal_preferences.font_family
    assert loaded.terminal_preferences.font_size == collected.terminal_preferences.font_size
