from __future__ import annotations

from typing import Any, Optional

from app.core.utils.app_logger import get_logger
from app.core.ai.tools.tool_registry import ToolRegistry
from app.core.models.ai_models import ToolResult

_log = get_logger("services.tool_executor")


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
