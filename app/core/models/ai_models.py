"""AI-related data models.

These dataclasses represent AI tools, results, and related structures.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Iterator, List, Optional


@dataclass
class ToolDefinition:
    """Describes a single callable tool exposed to the AI model.

    Attributes:
        name: Unique tool name used in OpenAI function-calling schema.
        description: Human-readable description of what the tool does.
        parameters_schema: JSON Schema dict describing the tool's parameters.
        callable: The Python callable that implements the tool.
    """

    name: str
    description: str
    parameters_schema: dict
    callable: Callable


@dataclass
class ToolResult:
    """Result of a tool execution.

    Attributes:
        tool_name: Name of the tool that was executed.
        output: Raw output returned by the tool callable.
        display_text: Human-readable string representation of the output.
        error: Error message if execution failed, otherwise ``None``.
    """

    tool_name: str
    output: Any
    display_text: str = ""
    error: Optional[str] = None


@dataclass
class AIResponse:
    content: str
    model: str
    tool_calls: List = field(default_factory=list)
    finish_reason: str = ""
    usage: Optional[dict] = None


@dataclass
class ProviderHealth:
    ok: bool
    message: str
    latency_ms: Optional[float] = None


@dataclass
class StreamToken:
    delta: str
    finish_reason: Optional[str] = None


@dataclass
class TaskRunResult:
    """Result returned by ConversationRuntime.run_task().

    Attributes:
        messages: Full message history at the time the task completed.
        tool_steps: List of ToolResult objects from each tool call iteration.
        final_response: The last assistant response text, or None if cancelled/errored.
        cancelled: True if the task was cancelled before completion.
        error: Error message string if the task failed, else None.
    """

    messages: List = field(default_factory=list)
    tool_steps: List = field(default_factory=list)
    final_response: Optional[str] = None
    cancelled: bool = False
    error: Optional[str] = None


@dataclass
class AgentPolicy:
    """Policy configuration governing agent behaviour, tool usage, and safety rules.

    Attributes:
        system_prompt: The system-level instruction given to the AI model.
        tool_usage_policy: Guidance on when and how the agent should invoke tools.
        safety_rules: List of rules the agent must enforce in every response.
    """

    system_prompt: str
    tool_usage_policy: str
    safety_rules: List[str] = field(default_factory=list)


@dataclass
class EventRecord:
    timestamp: datetime
    event_type: str
    source: str
    payload: dict
