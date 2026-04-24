from __future__ import annotations

from typing import Callable

from app.core.utils.app_logger import get_logger
from app.core.models.ai_models import ToolDefinition

_log = get_logger("services.tool_registry")


class ToolRegistry:
    """Registry that stores and exposes :class:`ToolDefinition` instances.

    Tools are keyed by name and can be retrieved individually or as a
    list of OpenAI-compatible function-calling schema dicts.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        """Register a tool definition.

        Args:
            definition: The :class:`ToolDefinition` to register.

        Raises:
            ValueError: If ``definition.name`` is empty or
                ``definition.callable`` is not callable.
        """
        if not definition.name:
            raise ValueError("ToolDefinition.name must be a non-empty string")
        if not callable(definition.callable):
            raise ValueError(
                f"ToolDefinition.callable for '{definition.name}' must be callable"
            )
        _log.debug("Registering tool: %s", definition.name)
        self._tools[definition.name] = definition

    def get_schema_list(self) -> list[dict]:
        """Return all tools as OpenAI function-calling schema dicts.

        Returns:
            List of dicts in the format expected by the OpenAI ``tools`` parameter.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters_schema,
                },
            }
            for t in self._tools.values()
        ]

    def get(self, name: str) -> Optional[ToolDefinition]:
        """Look up a tool by name.

        Args:
            name: The tool name to look up.

        Returns:
            The :class:`ToolDefinition` if found, otherwise ``None``.
        """
        return self._tools.get(name)
