# Feature: ai-chat-panel, Property 9: ToolExecutor returns ToolResult for any input
"""Property-based tests for ToolExecutor.

Uses Hypothesis to verify that execute() never raises and always returns
a ToolResult, with correct error/output values for all input cases.
"""
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.ai.tools.tool_executor import ToolExecutor, ToolResult
from app.core.ai.tools.tool_registry import ToolDefinition, ToolRegistry


# ---------------------------------------------------------------------------
# Property 9a: unregistered tool name → ToolResult.error == f"Tool not found: {tool_name}"
# Validates: Requirements 7.4, 7.5
# ---------------------------------------------------------------------------

@given(tool_name=st.text(min_size=1, max_size=50))
@settings(max_examples=100)
def test_property_9_unregistered_tool_returns_error(tool_name: str):
    # Feature: ai-chat-panel, Property 9: ToolExecutor returns ToolResult for any input
    # Validates: Requirements 7.4, 7.5
    registry = ToolRegistry()
    executor = ToolExecutor(registry)

    result = executor.execute(tool_name, {})

    assert isinstance(result, ToolResult)
    assert result.error == f"Tool not found: {tool_name}"


# ---------------------------------------------------------------------------
# Property 9b: registered tool that raises → ToolResult.error is set, no exception
# Validates: Requirements 7.6
# ---------------------------------------------------------------------------

@given(args=st.dictionaries(st.text(min_size=1, max_size=10), st.integers(), max_size=3))
@settings(max_examples=100)
def test_property_9_failing_tool_returns_error_no_exception(args: dict):
    # Feature: ai-chat-panel, Property 9: ToolExecutor returns ToolResult for any input
    # Validates: Requirements 7.6
    registry = ToolRegistry()
    registry.register(ToolDefinition(
        name="boom_tool",
        description="always raises",
        parameters_schema={},
        callable=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    ))
    executor = ToolExecutor(registry)

    result = executor.execute("boom_tool", args)

    assert isinstance(result, ToolResult)
    assert result.error == "boom"


# ---------------------------------------------------------------------------
# Property 9c: registered tool that succeeds → ToolResult.output matches return value
# Validates: Requirements 7.7
# ---------------------------------------------------------------------------

@given(
    return_value=st.one_of(st.integers(), st.text(), st.floats(allow_nan=False)),
    args=st.dictionaries(st.text(min_size=1, max_size=10), st.integers(), max_size=3),
)
@settings(max_examples=100)
def test_property_9_successful_tool_returns_output(return_value, args: dict):
    # Feature: ai-chat-panel, Property 9: ToolExecutor returns ToolResult for any input
    # Validates: Requirements 7.7
    registry = ToolRegistry()
    registry.register(ToolDefinition(
        name="ok_tool",
        description="always succeeds",
        parameters_schema={},
        callable=lambda **kwargs: return_value,
    ))
    executor = ToolExecutor(registry)

    result = executor.execute("ok_tool", args)

    assert isinstance(result, ToolResult)
    assert result.output == return_value
    assert result.error is None
