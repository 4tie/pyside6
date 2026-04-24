import json
import threading
from typing import AsyncGenerator, Iterator, Optional

from app.core.parsing.json_parser import parse_json_string

import requests

from app.core.ai.providers.provider_base import (
    AIProvider,
    AIResponse,
    ProviderHealth,
    StreamToken,
)
from app.core.utils.app_logger import get_logger

_log = get_logger("services.ollama_provider")


class OllamaProvider(AIProvider):
    """AI provider implementation for Ollama local inference server."""

    def __init__(self, base_url: str = "http://localhost:11434", timeout: int = 60) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session: Optional[requests.Session] = None
        self._cancel_flag = threading.Event()

    @property
    def provider_name(self) -> str:
        return "ollama"

    def _get_session(self) -> requests.Session:
        """Return the existing session or create a new one."""
        if self._session is None:
            self._session = requests.Session()
        return self._session

    def chat(self, messages: list[dict], model: str, **kwargs) -> AIResponse:
        """Send a blocking chat request to Ollama.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            model: Model identifier to use.
            **kwargs: Unused provider-specific options.

        Returns:
            AIResponse with the completed response content.

        Raises:
            ValueError: If the server returns a non-200 status code.
        """
        url = f"{self._base_url}/api/chat"
        payload = {"model": model, "messages": messages, "stream": False}
        _log.debug("chat() POST %s model=%s", url, model)

        response = self._get_session().post(url, json=payload, timeout=self._timeout)
        if response.status_code != 200:
            raise ValueError(f"Ollama chat failed: {response.status_code} {response.text}")

        resp = response.json()
        return AIResponse(
            content=resp["message"]["content"],
            model=resp.get("model", model),
            finish_reason=resp.get("done_reason", "stop"),
        )

    def stream_chat(self, messages: list[dict], model: str, **kwargs) -> Iterator[StreamToken]:
        """Send a streaming chat request to Ollama, yielding tokens as they arrive.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            model: Model identifier to use.
            **kwargs: Unused provider-specific options.

        Yields:
            StreamToken instances for each chunk; final token has finish_reason set.

        Raises:
            ValueError: If the server returns a non-200 status code.
        """
        url = f"{self._base_url}/api/chat"
        payload = {"model": model, "messages": messages, "stream": True}
        _log.debug("stream_chat() POST %s model=%s", url, model)

        response = self._get_session().post(url, json=payload, stream=True, timeout=self._timeout)
        if response.status_code != 200:
            raise ValueError(f"Ollama stream_chat failed: {response.status_code} {response.text}")

        for line in response.iter_lines():
            if self._cancel_flag.is_set():
                _log.info("stream_chat() cancelled")
                yield StreamToken(delta="", finish_reason="cancelled")
                return

            if not line:
                continue

            chunk = parse_json_string(line)
            done = chunk.get("done", False)
            yield StreamToken(
                delta=chunk["message"]["content"],
                finish_reason="stop" if done else None,
            )

            if done:
                return

    def list_models(self) -> list[str]:
        """Return available model names from the Ollama server.

        Returns:
            List of model name strings.

        Raises:
            ValueError: If the server returns a non-200 status code.
        """
        url = f"{self._base_url}/api/tags"
        _log.debug("list_models() GET %s", url)

        response = self._get_session().get(url, timeout=self._timeout)
        if response.status_code != 200:
            raise ValueError(f"Ollama list_models failed: {response.status_code} {response.text}")

        data = response.json()
        return [m["name"] for m in data["models"]]

    def health_check(self) -> ProviderHealth:
        """Check connectivity to the Ollama server and measure latency.

        Returns:
            ProviderHealth with ok=True and latency on success, ok=False on connection error.

        Raises:
            ValueError: If the server returns a non-200 status code.
        """
        url = f"{self._base_url}/api/tags"
        _log.debug("health_check() GET %s", url)

        start = time.monotonic()
        try:
            response = self._get_session().get(url, timeout=self._timeout)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            _log.warning("health_check() failed: %s", e)
            return ProviderHealth(ok=False, message=str(e))

        latency_ms = (time.monotonic() - start) * 1000

        if response.status_code != 200:
            raise ValueError(f"Ollama health_check failed: {response.status_code} {response.text}")

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
