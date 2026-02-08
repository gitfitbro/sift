"""AI provider registry and dispatch.

Providers are discovered via setuptools entry points (group ``sift.providers``).
Built-in providers (anthropic, gemini, ollama) are registered in pyproject.toml.
Third-party packages can add providers by declaring their own entry points.
"""
from __future__ import annotations

import logging
from typing import Optional

# Ensure .env is loaded before reading any env vars
import sift.config  # noqa: F401 — triggers dotenv loading

logger = logging.getLogger("sift.providers")

# Registry of available providers (lazy-loaded via entry points)
PROVIDERS: dict[str, type] = {}

_active_provider = None


def _register_defaults():
    """Discover and register providers via entry points.

    Falls back to direct imports if entry points are not available
    (e.g. running from source without pip install -e).
    """
    if PROVIDERS:
        return

    from sift.plugins import discover_providers
    discovered = discover_providers()

    if discovered:
        PROVIDERS.update(discovered)
        logger.debug("Discovered %d providers via entry points: %s",
                      len(discovered), list(discovered.keys()))
    else:
        # Fallback: direct imports for running from source without install
        logger.debug("No entry points found, falling back to direct imports")
        try:
            from .anthropic_provider import AnthropicProvider
            PROVIDERS["anthropic"] = AnthropicProvider
        except ImportError:
            pass
        try:
            from .gemini_provider import GeminiProvider
            PROVIDERS["gemini"] = GeminiProvider
        except ImportError:
            pass
        try:
            from .ollama_provider import OllamaProvider
            PROVIDERS["ollama"] = OllamaProvider
        except ImportError:
            pass


def get_provider(name: Optional[str] = None):
    """Get the active AI provider instance.

    Args:
        name: Provider name to use. If None, reads from config.

    Returns:
        An AI provider instance with chat() and transcribe() methods.

    Raises:
        ProviderUnavailableError: If provider name is unknown.
    """
    global _active_provider
    _register_defaults()

    if name:
        if name not in PROVIDERS:
            from sift.errors import ProviderUnavailableError
            available = ", ".join(sorted(PROVIDERS.keys()))
            raise ProviderUnavailableError(
                f"Unknown provider '{name}'. Available: {available}",
                provider=name,
            )
        _active_provider = PROVIDERS[name]()
        return _active_provider

    if _active_provider:
        return _active_provider

    # Auto-detect from config service
    from sift.core.config_service import get_config_service
    provider_name = get_config_service().get_provider_name()
    return get_provider(provider_name)


def get_provider_names() -> list[str]:
    """Get sorted list of all registered provider names."""
    _register_defaults()
    return sorted(PROVIDERS.keys())


def reset_provider():
    """Reset the cached provider (useful when env vars change)."""
    global _active_provider
    _active_provider = None
