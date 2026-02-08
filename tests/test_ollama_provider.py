"""Tests for Ollama provider — all HTTP calls mocked via httpx."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider(**env_overrides):
    """Create an OllamaProvider with optional env var overrides."""
    import os

    old_vals = {}
    for k, v in env_overrides.items():
        old_vals[k] = os.environ.get(k)
        os.environ[k] = v
    try:
        # Reset config service to pick up new env vars
        from sift.core.config_service import reset_config_service

        reset_config_service()
        from sift.providers.ollama_provider import OllamaProvider

        return OllamaProvider()
    finally:
        for k, v in old_vals.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        from sift.core.config_service import reset_config_service

        reset_config_service()


def _mock_response(status_code=200, json_data=None, text=""):
    """Build a mock httpx.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    if status_code >= 400:
        import httpx

        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=resp,
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# Init / config
# ---------------------------------------------------------------------------


class TestInit:
    def test_default_model_and_endpoint(self):
        provider = _make_provider()
        assert provider.model == "llama3.2"
        assert provider.endpoint == "http://localhost:11434"

    def test_env_override_model(self):
        provider = _make_provider(OLLAMA_MODEL="mistral")
        assert provider.model == "mistral"

    def test_env_override_endpoint(self):
        provider = _make_provider(OLLAMA_ENDPOINT="http://myhost:9999")
        assert provider.endpoint == "http://myhost:9999"

    def test_name_attribute(self):
        provider = _make_provider()
        assert provider.name == "ollama"


# ---------------------------------------------------------------------------
# is_available
# ---------------------------------------------------------------------------


class TestIsAvailable:
    @patch("sift.providers.ollama_provider._import_httpx")
    def test_server_responds_200(self, mock_httpx_fn):
        mock_httpx = MagicMock()
        mock_httpx.get.return_value = _mock_response(200, {"models": []})
        mock_httpx_fn.return_value = mock_httpx

        provider = _make_provider()
        assert provider.is_available() is True
        mock_httpx.get.assert_called_once()

    @patch("sift.providers.ollama_provider._import_httpx")
    def test_connect_error(self, mock_httpx_fn):
        import httpx

        mock_httpx = MagicMock()
        mock_httpx.get.side_effect = httpx.ConnectError("Connection refused")
        mock_httpx_fn.return_value = mock_httpx

        provider = _make_provider()
        assert provider.is_available() is False

    @patch("sift.providers.ollama_provider._import_httpx")
    def test_non_200_status(self, mock_httpx_fn):
        mock_httpx = MagicMock()
        mock_httpx.get.return_value = _mock_response(500)
        mock_httpx_fn.return_value = mock_httpx

        provider = _make_provider()
        assert provider.is_available() is False


# ---------------------------------------------------------------------------
# chat
# ---------------------------------------------------------------------------


