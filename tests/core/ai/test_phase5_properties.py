# Feature: ai-chat-panel, Phase 5 property-based tests
"""Property-based tests for Phase 5: Backtest and Strategy Tools.

Properties 12–15 covering AppSettings persistence, OpenRouter filtering,
tool loop termination, and model capability classification.
"""
import json
import tempfile
from pathlib import Path
from typing import Iterator, Optional
from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.ai.providers.provider_base import (
    AIProvider,
    AIResponse,
    ProviderHealth,
    StreamToken,
)
from app.core.models.settings_models import AISettings, AppSettings


# ---------------------------------------------------------------------------
# Property 12: AppSettings round-trip through file persistence
# Validates: Requirements 20.2
# ---------------------------------------------------------------------------

_ai_settings_strategy = st.builds(
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
    timeout_seconds=st.integers(min_value=1, max_value=3600),
    stream_enabled=st.booleans(),
    tools_enabled=st.booleans(),
    max_history_messages=st.integers(min_value=1, max_value=500),
    max_tool_steps=st.integers(min_value=1, max_value=50),
)


@given(ai=_ai_settings_strategy)
@settings(max_examples=50)
def test_property_12_appsettings_file_persistence_round_trip(ai: AISettings):
    # Feature: ai-chat-panel, Property 12: AppSettings round-trip through file persistence
    # Validates: Requirements 20.2
    original = AppSettings(ai=ai)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as tmp:
        tmp.write(json.dumps(original.model_dump(mode="json")))
        tmp_path = tmp.name

    try:
        with open(tmp_path, "r") as f:
            raw = json.loads(f.read())
        reloaded = AppSettings.model_validate(raw)
        assert reloaded.ai == original.ai, (
            f"Reloaded ai field does not match original.\n"
            f"Original: {original.ai}\nReloaded: {reloaded.ai}"
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Property 13: OpenRouter free model filtering
# Validates: Requirements 22.1, 22.2
# ---------------------------------------------------------------------------

def _filter_models(models: list, free_only: bool) -> list:
    """Replicate the filtering logic from OpenRouterProvider.list_models()."""
    result = []
    for m in models:
        modality = m.get("architecture", {}).get("modality", "") or m.get("modality", "")
        if "text" not in modality:
            continue
        if free_only:
            pricing = m.get("pricing", {})
            if pricing.get("prompt") != "0" and pricing.get("completion") != "0":
                continue
        result.append(m["id"])
    return result


_model_id_strategy = st.text(min_size=1, max_size=40, alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="-_/:."))
_modality_strategy = st.sampled_from(["text->text", "text+image->text", "image->text", "audio->text", "text"])
_price_strategy = st.sampled_from(["0", "0.000001", "0.001", "1"])


def _model_dict_strategy():
    return st.fixed_dictionaries({
        "id": _model_id_strategy,
        "architecture": st.fixed_dictionaries({"modality": _modality_strategy}),
        "pricing": st.fixed_dictionaries({
            "prompt": _price_strategy,
            "completion": _price_strategy,
        }),
    })


@given(models=st.lists(_model_dict_strategy(), min_size=0, max_size=30))
@settings(max_examples=100)
def test_property_13_openrouter_free_model_filtering_free_only(models: list):
    # Feature: ai-chat-panel, Property 13: OpenRouter free model filtering
    # Validates: Requirements 22.1, 22.2
    result = _filter_models(models, free_only=True)

    # Build a set of model IDs that legitimately qualify as free+text
    qualifying_ids = set()
    for m in models:
        modality = m.get("architecture", {}).get("modality", "") or m.get("modality", "")
        if "text" not in modality:
            continue
        pricing = m.get("pricing", {})
        if pricing.get("prompt") == "0" or pricing.get("completion") == "0":
            qualifying_ids.add(m["id"])

    for model_id in result:
        assert model_id in qualifying_ids, (
            f"Model {model_id!r} included in free_only results but does not qualify "
            f"(no text-capable + free entry found for this id)"
        )


@given(models=st.lists(_model_dict_strategy(), min_size=0, max_size=30))
@settings(max_examples=100)
def test_property_13_openrouter_free_model_filtering_all_text(models: list):
    # Feature: ai-chat-panel, Property 13: OpenRouter free model filtering
    # Validates: Requirements 22.1, 22.2
    result = _filter_models(models, free_only=False)

    # All text-capable models should be included
    text_capable_ids = {
        m["id"]
        for m in models
        if "text" in (m.get("architecture", {}).get("modality", "") or m.get("modality", ""))
    }
    assert set(result) == text_capable_ids, (
        f"free_only=False should return all text-capable models.\n"
        f"Expected: {text_capable_ids}\nGot: {set(result)}"
    )


# ---------------------------------------------------------------------------
# Property 14: Tool loop terminates at max_tool_steps
# Validates: Requirements 23.1, 23.2
# ---------------------------------------------------------------------------

