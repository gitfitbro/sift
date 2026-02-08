"""AI provider registry and dispatch."""
from __future__ import annotations
from typing import Optional

# Ensure .env is loaded before reading any env vars
import sift.config  # noqa: F401 — triggers dotenv loading


# Registry of available providers (lazy-loaded)
PROVIDERS = {}

_active_provider = None


def _register_defaults():
    """Register built-in providers."""
    if PROVIDERS:
        return
    from .anthropic_provider import AnthropicProvider
    from .gemini_provider import GeminiProvider
    PROVIDERS["anthropic"] = AnthropicProvider
    PROVIDERS["gemini"] = GeminiProvider


def get_provider(name: Optional[str] = None):
    """Get the active AI provider instance.

    Args:
        name: Provider name to use. If None, reads AI_PROVIDER env var (default: "anthropic").

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
            available = ", ".join(PROVIDERS.keys())
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


def reset_provider():
    """Reset the cached provider (useful when env vars change)."""
    global _active_provider
    _active_provider = None
