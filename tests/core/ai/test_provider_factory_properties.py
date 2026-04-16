# Feature: ai-chat-panel, Property 4: ProviderFactory raises ValueError for unknown providers
"""Property-based tests for ProviderFactory provider validation.

Uses Hypothesis to verify correctness properties across arbitrary inputs.
"""
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.ai.providers.ollama_provider import OllamaProvider
from app.core.ai.providers.openrouter_provider import OpenRouterProvider
from app.core.ai.providers.provider_factory import ProviderFactory
from app.core.models.settings_models import AISettings


# ---------------------------------------------------------------------------
# Property 4: ProviderFactory raises ValueError for unknown providers
# Validates: Requirements 5.1, 5.2, 5.3, 5.4
# ---------------------------------------------------------------------------

@given(st.text().filter(lambda v: v not in ("ollama", "openrouter")))
@settings(max_examples=100)
def test_property_4_provider_factory_raises_for_unknown_providers(invalid_value: str):
    # Feature: ai-chat-panel, Property 4: ProviderFactory raises ValueError for unknown providers
    # Validates: Requirements 5.1, 5.2, 5.3, 5.4
    ai_settings = AISettings.model_construct(
        provider=invalid_value,
        ollama_base_url="http://localhost:11434",
        openrouter_api_key=None,
        chat_model="",
        task_model="",
        routing_mode="single_model",
        cloud_fallback_enabled=False,
        openrouter_free_only=True,
        timeout_seconds=60,
        stream_enabled=True,
        tools_enabled=False,
        max_history_messages=50,
        max_tool_steps=8,
    )
    with pytest.raises(ValueError):
        ProviderFactory.create(ai_settings)


@pytest.mark.parametrize(
    "provider_value, expected_type",
    [
        ("ollama", OllamaProvider),
        ("openrouter", OpenRouterProvider),
    ],
)
def test_property_4_provider_factory_returns_correct_type(provider_value: str, expected_type: type):
    # Feature: ai-chat-panel, Property 4: ProviderFactory raises ValueError for unknown providers
    # Validates: Requirements 5.1, 5.2, 5.3, 5.4
    ai_settings = AISettings(provider=provider_value)
    result = ProviderFactory.create(ai_settings)
    assert isinstance(result, expected_type)