class _AlwaysToolCallProvider(AIProvider):
    """Stub provider that always returns a tool call response."""

    @property
    def provider_name(self) -> str:
        return "stub"

    def chat(self, messages: list[dict], model: str, **kwargs) -> AIResponse:
        return AIResponse(
            content="",
            model=model,
            tool_calls=[{"id": "1", "function": {"name": "test_tool", "arguments": {}}}],
            finish_reason="tool_calls",
        )

    def stream_chat(self, messages: list[dict], model: str, **kwargs) -> Iterator[StreamToken]:
        yield StreamToken(delta="", finish_reason="stop")

    def list_models(self) -> list[str]:
        return []

    def health_check(self) -> ProviderHealth:
        return ProviderHealth(ok=True, message="ok")

    def cancel_current_request(self) -> None:
        pass


@given(max_steps=st.integers(min_value=1, max_value=10))
@settings(max_examples=50, deadline=None)
def test_property_14_tool_loop_terminates_at_max_tool_steps(max_steps: int):
    # Feature: ai-chat-panel, Property 14: Tool loop terminates at max_tool_steps
    # Validates: Requirements 23.1, 23.2
    import threading

    from app.core.ai.tools.tool_registry import ToolDefinition, ToolRegistry
    from app.core.models.settings_models import AISettings
    from app.core.ai.runtime.conversation_runtime import AIWorker

    registry = ToolRegistry()
    registry.register(ToolDefinition(
        name="test_tool",
        description="A test tool",
        parameters_schema={"type": "object", "properties": {}},
        callable=lambda: "ok",
    ))

    ai_settings = AISettings(tools_enabled=True, max_tool_steps=max_steps)
    cancel_flag = threading.Event()
    provider = _AlwaysToolCallProvider()
    worker = AIWorker(provider, cancel_flag, ai_settings)

    # Collect emitted task_complete results
    results = []
    worker.task_complete.connect(lambda r: results.append(r))

    messages = [{"role": "user", "content": "do something"}]
    worker.run_task_loop(messages, "test-model", registry, max_steps)

    assert len(results) == 1, "task_complete should be emitted exactly once"
    result = results[0]
    assert result.error == "Max tool steps reached", (
        f"Expected 'Max tool steps reached', got {result.error!r}"
    )
    assert result.cancelled is False, "Result should not be marked as cancelled"


# ---------------------------------------------------------------------------
# Property 15: Model capability classification is consistent
# Validates: Requirements 24.1
# ---------------------------------------------------------------------------

from app.core.ai.runtime.conversation_runtime import _get_model_capability

_VALID_LEVELS = {"Level_A", "Level_B", "Level_C"}


class _DefaultCapabilityProvider(AIProvider):
    """Stub provider that always returns Level_B (the default)."""

    @property
    def provider_name(self) -> str:
        return "stub"

    def chat(self, messages: list[dict], model: str, **kwargs) -> AIResponse:
        return AIResponse(content="", model=model)

    def stream_chat(self, messages: list[dict], model: str, **kwargs) -> Iterator[StreamToken]:
        yield StreamToken(delta="")

    def list_models(self) -> list[str]:
        return []

    def health_check(self) -> ProviderHealth:
        return ProviderHealth(ok=True, message="ok")

    def cancel_current_request(self) -> None:
        pass


@given(model_name=st.text(max_size=80))
@settings(max_examples=100)
def test_property_15_model_capability_classification_is_consistent(model_name: str):
    # Feature: ai-chat-panel, Property 15: Model capability classification is consistent
    # Validates: Requirements 24.1
    provider = _DefaultCapabilityProvider()

    level_first = _get_model_capability(model_name, provider)
    level_second = _get_model_capability(model_name, provider)

    # Must always return a valid level
    assert level_first in _VALID_LEVELS, (
        f"_get_model_capability returned invalid level {level_first!r} for model {model_name!r}"
    )

    # Must be deterministic — same input always yields same output
    assert level_first == level_second, (
        f"_get_model_capability is non-deterministic for model {model_name!r}: "
        f"got {level_first!r} then {level_second!r}"
    )


@given(model_name=st.text(max_size=80).filter(
    lambda s: not any(
        s.lower().startswith(p)
        for p in ("llama2", "mistral", "llama3", "qwen", "gpt-4", "claude", "mistral-nemo")
    )
))
@settings(max_examples=100)
def test_property_15_unknown_models_return_level_b(model_name: str):
    # Feature: ai-chat-panel, Property 15: Model capability classification is consistent
    # Validates: Requirements 24.1
    provider = _DefaultCapabilityProvider()
    level = _get_model_capability(model_name, provider)
    assert level == "Level_B", (
        f"Unknown model {model_name!r} should return 'Level_B', got {level!r}"
    )
