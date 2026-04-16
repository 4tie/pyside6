# Feature: ai-chat-panel, Property 5: ConversationRuntime model routing is correct
"""Property-based tests for ConversationRuntime model routing.

Uses Hypothesis to verify that the correct model is always passed to the provider
for all combinations of routing_mode and call type.

Validates: Requirements 6.3, 6.4, 6.8
"""
import sys
from unittest.mock import MagicMock, patch, call

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from PySide6.QtWidgets import QApplication

from app.core.ai.runtime.conversation_runtime import ConversationRuntime
from app.core.models.settings_models import AISettings

# Ensure a QApplication exists for QObject-based tests
_app = QApplication.instance() or QApplication(sys.argv)


# ---------------------------------------------------------------------------
# Property 5: ConversationRuntime model routing is correct
# Validates: Requirements 6.3, 6.4, 6.8
# ---------------------------------------------------------------------------

_model_name_strategy = st.text(
    min_size=1,
    max_size=20,
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="-_.:"),
)


@given(
    routing_mode=st.sampled_from(["single_model", "dual_model"]),
    chat_model=_model_name_strategy,
    task_model=_model_name_strategy,
)
@settings(max_examples=100)
def test_property_5_send_message_always_uses_chat_model(
    routing_mode: str,
    chat_model: str,
    task_model: str,
) -> None:
    # Feature: ai-chat-panel, Property 5: ConversationRuntime model routing is correct
    # Validates: Requirements 6.3, 6.4, 6.8
    """send_message always uses chat_model regardless of routing_mode."""
    ai_settings = AISettings(
        routing_mode=routing_mode,
        chat_model=chat_model,
        task_model=task_model,
    )

    captured_model: list[str] = []

    def fake_start_worker(provider, run_fn):
        # Create a mock worker and call run_fn to capture the model argument
        mock_worker = MagicMock()
        mock_worker.run_chat = lambda messages, model: captured_model.append(model)
        mock_worker.run_task_loop = lambda messages, model, registry, steps, schemas=None: captured_model.append(model)
        run_fn(mock_worker)

    mock_provider = MagicMock()

    with patch("app.core.ai.runtime.conversation_runtime.ProviderFactory") as mock_factory:
        mock_factory.create.return_value = mock_provider

        runtime = ConversationRuntime(ai_settings)

        with patch.object(runtime, "_start_worker", side_effect=fake_start_worker):
            runtime.send_message("hello")

    assert len(captured_model) == 1, "Expected exactly one model to be captured"
    assert captured_model[0] == chat_model, (
        f"send_message should always use chat_model='{chat_model}', "
        f"but got '{captured_model[0]}' with routing_mode='{routing_mode}'"
    )


@given(
    routing_mode=st.sampled_from(["single_model", "dual_model"]),
    chat_model=_model_name_strategy,
    task_model=_model_name_strategy,
)
@settings(max_examples=100)
def test_property_5_run_task_routing_by_mode(
    routing_mode: str,
    chat_model: str,
    task_model: str,
) -> None:
    # Feature: ai-chat-panel, Property 5: ConversationRuntime model routing is correct
    # Validates: Requirements 6.3, 6.4, 6.8
    """run_task uses task_model when routing_mode=='dual_model', else chat_model."""
    ai_settings = AISettings(
        routing_mode=routing_mode,
        chat_model=chat_model,
        task_model=task_model,
    )

    captured_model: list[str] = []

    def fake_start_worker(provider, run_fn):
        mock_worker = MagicMock()
        mock_worker.run_chat = lambda messages, model: captured_model.append(model)
        mock_worker.run_task_loop = lambda messages, model, registry, steps, schemas=None: captured_model.append(model)
        run_fn(mock_worker)

    mock_provider = MagicMock()

    with patch("app.core.ai.runtime.conversation_runtime.ProviderFactory") as mock_factory:
        mock_factory.create.return_value = mock_provider

        runtime = ConversationRuntime(ai_settings)

        with patch.object(runtime, "_start_worker", side_effect=fake_start_worker):
            runtime.run_task("do something")

    assert len(captured_model) == 1, "Expected exactly one model to be captured"

    expected_model = task_model if routing_mode == "dual_model" else chat_model
    assert captured_model[0] == expected_model, (
        f"run_task with routing_mode='{routing_mode}' should use model='{expected_model}', "
        f"but got '{captured_model[0]}'"
    )


