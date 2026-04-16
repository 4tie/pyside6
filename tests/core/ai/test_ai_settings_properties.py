# Feature: ai-chat-panel, Property 1: AISettings serialization round-trip
"""Property-based tests for AISettings serialization.

Uses Hypothesis to verify correctness properties across arbitrary inputs.
"""
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.models.settings_models import AISettings


# ---------------------------------------------------------------------------
# Property 1: AISettings serialization round-trip
# Validates: Requirements 1.4, 20.1
# ---------------------------------------------------------------------------

@given(
    st.builds(
        AISettings,
        provider=st.text(
            max_size=20,
            alphabet=st.characters(whitelist_categories=("Ll",), whitelist_characters="_-"),
        ),
        ollama_base_url=st.text(min_size=1, max_size=50),
        openrouter_api_key=st.one_of(st.none(), st.text(max_size=50)),
        chat_model=st.text(max_size=50),
        task_model=st.text(max_size=50),
        routing_mode=st.sampled_from(["single_model", "dual_model"]),
        cloud_fallback_enabled=st.booleans(),
        openrouter_free_only=st.booleans(),
        timeout_seconds=st.integers(min_value=1, max_value=200),
        stream_enabled=st.booleans(),
        tools_enabled=st.booleans(),
        max_history_messages=st.integers(min_value=1, max_value=200),
        max_tool_steps=st.integers(min_value=1, max_value=200),
    )
)
@settings(max_examples=100)
def test_property_1_ai_settings_serialization_round_trip(original: AISettings):
    # Feature: ai-chat-panel, Property 1: AISettings serialization round-trip
    # Validates: Requirements 1.4, 20.1
    assert AISettings.model_validate(original.model_dump(mode="json")) == original


# ---------------------------------------------------------------------------
# Property 2: routing_mode validation rejects invalid values
# Feature: ai-chat-panel, Property 2: routing_mode validation rejects invalid values
# Validates: Requirements 1.2
# ---------------------------------------------------------------------------

import pytest
from pydantic import ValidationError


@given(st.text().filter(lambda v: v not in ("single_model", "dual_model")))
@settings(max_examples=100)
def test_property_2_routing_mode_rejects_invalid_values(invalid_value: str):
    # Feature: ai-chat-panel, Property 2: routing_mode validation rejects invalid values
    # Validates: Requirements 1.2
    with pytest.raises(ValidationError):
        AISettings(routing_mode=invalid_value)


@pytest.mark.parametrize("valid_value", ["single_model", "dual_model"])
def test_property_2_routing_mode_accepts_valid_values(valid_value: str):
    # Feature: ai-chat-panel, Property 2: routing_mode validation rejects invalid values
    # Validates: Requirements 1.2
    instance = AISettings(routing_mode=valid_value)
    assert instance.routing_mode == valid_value


# ---------------------------------------------------------------------------
# Property 3: AISettings partial JSON loading uses defaults
# Feature: ai-chat-panel, Property 3: AISettings partial JSON loading uses defaults
# Validates: Requirements 1.5
# ---------------------------------------------------------------------------

_AI_DEFAULTS = {
    "provider": "ollama",
    "ollama_base_url": "http://localhost:11434",
    "openrouter_api_key": None,
    "chat_model": "",
    "task_model": "",
    "routing_mode": "single_model",
    "cloud_fallback_enabled": False,
    "openrouter_free_only": True,
    "timeout_seconds": 60,
    "stream_enabled": True,
    "tools_enabled": False,
    "max_history_messages": 50,
    "max_tool_steps": 8,
}

_ALL_FIELD_STRATEGIES = {
    "provider": st.text(max_size=20),
    "ollama_base_url": st.text(min_size=1, max_size=50),
    "openrouter_api_key": st.one_of(st.none(), st.text(max_size=50)),
    "chat_model": st.text(max_size=50),
    "task_model": st.text(max_size=50),
    "routing_mode": st.sampled_from(["single_model", "dual_model"]),
    "cloud_fallback_enabled": st.booleans(),
    "openrouter_free_only": st.booleans(),
    "timeout_seconds": st.integers(min_value=1, max_value=3600),
    "stream_enabled": st.booleans(),
    "tools_enabled": st.booleans(),
    "max_history_messages": st.integers(min_value=1, max_value=500),
    "max_tool_steps": st.integers(min_value=1, max_value=50),
}


@given(
    included_keys=st.sets(
        st.sampled_from(sorted(_ALL_FIELD_STRATEGIES.keys())),
        min_size=1,
    ).flatmap(
        lambda keys: st.fixed_dictionaries({k: _ALL_FIELD_STRATEGIES[k] for k in keys})
    )
)
@settings(max_examples=100)
def test_property_3_partial_json_loading_uses_defaults(included_keys: dict):
    # Feature: ai-chat-panel, Property 3: AISettings partial JSON loading uses defaults
    # Validates: Requirements 1.5
    partial_dict = included_keys
    instance = AISettings.model_validate(partial_dict)

    for field_name, default_value in _AI_DEFAULTS.items():
        if field_name not in partial_dict:
            assert getattr(instance, field_name) == default_value, (
                f"Omitted field '{field_name}' should equal default {default_value!r}, "
                f"got {getattr(instance, field_name)!r}"
            )
