from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.core.utils.app_logger import get_logger
from app.core.ai.tools.tool_registry import ToolRegistry

_log = get_logger("services.tool_executor")


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


class ToolExecutor:
    """Executes tools from a :class:`ToolRegistry` by name.

    Args:
        registry: The registry to look up tools from.
    """

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def execute(self, tool_name: str, arguments: dict) -> ToolResult:
        """Execute a registered tool by name with the given arguments.

        Args:
            tool_name: Name of the tool to execute.
            arguments: Keyword arguments to pass to the tool callable.

        Returns:
            A :class:`ToolResult` with the output on success, or with
            ``error`` set if the tool was not found or raised an exception.
        """
        tool_definition = self._registry.get(tool_name)

        if tool_definition is None:
            return ToolResult(
                tool_name=tool_name,
                output="",
                display_text="",
                error=f"Tool not found: {tool_name}",
            )

        try:
            result = tool_definition.callable(**arguments)
            return ToolResult(
                tool_name=tool_name,
                output=result,
                display_text=str(result),
            )
        except Exception as exc:
            _log.error("Tool '%s' raised an exception: %s", tool_name, exc)
            return ToolResult(
                tool_name=tool_name,
                output="",
                display_text="",
                error=str(exc),
            )
