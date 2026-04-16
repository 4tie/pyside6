from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator, Optional

from app.core.utils.app_logger import get_logger

_log = get_logger("services.ai_provider")


@dataclass
class AIResponse:
    content: str
    model: str
    tool_calls: list = field(default_factory=list)
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


class AIProvider(ABC):
    """Abstract base class for all AI provider implementations."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the unique name of this provider."""
        ...

    @abstractmethod
    def chat(self, messages: list[dict], model: str, **kwargs) -> AIResponse:
        """Send a chat request and return a complete response.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            model: Model identifier to use for the request.
            **kwargs: Provider-specific options.

        Returns:
            AIResponse with the completed response.
        """
        ...

    @abstractmethod
    def stream_chat(self, messages: list[dict], model: str, **kwargs) -> Iterator[StreamToken]:
        """Send a chat request and yield streaming tokens.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            model: Model identifier to use for the request.
            **kwargs: Provider-specific options.

        Yields:
            StreamToken instances as they arrive.
        """
        ...

    @abstractmethod
    def list_models(self) -> list[str]:
        """Return a list of available model identifiers.

        Returns:
            List of model name strings.
        """
        ...

    @abstractmethod
    def health_check(self) -> ProviderHealth:
        """Check provider connectivity and return health status.

        Returns:
            ProviderHealth with ok status, message, and optional latency.
        """
        ...

    @abstractmethod
    def cancel_current_request(self) -> None:
        """Close the active HTTP session/connection to abort any in-progress request."""
        ...

    def get_model_capability(self, model: str) -> str:
        """Return Level_A, Level_B, or Level_C for the given model.

        Default implementation returns Level_B for all unknown models.

        Args:
            model: Model identifier string.

        Returns:
            Capability level string: 'Level_A', 'Level_B', or 'Level_C'.
        """
        return "Level_B"
