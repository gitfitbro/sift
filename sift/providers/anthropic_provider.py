"""Anthropic (Claude) AI provider."""

from __future__ import annotations

import base64
import logging
from pathlib import Path

logger = logging.getLogger("sift.providers.anthropic")


class AnthropicProvider:
    name = "anthropic"

    def __init__(self):
        from sift.core.config_service import get_config_service
        from sift.core.secrets import get_key

        self.api_key = get_key("anthropic")
        self.model = get_config_service().get_provider_model("anthropic")

    def is_available(self) -> bool:
        return self.api_key is not None

    def chat(self, system: str, user: str, max_tokens: int = 4000) -> str:
        """Send a chat message and return the response text."""
        import anthropic

        from sift.errors import (
            ProviderAuthError,
            ProviderError,
            ProviderModelError,
            ProviderQuotaError,
        )

        client = anthropic.Anthropic(api_key=self.api_key)

        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": user}],
        }
        if system:
            kwargs["system"] = system

        try:
            message = client.messages.create(**kwargs)
            return message.content[0].text
        except anthropic.AuthenticationError as e:
            raise ProviderAuthError(
                "Anthropic API key is invalid or expired.\n"
                "Check ANTHROPIC_API_KEY or run: sift config set-key anthropic",
                provider=self.name,
                model=self.model,
            ) from e
        except anthropic.RateLimitError as e:
            raise ProviderQuotaError(
                "Anthropic rate limit exceeded. Wait and retry.",
                provider=self.name,
                model=self.model,
            ) from e
        except anthropic.NotFoundError as e:
            raise ProviderModelError(
                f"Model '{self.model}' not found on Anthropic.",
                provider=self.name,
                model=self.model,
            ) from e
        except anthropic.APIError as e:
            raise ProviderError(
                f"Anthropic API error: {e}",
                provider=self.name,
                model=self.model,
            ) from e

    def transcribe(self, audio_path: Path) -> str | None:
        """Transcribe audio using Claude's audio document input."""
        import anthropic

        from sift.errors import ProviderAuthError, ProviderError

        logger.info("Transcribing with Claude (%s)...", self.model)

        audio_data = base64.standard_b64encode(audio_path.read_bytes()).decode("utf-8")

        suffix = audio_path.suffix.lower()
        media_types = {
            ".mp3": "audio/mp3",
            ".wav": "audio/wav",
            ".webm": "audio/webm",
            ".m4a": "audio/mp4",
            ".ogg": "audio/ogg",
            ".flac": "audio/flac",
        }
        media_type = media_types.get(suffix, "audio/mp3")

        client = anthropic.Anthropic(api_key=self.api_key)

        try:
            message = client.messages.create(
                model=self.model,
                max_tokens=16000,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "document",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": audio_data,
                                },
                            },
                            {
                                "type": "text",
                                "text": (
                                    "Please transcribe this audio recording verbatim. "
                                    "Include all speakers, filler words, and natural speech patterns. "
                                    "If there are multiple speakers, label them (Speaker 1, Speaker 2, etc). "
                                    "Output ONLY the transcript text, nothing else."
                                ),
                            },
                        ],
                    }
                ],
            )
            return message.content[0].text
        except anthropic.AuthenticationError as e:
            raise ProviderAuthError(
                "Anthropic API key is invalid or expired.",
                provider=self.name,
                model=self.model,
            ) from e
        except anthropic.APIError as e:
            raise ProviderError(
                f"Anthropic transcription error: {e}",
                provider=self.name,
                model=self.model,
            ) from e
