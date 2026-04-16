# Feature: ai-chat-panel, Property 8: ToolRegistry registration validates name and callable
"""Property-based tests for ToolRegistry registration validation.

Uses Hypothesis to verify correctness properties across arbitrary inputs.
"""
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.ai.tools.tool_registry import ToolDefinition, ToolRegistry


# ---------------------------------------------------------------------------
# Property 8a: empty name → ValueError
# Validates: Requirements 7.2
# ---------------------------------------------------------------------------

@given(
    name=st.just(""),
    fn=st.just(lambda: None),
)
@settings(max_examples=100)
def test_property_8_empty_name_raises_value_error(name: str, fn):
    # Feature: ai-chat-panel, Property 8: ToolRegistry registration validates name and callable
    # Validates: Requirements 7.2
    registry = ToolRegistry()
    definition = ToolDefinition(
        name=name,
        description="test",
        parameters_schema={},
        callable=fn,
    )
    with pytest.raises(ValueError):
        registry.register(definition)


# ---------------------------------------------------------------------------
# Property 8b: non-callable → ValueError
# Validates: Requirements 7.2
# ---------------------------------------------------------------------------

@given(
    name=st.text(min_size=1, max_size=20),
    non_callable=st.one_of(st.integers(), st.text(), st.none()),
)
@settings(max_examples=100)
def test_property_8_non_callable_raises_value_error(name: str, non_callable):
    # Feature: ai-chat-panel, Property 8: ToolRegistry registration validates name and callable
    # Validates: Requirements 7.2
    registry = ToolRegistry()
    definition = ToolDefinition(
        name=name,
        description="test",
        parameters_schema={},
        callable=non_callable,
    )
    with pytest.raises(ValueError):
        registry.register(definition)


# ---------------------------------------------------------------------------
# Property 8c (parametrized): valid definition → registration succeeds
# Validates: Requirements 7.2
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,fn", [
    ("my_tool", lambda: None),
    ("get_price", lambda x: x),
    ("run_backtest", print),
])
def test_property_8_valid_definition_registers_successfully(name: str, fn):
    # Feature: ai-chat-panel, Property 8: ToolRegistry registration validates name and callable
    # Validates: Requirements 7.2
    registry = ToolRegistry()
    definition = ToolDefinition(
        name=name,
        description="a valid tool",
        parameters_schema={},
        callable=fn,
    )
    registry.register(definition)
    assert registry.get(name) is definition
