"""Unit tests for OllamaProvider.

Validates: Requirements 3.1, 3.4, 3.5, 3.6
"""

import unittest
from unittest.mock import MagicMock

import requests

from app.core.ai.providers.ollama_provider import OllamaProvider


class TestOllamaProviderChat(unittest.TestCase):
    def test_chat_200_success(self):
        provider = OllamaProvider()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"content": "hello"},
            "model": "llama3",
            "done_reason": "stop",
        }
        mock_session = MagicMock()
        mock_session.post.return_value = mock_response
        provider._session = mock_session

        result = provider.chat([{"role": "user", "content": "hi"}], model="llama3")

        self.assertEqual(result.content, "hello")
        self.assertEqual(result.model, "llama3")
        self.assertEqual(result.finish_reason, "stop")

    def test_chat_non_200_raises_value_error(self):
        provider = OllamaProvider()
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_session = MagicMock()
        mock_session.post.return_value = mock_response
        provider._session = mock_session

        with self.assertRaises(ValueError):
            provider.chat([{"role": "user", "content": "hi"}], model="llama3")


class TestOllamaProviderHealthCheck(unittest.TestCase):
    def test_health_check_success(self):
        provider = OllamaProvider()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": [{"name": "llama3"}]}
        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        provider._session = mock_session

        health = provider.health_check()

        self.assertTrue(health.ok)
        self.assertIsNotNone(health.latency_ms)

    def test_health_check_connection_error(self):
        provider = OllamaProvider()
        mock_session = MagicMock()
        mock_session.get.side_effect = requests.exceptions.ConnectionError("refused")
        provider._session = mock_session

        health = provider.health_check()

        self.assertFalse(health.ok)

    def test_health_check_timeout(self):
        provider = OllamaProvider()
        mock_session = MagicMock()
        mock_session.get.side_effect = requests.exceptions.Timeout("timed out")
        provider._session = mock_session

        health = provider.health_check()

        self.assertFalse(health.ok)


class TestOllamaProviderCancel(unittest.TestCase):
    def test_cancel_closes_session(self):
        provider = OllamaProvider()
        # Trigger session creation
        provider._get_session()
        self.assertIsNotNone(provider._session)

        provider.cancel_current_request()

        self.assertIsNone(provider._session)


if __name__ == "__main__":
    unittest.main()
