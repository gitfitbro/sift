"""Ollama local AI provider — uses httpx to call the Ollama REST API."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("sift.providers.ollama")

# Well-known Ollama models shown by `sift models` when server is offline
OLLAMA_MODELS = {
    "llama3.2": "Meta Llama 3.2 (3B, default)",
    "llama3.2:1b": "Meta Llama 3.2 (1B, fastest)",
    "llama3.1": "Meta Llama 3.1 (8B)",
    "mistral": "Mistral 7B",
    "mixtral": "Mixtral 8x7B MoE",
    "codellama": "Code Llama",
    "phi3": "Microsoft Phi-3",
    "gemma2": "Google Gemma 2",
    "qwen2.5": "Alibaba Qwen 2.5",
    "deepseek-coder-v2": "DeepSeek Coder V2",
}


def _import_httpx():
    """Import httpx, raising a helpful error if missing."""
    try:
        import httpx
        return httpx
    except ImportError:
        raise ImportError(
            "httpx is required for Ollama support. Install with:\n"
            "  pip install httpx\n\n"
            "Or install sift with Ollama support:\n"
            "  pip install sift-cli[ollama]"
        )


class OllamaProvider:
    """Local AI provider using Ollama (llama3.2, mistral, etc.)."""

    name = "ollama"

    def __init__(self):
        from sift.core.config_service import get_config_service

        config = get_config_service()
        self.model = config.get_provider_model("ollama")
        self.endpoint = config.get(
            "providers.ollama.endpoint", "http://localhost:11434"
        )

    def is_available(self) -> bool:
        """Check if the Ollama server is reachable."""
        try:
            httpx = _import_httpx()
            response = httpx.get(f"{self.endpoint}/api/tags", timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False

    def chat(self, system: str, user: str, max_tokens: int = 4000) -> str:
        """Send a chat request to the Ollama server."""
        httpx = _import_httpx()
        from sift.errors import (
            ProviderError,
            ProviderModelError,
            ProviderUnavailableError,
        )

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"num_predict": max_tokens},
        }

        try:
            response = httpx.post(
                f"{self.endpoint}/api/chat",
                json=payload,
                timeout=300.0,  # Local models on CPU can be slow
            )
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"]
        except httpx.ConnectError as e:
            raise ProviderUnavailableError(
                f"Cannot connect to Ollama at {self.endpoint}. "
                "Make sure Ollama is running: ollama serve",
                provider=self.name,
                model=self.model,
            ) from e
        except httpx.TimeoutException as e:
            raise ProviderUnavailableError(
                f"Ollama request timed out. The model '{self.model}' may be "
                "too large for your hardware, or the server is overloaded.",
                provider=self.name,
                model=self.model,
            ) from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ProviderModelError(
                    f"Model '{self.model}' not found on Ollama. "
                    f"Pull it first: ollama pull {self.model}",
                    provider=self.name,
                    model=self.model,
                ) from e
            raise ProviderError(
                f"Ollama API error (HTTP {e.response.status_code}): "
                f"{e.response.text}",
                provider=self.name,
                model=self.model,
            ) from e
        except Exception as e:
            if isinstance(e, (ProviderError, ProviderUnavailableError, ProviderModelError)):
                raise
            raise ProviderError(
                f"Ollama error: {e}",
                provider=self.name,
                model=self.model,
            ) from e

    def transcribe(self, audio_path: Path) -> Optional[str]:
        """Ollama does not support audio transcription."""
        logger.info("Ollama does not support audio transcription, falling back.")
        return None

    def list_models(self) -> list[dict]:
        """List models available on the local Ollama server."""
        try:
            httpx = _import_httpx()
            response = httpx.get(f"{self.endpoint}/api/tags", timeout=10.0)
            response.raise_for_status()
            data = response.json()
            return data.get("models", [])
        except Exception as e:
            logger.warning("Could not list Ollama models: %s", e)
            return []
