import json
import threading
import time
from typing import Iterator, Optional

import requests

from app.core.ai.providers.provider_base import (
    AIProvider,
    AIResponse,
    ProviderHealth,
    StreamToken,
)
from app.core.utils.app_logger import get_logger

_log = get_logger("services.openrouter_provider")

_OPENROUTER_BASE = "https://openrouter.ai/api/v1"

# Model modality types considered text-capable
_TEXT_MODALITIES = {"text", "text->text", "text+image->text"}


class OpenRouterProvider(AIProvider):
    """AI provider implementation for the OpenRouter API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: int = 60,
        free_only: bool = True,
    ) -> None:
        self._api_key = api_key
        self._timeout = timeout
        self._free_only = free_only
        self._session: Optional[requests.Session] = None
        self._cancel_flag = threading.Event()

    @property
    def provider_name(self) -> str:
        return "openrouter"

    def _get_session(self) -> requests.Session:
        """Return the existing session or create a new one with auth headers."""
        if self._session is None:
            session = requests.Session()
            if self._api_key:
                session.headers.update({"Authorization": f"Bearer {self._api_key}"})
            self._session = session
        return self._session

    def chat(self, messages: list[dict], model: str, **kwargs) -> AIResponse:
        """Send a blocking chat request to OpenRouter.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            model: Model identifier to use.
            **kwargs: Unused provider-specific options.

        Returns:
            AIResponse with the completed response content.

        Raises:
            ValueError: If the server returns a non-200 status code.
        """
        url = f"{_OPENROUTER_BASE}/chat/completions"
        payload = {"model": model, "messages": messages}
        _log.debug("chat() POST %s model=%s", url, model)

        response = self._get_session().post(url, json=payload, timeout=self._timeout)
        if response.status_code != 200:
            raise ValueError(f"OpenRouter chat failed: {response.status_code} {response.text}")

        resp = response.json()
        return AIResponse(
            content=resp["choices"][0]["message"]["content"],
            model=resp.get("model", model),
            finish_reason=resp["choices"][0].get("finish_reason", "stop"),
            usage=resp.get("usage"),
        )

    def stream_chat(self, messages: list[dict], model: str, **kwargs) -> Iterator[StreamToken]:
        """Send a streaming chat request to OpenRouter, yielding tokens as they arrive.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            model: Model identifier to use.
            **kwargs: Unused provider-specific options.

        Yields:
            StreamToken instances for each chunk; cancelled token if request is cancelled.

        Raises:
            ValueError: If the server returns a non-200 status code.
        """
        url = f"{_OPENROUTER_BASE}/chat/completions"
        payload = {"model": model, "messages": messages, "stream": True}
        _log.debug("stream_chat() POST %s model=%s", url, model)

        response = self._get_session().post(url, json=payload, stream=True, timeout=self._timeout)
        if response.status_code != 200:
            raise ValueError(f"OpenRouter stream_chat failed: {response.status_code} {response.text}")

        for line in response.iter_lines():
            if self._cancel_flag.is_set():
                _log.info("stream_chat() cancelled")
                yield StreamToken(delta="", finish_reason="cancelled")
                return

            if not line:
                continue

            # SSE lines are prefixed with "data: "
            if isinstance(line, bytes):
                line = line.decode("utf-8")

            if not line.startswith("data: "):
                continue

            data = line[len("data: "):]
            if data.strip() == "[DONE]":
                return

            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                _log.warning("stream_chat() failed to parse SSE line: %s", data)
                continue

            choice = chunk["choices"][0]
            yield StreamToken(
                delta=choice["delta"].get("content", ""),
                finish_reason=choice.get("finish_reason"),
            )

    def list_models(self) -> list[str]:
        """Return available text-capable model IDs from OpenRouter.

        Filters to free models when ``free_only`` is True.

        Returns:
            List of model id strings.

        Raises:
            ValueError: If the server returns a non-200 status code.
        """
        url = f"{_OPENROUTER_BASE}/models"
        _log.debug("list_models() GET %s", url)

        response = self._get_session().get(url, timeout=self._timeout)
        if response.status_code != 200:
            raise ValueError(f"OpenRouter list_models failed: {response.status_code} {response.text}")

        data = response.json()
        models = data.get("data", [])

        result = []
        for m in models:
            # Filter to text-capable models by checking modality field
            modality = m.get("architecture", {}).get("modality", "") or m.get("modality", "")
            if not any(t in modality for t in ("text",)):
                continue

            if self._free_only:
                pricing = m.get("pricing", {})
                prompt_price = pricing.get("prompt", "1")
                completion_price = pricing.get("completion", "1")
                if prompt_price != "0" and completion_price != "0":
                    continue

            result.append(m["id"])

        return result

    def health_check(self) -> ProviderHealth:
        """Check connectivity to OpenRouter and return health status.

        Returns immediately with ok=False if no API key is configured,
        without making any network request.

        Returns:
            ProviderHealth with ok=True and latency on success, ok=False otherwise.
        """
        if not self._api_key:
            return ProviderHealth(ok=False, message="API key not configured")

        url = f"{_OPENROUTER_BASE}/models"
        _log.debug("health_check() GET %s", url)

        start = time.monotonic()
        try:
            response = self._get_session().get(url, timeout=self._timeout)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            _log.warning("health_check() failed: %s", e)
            return ProviderHealth(ok=False, message=str(e))

        latency_ms = (time.monotonic() - start) * 1000

        if response.status_code != 200:
            return ProviderHealth(
                ok=False,
                message=f"HTTP {response.status_code}: {response.text}",
            )

        return ProviderHealth(ok=True, message="Connected", latency_ms=latency_ms)

    def cancel_current_request(self) -> None:
        """Signal cancellation and close the active HTTP session.

        The next call to any method will create a fresh session.
        """
        _log.info("cancel_current_request() called")
        self._cancel_flag.set()
        if self._session is not None:
            self._session.close()
            self._session = None
        self._cancel_flag.clear()
