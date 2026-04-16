from app.core.ai.providers.ollama_provider import OllamaProvider
from app.core.ai.providers.openrouter_provider import OpenRouterProvider
from app.core.ai.providers.provider_base import AIProvider
from app.core.models.settings_models import AISettings


class ProviderFactory:
    """Factory for creating AI provider instances from settings."""

    @staticmethod
    def create(ai_settings: AISettings) -> AIProvider:
        """Instantiate and return the appropriate AIProvider for the given settings.

        Args:
            ai_settings: AI configuration containing provider selection and credentials.

        Returns:
            An AIProvider instance configured from ai_settings.

        Raises:
            ValueError: If ai_settings.provider is not a recognised provider name.
        """
        if ai_settings.provider == "ollama":
            return OllamaProvider(
                base_url=ai_settings.ollama_base_url,
                timeout=ai_settings.timeout_seconds,
            )
        if ai_settings.provider == "openrouter":
            return OpenRouterProvider(
                api_key=ai_settings.openrouter_api_key,
                timeout=ai_settings.timeout_seconds,
                free_only=ai_settings.openrouter_free_only,
            )
        raise ValueError(f"Unsupported provider: {ai_settings.provider!r}")