# ---------------------------------------------------------------------------
# Property 6: History trimming preserves system message and respects limit
# Feature: ai-chat-panel, Property 6: History trimming preserves system message and respects limit
# Validates: Requirements 6.2
# ---------------------------------------------------------------------------

_non_system_role_strategy = st.sampled_from(["user", "assistant"])
_message_content_strategy = st.text(min_size=1, max_size=50)


@given(
    max_history_messages=st.integers(min_value=2, max_value=20),
    messages=st.lists(
        st.fixed_dictionaries({
            "role": _non_system_role_strategy,
            "content": _message_content_strategy,
        }),
        min_size=1,
    ).filter(lambda msgs: True),  # length check done dynamically after knowing max_history_messages
)
@settings(max_examples=100)
def test_property_6_history_trimming_preserves_system_message(
    max_history_messages: int,
    messages: list,
) -> None:
    # Feature: ai-chat-panel, Property 6: History trimming preserves system message and respects limit
    # Validates: Requirements 6.2
    """History trimming always keeps system message first and respects the limit."""
    # Ensure the message list exceeds the limit (system + messages > max_history_messages)
    # We need at least max_history_messages non-system messages so total exceeds limit
    if len(messages) < max_history_messages:
        # Pad with extra user messages to exceed the limit
        extra = max_history_messages - len(messages) + 1
        messages = messages + [{"role": "user", "content": f"extra {i}"} for i in range(extra)]

    ai_settings = AISettings(max_history_messages=max_history_messages)
    runtime = ConversationRuntime(ai_settings)

    system_msg = {"role": "system", "content": "You are a helpful assistant."}
    runtime._history = [system_msg] + list(messages)

    runtime._trim_history()

    # Assert 1: system message is always first
    assert runtime._history[0]["role"] == "system", (
        "System message must always be the first message after trimming"
    )

    # Assert 2: total count never exceeds the limit
    assert len(runtime._history) <= max_history_messages, (
        f"History length {len(runtime._history)} exceeds max_history_messages={max_history_messages}"
    )

    # Assert 3: most recent messages are retained
    # The last (max_history_messages - 1) non-system messages should be present
    retained_count = max_history_messages - 1  # one slot taken by system message
    expected_tail = messages[-retained_count:] if retained_count <= len(messages) else messages
    actual_non_system = runtime._history[1:]

    for msg in expected_tail:
        assert msg in actual_non_system, (
            f"Expected recent message {msg!r} to be retained after trimming, "
            f"but it was not found in {actual_non_system!r}"
        )


# ---------------------------------------------------------------------------
# Property 7: clear_history leaves only the system message
# Feature: ai-chat-panel, Property 7: clear_history leaves only the system message
# Validates: Requirements 6.9
# ---------------------------------------------------------------------------

_role_strategy = st.sampled_from(["user", "assistant", "tool", "system"])


@given(
    messages=st.lists(
        st.fixed_dictionaries({
            "role": _role_strategy,
            "content": _message_content_strategy,
        }),
        min_size=0,
        max_size=20,
    ),
)
@settings(max_examples=100)
def test_property_7_clear_history_leaves_only_system_message(
    messages: list,
) -> None:
    # Feature: ai-chat-panel, Property 7: clear_history leaves only the system message
    # Validates: Requirements 6.9
    """For any history state, clear_history() leaves exactly one system message."""
    ai_settings = AISettings()
    runtime = ConversationRuntime(ai_settings)

    # Build history: ensure at least one system message is present
    system_msg = {"role": "system", "content": "You are a helpful assistant."}
    runtime._history = [system_msg] + list(messages)

    runtime.clear_history()

    # Assert 1: exactly one message remains
    assert len(runtime._history) == 1, (
        f"Expected exactly 1 message after clear_history(), got {len(runtime._history)}"
    )

    # Assert 2: the remaining message is the system message
    assert runtime._history[0]["role"] == "system", (
        f"Expected remaining message to have role='system', "
        f"got role='{runtime._history[0]['role']}'"
    )
