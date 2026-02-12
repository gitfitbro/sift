"""AI Provider Protocol and Base Class."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class AIProvider(Protocol):
    """Protocol that all AI providers must satisfy."""

    name: str
    model: str
    max_context_window: int

    def is_available(self) -> bool: ...
    def chat(self, system: str, user: str, max_tokens: int = 4000) -> str: ...
    def transcribe(self, audio_path: Path) -> str | None: ...


class BaseProvider:
    """Common base for AI providers to reduce initialization boilerplate."""

    name: str = ""
    max_context_window: int = 128000  # Default conservative limit

    def __init__(self):
        from sift.core.config_service import get_config_service
        from sift.core.secrets import get_key

        config_svc = get_config_service()
        self.api_key = get_key(self.name) if self.name else None
        self.model = config_svc.get_provider_model(self.name) if self.name else ""

    def is_available(self) -> bool:
        return self.api_key is not None