class TestChat:
    @patch("sift.providers.ollama_provider._import_httpx")
    def test_successful_chat(self, mock_httpx_fn):
        import httpx

        mock_httpx = MagicMock()
        mock_httpx.ConnectError = httpx.ConnectError
        mock_httpx.TimeoutException = httpx.TimeoutException
        mock_httpx.HTTPStatusError = httpx.HTTPStatusError
        mock_httpx.post.return_value = _mock_response(
            200, {"message": {"content": "Hello from llama!"}}
        )
        mock_httpx_fn.return_value = mock_httpx

        provider = _make_provider()
        result = provider.chat("You are helpful.", "Say hello", max_tokens=100)
        assert result == "Hello from llama!"

        # Verify the payload
        call_kwargs = mock_httpx.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["model"] == "llama3.2"
        assert payload["stream"] is False
        assert len(payload["messages"]) == 2
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][1]["role"] == "user"

    @patch("sift.providers.ollama_provider._import_httpx")
    def test_empty_system_prompt(self, mock_httpx_fn):
        import httpx

        mock_httpx = MagicMock()
        mock_httpx.ConnectError = httpx.ConnectError
        mock_httpx.TimeoutException = httpx.TimeoutException
        mock_httpx.HTTPStatusError = httpx.HTTPStatusError
        mock_httpx.post.return_value = _mock_response(200, {"message": {"content": "response"}})
        mock_httpx_fn.return_value = mock_httpx

        provider = _make_provider()
        provider.chat("", "Just a user message")

        call_kwargs = mock_httpx.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        # No system message when system prompt is empty
        assert len(payload["messages"]) == 1
        assert payload["messages"][0]["role"] == "user"

    @patch("sift.providers.ollama_provider._import_httpx")
    def test_connect_error_raises_unavailable(self, mock_httpx_fn):
        import httpx

        mock_httpx = MagicMock()
        mock_httpx.ConnectError = httpx.ConnectError
        mock_httpx.TimeoutException = httpx.TimeoutException
        mock_httpx.HTTPStatusError = httpx.HTTPStatusError
        mock_httpx.post.side_effect = httpx.ConnectError("Connection refused")
        mock_httpx_fn.return_value = mock_httpx

        from sift.errors import ProviderUnavailableError

        provider = _make_provider()
        with pytest.raises(ProviderUnavailableError, match="Cannot connect"):
            provider.chat("sys", "user")

    @patch("sift.providers.ollama_provider._import_httpx")
    def test_timeout_raises_unavailable(self, mock_httpx_fn):
        import httpx

        mock_httpx = MagicMock()
        mock_httpx.ConnectError = httpx.ConnectError
        mock_httpx.TimeoutException = httpx.TimeoutException
        mock_httpx.HTTPStatusError = httpx.HTTPStatusError
        mock_httpx.post.side_effect = httpx.ReadTimeout("timed out")
        mock_httpx_fn.return_value = mock_httpx

        from sift.errors import ProviderUnavailableError

        provider = _make_provider()
        with pytest.raises(ProviderUnavailableError, match="timed out"):
            provider.chat("sys", "user")

    @patch("sift.providers.ollama_provider._import_httpx")
    def test_404_raises_model_error(self, mock_httpx_fn):
        import httpx

        mock_httpx = MagicMock()
        mock_httpx.ConnectError = httpx.ConnectError
        mock_httpx.TimeoutException = httpx.TimeoutException
        mock_httpx.HTTPStatusError = httpx.HTTPStatusError

        resp_404 = _mock_response(404, text="model not found")
        mock_httpx.post.return_value = resp_404
        mock_httpx_fn.return_value = mock_httpx

        from sift.errors import ProviderModelError

        provider = _make_provider()
        with pytest.raises(ProviderModelError, match="not found"):
            provider.chat("sys", "user")

    @patch("sift.providers.ollama_provider._import_httpx")
    def test_500_raises_provider_error(self, mock_httpx_fn):
        import httpx

        mock_httpx = MagicMock()
        mock_httpx.ConnectError = httpx.ConnectError
        mock_httpx.TimeoutException = httpx.TimeoutException
        mock_httpx.HTTPStatusError = httpx.HTTPStatusError

        resp_500 = _mock_response(500, text="internal error")
        mock_httpx.post.return_value = resp_500
        mock_httpx_fn.return_value = mock_httpx

        from sift.errors import ProviderError

        provider = _make_provider()
        with pytest.raises(ProviderError, match="HTTP 500"):
            provider.chat("sys", "user")


# ---------------------------------------------------------------------------
# transcribe
# ---------------------------------------------------------------------------


class TestTranscribe:
    def test_returns_none(self):
        provider = _make_provider()
        result = provider.transcribe(Path("/some/audio.wav"))
        assert result is None


# ---------------------------------------------------------------------------
# list_models
# ---------------------------------------------------------------------------


class TestListModels:
    @patch("sift.providers.ollama_provider._import_httpx")
    def test_success(self, mock_httpx_fn):
        models_data = [
            {"name": "llama3.2:latest", "size": 2000000000},
            {"name": "mistral:latest", "size": 4000000000},
        ]
        mock_httpx = MagicMock()
        mock_httpx.get.return_value = _mock_response(200, {"models": models_data})
        mock_httpx_fn.return_value = mock_httpx

        provider = _make_provider()
        result = provider.list_models()
        assert len(result) == 2
        assert result[0]["name"] == "llama3.2:latest"

    @patch("sift.providers.ollama_provider._import_httpx")
    def test_server_down_returns_empty(self, mock_httpx_fn):
        import httpx

        mock_httpx = MagicMock()
        mock_httpx.get.side_effect = httpx.ConnectError("refused")
        mock_httpx_fn.return_value = mock_httpx

        provider = _make_provider()
        result = provider.list_models()
        assert result == []


# ---------------------------------------------------------------------------
# Provider registration & protocol
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_in_providers_registry(self):
        from sift.providers import PROVIDERS, _register_defaults

        _register_defaults()
        assert "ollama" in PROVIDERS

    def test_get_provider_ollama(self):
        from sift.providers import get_provider, reset_provider

        reset_provider()
        provider = get_provider("ollama")
        assert provider.name == "ollama"


class TestProtocol:
    def test_satisfies_ai_provider(self):
        from sift.providers.base import AIProvider

        provider = _make_provider()
        assert isinstance(provider, AIProvider)
