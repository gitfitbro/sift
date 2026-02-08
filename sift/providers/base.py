"""AI Provider Protocol - formalizes the interface all providers must satisfy."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class AIProvider(Protocol):
    """Protocol that all AI providers must satisfy.

    Existing providers (AnthropicProvider, GeminiProvider) already implement
    this interface via duck typing. This formalizes it for type checking and
    future plugin discovery.
    """

    name: str
    model: str

    def is_available(self) -> bool: ...
    def chat(self, system: str, user: str, max_tokens: int = 4000) -> str: ...
    def transcribe(self, audio_path: Path) -> str | None: ...
