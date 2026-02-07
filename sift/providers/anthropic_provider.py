"""Anthropic (Claude) AI provider."""
from __future__ import annotations
import os
import base64
from pathlib import Path
from typing import Optional
from sift.ui import console


class AnthropicProvider:
    name = "anthropic"

    def __init__(self):
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250514")

    def is_available(self) -> bool:
        return self.api_key is not None

    def chat(self, system: str, user: str, max_tokens: int = 4000) -> str:
        """Send a chat message and return the response text."""
        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key)

        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": user}],
        }
        if system:
            kwargs["system"] = system

        message = client.messages.create(**kwargs)
        return message.content[0].text

    def transcribe(self, audio_path: Path) -> Optional[str]:
        """Transcribe audio using Claude's audio document input."""
        import anthropic

        console.print(f"[dim]Transcribing with Claude ({self.model})...[/dim]")

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
