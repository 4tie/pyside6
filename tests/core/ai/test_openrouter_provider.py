"""Unit tests for OpenRouterProvider.

Validates: Requirements 4.4, 4.6
"""

import logging
import unittest
from unittest.mock import MagicMock, patch

from app.core.ai.providers.openrouter_provider import OpenRouterProvider
from app.core.ai.providers.provider_base import ProviderHealth

_OPENROUTER_CHAT_RESPONSE = {
    "choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}],
    "model": "gpt-4",
    "usage": {"total_tokens": 10},
}


class TestOpenRouterHealthCheck(unittest.TestCase):
    def test_health_check_no_api_key(self):
        """health_check() returns ok=False immediately without any network call."""
        provider = OpenRouterProvider(api_key=None)
        mock_session = MagicMock()
        provider._session = mock_session

        result = provider.health_check()

        self.assertIsInstance(result, ProviderHealth)
        self.assertFalse(result.ok)
        self.assertEqual(result.message, "API key not configured")
        mock_session.get.assert_not_called()


class TestOpenRouterChat(unittest.TestCase):
    def test_chat_200_success(self):
        """chat() returns AIResponse with correct content on a 200 response."""
        provider = OpenRouterProvider(api_key="sk-test-key")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _OPENROUTER_CHAT_RESPONSE
        mock_session = MagicMock()
        mock_session.post.return_value = mock_response
        provider._session = mock_session

        result = provider.chat([{"role": "user", "content": "hi"}], model="gpt-4")

        self.assertEqual(result.content, "hello")
        self.assertEqual(result.model, "gpt-4")
        self.assertEqual(result.finish_reason, "stop")
        self.assertEqual(result.usage, {"total_tokens": 10})


class TestOpenRouterApiKeyLogging(unittest.TestCase):
    def test_api_key_not_logged_in_full(self):
        """No log message should contain the full API key."""
        full_key = "sk-test-12345678abcdef"
        provider = OpenRouterProvider(api_key=full_key)

        # Mock the session so health_check doesn't make a real network call
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        provider._session = mock_session

        # Capture all log output via a custom handler
        captured = []

        class CapturingHandler(logging.Handler):
            def emit(self, record):
                captured.append(self.format(record))

        capturing_handler = CapturingHandler()
        root_logger = logging.getLogger()
        root_logger.addHandler(capturing_handler)
        try:
            provider.health_check()
        finally:
            root_logger.removeHandler(capturing_handler)

        for message in captured:
            self.assertNotIn(full_key, message, f"Full API key found in log: {message!r}")


class TestOpenRouterCancel(unittest.TestCase):
    def test_cancel_closes_session(self):
        """cancel_current_request() closes the session and sets _session to None."""
        provider = OpenRouterProvider(api_key="sk-test-key")
        # Trigger session creation
        provider._get_session()
        self.assertIsNotNone(provider._session)

        provider.cancel_current_request()

        self.assertIsNone(provider._session)


if __name__ == "__main__":
    unittest.main()
