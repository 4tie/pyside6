import threading
import time
from typing import Iterator, Optional

from app.core.parsing.json_parser import parse_json_string

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

# HTTP status codes that should trigger key rotation
_ROTATION_STATUS_CODES = {401, 402, 429}

# Model modality types considered text-capable
_TEXT_MODALITIES = {"text", "text->text", "text+image->text"}


class OpenRouterProvider(AIProvider):
    """AI provider implementation for the OpenRouter API with key rotation support."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_keys: Optional[list[str]] = None,
        timeout: int = 60,
        free_only: bool = True,
    ) -> None:
        # Build deduplicated, non-empty keys list
        combined: list[str] = []
        if api_keys:
            combined.extend(k for k in api_keys if k and k.strip())
        if api_key and api_key.strip() and api_key not in combined:
            combined.append(api_key)
        self._api_keys: list[str] = list(dict.fromkeys(combined))  # preserve order, dedupe

        # Back-compat single-key property
        self._api_key: Optional[str] = self._api_keys[0] if self._api_keys else None

        self._current_key_index: int = 0
        self._timeout = timeout
        self._free_only = free_only
        self._session: Optional[requests.Session] = None
        self._cancel_flag = threading.Event()

    @property
    def provider_name(self) -> str:
        return "openrouter"

    # ------------------------------------------------------------------
    # Key rotation helpers
    # ------------------------------------------------------------------

    def _get_current_key(self) -> Optional[str]:
        """Return the key at the current rotation index, or None if no keys."""
        if not self._api_keys:
            return None
        return self._api_keys[self._current_key_index]

    def _rotate_key(self) -> bool:
        """Advance to the next key.

        Returns:
            True if a new key is now active, False if we have exhausted all keys.
        """
        if not self._api_keys:
            return False
        old_idx = self._current_key_index
        next_idx = old_idx + 1
        if next_idx >= len(self._api_keys):
            return False
        total = len(self._api_keys)
        _log.info(
            "OpenRouter key %d/%d failed (%s...), rotating to next key",
            old_idx + 1,
            total,
            self._api_keys[old_idx][:8],
        )
        self._current_key_index = next_idx
        # Close old session so the next _get_session() call rebuilds with the new key
        if self._session is not None:
            self._session.close()
            self._session = None
        return True

    def _reset_key_index(self) -> None:
        """Reset rotation back to the first key (called after a successful request)."""
        self._current_key_index = 0

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def _get_session(self) -> requests.Session:
        """Return (or create) a session bearing the current key's Authorization header."""
        if self._session is None:
            session = requests.Session()
            current_key = self._get_current_key()
            if current_key:
                session.headers.update({"Authorization": f"Bearer {current_key}"})
            self._session = session
        return self._session

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chat(self, messages: list[dict], model: str, **kwargs) -> AIResponse:
        """Send a blocking chat request to OpenRouter, rotating keys on auth/rate errors.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            model: Model identifier to use.
            **kwargs: Unused provider-specific options.

        Returns:
            AIResponse with the completed response content.

        Raises:
            ValueError: If all keys are exhausted or the server returns a non-200 status.
        """
        url = f"{_OPENROUTER_BASE}/chat/completions"
        payload = {"model": model, "messages": messages}
        max_attempts = max(1, len(self._api_keys))

        for attempt in range(max_attempts):
            _log.debug("chat() POST %s model=%s attempt=%d", url, model, attempt + 1)
            try:
                response = self._get_session().post(url, json=payload, timeout=self._timeout)
            except requests.exceptions.ConnectionError as exc:
                _log.warning("chat() ConnectionError on attempt %d: %s", attempt + 1, exc)
                if not self._rotate_key():
                    raise ValueError(f"OpenRouter chat connection failed: {exc}") from exc
                continue

            if response.status_code == 200:
                resp = response.json()
                return AIResponse(
                    content=resp["choices"][0]["message"]["content"],
                    model=resp.get("model", model),
                    finish_reason=resp["choices"][0].get("finish_reason", "stop"),
                    usage=resp.get("usage"),
                )

            if response.status_code in _ROTATION_STATUS_CODES:
                _log.warning(
                    "chat() HTTP %d on attempt %d — triggering key rotation",
                    response.status_code,
                    attempt + 1,
                )
                if not self._rotate_key():
                    raise ValueError(
                        f"OpenRouter chat failed: {response.status_code} {response.text}"
                    )
                continue

            raise ValueError(f"OpenRouter chat failed: {response.status_code} {response.text}")

        raise ValueError("OpenRouter chat failed: all API keys exhausted")

    def stream_chat(self, messages: list[dict], model: str, **kwargs) -> Iterator[StreamToken]:
        """Send a streaming chat request, rotating keys on auth/rate errors.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            model: Model identifier to use.
            **kwargs: Unused provider-specific options.

        Yields:
            StreamToken instances for each chunk; cancelled token if request is cancelled.

        Raises:
            ValueError: If all keys are exhausted or the server returns a non-200 status.
        """
        url = f"{_OPENROUTER_BASE}/chat/completions"
        payload = {"model": model, "messages": messages, "stream": True}
        max_attempts = max(1, len(self._api_keys))

        for attempt in range(max_attempts):
            _log.debug("stream_chat() POST %s model=%s attempt=%d", url, model, attempt + 1)
            try:
                response = self._get_session().post(
                    url, json=payload, stream=True, timeout=self._timeout
                )
            except requests.exceptions.ConnectionError as exc:
                _log.warning("stream_chat() ConnectionError on attempt %d: %s", attempt + 1, exc)
                if not self._rotate_key():
                    raise ValueError(f"OpenRouter stream_chat connection failed: {exc}") from exc
                continue

            if response.status_code in _ROTATION_STATUS_CODES:
                _log.warning(
                    "stream_chat() HTTP %d on attempt %d — triggering key rotation",
                    response.status_code,
                    attempt + 1,
                )
                if not self._rotate_key():
                    raise ValueError(
                        f"OpenRouter stream_chat failed: {response.status_code} {response.text}"
                    )
                continue

            if response.status_code != 200:
                raise ValueError(
                    f"OpenRouter stream_chat failed: {response.status_code} {response.text}"
                )

            # Successful response — stream tokens
            yield from self._iter_stream(response)
            return

        raise ValueError("OpenRouter stream_chat failed: all API keys exhausted")

    def _iter_stream(self, response: requests.Response) -> Iterator[StreamToken]:
        """Iterate SSE lines from a streaming response and yield StreamToken objects."""
        for line in response.iter_lines():
            if self._cancel_flag.is_set():
                _log.info("stream_chat() cancelled")
                yield StreamToken(delta="", finish_reason="cancelled")
                return

            if not line:
                continue

            if isinstance(line, bytes):
                line = line.decode("utf-8")

            if not line.startswith("data: "):
                continue

            data = line[len("data: "):]
            if data.strip() == "[DONE]":
                return

            try:
                chunk = parse_json_string(data)
            except Exception:
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

        Returns immediately with ok=False if no API key is configured.

        Returns:
            ProviderHealth with ok=True and latency on success, ok=False otherwise.
        """
        if not self._get_current_key():
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
        """Signal cancellation and close the active HTTP session."""
        _log.info("cancel_current_request() called")
        self._cancel_flag.set()
        if self._session is not None:
            self._session.close()
            self._session = None
        self._cancel_flag.clear()
