from abc import ABC, abstractmethod


class AppContextProvider(ABC):
    """Abstract base class for all application context providers."""

    @abstractmethod
    def get_context(self) -> dict:
        """Return a dict of context data for the AI system prompt.

        Returns:
            A plain dict with JSON-serializable values.
        """
        ...
